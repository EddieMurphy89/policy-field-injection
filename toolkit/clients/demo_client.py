"""Deterministic plumbing-demo backend — NOT a model.

Purpose: let a clean checkout run the harness end-to-end (runner, JSONL
evidence logs, metrics) without an API key or local weights. Outputs are
synthetic pseudo-probabilities derived from hashing the request; they exist
only to exercise the pipeline's plumbing.

**Never cite numbers produced by this backend as model evidence.** Any record
written through it carries model="demo-plumbing" so logs cannot be confused
with real model output.
"""

import hashlib
import math

MODEL_ID = "demo-plumbing"


def _rng01(*parts):
    """Deterministic pseudo-random doubles in (0, 1) from request content."""
    out = []
    for i, p in enumerate(parts):
        h = hashlib.sha256(f"{i}:{p}".encode()).digest()
        out.append((int.from_bytes(h[:8], "big") % 10_000) / 10_000 + 1e-4)
    return out


def ask(state, questions, model=None, timeout=30, retries=0):
    state_s = str(state)
    answers = {}
    for name, q in questions.items():
        qtype = q.get("type")
        if qtype == "choice":
            opts = list(q["criteria"])
            raw = _rng01(state_s, name, *opts)
            exps = [math.exp(4 * r) for r in raw[: len(opts)]]
            total = sum(exps)
            probs = {o: e / total for o, e in zip(opts, exps)}
            choice = max(probs, key=probs.get)
            answers[name] = {"choice": choice, "probabilities": probs,
                             "confidence": probs[choice]}
        elif qtype == "noul":
            answers[name] = {"noul": _rng01(state_s, name, "noul")[0]}
        elif qtype == "score":
            levels = q["criteria"]
            ws = _rng01(state_s, name, *map(str, range(len(levels))))
            total = sum(ws)
            probs = [w / total for w in ws[: len(levels)]]
            answers[name] = {"score": sum(i * p for i, p in enumerate(probs)),
                             "probabilities": probs}
        else:
            raise ValueError(f"unknown question type: {qtype}")
    return {"model": MODEL_ID, "answers": answers, "synthetic": True}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
