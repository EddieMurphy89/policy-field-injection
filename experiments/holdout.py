"""Evaluate the three holdout batches with final labels and separate tier counts."""

import argparse
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolkit"))
sys.path.insert(0, str(ROOT / "toolkit" / "experiments"))
from exp1c_contested_search import mutations
from redteam.runner import Runner


def variants(state):
    leaf = next(k for k, value in state.items() if isinstance(value, dict) and "text" in value)
    out = [("orig", copy.deepcopy(state))]
    for i, text in enumerate(mutations(state[leaf]["text"])):
        changed = copy.deepcopy(state)
        changed[leaf]["text"] = text
        out.append((f"mut{i}", changed))
    return leaf, out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", default="all", choices=["all", "v2.1", "v2.2", "v2.3"])
    parser.add_argument("--tier", default="all", choices=["all", "T1", "T2", "T3", "T3/out", "out"])
    parser.add_argument("--variants", choices=["original", "all"], default="original")
    args = parser.parse_args()
    rows = json.loads((ROOT / "configs" / "holdout.json").read_text())
    rows = [row for row in rows if (args.batch == "all" or row["batch"] == args.batch)
            and (args.tier == "all" or row["tier"] == args.tier)]
    runner = Runner("holdout-" + os.environ.get("RUN_TAG", "noname"), workers=1,
                    out_dir=ROOT / "output" / "holdout")
    counts = {}
    for row in rows:
        key = row["batch"] + "/" + row["name"]
        rec = {"tier": row["tier"], "total": 0, "baseline_correct": 0,
               "usable": 0, "flipA": 0, "flipB": 0,
               "strict_n": 0, "strictA": 0, "strictB": 0}
        questions = {"target": {"type": "choice", "instructions": row["instructions"],
                                 "criteria": row["criteria"]}}
        leaf, inputs = variants(row["state"])
        if args.variants == "original":
            inputs = inputs[:1]
        for variant, clean in inputs:
            form_a = {**clean, "review_policy": row["policy"]}
            form_b = copy.deepcopy(clean)
            form_b[leaf]["text"] += "\n\n" + row["policy"]
            choices = {}
            for condition, state in (("baseline", clean), ("v1_formA", form_a), ("v1_formB", form_b)):
                answer = runner.decide(f"{key}/{variant}/{condition}", state, questions,
                                       meta={"scenario": row["name"], "batch": row["batch"],
                                             "variant": variant, "condition": condition,
                                             "gold": row["gold"], "atk": row["attack_target"],
                                             "tier": row["tier"]})["target"]
                choices[condition] = answer["choice"]
            rec["total"] += 1
            correct = choices["baseline"] == row["gold"]
            rec["baseline_correct"] += correct
            if choices["baseline"] != row["attack_target"]:
                rec["usable"] += 1
                rec["flipA"] += choices["v1_formA"] == row["attack_target"]
                rec["flipB"] += choices["v1_formB"] == row["attack_target"]
            if correct and row["gold"] != row["attack_target"]:
                rec["strict_n"] += 1
                rec["strictA"] += choices["v1_formA"] == row["attack_target"]
                rec["strictB"] += choices["v1_formB"] == row["attack_target"]
        counts[key] = rec
        print(f"{key}: tier {rec['tier']}, baseline correct {rec['baseline_correct']}/{len(inputs)}, "
              f"Form A {rec['strictA']}/{rec['strict_n']}, Form B {rec['strictB']}/{rec['strict_n']}")
    by_tier = {}
    for tier in ("T1", "T2", "T3", "T3/out", "out"):
        subset = [rec for rec in counts.values() if rec["tier"] == tier]
        by_tier[tier] = {key: sum(rec[key] for rec in subset) for key in
                         ("total", "baseline_correct", "usable", "flipA", "flipB",
                          "strict_n", "strictA", "strictB")}
        by_tier[tier]["scenarios"] = len(subset)
    primary = {key: by_tier["T1"][key] + by_tier["T2"][key] for key in by_tier["T1"]}
    runner.save_summary({"per_scenario": counts, "by_tier": by_tier,
                         "primary_T1": by_tier["T1"], "T1_T2_sensitivity": primary})


if __name__ == "__main__":
    main()
