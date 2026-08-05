"""
plausibility.py
================
Phase 3: Pedagogical Quality (Plausibility Score).

The Plausibility Score is the percentage of a task's distractors that map
onto the Okuboyejo et al. (2025) error taxonomy:
    - Slight Error            : single-edit slip from a valid string
    - Logical: Additional     : distractor is valid under a *stricter*
                                 mutation of the target regex (over-restriction)
    - Logical: Omitted        : distractor is valid under a *looser*
                                 mutation of the target regex (under-restriction /
                                 missing restriction)
    - Logical: Incorrect      : distractor matches neither the target nor an
                                 obvious tightened/loosened variant, but is
                                 within edit-distance 2 of a valid string
                                 (a plausible "wrong restriction" rather than
                                 noise)
    - Syntax Error            : distractor contains one of the regex's own
                                 metacharacters taken literally (the student
                                 typed the operator as if it were input)

IMPORTANT: this is a heuristic, rule-based classifier, not a substitute for
the qualitative coding scheme in Okuboyejo et al. It's meant as (a) a fast
first-pass filter you run over all 250 LLM distractors (50 tasks x 5
distractors incl. the correct one -> 200 actual distractors) before human
or LLM-assisted review, and (b) the exact classifier already used by
mcq_search.py to *label* the symbolic baseline's own distractors, so both
systems are scored with one consistent instrument. For your write-up: report
inter-rater agreement if you also have a human/GPT-4o-as-judge pass, and
treat this module's output as a proposed label to be confirmed, not ground
truth.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from regex_engine import regex_to_dfa, minimize, dfa_accepts, RegexSyntaxError
from mcq_search import _mutated_pattern_variants, _mutate_one_char


TAXONOMY_CATEGORIES = (
    "slight_error",
    "logical_additional",
    "logical_omitted",
    "logical_incorrect",
    "syntax_error",
    "unclassified",  # doesn't cleanly map -- counts against the plausibility score
)


@dataclass
class DistractorLabel:
    string: str
    category: str
    detail: str = ""


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def classify_distractor(pattern: str, valid_string: str, distractor: str,
                         alphabet) -> DistractorLabel:
    """Rule order matters: syntax check first (cheapest, highest precision),
    then slight-edit, then the two logical-mutation checks, then a fuzzy
    'incorrect restriction' fallback before giving up as unclassified."""
    alphabet = tuple(alphabet)

    # 1. Syntax Error: distractor literally contains a metacharacter from
    #    the pattern text that isn't in the study's data alphabet
    meta_in_pattern = {c for c in pattern if c in "|*+?(){}[]^-"}
    if any(ch in meta_in_pattern for ch in distractor):
        return DistractorLabel(distractor, "syntax_error",
                                "contains a regex operator typed as literal input")

    # 2. Slight Error: within edit-distance 1 of the valid string
    if levenshtein(distractor, valid_string) == 1:
        return DistractorLabel(distractor, "slight_error",
                                "single-character edit from the correct string")

    # 3 & 4. Logical errors: check against tightened/loosened pattern variants
    try:
        for kind, mutated in _mutated_pattern_variants(pattern):
            if kind not in ("additional", "omitted"):
                continue
            try:
                mdfa = minimize(regex_to_dfa(mutated, frozenset(alphabet)))
            except RegexSyntaxError:
                continue
            if dfa_accepts(mdfa, distractor):
                label = "logical_additional" if kind == "additional" else "logical_omitted"
                return DistractorLabel(distractor, label,
                                        f"matches a {'stricter' if kind=='additional' else 'looser'} "
                                        f"misreading of the regex ({mutated!r})")
    except RegexSyntaxError:
        pass

    # 5. Logical: Incorrect Restriction (fuzzy fallback) -- close to a valid
    #    string (edit-distance <= 2) without being a clean slight-error or
    #    a clean tightened/loosened match; treated as "plausible but not
    #    precisely characterised" rather than noise
    if levenshtein(distractor, valid_string) <= 2:
        return DistractorLabel(distractor, "logical_incorrect",
                                "close to a valid string but matches neither the "
                                "target nor an obvious tightened/loosened variant")

    return DistractorLabel(distractor, "unclassified",
                            "does not map to a documented error pattern")


def plausibility_score(pattern: str, valid_string: str, distractors: list,
                        alphabet) -> dict:
    labels = [classify_distractor(pattern, valid_string, d, alphabet) for d in distractors]
    n = len(labels)
    n_mapped = sum(1 for l in labels if l.category != "unclassified")
    counts = {cat: sum(1 for l in labels if l.category == cat) for cat in TAXONOMY_CATEGORIES}
    return {
        "labels": labels,
        "plausibility_score": (n_mapped / n) if n else 0.0,
        "category_counts": counts,
    }


def aggregate_plausibility(per_task_scores: list) -> float:
    """Mean plausibility score across all tasks (macro-average per task,
    not micro-averaged over pooled distractors, so every task counts
    equally regardless of how many distractors it happened to produce)."""
    if not per_task_scores:
        return 0.0
    return sum(s["plausibility_score"] for s in per_task_scores) / len(per_task_scores)