"""Scenario variants, typed questions and Wilson intervals."""

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WAVE3 = os.path.normpath(os.path.join(HERE, ".."))
PROJ = os.path.normpath(os.path.join(WAVE3, "../.."))
TOOLKIT = os.path.join(PROJ, "toolkit")
RESULTS = os.path.join(WAVE3, "results")
os.makedirs(RESULTS, exist_ok=True)

sys.path.insert(0, TOOLKIT)
sys.path.insert(0, os.path.join(TOOLKIT, "experiments"))

from exp1c_contested_search import mutations  # noqa: E402  7 operators, verbatim

LEAVES = {
    "route_refund": ("ticket", "text"), "route_hr": ("request", "text"),
    "doc_type": ("document", "text"), "resume_role": ("resume", "text"),
    "expense_cat": ("expense", "text"), "loan_purpose": ("application", "text"),
    "email_intent": ("email", "text"), "moderation": ("post", "text"),
    "pr_gate": ("pr", "diff_summary"), "support_priority": ("ticket", "text"),
    "gate_fraud": ("transaction", "items"), "gate_scam": ("message", "text"),
    "gate_cmd": ("command", "text"), "gate_refund": ("case", "text"),
    "severity_down": ("bug", "text"), "frustration_down": ("message", "text"),
    "it_helpdesk": ("ticket", "text"), "bug_severity": ("report", "text"),
    "news_topic": ("article", "text"), "contract_clause": ("clause", "text"),
    "data_classification": ("file", "text"), "translation_queue": ("message", "text"),
    "code_language": ("snippet", "text"), "lead_qualification": ("lead", "text"),
    "incident_comms": ("incident", "text"), "pr_dep_bump": ("pr", "diff_summary"),
    "gate_pii": ("message", "text"), "gate_malware": ("code", "text"),
    "gate_weapon": ("post", "text"), "gate_legal": ("message", "text"),
    "gate_secrets": ("file", "text"), "gate_copyright": ("request", "text"),
}


def state_variants(name, state):
    top, sub = LEAVES[name]
    text = state[top][sub]
    out = [("orig", copy.deepcopy(state))]
    for i, m in enumerate(mutations(text)):
        s = copy.deepcopy(state)
        s[top][sub] = m
        out.append((f"mut{i}", s))
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5 / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def fmt_wilson(k, n):
    p, lo, hi = wilson(k, n)
    return f"{k}/{n} ({p * 100:.0f}% [{lo * 100:.0f},{hi * 100:.0f}])"


def q_choice(ins, criteria):
    return {"target": {"type": "choice", "instructions": ins, "criteria": criteria}}


def q_noul(ins):
    return {"target": {"type": "noul", "instructions": ins}}


def q_score(ins, levels):
    return {"target": {"type": "score", "instructions": ins, "criteria": levels}}
