"""Dedicated Intern-Decision-2B engine shared by the two detector prompts."""

import os
import threading
from pathlib import Path

_ENGINE = None
_LOCK = threading.Lock()


def predict(state, questions):
    global _ENGINE
    if _ENGINE is None:
        with _LOCK:
            if _ENGINE is None:
                from clients.intern_client import load_engine
                default = Path(__file__).resolve().parents[2] / "models" / "Intern-Decision-2B"
                _ENGINE = load_engine(
                    os.environ.get("DETECTOR_MODEL_DIR", str(default)),
                    os.environ.get("DETECTOR_DEVICE", "cpu"),
                    os.environ.get("DETECTOR_DTYPE", "float32"))
    return _ENGINE.predict({"state": state, "questions": questions})
