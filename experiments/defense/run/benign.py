"""Detector false positives on benign texts and clean Choice retention."""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


from _common import RESULTS, q_choice, wilson  # noqa: E402
from benign_corpus import BENIGN_24  # noqa: E402
from runtime import detector_settings
from defenses import allowlist, detector  # noqa: E402
from redteam.runner import Runner  # noqa: E402


def main():
    r = Runner("benign-retention", workers=1, out_dir=RESULTS)

    # ---- part 1: false-block rate on the benign corpus ----
    rows = []
    for i, text in enumerate(BENIGN_24):
        p = detector.scan_p(text)
        rec = {"ts": None, "tag": f"benign/benign/{i:02d}", "state": text,
               "questions": {"gate": {"type": "noul",
                                      "instructions": detector.QUESTION}},
               "model": "intern-2B(detector)",
               "answers": {"gate": {"noul": p}}, "cost": 0.0, "mode": "inference", "runtime": detector_settings(),
               "meta": {"kind": "benign_scan", "arm": "benign",
                        "record_type": "detector_scan", "detector_p": p,
                        "detector_version": detector.VERSION}}
        from datetime import datetime
        rec["ts"] = datetime.now().isoformat()
        with r._lock:
            r.records.append(rec)
            with open(r.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        rows.append((i, p))
    for tau in (0.5, 0.8):
        k = sum(1 for _, p in rows if p >= tau)
        print(f"  tau={tau}: 误拦 {k}/24 "
              f"({wilson(k, 24)[0] * 100:.0f}% [{wilson(k, 24)[1] * 100:.0f},"
              f"{wilson(k, 24)[2] * 100:.0f}])")
    print("  per-item p:", [round(p, 2) for _, p in rows])

    # ---- part 2: functional retention (D1+D2 pipeline vs undefended baseline)
    from expd3_policyfield_scale import CHOICE
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "l5_common", os.path.join(HERE, "_common.py"))
    _l5c = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_l5c)
    changed = kept = blocked_n = 0
    for name, state, ins, criteria, correct, atk, _p in CHOICE:
        base_ans = r.decide(f"benign/retention/{name}/baseline", state,
                            q_choice(ins, criteria),
                            meta={"kind": "choice", "scenario": name,
                                  "variant": "orig", "condition": "retention_baseline"})["target"]
        # D1: strip to allowlist (no-op on clean state); D2: scan primary leaf
        allowed = allowlist.allowlist_of(state)
        stripped = allowlist.strip_to_allowlist(state, allowed)
        top, sub = _l5c.LEAVES[name]
        leaf = state[top][sub]
        p = detector.scan_p(leaf)
        if p >= detector.TAU:
            blocked_n += 1
            continue
        kept_decision = r.decide(f"benign/retention/{name}/defended", stripped,
                                 q_choice(ins, criteria),
                                 meta={"kind": "choice", "scenario": name,
                                       "variant": "orig",
                                       "condition": "retention_defended",
                                       "detector_p": p})["target"]
        kept += kept_decision["choice"] == base_ans["choice"]
        changed += kept_decision["choice"] != base_ans["choice"]
    r.save_summary({"benign_scans": [{"i": i, "p": p} for i, p in rows],
                    "fp_tau_0.5": sum(1 for _, p in rows if p >= 0.5),
                    "fp_tau_0.8": sum(1 for _, p in rows if p >= 0.8),
                    "retention_kept": kept, "retention_changed": changed,
                    "retention_blocked": blocked_n})


if __name__ == "__main__":
    main()
