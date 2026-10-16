"""Scenario variants, baseline verification and Form B payload placement."""

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
L5 = os.path.normpath(os.path.join(HERE, ".."))
PROJ = os.path.normpath(os.path.join(L5, "../.."))
TOOLKIT = os.path.join(PROJ, "toolkit")
RESULTS = os.path.join(L5, "results")
os.makedirs(RESULTS, exist_ok=True)

sys.path.insert(0, TOOLKIT)
sys.path.insert(0, os.path.join(TOOLKIT, "experiments"))
sys.path.insert(0, TOOLKIT)  # defenses package

from exp1c_contested_search import mutations  # noqa: E402

LEAVES = {
    "route_refund": ("ticket", "text"), "route_hr": ("request", "text"),
    "doc_type": ("document", "text"), "resume_role": ("resume", "text"),
    "expense_cat": ("expense", "text"), "loan_purpose": ("application", "text"),
    "email_intent": ("email", "text"), "moderation": ("post", "text"),
    "pr_gate": ("pr", "diff_summary"), "support_priority": ("ticket", "text"),
    "gate_fraud": ("transaction", "items"), "gate_scam": ("message", "text"),
    "gate_cmd": ("command", "text"), "gate_refund": ("case", "text"),
    "severity_down": ("bug", "text"), "frustration_down": ("message", "text"),
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


def form_b_state(name, state, policy_text):
    """Form B: v1 policy text embedded INSIDE the referenced text leaf value,
    appended as a single note paragraph (一段式注释形态)."""
    top, sub = LEAVES[name]
    s = copy.deepcopy(state)
    s[top][sub] = f"{s[top][sub]}\n\n{policy_text}"
    return s


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


def load_reuse(path):
    """{(scenario, variant): {"baseline": ans, "v1": ans, "state_clean": ..., "state_v1": ...}}"""
    out = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            m = r["meta"]
            key = (m["scenario"], m["variant"])
            slot = out.setdefault(key, {})
            if m.get("condition") == "baseline":
                slot["baseline"] = r["answers"]["target"]
                slot["state_clean"] = r["state"]
            elif m.get("condition") == "v1_policy_text":
                slot["v1"] = r["answers"]["target"]
                slot["state_v1"] = r["state"]
    return out


def verify_reuse(reuse, pool="expd3", only=None):
    """Byte-level: regenerated variant states must equal reused records' states,
    and reused v1 state must equal clean state + the injected field.
    `only`: optional set of scenario names to restrict verification to."""
    from expd3_policyfield_scale import CHOICE as E3C, NOUL as E3N
    from expd4_policyfield_ablation import NOUL as E4N
    tables = {"expd3": list(E3C), "expd3-noul": list(E3N), "expd4-noul": list(E4N)}[pool]
    if only is not None:
        tables = [t for t in tables if t[0] in only]
    ok_state = ok_attack = bad = 0
    details = []
    for t in tables:
        if pool.startswith("expd3") and pool.endswith("noul"):
            name, state, ins = t[0], t[1], t[2]
            policy, field = t[5], "screening_policy"
        elif "noul" in pool:
            name, state, ins = t[0], t[1], t[2]
            policy, field = t[5], "screening_policy"
        else:
            name, state, ins = t[0], t[1], t[2]
            policy, field = t[6], "review_policy"
        for vid, s in state_variants(name, state):
            rec = reuse.get((name, vid))
            if rec is None:
                bad += 1
                details.append(f"MISSING {name}/{vid}")
                continue
            same = json.dumps(rec["state_clean"], sort_keys=True, ensure_ascii=False) == \
                json.dumps(s, sort_keys=True, ensure_ascii=False)
            ok_state += same
            bad += not same
            if not same:
                details.append(f"STATE-DIFF {name}/{vid}")
                continue
            expected = dict(s)
            expected[field] = policy
            same_a = json.dumps(rec["state_v1"], sort_keys=True, ensure_ascii=False) == \
                json.dumps(expected, sort_keys=True, ensure_ascii=False)
            ok_attack += same_a
            bad += not same_a
            if not same_a:
                details.append(f"ATTACK-DIFF {name}/{vid}")
    return ok_state, ok_attack, bad, details
