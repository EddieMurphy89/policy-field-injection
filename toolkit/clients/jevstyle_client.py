"""Local Jev-Style-Qwen3.5-2B-Decision-v2 (chaoliangUNSW) adapter.

Letter readout on Qwen3.5-2B-Base + LoRA r32: prompt renders options as
"A. <option>", next-position letter logits (" A".." Z") projected in fp32,
softmax over declared options, calibration temperature from calibration.json
applied (standard logits/T scaling — differs from Intern-Decision's
softmax(log p / T)).

Interface adaptations (flagged, not model behavior):
  * The native interface takes one question per call with bare option strings;
    our adapter passes "key: description" composite strings (same visible
    content as decider's rendering) and maps probabilities back to the
    original criteria keys positionally.
  * state dicts are JSON-dumped (native interface takes a string).
  * noul: options ["no", "yes"], noul <- P(yes). criteria tolerated/ignored
    (descriptions dropped — the native interface has no slot for them).
  * score: options = ordered level descriptions, score = expected index.
"""

import json
import os
import threading

MODEL_ID = "chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-v2@6b84dda83feb79d7ed14c4c312fcb918be76cbff"

_CACHE = None
_LOCK = threading.Lock()


def _model_dir():
    env = os.environ.get("JEVSTYLE_MODEL_DIR")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "models",
                                         "Jev-Style-2B-v2"))


def _model():
    global _CACHE
    if _CACHE is None:
        with _LOCK:
            if _CACHE is None:
                import sys
                mdir = _model_dir()
                sys.path.insert(0, mdir)
                from jev_h100.model import load
                model, tok = load(mdir, device=os.environ.get("JEVSTYLE_DEVICE", "cpu"))
                with open(os.path.join(mdir, "calibration.json")) as f:
                    temperature = json.load(f)["temperature"]
                _CACHE = (model, tok, temperature)
    return _CACHE


def _predict_probs(options, state_text, question):
    import numpy as np
    model, tok, temperature = _model()  # first: inserts model dir into sys.path
    from jev_h100.common import probabilities, record
    from jev_h100.model import predict
    row = record("request", state_text, question, options, 0, "user")
    pred = predict(model, tok, [row], os.environ.get("JEVSTYLE_DEVICE", "cpu"),
                   batch_size=1)[0]
    return probabilities(np.asarray(pred["logits"], dtype=float),
                         temperature).tolist()


def ask(state, questions, model=None, timeout=30, retries=5):
    """One decision request per question (native interface is single-question).

    timeout/retries exist for contract compatibility; local inference either
    returns or raises.
    """
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty mapping")
    state_text = state if isinstance(state, str) else json.dumps(
        state, ensure_ascii=False)
    answers = {}
    for qid, spec in questions.items():
        kind = spec.get("type")
        ins = spec.get("instructions", "")
        if kind == "choice":
            keys = list(spec["criteria"].keys())
            options = [f"{k}: {spec['criteria'][k]}" for k in keys]
            p = _predict_probs(options, state_text, ins)
            probs = {k: float(pi) for k, pi in zip(keys, p)}
            best = max(probs, key=probs.get)
            answers[qid] = {"choice": best, "probabilities": probs,
                            "confidence": probs[best]}
        elif kind == "noul":
            p = _predict_probs(["no", "yes"], state_text, ins)
            answers[qid] = {"noul": float(p[1])}
        elif kind == "score":
            levels = list(spec["criteria"])
            p = _predict_probs(levels, state_text, ins)
            answers[qid] = {"score": float(sum(i * pi for i, pi in enumerate(p))),
                            "confidence": float(max(p))}
        else:
            raise ValueError(f"unsupported question type for {qid!r}: {kind!r}")
    return {"model": model or MODEL_ID,
            "answers": answers,
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
