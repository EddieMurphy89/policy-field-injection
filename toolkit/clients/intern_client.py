"""Text-only Intern-Decision adapter. Configure checkpoint, device and dtype with INTERN_*."""

import os
import sys
import threading
import importlib.util

_ENGINE = None
_LOCK = threading.Lock()

_REVISIONS = {
    "Intern-Decision-0.8B": "85a0cc5a99d67ea8d56dfe98115689212867171d",
    "Intern-Decision-2B": "8797836c65fc91a2435b1fb6850b5f0aabd75cc3",
    "Intern-Decision-4B": "0e5e6aa7d6d750e2b1504ba11a8136cb58aeb3cd",
}


def _model_dir():
    env = os.environ.get("INTERN_MODEL_DIR")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "models",
                                         "Intern-Decision-0.8B"))


def _engine():
    global _ENGINE
    if _ENGINE is None:
        with _LOCK:
            if _ENGINE is None:
                mdir = _model_dir()
                _ENGINE = load_engine(
                    mdir, os.environ.get("INTERN_DEVICE", "cpu"),
                    os.environ.get("INTERN_DTYPE", "float32"))
    return _ENGINE


def load_engine(model_dir, device="cpu", dtype="float32"):
    """Load an independent engine from the checkpoint's inference source."""
    model_dir = os.path.abspath(model_dir)
    source = os.path.join(model_dir, "inference.py")
    if not os.path.isfile(source):
        raise FileNotFoundError(f"Download the complete Intern snapshot: {source}")
    sys.path.insert(0, model_dir)
    name = "_intern_inference_" + os.path.basename(model_dir).replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.DecisionEngine(model_dir, device=device, dtype=dtype)


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
    """One typed-decision request against the resident Intern-Decision engine.

    timeout/retries exist for contract compatibility with networked backends;
    local inference either returns or raises, so they are unused.
    """
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty mapping")
    result = _engine().predict({"state": state, "questions": questions})
    answers = {qid: _adapt(qid, spec, result["answers"][qid])
               for qid, spec in questions.items()}
    name = result.get("model", "Intern-Decision")
    rev = _REVISIONS.get(name, "unknown")
    return {"model": model or f"internlm/{name}@{rev}",
            "answers": answers,
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
