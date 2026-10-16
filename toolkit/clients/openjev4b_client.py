"""OpenJev 4B typed-decision adapter using the checkpoint inference code."""

import json
import os
import threading

MODEL_ID = "AlexWortega/openjev:qwen3.5-4b-nli-v5@a20448012c213128955ca0c693e7c943865cab77"

_MODEL = None
_LOCK = threading.Lock()


def _root():
    return os.environ.get("OPENJEV4B_DIR") or os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "models", "openjev-4b"))


def _model():
    global _MODEL
    if _MODEL is None:
        with _LOCK:
            if _MODEL is None:
                import sys
                root = _root()
                sys.path.insert(0, os.path.join(root, "code"))
                sys.path.insert(0, root)
                os.environ.setdefault("OPENJEV_DEVICE", "cpu")
                from openjev_decide import OpenJev
                _MODEL = OpenJev.from_pretrained(root,
                                                 subfolder="qwen3.5-4b-nli-v5")
    return _MODEL


def ask(state, questions, model=None, timeout=30, retries=5):
    """One decide() call; per-option forward passes internally."""
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty mapping")
    _model()  # ensures sys.path before importing openjev_decide below
    from openjev_decide import RUBRIC_MARK
    qids = list(questions)
    qlist = []
    for qid in qids:
        spec = questions[qid]
        kind = spec.get("type")
        if kind == "choice":
            criteria = spec["criteria"]
            keys = list(criteria.keys())
            qlist.append({"type": "choice",
                          "instructions": spec["instructions"] + RUBRIC_MARK
                          + json.dumps({k: criteria[k] for k in keys},
                                       ensure_ascii=False),
                          "options": keys})
        elif kind == "noul":
            crit = spec.get("criteria") or {}
            qlist.append({"type": "noul",
                          "instructions": spec["instructions"] + RUBRIC_MARK
                          + json.dumps({"no": crit.get("false", "no"),
                                        "yes": crit.get("true", "yes")},
                                       ensure_ascii=False),
                          "options": ["no", "yes"]})
        elif kind == "score":
            qlist.append({"type": "score",
                          "instructions": spec["instructions"],
                          "options": list(spec["criteria"])})
        else:
            raise ValueError(f"unsupported question type for {qid!r}: {kind!r}")
    out = _model().decide(state, qlist)
    answers = {}
    for qid, ans in zip(qids, out):
        spec = questions[qid]  # original spec (qlist entries carry no criteria)
        kind = spec.get("type")
        if kind == "noul":
            answers[qid] = {"noul": float(ans["noul"])}
            continue
        probs = {k: float(v) for k, v in ans["probabilities"].items()}
        if kind == "choice":
            best = max(probs, key=probs.get)
            answers[qid] = {"choice": best, "probabilities": probs,
                            "confidence": probs[best]}
        else:
            # probabilities are keyed by level description; expected index
            # follows the declared level ORDER (criteria list order)
            levels = list(spec["criteria"])
            ordered = [probs[l] for l in levels]
            answers[qid] = {"score": float(sum(i * p for i, p in enumerate(ordered))),
                            "confidence": max(ordered)}
    return {"model": model or MODEL_ID,
            "answers": answers,
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
