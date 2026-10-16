"""Choice defense arms: field allowlist, policy detector and detector bypass."""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (LEAVES, RESULTS, fmt_wilson, form_b_state, load_reuse,
                     q_choice, state_variants, verify_reuse)
from a2_payloads import A2, DETECTOR_LINE
from runtime import detector_settings
from defenses import allowlist, detector
from redteam.runner import Runner

TAG = os.environ.get("RUN_TAG", "noname")
REUSE = os.environ.get("BASELINE_FILE")  # required for the choice matrix; unused when imported


def log_detector(r, tag, text, meta):
    """Append a detector-scan record to the runner's jsonl (bypasses
    client.ask — the detector is a fixed intern-2B, not the defended model)."""
    p = detector.scan_p(text)
    rec = {"ts": datetime.now().isoformat(), "tag": tag, "state": text,
           "questions": {"gate": {"type": "noul",
                                  "instructions": detector.QUESTION}},
           "model": "intern-2B(detector)", "answers": {"gate": {"noul": p}},
           "cost": 0.0, "mode": "inference", "runtime": detector_settings(),
           "meta": {**meta, "record_type": "detector_scan", "detector_p": p,
                    "detector_tau": detector.TAU,
                    "detector_version": detector.VERSION}}
    with r._lock:
        r.records.append(rec)
        with open(r.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return p


def scenarios():
    from expd3_policyfield_scale import CHOICE
    return CHOICE


def main():
    arms = sys.argv[1:]
    if not REUSE:
        raise SystemExit("BASELINE_FILE env var (fresh baseline JSONL path) is required")
    reuse = load_reuse(REUSE)
    ok_s, ok_a, bad, details = verify_reuse(reuse, "expd3")
    print(f"[reuse-verify] {REUSE}\n  state-clean OK {ok_s}, attack-shape OK {ok_a}, bad {bad}")
    for d in details[:10]:
        print("  ", d)
    if bad:
        raise SystemExit("reuse verification failed; refuse to run")

    # ---------------- F1: D1 + Form A ----------------
    if "f1" in arms:
        r = Runner(f"defense-{TAG}-f1", workers=1, out_dir=RESULTS)
        k = n = id_ok = 0
        for name, state, ins, criteria, correct, atk, policy in scenarios():
            for vid, s in state_variants(name, state):
                sa = dict(s)
                sa["review_policy"] = policy
                stripped = allowlist.strip_to_allowlist(sa, allowlist.allowlist_of(s))
                id_ok += stripped == s
                b = reuse[(name, vid)]["baseline"]
                a = r.decide(f"f1/{name}/{vid}", stripped, q_choice(ins, criteria),
                             meta={"kind": "choice", "scenario": name, "variant": vid,
                                   "condition": "f1_d1_formA", "atk": atk,
                                   "defense": "D1", "stripped_to_clean": stripped == s})["target"]
                if b["choice"] == atk:
                    continue
                n += 1
                k += a["choice"] == atk
        print(f"[F1] flip {fmt_wilson(k, n)}; strip==clean in {id_ok}/80")
        r.save_summary({"arm": "f1", "flips": k, "n": n, "strip_eq_clean": id_ok})

    # ---------------- F2: Form B, no defense ----------------
    if "f2" in arms:
        r = Runner(f"defense-{TAG}-f2", workers=1, out_dir=RESULTS)
        k = n = 0
        for name, state, ins, criteria, correct, atk, policy in scenarios():
            for vid, s in state_variants(name, state):
                sb = form_b_state(name, s, policy)
                b = reuse[(name, vid)]["baseline"]
                a = r.decide(f"f2/{name}/{vid}", sb, q_choice(ins, criteria),
                             meta={"kind": "choice", "scenario": name, "variant": vid,
                                   "condition": "f2_formB", "atk": atk})["target"]
                if b["choice"] == atk:
                    continue
                n += 1
                k += a["choice"] == atk
        print(f"[F2] flip {fmt_wilson(k, n)}")
        r.save_summary({"arm": "f2", "flips": k, "n": n})

    # ---------------- F3: D1 + Form B ----------------
    if "f3" in arms:
        r = Runner(f"defense-{TAG}-f3", workers=1, out_dir=RESULTS)
        k = n = id_ok = 0
        for name, state, ins, criteria, correct, atk, policy in scenarios():
            for vid, s in state_variants(name, state):
                sb = form_b_state(name, s, policy)
                stripped = allowlist.strip_to_allowlist(sb, allowlist.allowlist_of(s))
                id_ok += stripped == sb
                b = reuse[(name, vid)]["baseline"]
                a = r.decide(f"f3/{name}/{vid}", stripped, q_choice(ins, criteria),
                             meta={"kind": "choice", "scenario": name, "variant": vid,
                                   "condition": "f3_d1_formB", "atk": atk,
                                   "defense": "D1", "stripped_unchanged": stripped == sb})["target"]
                if b["choice"] == atk:
                    continue
                n += 1
                k += a["choice"] == atk
        print(f"[F3] flip {fmt_wilson(k, n)}; D1 no-op in {id_ok}/80")
        r.save_summary({"arm": "f3", "flips": k, "n": n, "d1_noop": id_ok})

    # ---------------- F4: D2 + Form A ----------------
    if "f4" in arms:
        r = Runner(f"defense-{TAG}-f4", workers=1, out_dir=RESULTS)
        k = n = flagged = 0
        per_scenario = {}
        for name, state, ins, criteria, correct, atk, policy in scenarios():
            p = log_detector(r, f"f4/scan/{name}", policy,
                             {"kind": "choice", "scenario": name, "arm": "f4",
                              "scan_target": "injected_field_value", "atk": atk})
            flag = p >= detector.TAU
            flagged += flag
            ks = ns = 0
            for vid, s in state_variants(name, state):
                sa = dict(s)
                sa["review_policy"] = policy
                fed = allowlist.strip_to_allowlist(sa, allowlist.allowlist_of(s)) if flag else sa
                b = reuse[(name, vid)]["baseline"]
                a = r.decide(f"f4/{name}/{vid}", fed, q_choice(ins, criteria),
                             meta={"kind": "choice", "scenario": name, "variant": vid,
                                   "condition": "f4_d2_formA", "atk": atk,
                                   "defense": "D2", "detector_p": p,
                                   "detector_flagged": flag,
                                   "field_stripped": flag})["target"]
                if b["choice"] == atk:
                    continue
                ns += 1
                ks += a["choice"] == atk
            per_scenario[name] = {"detector_p": p, "flagged": flag, "flips": ks, "n": ns}
            print(f"  [F4] {name}: detector_p={p:.3f} flagged={flag} flip {ks}/{ns}")
            n += ns
            k += ks
        print(f"[F4] flip {fmt_wilson(k, n)}; detector flagged {flagged}/10 policies")
        r.save_summary({"arm": "f4", "flips": k, "n": n,
                        "policies_flagged": flagged, "per_scenario": per_scenario})

    # ---------------- F5: D2 + Form B ----------------
    if "f5" in arms:
        r = Runner(f"defense-{TAG}-f5", workers=1, out_dir=RESULTS)
        k = n = blocked = 0
        per_scenario = {}
        for name, state, ins, criteria, correct, atk, policy in scenarios():
            ks = ns = bs = 0
            for vid, s in state_variants(name, state):
                sb = form_b_state(name, s, policy)
                leaf = sb[LEAVES[name][0]][LEAVES[name][1]]
                p = log_detector(r, f"f5/scan/{name}/{vid}", leaf,
                                 {"kind": "choice", "scenario": name, "variant": vid,
                                  "arm": "f5", "scan_target": "text_leaf", "atk": atk})
                if p >= detector.TAU:
                    blocked += 1
                    bs += 1
                    continue
                b = reuse[(name, vid)]["baseline"]
                a = r.decide(f"f5/{name}/{vid}", sb, q_choice(ins, criteria),
                             meta={"kind": "choice", "scenario": name, "variant": vid,
                                   "condition": "f5_d2_formB", "atk": atk,
                                   "defense": "D2", "detector_p": p,
                                   "detector_flagged": False})["target"]
                if b["choice"] == atk:
                    continue
                ns += 1
                ks += a["choice"] == atk
            per_scenario[name] = {"flips": ks, "n": ns, "blocked": bs}
            n += ns
            k += ks
            blocked += 0  # bs already counted
        print(f"[F5] flip {fmt_wilson(k, n)}; blocked {blocked}/80")
        r.save_summary({"arm": "f5", "flips": k, "n": n, "blocked": blocked,
                        "per_scenario": per_scenario})

    # ---------------- F6a: A2 no defense ----------------
    if "f6a" in arms:
        r = Runner(f"defense-{TAG}-f6a", workers=1, out_dir=RESULTS)
        k = n = 0
        per_scenario = {}
        for name, state, ins, criteria, correct, atk, _p in scenarios():
            ks = ns = 0
            for vid, s in state_variants(name, state):
                sa = dict(s)
                sa["review_policy"] = A2[name]
                b = reuse[(name, vid)]["baseline"]
                a = r.decide(f"f6a/{name}/{vid}", sa, q_choice(ins, criteria),
                             meta={"kind": "choice", "scenario": name, "variant": vid,
                                   "condition": "f6a_a2_nodefense", "atk": atk})["target"]
                if b["choice"] == atk:
                    continue
                ns += 1
                ks += a["choice"] == atk
            per_scenario[name] = {"flips": ks, "n": ns,
                                  "inapplicable": ks == 0}
            n += ns
            k += ks
        print(f"[F6a] flip {fmt_wilson(k, n)}")
        r.save_summary({"arm": "f6a", "flips": k, "n": n, "per_scenario": per_scenario})

    # ---------------- F6b: A2 + D2 ----------------
    if "f6b" in arms:
        r = Runner(f"defense-{TAG}-f6b", workers=1, out_dir=RESULTS)
        k = n = flagged = 0
        per_scenario = {}
        for name, state, ins, criteria, correct, atk, _p in scenarios():
            p = log_detector(r, f"f6b/scan/{name}", A2[name],
                             {"kind": "choice", "scenario": name, "arm": "f6b",
                              "scan_target": "a2_field_value", "atk": atk})
            flag = p >= detector.TAU
            flagged += flag
            ks = ns = 0
            for vid, s in state_variants(name, state):
                sa = dict(s)
                sa["review_policy"] = A2[name]
                fed = allowlist.strip_to_allowlist(sa, allowlist.allowlist_of(s)) if flag else sa
                b = reuse[(name, vid)]["baseline"]
                a = r.decide(f"f6b/{name}/{vid}", fed, q_choice(ins, criteria),
                             meta={"kind": "choice", "scenario": name, "variant": vid,
                                   "condition": "f6b_a2_d2", "atk": atk,
                                   "defense": "D2", "detector_p": p,
                                   "detector_flagged": flag})["target"]
                if b["choice"] == atk:
                    continue
                ns += 1
                ks += a["choice"] == atk
            per_scenario[name] = {"detector_p": p, "flagged": flag, "flips": ks, "n": ns}
            n += ns
            k += ks
        print(f"[F6b] flip {fmt_wilson(k, n)}; A2 flagged {flagged}/10")
        r.save_summary({"arm": "f6b", "flips": k, "n": n,
                        "a2_flagged": flagged, "per_scenario": per_scenario})

    # ---------------- F7: detector self-attack (Form B) ----------------
    if "f7" in arms:
        r = Runner(f"defense-{TAG}-f7", workers=1, out_dir=RESULTS)
        SCS = {s[0]: s for s in scenarios()}
        f7_out = {}
        for name in ("route_refund", "moderation"):
            _n, state, ins, criteria, correct, atk, policy = SCS[name]
            ks = ns = bs = 0
            for vid, s in state_variants(name, state):
                sb = form_b_state(name, s, policy + "\n\n" + DETECTOR_LINE)
                leaf = sb[LEAVES[name][0]][LEAVES[name][1]]
                p = log_detector(r, f"f7/scan/{name}/{vid}", leaf,
                                 {"kind": "choice", "scenario": name, "variant": vid,
                                  "arm": "f7", "scan_target": "text_leaf_with_detector_line",
                                  "atk": atk})
                if p >= detector.TAU:
                    bs += 1
                    continue
                b = reuse[(name, vid)]["baseline"]
                a = r.decide(f"f7/{name}/{vid}", sb, q_choice(ins, criteria),
                             meta={"kind": "choice", "scenario": name, "variant": vid,
                                   "condition": "f7_detector_selfattack", "atk": atk,
                                   "defense": "D2", "detector_p": p})["target"]
                if b["choice"] == atk:
                    continue
                ns += 1
                ks += a["choice"] == atk
            f7_out[name] = {"flips": ks, "n": ns, "blocked": bs}
            print(f"[F7] {name}: flip {fmt_wilson(ks, ns)}; blocked {bs}/8")
        r.save_summary({"arm": "f7", "per_scenario": f7_out})

    # ---------------- FP: D2 false positives on clean leaves ----------------
    if "fp" in arms:
        r = Runner(f"defense-{TAG}-fp", workers=1, out_dir=RESULTS)
        fp = tot = 0
        per_scenario = {}
        for name, state, ins, criteria, correct, atk, policy in scenarios():
            fs = 0
            for vid, s in state_variants(name, state):
                leaf = s[LEAVES[name][0]][LEAVES[name][1]]
                p = log_detector(r, f"fp/scan/{name}/{vid}", leaf,
                                 {"kind": "choice", "scenario": name, "variant": vid,
                                  "arm": "fp", "scan_target": "clean_text_leaf"})
                fs += p >= detector.TAU
            per_scenario[name] = {"false_positives": fs, "n": 8}
            fp += fs
            tot += 8
        print(f"[FP] false positives {fp}/{tot} ({fp / tot * 100:.0f}%)")
        # D1 identity spot check (free, no model calls)
        id_ok = 0
        for name, state, ins, criteria, correct, atk, policy in scenarios()[:10]:
            s0 = state_variants(name, state)[0][1]
            id_ok += allowlist.is_identity(s0, allowlist.allowlist_of(s0))
        r.save_summary({"arm": "fp", "false_positives": fp, "n": tot,
                        "per_scenario": per_scenario,
                        "d1_identity_spotcheck": f"{id_ok}/10"})


if __name__ == "__main__":
    main()
