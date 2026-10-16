"""Experiment runner: parallel execution + JSONL logging + metrics.

用法:
    runner = Runner("exp1")
    ans = runner.decide(tag, state, questions, meta={...})   # 单次调用并记录
    runner.map(jobs)                                          # 并行执行一批
    runner.save_summary(summary)                              # 落盘汇总
"""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from client import ask, answers_of, cost_of
from runtime import capture


class Runner:
    def __init__(self, experiment, workers=6, out_dir=None):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base = out_dir or os.path.join(root, "results")
        os.makedirs(base, exist_ok=True)
        self.path = os.path.join(
            base, f"{experiment}-{datetime.now():%Y%m%d-%H%M%S-%f}.jsonl")
        self.records = []
        self.total_cost = 0.0
        self.workers = workers
        self._lock = threading.Lock()

    def decide(self, tag, state, questions, meta=None):
        """单次决策请求; 记录完整请求/响应到 JSONL。返回 answers dict。"""
        resp = ask(state, questions)
        ans = answers_of(resp)
        c = cost_of(resp) or 0.0
        rec = {
            "ts": datetime.now().isoformat(),
            "tag": tag,
            "state": state,
            "questions": questions,
            "model": resp.get("model"),
            "answers": ans,
            "cost": c,
            "mode": resp.get("mode", "synthetic" if resp.get("synthetic") else "inference"),
            "runtime": capture(os.environ.get("DECISION_CLIENT", "jev"), resp),
            "meta": meta or {},
        }
        with self._lock:
            self.records.append(rec)
            self.total_cost += c
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return ans

    def map(self, jobs):
        """并行执行一批任务。jobs: list of callables, 每个返回任意值。"""
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            return list(pool.map(lambda fn: fn(), jobs))

    def save_summary(self, summary):
        out = self.path.replace(".jsonl", ".summary.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\nsummary -> {out}")
        print(f"records -> {self.path}  ({len(self.records)} calls, ${self.total_cost:.6f})")


# ------------------------------------------------------------- 指标

def top_gap(probs):
    """top1 与 top2 的概率差, 用于 contested 判定。"""
    vals = sorted(probs.values(), reverse=True)
    return (vals[0] - vals[1]) if len(vals) >= 2 else 1.0


def tv_distance(p, q):
    """两个离散分布的 total variation 距离 (按键对齐)。"""
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)
