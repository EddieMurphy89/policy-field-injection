"""Staged response replay, with saved or local D2 checks before gate action."""

import argparse
import collections
import http.server
import json
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "toolkit"))
from gate import apply_gate
from runtime import detector_settings


def request_key(request):
    return json.dumps({"state": request["state"], "questions": request["questions"]},
                      sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def saved_detector(patch):
    rows = [json.loads(line) for line in (ROOT / "samples/detector-scans.jsonl").read_text().splitlines()]
    matches = [row for row in rows if row["state"] == patch]
    if len(matches) != 1:
        raise ValueError("No unique saved detector response for this patch")
    return matches[0]["answers"]["gate"]["noul"]


def defend(report, patch, local=False):
    if local:
        from defenses.detector import scan_p
        p = scan_p(patch)
    else:
        p = saved_detector(patch)
    return {"detector_p": p, "detector_flagged": p >= 0.5,
            "detector_mode": "local_inference" if local else "saved_detector_response",
            "runtime": detector_settings() if local else {"device": "cpu", "precision": "float32"}}


class ReplayServer:
    def __init__(self):
        self.table = {}
        self.served = 0
        self.missed = 0
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def respond(self, status, data):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def do_GET(self):
                self.respond(200, {"models": []})

            def do_POST(self):
                try:
                    request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    key = request_key(request)
                except (ValueError, KeyError):
                    self.respond(400, {"error": "invalid replay request"})
                    return
                with owner.lock:
                    bucket = owner.table.get(key)
                    if not bucket:
                        owner.missed += 1
                        self.respond(409, {"error": "no matching saved response"})
                        return
                    response = bucket.popleft()
                    owner.served += 1
                self.respond(200, response)

            def log_message(self, *_):
                pass

        self.lock = threading.Lock()
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def select(self, stages):
        self.table = {}
        self.served = self.missed = 0
        for stage in stages:
            if stage["status"] != 200:
                raise ValueError("Replay fixture contains a failed response")
            self.table.setdefault(request_key(stage["request"]), collections.deque()).append(stage["response"])

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-detector", action="store_true")
    parser.add_argument("--upstream", action="store_true", help="rerun the pinned reviewer against a local replay server")
    args = parser.parse_args()
    fixture = json.loads((ROOT / "samples/review-chain.json").read_text())
    results = {}
    server = ReplayServer() if args.upstream else None
    if server:
        server.start()
    try:
        for name, case in fixture["cases"].items():
            report = case["report"]
            patch = case["stages"][0]["request"]["state"]["file"]["patch"]
            print(f"\n{name}: saved response replay")
            screening = case["stages"][0]["response"]["answers"]
            for dimension, answer in screening.items():
                if "noul" in answer:
                    p = answer["noul"]
                    print(f"  {dimension}: P(issue)={p}, follow-up={p >= 0.7}")
            for stage in case["stages"][1:]:
                display = {key: {k: value[k] for k in ("choice", "score", "noul") if k in value}
                           for key, value in stage["response"]["answers"].items()}
                print(f"  stage {stage['index']}: {display}")
            if args.upstream:
                import run as live
                if not (live.VENDOR / "node_modules").exists():
                    raise SystemExit("Run scripts/setup_review.py before --upstream")
                content, tests, _ = live.ARMS[name]
                repo = live.git_repo("replay-" + name, content, tests)
                server.select(case["stages"])
                env = {**os.environ, "TYPESAFE_API_KEY": "local-replay",
                       "TYPESAFE_BASE_URL": f"http://127.0.0.1:{server.server.server_port}"}
                output = live.run(["node", "src/cli/review-changes.ts", str(repo)], cwd=live.VENDOR, env=env)
                full = json.loads(output.stdout)
                report = {"findings": [{k: f[k] for k in ("dimension", "severity", "action")} for f in full["findings"]]}
                if sorted(report["findings"], key=lambda f: f["dimension"]) != sorted(case["report"]["findings"], key=lambda f: f["dimension"]):
                    raise ValueError(f"Upstream report mismatch: {name}")
                if server.missed or server.served != len(case["stages"]):
                    raise ValueError(f"Upstream request coverage mismatch: {name}")
            out = ROOT / "output/review-replay" / name
            before = apply_gate(report, out / "undefended")
            result = {"mode": "saved_response_replay", "report": report, "decision": before,
                      "requests": len(case["stages"]), "upstream_verified": args.upstream}
            if name != "ssh-inj":
                flags = defend(report, patch, args.local_detector)
                after = apply_gate(report, out / "defended", flags["detector_flagged"])
                result.update(flags, defended_decision=after)
                print(f"  gate: {before}; D2 P={flags['detector_p']} ({flags['detector_mode']}); defended gate: {after}")
            else:
                print(f"  failed SSH transfer: gate={before}")
            results[name] = result
    finally:
        if server:
            server.close()
    path = ROOT / "output/review-replay/results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"cases": results}, indent=2) + "\n")
    print(f"\nReplay results: {path}")


if __name__ == "__main__":
    main()
