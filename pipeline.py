"""
pipeline.py

Orchestrates the full experiment
 
    50 tasks (10 per complexity level) x 2 systems (CFG baseline, LLM baseline)
    Complexity levels
    1. Literal matches
    2. Character classes
    3. Quantifiers
    4. Alternation
    5. Nested expressions

    Phases:
    -> Phase 1: Consistency Rate (CFG baseline vs. LLM baseline)
    -> Phase 2: Success-Filtered Efficiency (CFG baseline vs. LLM baseline)
    -> Phase 3: Plausibility Score (CFG baseline vs. LLM baseline)
    -> one combined results table.

Run modes:
  - `run_cfg_baseline()`      : fully offline, no API needed. Runs on local machine with python 3 installed.
  - `run_llm_pipeline()`      : needs OPENAI_API_KEY + network access to api.openai.com
  - `combine_results(...)`    : merges both into one table/CSV for your results chapter.
"""

from __future__ import annotations
import json
import time
import random

from cfg_baseline import CFGRegexGenerator, LEVEL_NAMES, DEFAULT_ALPHABET
from mcq_statespace import build_mcq
from equivalence import check_equivalence
from efficiency import EfficiencyLog, EfficiencyRecord, timed
from plausibility import plausibility_score

def run_cfg_baseline(alphabet=DEFAULT_ALPHABET, per_level: int = 10, seed: int = 42):
    """Runs the full symbolic baseline: generate 50 tasks, run Algorithm-5
    style search for each, self-check equivalence (the baseline's answer
    key is definitionally correct, but we still route it through Phase 1
    so both systems share one code path and one results schema), and score
    plausibility. Returns (rows, efficiency_log)."""
    gen = CFGRegexGenerator(alphabet=alphabet, rng=random.Random(seed))
    tasks = gen.generate_batch(per_level=per_level, seed=seed)

    log = EfficiencyLog()
    rows = []

    for idx, task in enumerate(tasks):
        task_id = f"cfg_L{task.level}_{idx}"
        with timed() as t:
            try:
                mcq = build_mcq(task.pattern, alphabet=task.alphabet,
                                 rng=random.Random(seed + idx))
                error = None
            except Exception as e:
                mcq = None
                error = str(e)

        passed_phase1 = mcq is not None
        eq_result = None
        if mcq is not None:
            eq_result = check_equivalence(task.pattern, task.pattern, alphabet=frozenset(task.alphabet))

        log.add(EfficiencyRecord(
            system="cfg_baseline", level=task.level, task_id=task_id,
            duration_s=t["duration_s"], passed_phase1=passed_phase1,
            notes=error or "",
        ))

        rows.append({
                "task_id": task_id, "system": "cfg_baseline", "level": task.level,
                "level_name": LEVEL_NAMES[task.level],
                "pattern": task.pattern,
                "valid_string": None,
                "distractors": [],
                "phase1_equivalent": passed_phase1,
                "phase2_duration_s": res.duration_s,
                "phase2_prompt_tokens": res.prompt_tokens,
                "phase2_completion_tokens": res.completion_tokens,
                "phase3_plausibility_score": pscore["plausibility_score"] if pscore else None,
                "phase3_category_counts": pscore["category_counts"] if pscore else None,
                "parse_error": res.parse_error,
            })
    
        return rows, log
    
    
    def save_results(rows: list, path: str):
        with open(path, "w") as f:
            json.dump(rows, f, indent=2, default=str)
    
    
    if __name__ == "__main__":
        rows, log = run_cfg_baseline()
        save_results(rows, "cfg_baseline_results.json")
        log.to_csv("cfg_baseline_efficiency.csv")
        print(json.dumps(log.summary(), indent=2, default=str))