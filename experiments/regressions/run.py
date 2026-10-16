"""Run the 6 + 6 + 5 candidate-fix regression cases without model calls."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    targets = Path(os.environ.get("REGRESSION_TARGET_ROOT", str(HERE / "vendor")))
    tsx = Path(os.environ.get("REGRESSION_TSX", str(HERE / "vendor/runtime/node_modules/.bin/tsx")))
    if not tsx.exists():
        raise SystemExit("Run scripts/setup_regressions.py first")
    env = {**os.environ, "REGRESSION_TARGET_ROOT": str(targets),
           "REVIEW_FIXTURE": str(ROOT / "samples/review-chain.json")}
    results = []
    for name, count in (("jev_review.mjs", 6), ("jev_router.mjs", 6), ("fast_jev_compaction.mjs", 5)):
        output = subprocess.check_output([str(tsx), str(HERE / name)], env=env, text=True)
        result = json.loads(output)
        if len(result["results"]) != count:
            raise ValueError(f"Unexpected case count in {name}")
        results.append(result)
        print(f"{result['target']}: {count} cases")
    out = ROOT / "output/regressions"
    review, router, compaction = [[case["facts"] for case in suite["results"]] for suite in results]
    checks = [
        review[0]["heading_lines_neutralized"] == 2 and review[0]["payload_body_survives_verbatim"],
        review[1]["unchanged"], review[2]["neutralized"] and review[2]["body_survives"],
        review[3]["unchanged"], review[4]["unchanged"], review[5]["ok"],
        router[0]["old_regex_matches"] and router[0]["new_detectOverride"] is None and not router[0]["decide_with_allowOverride"]["changed"],
        not router[1]["decision"]["changed"], router[2]["decision"]["tier"] == "fable" and router[2]["decision"]["changed"],
        router[3]["decision"]["tier"] == "sonnet" and router[3]["decision"]["changed"],
        not router[4]["decision"]["changed"], router[5]["detectOverride"] is None and not router[5]["changed"],
        not compaction[0]["marked"] and compaction[0]["intact"],
        all(compaction[1][key] for key in ["marked", "head_survives", "body_beyond_head_removed", "truncated_note"]),
        not compaction[2]["marked"] and compaction[2]["intact"],
        compaction[3]["keep_unchanged"] and compaction[3]["long_marked"],
        compaction[4]["policyTextHits"] == {"input": 4, "output": 4} and compaction[4]["decisions"] == ["keep"],
    ]
    if not all(checks):
        raise AssertionError(f"Regression observation changed in cases {[i + 1 for i, ok in enumerate(checks) if not ok]}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(f"17 regression observations: {out / 'results.json'}")


if __name__ == "__main__":
    main()
