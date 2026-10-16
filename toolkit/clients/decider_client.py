"""Local decider-0.8b (Mapika) adapter.

Letter-probability readout on Qwen3.5-0.8B-Base: logits at each "Answer k: ("
slot restricted to option-letter tokens, softmax, temperature 1.03 (from the
checkpoint's decider_config.json). Inference keeps the caller's option order
(_Keep/_NoShuffle; the rng shuffle in prompt.build is training-only).

Contract mapping — all three primitives native, no degradation:
    choice: choice/probabilities/confidence native (probabilities rounded to
            4dp by decider's format_answer)
    noul:   noul <- P(yes) (native; criteria optional)
    score:  score = expected level index; decider default isolated_levels=true
            (each level judged as its own yes/no row, then combined) — native
            decider behavior, not an adapter adaptation
"""

import os
import threading

MODEL_ID = "Mapika/decider-0.8b@a0a01d6f8135298f400a8c856b355793012ae971"

_DECIDER = None
_LOCK = threading.Lock()


def _model_dir():
    env = os.environ.get("DECIDER_MODEL_DIR")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "models",
                                         "decider-0.8b"))


def _decider():
    global _DECIDER
    if _DECIDER is None:
        with _LOCK:
            if _DECIDER is None:
                import sys
                import torch
                mdir = _model_dir()
                sys.path.insert(0, mdir)  # the repo's bundled decider/ package
                from decider.infer import Decider
                _DECIDER = Decider(mdir,
                                   device=os.environ.get("DECIDER_DEVICE", "cpu"),
                                   dtype=torch.float32)
    return _DECIDER


def _adapt(qid, spec, ans):
    kind = spec.get("type")
    if kind == "choice":
        return {"choice": ans["choice"],
                "probabilities": dict(ans["probabilities"]),
                "confidence": float(ans["confidence"])}
    if kind == "score":
        return {"score": float(ans["score"]),
                "confidence": float(ans["confidence"])}
    if kind == "noul":
        return {"noul": float(ans["noul"])}
    raise ValueError(f"unsupported question type for {qid!r}: {kind!r}")


def ask(state, questions, model=None, timeout=30, retries=5):
    """One typed-decision request against the resident decider engine.

    timeout/retries exist for contract compatibility with networked backends;
    local inference either returns or raises, so they are unused.
    """
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty mapping")
    result = _decider().system_one(state, questions)
    answers = {qid: _adapt(qid, spec, result["answers"][qid])
               for qid, spec in questions.items()}
    return {"model": model or MODEL_ID,
            "answers": answers,
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
