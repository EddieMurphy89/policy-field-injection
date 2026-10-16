"""SemIf direct-options-v1 control using the bundled MLX scorer."""

import os
import threading

REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
MODEL_ID = "SemIf(direct-options-v1)+Qwen/Qwen3.5-4B@" + REVISION

_CACHE = None
_LOCK = threading.Lock()


def _engine():
    global _CACHE
    if _CACHE is None:
        with _LOCK:
            if _CACHE is None:
                from third_party.semif_phase1 import mlx_backend
                mdir = os.environ.get("SEMIF_MODEL_DIR") or os.path.normpath(
                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "..", "models", "Qwen3.5-4B"))
                model, tok, meta = mlx_backend.load_model(mdir, REVISION)
                _CACHE = (model, tok, meta)
    return _CACHE


def ask(state, questions, model=None, timeout=30, retries=5):
    """Score each question via SemIf direct readout (letters A.., one forward
    per question). timeout/retries unused (local inference)."""
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty mapping")
    m, tok, meta = _engine()
    answers = {}
    for qid, spec in questions.items():
        kind = spec.get("type")
        if kind == "choice":
            keys = list(spec["criteria"].keys())
            opts = [{"id": k, "description": spec["criteria"][k]} for k in keys]
        elif kind == "noul":
            keys = ["no", "yes"]
            crit = spec.get("criteria") or {}
            opts = [{"id": "no", "description": crit.get("false", "no")},
                    {"id": "yes", "description": crit.get("true", "yes")}]
        elif kind == "score":
            levels = list(spec["criteria"])
            keys = [str(i) for i in range(len(levels))]
            opts = [{"id": k, "description": d} for k, d in zip(keys, levels)]
        else:
            raise ValueError(f"unsupported question type for {qid!r}: {kind!r}")
        row = {"id": qid, "state": state, "question": spec["instructions"],
               "options": opts}
        from third_party.semif_phase1 import mlx_backend
        res = mlx_backend.score(m, tok, row, meta)
        p = res["probabilities"]
        probs = {k: float(pi) for k, pi in zip(keys, p)}
        if kind == "choice":
            best = max(probs, key=probs.get)
            answers[qid] = {"choice": best, "probabilities": probs,
                            "confidence": probs[best]}
        elif kind == "noul":
            answers[qid] = {"noul": probs["yes"]}
        else:
            answers[qid] = {"score": float(sum(i * pi for i, pi in enumerate(p))),
                            "confidence": max(p)}
    return {"model": model or MODEL_ID,
            "answers": answers,
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
