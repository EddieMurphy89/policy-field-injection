"""Download one configured model snapshot, including its inference source."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    models = json.loads((ROOT / "configs" / "backends.json").read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=[name for name in models if "repo_id" in models[name]])
    args = parser.parse_args()
    entry = models[args.model]
    from huggingface_hub import snapshot_download
    path = snapshot_download(entry["repo_id"], revision=entry["revision"],
                             local_dir=str(ROOT / entry["local_dir"]))
    print(f"Downloaded: {path}")
    print(f"export {entry['path_env']}='{path}'")
    print(f"export DECISION_CLIENT={entry['backend']}")
    print(f"Runtime: {entry['runtime']}")


if __name__ == "__main__":
    main()
