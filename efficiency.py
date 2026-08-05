"""
efficiency.py

Phase 2: Success-Filtered Efficiency.

Efficiency is measured only over the subset of outputs that already passed Phase 1 (
formal correctness). A fast but wrong output shouldn't be counted as "efficient" -- it's
simply excluded from this metric (while still counting against Consistency Rate in Phase 1)

This script provides:
    - `timed()` context manager / decorator for wrappig either the CFG baseline's generate+search step or a singke LLM call.
    - `EfficiencyLog`, a flat, appendable record structure so CFG-baseline rows and GPT-4o rows share one schema and can be 
    merged into a single comparison table/DataFrame for your results chapter.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager
from typing import Optional
import time
import csv


@dataclass
class EfficiencyRecord:
    system: str          # "cfg_baseline" | "gpt-4o"
    level: int
    task_id: str
    duration_s: float
    passed_phase1: bool
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    notes: str = ""


@contextmanager
def timed():
    """Usage:
        with timed() as t:
            ... work ...
        elapsed = t['duration_s']
    """
    box = {}
    t0 = time.perf_counter()
    try:
        yield box
    finally:
        box["duration_s"] = time.perf_counter() - t0


class EfficiencyLog:
    def __init__(self):
        self.records: list[EfficiencyRecord] = []

    def add(self, record: EfficiencyRecord):
        self.records.append(record)

    def success_filtered(self, system: Optional[str] = None):
        rows = [r for r in self.records if r.passed_phase1]
        if system:
            rows = [r for r in rows if r.system == system]
        return rows

    def mean_duration(self, system: str) -> Optional[float]:
        rows = self.success_filtered(system)
        if not rows:
            return None
        return sum(r.duration_s for r in rows) / len(rows)

    def mean_tokens(self, system: str) -> Optional[dict]:
        rows = [r for r in self.success_filtered(system) if r.prompt_tokens is not None]
        if not rows:
            return None
        return {
            "prompt_tokens": sum(r.prompt_tokens for r in rows) / len(rows),
            "completion_tokens": sum(r.completion_tokens for r in rows) / len(rows),
        }

    def summary(self) -> dict:
        systems = sorted({r.system for r in self.records})
        out = {}
        for sys_name in systems:
            total = [r for r in self.records if r.system == sys_name]
            passed = self.success_filtered(sys_name)
            out[sys_name] = {
                "n_total": len(total),
                "n_passed_phase1": len(passed),
                "consistency_rate": (len(passed) / len(total)) if total else 0.0,
                "mean_duration_s_success_filtered": self.mean_duration(sys_name),
                "mean_tokens_success_filtered": self.mean_tokens(sys_name),
            }
        return out

    def to_csv(self, path: str):
        if not self.records:
            return
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(asdict(self.records[0]).keys()))
            writer.writeheader()
            for r in self.records:
                writer.writerow(asdict(r))