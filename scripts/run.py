"""Public experiment entry point. Each matrix runs in its own process."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(path, args=(), env=None):
    subprocess.run([sys.executable, str(ROOT / path), *args], cwd=ROOT,
                   env=env or os.environ.copy(), check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("smoke", help="synthetic backend; no weights or API key")
    subs.add_parser("replay", help="saved response and gate replay; no inference")
    subs.add_parser("bypass-replay", help="saved detector escape and downstream secret-gate response")
    matrix = subs.add_parser("matrix")
    matrix.add_argument("phases", nargs="+", choices=["p1", "p2", "extnew", "ablation",
                                                    "position", "thai", "contested"])
    subs.add_parser("candidates", help="fresh baseline and twelve-candidate family")
    defense = subs.add_parser("defense")
    defense.add_argument("--kind", choices=["choice", "noul"], default="choice")
    defense.add_argument("arms", nargs="+", choices=["f1", "f2", "f3", "f4", "f5",
                                                    "f6a", "f6b", "f7", "fp"])
    holdout = subs.add_parser("holdout")
    holdout.add_argument("--batch", choices=["all", "v2.1", "v2.2", "v2.3"], default="all")
    holdout.add_argument("--tier", choices=["all", "T1", "T2", "T3", "T3/out", "out"], default="all")
    holdout.add_argument("--variants", choices=["original", "all"], default="original")
    review = subs.add_parser("review-chain", help="fresh Jev review calls")
    review.add_argument("--profile", choices=["smoke", "confirmation"], default="smoke")
    review.add_argument("--defended", action="store_true")
    review.add_argument("--ssh", action="store_true")
    replay = subs.add_parser("review-replay", help="full saved stages and paired D2 gate replay")
    replay.add_argument("--local-detector", action="store_true")
    replay.add_argument("--upstream", action="store_true")
    subs.add_parser("regressions", help="17 pure-code candidate-fix cases")
    subs.add_parser("matched", help="payload-type and provenance controls")
    subs.add_parser("thresholds", help="2x2 detector ablation and threshold counts")
    subs.add_parser("benign", help="detector false positives and clean decision retention")
    source_aware = subs.add_parser("source-aware", help="24 attacks and 24 benign inputs for detector v2")
    source_aware.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    if args.command == "smoke":
        env["DECISION_CLIENT"] = "demo"
        execute("toolkit/experiments/demo_quickstart.py", env=env)
    elif args.command == "replay":
        execute("experiments/replay.py")
    elif args.command == "bypass-replay":
        execute("experiments/bypass_replay.py")
    elif args.command == "regressions":
        execute("experiments/regressions/run.py")
    elif args.command == "source-aware":
        execute("experiments/defense/run/source_aware.py", ["--replay"] if args.replay else [])
    elif args.command == "review-replay":
        extra = (["--local-detector"] if args.local_detector else []) + (["--upstream"] if args.upstream else [])
        execute("experiments/review_chain/replay.py", extra)
    else:
        if args.command == "review-chain":
            execute("experiments/review_chain/run.py", ["--profile", args.profile] + (["--defended"] if args.defended else []) + (["--ssh"] if args.ssh else []), env=env)
            return
        if not env.get("DECISION_CLIENT"):
            parser.error("Set DECISION_CLIENT to a backend before running model experiments")
        env.setdefault("RUN_TAG", env["DECISION_CLIENT"])
        if args.command == "matched":
            execute("experiments/matched/run.py", env=env)
        elif args.command == "thresholds":
            execute("experiments/defense/run/thresholds.py", env=env)
        elif args.command == "matrix":
            execute("experiments/matrix/run/evaluate.py", args.phases, env)
        elif args.command == "candidates":
            execute("experiments/candidate_family/run/evaluate.py", env=env)
        elif args.command == "defense":
            if args.kind == "noul" and set(args.arms) - {"f4", "f7"}:
                parser.error("Noul supports f4 and f7")
            preparation = subprocess.run(
                [sys.executable, str(ROOT / "experiments/defense/run/prepare_baseline.py"), args.kind],
                cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, check=True)
            baseline = preparation.stdout.strip().splitlines()[-1]
            print(f"Fresh defense baseline: {baseline}", flush=True)
            env.update(BASELINE_FILE=baseline, BASELINE_E3=baseline, BASELINE_E4=baseline)
            execute(f"experiments/defense/run/{args.kind}.py", args.arms, env)
        elif args.command == "holdout":
            execute("experiments/holdout.py", ["--batch", args.batch, "--tier", args.tier, "--variants", args.variants], env)
        elif args.command == "benign":
            execute("experiments/defense/run/benign.py", env=env)


if __name__ == "__main__":
    main()
