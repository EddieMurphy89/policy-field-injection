"""Replay two saved Choice responses and review-report gate excerpts."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolkit"))
from clients import replay_client
from gate import apply_gate


def main():
    for line in (ROOT / "samples" / "choice.jsonl").read_text().splitlines():
        row = json.loads(line)
        result = replay_client.ask(row["state"], row["questions"])
        answer = result["answers"]["target"]
        print(f"Saved response / {row['meta']['condition']}: {answer['choice']} "
              f"({result['recorded_model']})")
    for name in ("baseline", "attack"):
        report = json.loads((ROOT / "samples" / f"review-{name}.json").read_text())
        outcome = apply_gate(report, ROOT / "output" / "gate-replay" / name)
        print(f"Saved report excerpt / {name}: {outcome}")
    print("Replay complete. The review model was not called; the gate only writes a local marker.")


if __name__ == "__main__":
    main()
