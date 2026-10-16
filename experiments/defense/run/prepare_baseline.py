"""Create clean and Form A responses used by the defense matrix."""

import sys
from _common import RESULTS, q_choice, q_noul, state_variants
from redteam.runner import Runner


def prepare(kind):
    if kind == "choice":
        from expd3_policyfield_scale import CHOICE
        tables = [("expd3", CHOICE)]
    else:
        from noul import gate_tables
        tables = [(pool, [row]) for _, row, pool in gate_tables()]
    runner = Runner("baseline-" + kind, workers=1, out_dir=RESULTS)
    for pool, table in tables:
        for row in table:
            name, state, instructions = row[:3]
            if kind == "choice":
                questions = q_choice(instructions, row[3])
                policy, field = row[6], "review_policy"
            else:
                questions = q_noul(instructions)
                policy, field = row[5], "screening_policy"
            for variant, clean in state_variants(name, state):
                for condition, fed in (("baseline", clean),
                                       ("v1_policy_text", {**clean, field: policy})):
                    runner.decide(f"{name}/{variant}/{condition}", fed, questions,
                                  meta={"kind": kind, "pool": pool, "scenario": name,
                                        "variant": variant, "condition": condition})
    return runner.path


if __name__ == "__main__":
    print(prepare(sys.argv[1]))
