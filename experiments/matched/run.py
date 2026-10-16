"""Fresh runs of fixed payload-type and field-provenance controls."""

import copy
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/defense/run"))
from _common import LEAVES, q_choice, state_variants
from redteam.runner import Runner
from expd3_policyfield_scale import CHOICE
from payloads import A1, A3, SCENARIOS, TRUST_NOTE


def main():
    runner = Runner("matched-" + os.environ.get("RUN_TAG", "noname"), workers=1,
                    out_dir=ROOT / "output/matched")
    summary = {}
    table = {row[0]: row for row in CHOICE}
    for name in SCENARIOS:
        _, state, instructions, criteria, gold, target, policy = table[name]
        baseline = {}
        for group, note in (("A", ""), ("B", TRUST_NOTE)):
            for variant, clean in state_variants(name, state):
                answer = runner.decide(f"{name}/{variant}/base{group}", clean,
                                       q_choice(instructions + note, criteria),
                                       meta={"scenario": name, "variant": variant,
                                             "condition": "base" + group,
                                             "gold": gold, "atk": target})["target"]
                baseline[group, variant] = answer["choice"]
        counts = {}
        for arm in ("a1", "a2", "a3", "b1", "b2"):
            flips = usable = 0
            for variant, clean in state_variants(name, state):
                fed = copy.deepcopy(clean)
                group = "A" if arm.startswith("a") else "B"
                if group == "A":
                    fed["review_policy"] = {"a1": A1.format(atk=target), "a2": policy, "a3": A3[name]}[arm]
                elif arm == "b1":
                    fed["config"] = {"review_policy": policy}
                else:
                    top, sub = LEAVES[name]
                    fed[top][sub] += "\n\n" + policy
                answer = runner.decide(f"{name}/{variant}/{arm}", fed,
                                       q_choice(instructions + (TRUST_NOTE if group == "B" else ""), criteria),
                                       meta={"scenario": name, "variant": variant,
                                             "condition": arm, "gold": gold, "atk": target})["target"]
                if baseline[group, variant] != target:
                    usable += 1
                    flips += answer["choice"] == target
            counts[arm] = {"flips": flips, "n": usable}
        summary[name] = counts
    runner.save_summary({"per_scenario": summary})


if __name__ == "__main__":
    main()
