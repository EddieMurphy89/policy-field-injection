"""Exact-request replay of saved responses. No network or model inference."""

import copy
import json
import os
from pathlib import Path


def request_key(state, questions):
    return json.dumps({"state": state, "questions": questions},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def ask(state, questions, model=None, timeout=30, retries=5):
    default = Path(__file__).resolve().parents[2] / "samples" / "choice.jsonl"
    path = Path(os.environ.get("REPLAY_FILE", str(default)))
    key = request_key(state, questions)
    matches = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    matches = [row for row in matches
               if request_key(row["state"], row["questions"]) == key]
    if len(matches) != 1:
        raise ValueError(f"Replay requires exactly one matching saved request; found {len(matches)}")
    row = matches[0]
    return {"model": "replay:" + row["model"], "recorded_model": row["model"],
            "answers": copy.deepcopy(row["answers"]), "mode": "saved_response_replay",
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
