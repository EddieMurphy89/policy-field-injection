"""Local Cloudflare clef-flash (4-bit MLX) adapter.

Loads mlx-community/clef-flash-4bit via the clef_mlx.py loader bundled in the model snapshot.
Text channel only (no images/videos are ever passed).

Contract mapping — all three primitives NATIVE (Jev envelope), no degradation:
    choice: choice/probabilities/confidence native (probabilities 4dp-rounded
            by clef_mlx.systemone_answer)
    noul:   noul <- P(true) native (criteria optional)
    score:  score = expected level index (native), confidence native
"""

import os
import threading

MODEL_ID = "mlx-community/clef-flash-4bit@140bf7e037f5fa95a96535feca112f46c15927cf"

_MODEL = None
_LOCK = threading.Lock()


def _model():
    global _MODEL
    if _MODEL is None:
        with _LOCK:
            if _MODEL is None:
                import sys
                mdir = os.environ.get("CLEF_MODEL_DIR") or os.path.normpath(
                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "..", "models", "clef-flash-4bit"))
                sys.path.insert(0, mdir)
                import clef_mlx
                _MODEL = clef_mlx.load(mdir)
    return _MODEL


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
    """One SystemOne request against the resident clef-flash model.

    timeout/retries exist for contract compatibility with networked backends;
    local inference either returns or raises, so they are unused.
    """
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty mapping")
    result = _model().systemone({"model": "clef-flash", "state": state,
                                 "questions": questions})
    answers = {qid: _adapt(qid, spec, result["answers"][qid])
               for qid, spec in questions.items()}
    return {"model": model or MODEL_ID,
            "answers": answers,
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
