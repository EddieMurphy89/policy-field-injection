"""Local Julia-1 (SupersonicLabs) adapter — System One typed-decision model.

Implements the contract in clients/ADAPTERS.md. The engine is a module-level
lazy singleton: weights load once on the first ask(), never per call.

Model dir resolution (first hit wins):
    $JULIA_MODEL_DIR  ->  $PROJ/models/Julia-1  (../../models/Julia-1 rel. to this file)

Field mapping from Julia's typed API to the adapter contract
(interface adaptation):
    choice: choice/probabilities native;  confidence <- max_probability
    score:  score (expected rubric index) native;  confidence <- max_probability
    noul:   noul native; contract keeps only {"noul": p}
"""

import os
import threading

MODEL_ID = "SupersonicLabs/Julia-1@a85b127321d580d65176c89ced8273f305745d85"

_ENGINE = None
_LOCK = threading.Lock()


def _model_dir():
    env = os.environ.get("JULIA_MODEL_DIR")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "models", "Julia-1"))


def _engine():
    global _ENGINE
    if _ENGINE is None:
        with _LOCK:
            if _ENGINE is None:
                from julia import load_model
                _ENGINE = load_model(_model_dir(), device="cpu",
                                     strict_encoding=True,
                                     max_length=8192, head_length=512)
    return _ENGINE


def _adapt(qid, spec, ans):
    kind = spec.get("type")
    if kind == "choice":
        return {"choice": ans["choice"],
                "probabilities": dict(ans["probabilities"]),
                "confidence": float(ans["max_probability"])}
    if kind == "score":
        return {"score": float(ans["score"]),
                "confidence": float(ans["max_probability"])}
    if kind == "noul":
        return {"noul": float(ans["noul"])}
    raise ValueError(f"unsupported question type for {qid!r}: {kind!r}")


def ask(state, questions, model=None, timeout=30, retries=5):
    """One typed-decision request against the resident Julia-1 engine.

    timeout/retries exist for contract compatibility with networked backends;
    local inference either returns or raises, so they are unused.
    """
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty mapping")
    result = _engine().predict(state=state, questions=questions)
    answers = {qid: _adapt(qid, spec, result["answers"][qid])
               for qid, spec in questions.items()}
    return {"model": model or MODEL_ID,
            "answers": answers,
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
