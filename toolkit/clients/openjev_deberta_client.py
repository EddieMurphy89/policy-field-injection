"""Local open-jev-deberta-v3-large (kotoba labs) adapter.

DeBERTa-v3-large encoder typed-decision model (span head over [mean(question);
mean(option); product], temperature from open_jev_config.json). Package ships
in the repo snapshot (typed_decisions/), loaded from the local dir.

Interface adaptations (flagged, not model behavior):
  * native decide() takes a STRING state -> dict states are JSON-dumped.
  * native options are bare strings -> we pass "key: description" composites
    (same visible content as the decider rendering) and map probabilities
    back to criteria keys positionally.
  * noul: native (no/yes fixed options), noul = p(yes); criteria absent OK.
"""

import json
import os
import threading

MODEL_ID = "com-kotobalabs/open-jev-deberta-v3-large@188ee67a5c93122b916e5acd5bdb0cb3623e380a"

_MODEL = None
_LOCK = threading.Lock()


def _model():
    global _MODEL
    if _MODEL is None:
        with _LOCK:
            if _MODEL is None:
                import sys
                mdir = os.environ.get("OPENJEV_MODEL_DIR") or os.path.normpath(
                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "..", "models", "open-jev-deberta-v3-large"))
                sys.path.insert(0, mdir)
                from typed_decisions.open_jev import OpenJev
                _MODEL = OpenJev.from_pretrained(mdir, device="cpu")
    return _MODEL


def ask(state, questions, model=None, timeout=30, retries=5):
    """One decide() call; all questions share the state. timeout/retries unused."""
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty mapping")
    state_text = state if isinstance(state, str) else json.dumps(
        state, ensure_ascii=False)
    qids = list(questions)
    key_map = {}
    qlist = []
    for qid in qids:
        spec = questions[qid]
        kind = spec.get("type")
        if kind == "choice":
            keys = list(spec["criteria"].keys())
            key_map[qid] = keys
            qlist.append({"type": "choice", "instructions": spec["instructions"],
                          "options": [f"{k}: {spec['criteria'][k]}" for k in keys]})
        elif kind == "score":
            levels = list(spec["criteria"])
            key_map[qid] = levels
            qlist.append({"type": "score", "instructions": spec["instructions"],
                          "options": levels})
        elif kind == "noul":
            qlist.append({"type": "noul", "instructions": spec["instructions"]})
        else:
            raise ValueError(f"unsupported question type for {qid!r}: {kind!r}")
    out = _model().decide(state_text, qlist)
    answers = {}
    for qid, spec, ans in zip(qids, qlist, out):
        kind = spec.get("type")
        if kind == "choice":
            keys = key_map[qid]
            probs = {k: float(v) for k, v in zip(keys, ans["probabilities"].values())}
            best = max(probs, key=probs.get)
            answers[qid] = {"choice": best, "probabilities": probs,
                            "confidence": float(ans["confidence"])}
        elif kind == "score":
            answers[qid] = {"score": float(ans["score"]),
                            "confidence": float(ans["confidence"])}
        else:
            answers[qid] = {"noul": float(ans["noul"])}
    return {"model": model or MODEL_ID,
            "answers": answers,
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
