"""Recount the archived twelve-model candidate experiment without model calls."""

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def recount_model(rows, entry, variants, order):
    if len(rows) != entry["records"]:
        raise ValueError(f"{entry['tag']}: unexpected record count")
    grouped = defaultdict(dict)
    for row in rows:
        meta = row["meta"]
        name, variant = meta["scenario"], meta["variant"]
        condition = meta.get("condition", meta.get("phase"))
        if (meta.get("kind") != "choice" or name not in entry["scenarios"]
                or variant not in variants
                or condition not in ["baseline", "v1_policy_text", *order[1:]]):
            raise ValueError(f"Unexpected record: {name}/{variant}/{condition}")
        key = (variant, condition)
        if key in grouped[name]:
            raise ValueError(f"Duplicate record: {name}/{variant}/{condition}")
        question = row["questions"]["target"]
        choice = row["answers"]["target"]["choice"]
        if question["type"] != "choice" or choice not in question["criteria"]:
            raise ValueError(f"Invalid Choice response: {name}/{variant}/{condition}")
        grouped[name][key] = row
    if set(grouped) != set(entry["scenarios"]):
        raise ValueError(f"{entry['tag']}: missing scenarios")

    counts = dict.fromkeys(["fixed_flips", "family_flips", "usable_variants",
                           "fixed_coverage", "family_coverage", "evaluable_cells"], 0)
    cells = {}
    for name in entry["scenarios"]:
        records = grouped[name]
        base = {}
        for variant in variants:
            if (variant, "baseline") not in records:
                raise ValueError(f"Missing baseline: {name}/{variant}")
            base[variant] = records[(variant, "baseline")]
        meta = base[variants[0]]["meta"]
        target, gold = meta["atk"], meta["correct"]
        for (variant, condition), row in records.items():
            if (row["questions"] != base[variant]["questions"]
                    or row["meta"]["atk"] != target or row["meta"].get("correct", gold) != gold):
                raise ValueError(f"Task or labels changed: {name}/{variant}/{condition}")
        usable = [v for v in variants if base[v]["answers"]["target"]["choice"] != target]

        def hits(condition):
            missing = [v for v in usable if (v, condition) not in records]
            if missing:
                raise ValueError(f"Missing {name}/{condition}: {missing}")
            return sum(records[(v, condition)]["answers"]["target"]["choice"] == target
                       for v in usable)

        scores = {order[0]: hits("v1_policy_text")}
        inherited = scores[order[0]] == len(usable)
        for candidate in order[1:]:
            recorded = {v for v in variants if (v, candidate) in records}
            expected = set() if inherited else set(usable)
            if recorded != expected:
                raise ValueError(f"Incomplete or unexpected candidate calls: {name}/{candidate}")
            if not inherited:
                scores[candidate] = hits(candidate)
        best = max(scores, key=scores.get)  # Insertion order preserves the lowest-index tie rule.
        cells[name] = {
            "usable_variants": usable,
            "baseline_correct": sum(r["answers"]["target"]["choice"] == gold for r in base.values()),
            "fixed_flips": scores[order[0]], "candidate_flips": scores,
            "chosen_candidate": best, "family_flips": scores[best],
            "inherited_fixed": inherited,
        }
        counts["usable_variants"] += len(usable)
        counts["fixed_flips"] += scores[order[0]]
        counts["family_flips"] += scores[best]
        counts["fixed_coverage"] += scores[order[0]] > 0
        counts["family_coverage"] += scores[best] > 0
        counts["evaluable_cells"] += bool(usable)
    if counts != entry["expected"]:
        raise ValueError(f"{entry['tag']}: archived counts differ from the recorded result: {counts}")
    residual = {name: cell for name, cell in cells.items()
                if cell["family_flips"] < len(cell["usable_variants"])}
    return {"counts": counts, "cells": cells, "residual_cells": residual}


def recount(root=ROOT):
    config = json.loads((root / "configs/candidate_archive.json").read_text())
    models, total, residual = {}, {}, []
    records = 0
    for entry in config["models"]:
        with gzip.open(root / entry["file"], "rt", encoding="utf-8") as source:
            rows = [json.loads(line) for line in source]
        result = recount_model(rows, entry, config["variants"], config["candidate_order"])
        models[entry["tag"]] = result
        records += len(rows)
        for key, value in result["counts"].items():
            total[key] = total.get(key, 0) + value
        residual.extend({"model": entry["tag"], "scenario": name, **cell}
                        for name, cell in result["residual_cells"].items())
    return {"records": records, "totals": total, "models": models, "residual_cells": residual}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Save all cell and residual-cell counts as JSON")
    args = parser.parse_args()
    result = recount()
    for name, model in result["models"].items():
        c = model["counts"]
        print(f"{name}: fixed {c['fixed_flips']}/{c['usable_variants']}; "
              f"family {c['family_flips']}/{c['usable_variants']}; "
              f"coverage {c['fixed_coverage']} -> {c['family_coverage']}/{c['evaluable_cells']}")
    print(json.dumps({"records": result["records"], **result["totals"],
                      "residual_cells": len(result["residual_cells"])}, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
