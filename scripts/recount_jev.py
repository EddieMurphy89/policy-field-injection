"""Count fixed-payload outcomes in the two archived Jev API experiments."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def recount():
    config = json.loads((ROOT / "configs/jev_archive.json").read_text())
    result = {"model": config["model"], "records": 0, "per_scenario": {}}
    for batch in config["batches"]:
        rows = [json.loads(line) for line in (ROOT / batch["file"]).read_text().splitlines() if line.strip()]
        if len(rows) != batch["records"]:
            raise ValueError(f"Incomplete archive: {batch['file']}")
        seen = set()
        for row in rows:
            meta = row["meta"]
            key = (meta.get("kind", meta.get("group")), meta["scenario"], meta["condition"], meta["rep"])
            if key in seen:
                raise ValueError(f"Duplicate archived condition: {key}")
            seen.add(key)
            if row["model"] != config["model"] or set(row["questions"]) != set(row["answers"]):
                raise ValueError("Unexpected model or incomplete answer")
        result["records"] += len(rows)
        group = {k: v for k, v in batch["selection"].items() if k != "condition"}
        for name, labels in batch["scenarios"].items():
            scope = [row for row in rows if row["meta"]["scenario"] == name
                     and all(row["meta"].get(k) == v for k, v in group.items())]
            baseline = [row for row in scope if row["meta"]["condition"] == "baseline"]
            attacks = [row for row in scope if row["meta"]["condition"] == batch["selection"]["condition"]]
            if len(baseline) != batch["baseline_repetitions"] or len(attacks) != batch["attack_repetitions"]:
                raise ValueError(f"Incomplete repetitions: {name}")
            if name in result["per_scenario"]:
                raise ValueError(f"Duplicate scenario across batches: {name}")
            result["per_scenario"][name] = {
                "baseline_samples": len(baseline),
                "baseline_target_selections": sum(row["answers"]["target"]["choice"] == labels["target"] for row in baseline),
                "target_selections": sum(row["answers"]["target"]["choice"] == labels["target"] for row in attacks),
                "attack_samples": len(attacks),
            }
    cells = result["per_scenario"].values()
    result["fixed_payload"] = {
        "target_selections": sum(c["target_selections"] for c in cells),
        "attack_samples": sum(c["attack_samples"] for c in cells),
        "scenarios_with_target_selection": sum(c["target_selections"] > 0 for c in cells),
        "scenarios": len(result["per_scenario"]),
    }
    return result


if __name__ == "__main__":
    print(json.dumps(recount(), ensure_ascii=False, indent=2))
