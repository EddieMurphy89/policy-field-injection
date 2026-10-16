# Client Adapter Contract

Every backend under `clients/` is a module named `<name>_client.py` that
exposes three module-level functions. `client.py` (toolkit root) dispatches
to the backend named by the `DECISION_CLIENT` environment variable.

```python
def ask(state, questions, model=None, timeout=30, retries=5) -> dict
def answers_of(response: dict) -> dict
def cost_of(response: dict) -> float   # 0.0 for local models
```

## Request shapes (Jev-compatible)

`state` is either a string or a JSON-serializable dict/list.
`questions` is a dict of `{question_name: question_spec}` with three
primitive types:

```python
# Choice — pick exactly one option
{"type": "choice", "instructions": str, "criteria": {option: description, ...}}

# Noul — boolean gate; answer is P(true)
{"type": "noul", "instructions": str, "criteria": {"true": str, "false": str}}

# Score — graded level; criteria is an ORDERED list of level descriptions
{"type": "score", "instructions": str, "criteria": [level_desc, ...]}
```

## Response shape

`ask` must return a dict with at least:

```python
{
    "model": str,                    # backend identifier, used in logs
    "answers": {
        "<question_name>": {
            # choice:  {"choice": str, "probabilities": {opt: p}, "confidence": float}
            # noul:    {"noul": float}                        # P(true)
            # score:   {"score": float, "confidence": float}
        },
    },
    "usage": {"cost": float},        # optional; 0.0 for local models
}
```

## Implementation notes

- Load heavy resources (local model weights) once, in a module-level lazy
  singleton — never per `ask()` call.
- Probabilities for a choice answer must sum to ~1.0 across the option set
  (renormalize if the backend exposes raw scores/logits).
- The adapter must not swallow errors silently; raise on unrecoverable
  backend failure so the runner's log reflects it.
- Reference implementation: `clients/jev_client.py`.
