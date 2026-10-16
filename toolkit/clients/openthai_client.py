"""Local OpenThai-SystemOne (iApp Technology) adapter.

Qwen3.5-0.8B text tower + 256-slot decision head (control tokens
<|ts_opt_i|>; option "name: description" text enters the sequence; readout at
<|ts_answer|>). Loads via the official openthai-systemone package from the
local snapshot (code reviewed: torch/transformers only, no network/exec).

Contract mapping — all three primitives native, no degradation:
    choice: choice/probabilities/confidence native
    noul:   noul <- p(yes) native (criteria optional)
    score:  score/confidence native
"""

import os
import threading

MODEL_ID = "iapp/OpenThai-SystemOne@dc67b0295ab7ac94b05d27187150d9a4b5784554"

_CLIENT = None
_LOCK = threading.Lock()


def _model_dir():
    return os.environ.get("OPENTHAI_MODEL_DIR") or os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "models", "OpenThai-SystemOne"))


def _client():
    global _CLIENT
    if _CLIENT is None:
        with _LOCK:
            if _CLIENT is None:
                from openthai_systemone import SystemOneClient
                _CLIENT = SystemOneClient(_model_dir(), device="cpu")
    return _CLIENT


def ask(state, questions, model=None, timeout=30, retries=5):
    """One system_one call. timeout/retries unused (local inference)."""
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty mapping")
    resp = _client().system_one(state=state, questions=questions)
    answers = {}
    for qid, spec in questions.items():
        a = resp.answers[qid]
        kind = spec.get("type")
        if kind == "choice":
            answers[qid] = {"choice": a.choice,
                            "probabilities": dict(a.probabilities),
                            "confidence": float(a.confidence)}
        elif kind == "score":
            answers[qid] = {"score": float(a.score),
                            "confidence": float(a.confidence)}
        elif kind == "noul":
            answers[qid] = {"noul": float(a.noul)}
        else:
            raise ValueError(f"unsupported question type for {qid!r}: {kind!r}")
    return {"model": model or MODEL_ID,
            "answers": answers,
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
