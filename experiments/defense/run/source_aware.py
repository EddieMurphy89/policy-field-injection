"""Evaluate the source-aware detector on 24 fixed attacks and 24 benign texts."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "toolkit"))

from defenses import detector_v2
from runtime import detector_settings


def request_for(case, trusted):
    state = detector_v2.STATE_TEMPLATE.format(trusted=trusted, source=case["source"], text=case["text"])
    return state, {"gate": {"type": "noul", "instructions": detector_v2.QUESTION}}


def evaluate(config, saved=None, predict=None):
    cases = config["cases"]
    ids = [case["id"] for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate case ID")
    replay = None
    if saved is not None:
        replay = {row["id"]: row for row in saved}
        if len(replay) != len(saved) or set(replay) != set(ids):
            raise ValueError("Saved responses must cover each configured case exactly once")
    elif predict is None:
        from defenses.detector_backend import predict
    records = []
    summary = {"threshold": config["threshold"], "attack": {"flagged": 0, "total": 0},
               "benign": {"flagged": 0, "total": 0}, "attack_by_scenario": {}}
    for case in cases:
        state, questions = request_for(case, config["trusted"])
        if replay is not None:
            row = replay[case["id"]]
            if row["state"] != state or row["questions"] != questions:
                raise ValueError(f"Saved request differs from configured input: {case['id']}")
            probability = float(row["answers"]["gate"]["noul"])
            runtime = row.get("runtime", {"backend": "intern", "checkpoint": "Intern-Decision-2B"})
        else:
            probability = float(predict(state, questions)["answers"]["gate"]["noul"])
            runtime = detector_settings()
        if not 0 <= probability <= 1:
            raise ValueError(f"Invalid probability for {case['id']}")
        flagged = probability >= config["threshold"]
        group = summary[case["group"]]
        group["total"] += 1
        group["flagged"] += flagged
        if case["group"] == "attack":
            cell = summary["attack_by_scenario"].setdefault(case["scenario"], {"flagged": 0, "total": 0})
            cell["total"] += 1
            cell["flagged"] += flagged
        records.append({"id": case["id"], "state": state, "questions": questions,
                        "model": "intern-2B(detector-v2)", "answers": {"gate": {"noul": probability}},
                        "mode": "saved_response_replay" if replay is not None else "inference",
                        "runtime": runtime,
                        "meta": {key: case[key] for key in ("group", "scenario", "variant", "payload_tone") if key in case}})
    return summary, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", action="store_true", help="use the recorded local detector responses")
    args = parser.parse_args()
    config = json.loads((ROOT / "configs/source_aware.json").read_text())
    saved = None
    if args.replay:
        saved = [json.loads(line) for line in (ROOT / "samples/source-aware.jsonl").read_text().splitlines() if line.strip()]
    summary, rows = evaluate(config, saved=saved)
    directory = ROOT / "output/source-aware"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"source-aware-{datetime.now():%Y%m%d-%H%M%S-%f}.jsonl"
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    path.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print(f"Records: {path}")


if __name__ == "__main__":
    main()
