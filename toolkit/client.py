"""Client dispatcher — routes decision calls to the selected backend.

The backend is chosen by the DECISION_CLIENT environment variable
(default: "jev"). Backends live in clients/<name>_client.py and must
implement the adapter contract documented in clients/ADAPTERS.md:

    ask(state, questions, ...) -> response dict
    answers_of(response) -> dict
    cost_of(response) -> float

All redteam code imports through this module, so switching the model
under test is a one-line environment change:

    DECISION_CLIENT=julia python experiments/expd3_policyfield_scale.py
"""

import importlib
import os

_BACKEND_NAME = os.environ.get("DECISION_CLIENT", "jev")
_backend = importlib.import_module(f"clients.{_BACKEND_NAME}_client")

ask = _backend.ask
answers_of = _backend.answers_of
cost_of = _backend.cost_of
