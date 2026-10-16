"""Fetch the pinned upstream reviewer and install its Node dependencies."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = json.loads((ROOT / "configs" / "review_chain.json").read_text())
    target = ROOT / config["local_dir"]
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", config["repo_url"], str(target)], check=True)
        subprocess.run(["git", "checkout", "--detach", config["revision"]], cwd=target, check=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, text=True).strip()
    if revision != config["revision"]:
        raise SystemExit("Existing reviewer checkout differs from configs/review_chain.json")
    subprocess.run(["npm", "ci"], cwd=target, check=True)
    print(f"Reviewer ready: {target}")


if __name__ == "__main__":
    main()
