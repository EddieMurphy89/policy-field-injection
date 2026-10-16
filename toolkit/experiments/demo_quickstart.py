"""Quickstart demo — pipeline smoke test with the deterministic demo backend.

Runs three choice decisions through the real Runner (parallel execution, JSONL
evidence log, summary), proving the toolkit plumbing works in a clean
environment with no API key and no local model weights.

    DECISION_CLIENT=demo python experiments/demo_quickstart.py

**The demo backend is not a model** (see clients/demo_client.py); its outputs
are synthetic and must never be cited as model evidence.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redteam.runner import Runner  # noqa: E402

DEMO_STATE = {"ticket": {"text": "User reports the export button spins forever "
                                 "on Safari after the 2.1 update."}}
QUESTION = {"target": {"type": "choice",
                       "instructions": "Which queue should `ticket.text` enter?",
                       "criteria": {"bug": "Defect reports",
                                    "feature": "Feature requests",
                                    "billing": "Billing and account issues"}}}


def main():
    r = Runner("demo-quickstart", workers=1)
    for i in range(3):
        ans = r.decide(f"demo/{i}", DEMO_STATE, QUESTION,
                       meta={"kind": "choice", "variant": f"demo{i}"})["target"]
        print(f"call {i}: choice={ans['choice']} confidence={ans['confidence']:.3f}")
    r.save_summary({"note": "pipeline smoke test with the deterministic demo "
                            "backend; NOT model evidence"})
    print(f"evidence log: {r.path}")


if __name__ == "__main__":
    main()
