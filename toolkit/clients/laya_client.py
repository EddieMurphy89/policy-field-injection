"""Laya multilingual adapter. Choice and Score confidence use answer_confidence."""

import os
import threading

MODEL_ID = "convaiinnovations/laya:multilingual@7b928d828b7b0e022f929d9bd2e44165aa270148"

_AGENT = None
_LOCK = threading.Lock()


def _agent():
    global _AGENT
    if _AGENT is None:
        with _LOCK:
            if _AGENT is None:
                import laya
                _AGENT = laya.load(os.environ.get("LAYA_MODEL_DIR", "convaiinnovations/laya"),
                                   subfolder="multilingual",
                                   revision=os.environ.get("LAYA_REVISION",
                                       "7b928d828b7b0e022f929d9bd2e44165aa270148"),
                                   device=os.environ.get("LAYA_DEVICE", "cpu"))
    return _AGENT


def _adapt(qid, spec, ans):
    kind = spec.get("type")
    if kind == "choice":
        return {"choice": ans["choice"],
                "probabilities": dict(ans["probabilities"]),
                "confidence": float(ans["answer_confidence"])}
    if kind == "score":
        return {"score": float(ans["score"]),
                "confidence": float(ans["answer_confidence"])}
    if kind == "noul":
        return {"noul": float(ans["noul"])}
    raise ValueError(f"unsupported question type for {qid!r}: {kind!r}")


def ask(state, questions, model=None, timeout=30, retries=5):
    """One typed-decision request against the resident laya-multilingual agent.

    timeout/retries exist for contract compatibility with networked backends;
    local inference either returns or raises, so they are unused.
    """
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty mapping")
    result = _agent().predict(state, questions)
    answers = {qid: _adapt(qid, spec, result["answers"][qid])
               for qid, spec in questions.items()}
    return {"model": model or MODEL_ID,
            "answers": answers,
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
