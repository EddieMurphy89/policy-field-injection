"""Replay the saved documentation-example bypass of the policy detector."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    rows = [json.loads(line) for line in (ROOT / "samples/bypass.jsonl").read_text().splitlines()]
    baseline = next(row for row in rows if row["meta"].get("condition") == "baseline")
    scan = next(row for row in rows if row["meta"].get("record_type") == "detector_scan")
    attacked = next(row for row in rows if row["meta"].get("condition") == "f4_d2_formA")
    p = scan["answers"]["gate"]["noul"]
    print("Mode: saved response replay")
    print(f"Policy detector: P(yes)={p}, flagged={p >= 0.5}")
    print(f"Clef-Flash secret gate: clean P(secret)={baseline['answers']['target']['noul']}; "
          f"attacked P(secret)={attacked['answers']['target']['noul']}")
    print("Three saved responses replayed; no inference or API calls.")


if __name__ == "__main__":
    main()
