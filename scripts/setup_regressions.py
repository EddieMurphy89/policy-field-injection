"""Fetch the three pinned candidate fixes and the TypeScript test runtime."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "experiments/regressions/vendor"


def main():
    config = json.loads((ROOT / "configs/regressions.json").read_text())
    TARGETS.mkdir(parents=True, exist_ok=True)
    for name, spec in config.items():
        target = TARGETS / name
        if not target.exists():
            subprocess.run(["git", "clone", spec["repo_url"], str(target)], check=True)
            subprocess.run(["git", "checkout", "--detach", spec["revision"]], cwd=target, check=True)
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, text=True).strip()
        if revision != spec["revision"]:
            raise SystemExit(f"Unexpected revision for {name}")
        if name == "jev-router":
            subprocess.run(["npm", "ci"], cwd=target, check=True)
    runtime = TARGETS / "runtime"
    runtime.mkdir(exist_ok=True)
    subprocess.run(["npm", "install", "--prefix", str(runtime), "--no-save", "tsx@4.23.13"], check=True)
    print(f"Candidate fixes ready: {TARGETS}")


if __name__ == "__main__":
    main()
