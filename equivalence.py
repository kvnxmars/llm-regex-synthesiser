"""
equivalence.py
===================
Phase 1 of the evaluation pipeline: Formal Correctness / Consistency Rate

Given a target regex (the "ground truth" specification from the CFG task) and
a candidate regex (an LLM's synthesized output, or a symbolic baseline
output), determine whether they define the same regular language.

So we will build a minimal DFA for each regex over a shared alphabet, then
check language equivalence via a product automation symmetric difference search
rather than DFA isomorphism, which is more fragile to get right and unnecessary
--- symmetric difference emptiness is the standard and simplest correct method for
language equivalence.

"""

from __future__ import annotations
from dataclasses import dataclass
from typing import FrozenSet, Optimal
from collections import deque

from regex_engine import (
    regex_to_dfa, minimize, DFA, RegexSyntaxError, infer_alphabet,
)

@dataclass
class EquivalenceResult:
    equivalent:bool
    reason: str
    counterexample: Optimal[str] = None  # a string accepted by exactly one side
    target_valid: bool = True
    candidate_valid: bool = True

def check_equivalence(target_pattern: str, candidate_pattern: str,
                       alphabet: Optional[FrozenSet[str]] = None,
                       max_counterexample_len: int = 8) -> EquivalenceResult:
    """Returns whether candidate_pattern defines the same language as
    target_pattern. If candidate_pattern fails to parse (a malformed LLM
    output), that itself is recorded as non-equivalent rather than raising,
    since 'the model produced an invalid regex' is a valid experimental
    outcome to log for the Consistency Rate metric."""

    if alphabet is None:
        try:
            alphabet = infer_alphabet(target_pattern) | infer_alphabet(candidate_pattern)
        except RegexSyntaxError as e:
            return EquivalenceResult(False, f"alphabet inference failed: {e}",
                                      candidate_valid=False)

    try:
        dfa_target = minimize(regex_to_dfa(target_pattern, alphabet))
    except RegexSyntaxError as e:
        return EquivalenceResult(False, f"target regex invalid: {e}", target_valid=False)

    try:
        dfa_candidate = minimize(regex_to_dfa(candidate_pattern, alphabet))
    except RegexSyntaxError as e:
        return EquivalenceResult(False, f"candidate regex failed to parse: {e}",
                                  candidate_valid=False)

    ce = _find_symmetric_difference_witness(dfa_target, dfa_candidate, alphabet,
                                             max_len=max_counterexample_len)
    if ce is None:
        return EquivalenceResult(True, "languages match (no distinguishing string found)")
    return EquivalenceResult(False, "languages differ", counterexample=ce)


def _find_symmetric_difference_witness(a: DFA, b: DFA, alphabet: FrozenSet[str],
                                        max_len: int) -> Optional[str]:
    """BFS over the product automaton for the shortest string accepted by
    exactly one of A, B. Bounded by max_len as a practical safeguard --
    with both DFAs minimized and finite, any non-equivalence is witnessed
    by a string no longer than (|A|*|B| - 1), so max_len should be set >=
    that product for a guaranteed-complete check; for the small regexes in
    this study a modest bound is enough in practice."""
    start = (a.start, b.start)
    seen = {start}
    queue = deque([(start, "")])
    bound = max(max_len, a.num_states * b.num_states)  # safe theoretical bound
    while queue:
        (sa, sb), prefix = queue.popleft()
        in_a = sa in a.accepts
        in_b = sb in b.accepts
        if in_a != in_b:
            return prefix
        if len(prefix) >= bound:
            continue
        for sym in alphabet:
            nxt = (a.transitions[sa][sym], b.transitions[sb][sym])
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, prefix + sym))
    return None


def consistency_rate(results: list) -> float:
    """results: list of EquivalenceResult. Returns the fraction judged
    formally correct (Phase 1 pass rate)."""
    if not results:
        return 0.0
    return sum(1 for r in results if r.equivalent) / len(results)