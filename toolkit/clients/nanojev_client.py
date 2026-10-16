"""NanoJev CPU adapter. Noul maps to boolean; confidence is max probability.
State serialization follows the upstream implementation."""

import os
import threading

MODEL_ID = "C-Tianyu/NanoJev@unified-games-v1"

_ENGINE = None
_LOCK = threading.Lock()


def _model_dir():
    return os.environ.get("NANOJEV_MODEL_DIR") or os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "models", "NanoJev"))


def _engine():
    global _ENGINE
    if _ENGINE is None:
        with _LOCK:
            if _ENGINE is None:
                import sys
                mdir = _model_dir()
                sys.path.insert(0, os.path.join(mdir, "source", "scripts"))
                import torch
                from predict_toy_decisions import (DecisionPredictor,
                                                   local_checkpoint_files,
                                                   load_decision_model_class,
                                                   read_json)
                # CPU port: replicate DecisionPredictor.__init__ without the
                # CUDA guard; precision="fp32" so no CUDA autocast anywhere.
                eng = DecisionPredictor.__new__(DecisionPredictor)
                root, paths = local_checkpoint_files(mdir)
                run_config = read_json(paths["run_config"])
                from safetensors.torch import load_file
                from transformers import AutoConfig, AutoModel, AutoTokenizer
                tokenizer = AutoTokenizer.from_pretrained(
                    str(paths["tokenizer"]), local_files_only=True,
                    trust_remote_code=False)
                if tokenizer.pad_token_id is None:
                    tokenizer.pad_token = tokenizer.eos_token
                body_config = AutoConfig.from_pretrained(
                    str(paths["body_config"]), local_files_only=True,
                    trust_remote_code=False)
                body_config.use_cache = False
                body = AutoModel.from_config(body_config,
                                             attn_implementation="sdpa",
                                             trust_remote_code=False).float()
                DecisionModel = load_decision_model_class()
                model = DecisionModel(body, run_config["set_head"])
                weights = load_file(str(paths["weights"]), device="cpu")
                model.load_state_dict(weights, strict=True)
                model.to(device="cpu", dtype=torch.float32)
                model.eval()
                eng.model = model
                eng.tokenizer = tokenizer
                eng.root = root
                eng.run_config = run_config
                eng.limit = run_config.get("max_length", 512)
                eng.device = torch.device("cpu")
                eng.precision = "fp32"
                eng.disable_native_triton = False
                eng.inference_calls = 0
                eng._torch = torch
                _ENGINE = eng
    return _ENGINE


def ask(state, questions, model=None, timeout=30, retries=5):
    """One NanoJev predict call (single state). timeout/retries unused."""
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty mapping")
    nq = {}
    for qid, spec in questions.items():
        kind = spec.get("type")
        if kind == "noul":
            q = {"type": "boolean", "instructions": spec["instructions"]}
            if spec.get("criteria"):
                q["criteria"] = spec["criteria"]
            nq[qid] = q
        elif kind in ("choice", "score"):
            nq[qid] = {"type": kind, "instructions": spec["instructions"],
                       "criteria": spec["criteria"]}
        else:
            raise ValueError(f"unsupported question type for {qid!r}: {kind!r}")
    out = _engine().predict({"states": [{"id": "s0", "state": state,
                                         "questions": nq}]})
    answers = {}
    for qid, spec in questions.items():
        a = out["states"][0]["answers"][qid]
        kind = spec.get("type")
        if kind == "choice":
            answers[qid] = {"choice": a["choice"],
                            "probabilities": dict(a["probabilities"]),
                            "confidence": max(a["probabilities"].values())}
        elif kind == "score":
            answers[qid] = {"score": float(a["score"]),
                            "confidence": max(a["probabilities"].values())}
        else:
            answers[qid] = {"noul": float(a["p_true"])}
    return {"model": model or MODEL_ID,
            "answers": answers,
            "usage": {"cost": 0.0}}


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return 0.0
