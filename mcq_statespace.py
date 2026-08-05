"""
mcq_search.py
=============
State-space search that, given a regex, produces one valid string and four
"plausible" invalid strings -- the Algorithm-5 analogue from Ade-Ibijola
(2018). This is the O(n^3)-flavoured bottleneck of the symbolic baseline:
it walks the DFA's state space (build/minimize is roughly O(n^2)-O(n^3) in
the number of NFA states depending on alphabet size, and generating +
mutating candidate strings adds a further polynomial factor), which is
exactly why it's timed separately in efficiency.py as the baseline cost to
compare against GPT-4o's wall-clock/token cost.

Distractor strategy (feeds directly into Phase 3 plausibility labelling):
  1. Slight Error      - single-character edit (substitution/insertion/
                          deletion) applied to a valid string, landing
                          just outside the language.
  2. Logical: Additional Restriction   - string valid under a *stricter*
                          mutation of the regex (e.g. '*' -> '+') but not
                          the original.
  3. Logical: Omitted Restriction      - string valid under a *looser*
                          mutation (e.g. dropping a quantifier / branch)
                          but not the original.
  4. Syntax Error       - a string built by literally including regex
                          metacharacters from the pattern text itself
                          (a classic novice error: typing the regex's
                          punctuation as if it were literal input).

Each distractor is verified against the *original* DFA to guarantee it is
genuinely invalid (never accidentally also a valid match).
"""

from __future__ import annotations
from dataclasses import dataclass, field
import random

from regex_engine import (
    regex_to_dfa, minimize, dfa_accepts, enumerate_strings, parse_regex,
    infer_alphabet, RegexSyntaxError,
)


@dataclass
class MCQSet:
    pattern: str
    valid: str
    invalid: list = field(default_factory=list)   # 4 strings, each labelled
    labels: list = field(default_factory=list)     # parallel list of taxonomy labels


def _mutate_one_char(s: str, alphabet: tuple, rng: random.Random) -> str:
    """A single-edit (Levenshtein distance 1) mutation: substitution,
    insertion, or deletion, chosen uniformly."""
    if not s:
        return rng.choice(alphabet)
    op = rng.choice(["sub", "ins", "del"] if len(s) > 1 else ["sub", "ins"])
    i = rng.randrange(len(s))
    if op == "sub":
        repl = rng.choice([c for c in alphabet if c != s[i]] or list(alphabet))
        return s[:i] + repl + s[i + 1:]
    if op == "ins":
        return s[:i] + rng.choice(alphabet) + s[i:]
    return s[:i] + s[i + 1:]  # del


def _mutated_pattern_variants(pattern: str) -> list:
    """Cheap textual mutations of the regex used to derive 'logical error'
    distractors (additional/omitted restriction). These aren't a full
    grammar-aware transform -- they're deliberately simple, mirroring the
    kind of small misreadings a student makes (e.g. '*' <-> '+', dropping
    an alternation branch, narrowing a character class)."""
    variants = []
    if "*" in pattern:
        variants.append(("additional", pattern.replace("*", "+", 1)))
    if "+" in pattern:
        variants.append(("omitted", pattern.replace("+", "*", 1)))
    if "|" in pattern:
        # drop the first alternative -> stricter (additional restriction)
        idx = pattern.index("|")
        # find matching branch bounds crudely (fine for the flat/shallow
        # patterns produced by cfg_generator; for deeply nested patterns,
        # fall back to no-op and let the caller retry another strategy)
        left_start = 0
        for j in range(idx - 1, -1, -1):
            if pattern[j] in "(|":
                left_start = j + 1
                break
        stricter = pattern[:left_start] + pattern[idx + 1:]
        variants.append(("additional", stricter))
    if pattern.startswith("[") and "]" in pattern:
        end = pattern.index("]")
        body = pattern[1:end]
        if len(body) > 1:
            looser = pattern  # widening a class needs the alphabet; handled by caller
            variants.append(("omitted_placeholder", looser))
    return variants


def build_mcq(pattern: str, alphabet=None, rng: random.Random = None,
              max_search_len: int = 6) -> MCQSet:
    rng = rng or random.Random()
    if alphabet is None:
        alphabet = tuple(sorted(infer_alphabet(pattern)))
    dfa = minimize(regex_to_dfa(pattern, frozenset(alphabet)))

    valid_candidates = enumerate_strings(dfa, max_len=max_search_len, limit=20,
                                          accepting_only=True)
    if not valid_candidates:
        raise ValueError(f"No accepting string found for {pattern!r} within length {max_search_len}")
    valid = rng.choice(valid_candidates)

    invalid = []
    labels = []

    # 1. Slight Error: single-edit mutation of a valid string that the DFA rejects
    for _ in range(30):
        cand = _mutate_one_char(valid, alphabet, rng)
        if cand != valid and not dfa_accepts(dfa, cand):
            invalid.append(cand)
            labels.append("slight_error")
            break

    # 2 & 3. Logical errors via mutated-pattern DFAs
    for kind, mutated_pattern in _mutated_pattern_variants(pattern):
        if len(invalid) >= 3:
            break
        try:
            mdfa = minimize(regex_to_dfa(mutated_pattern, frozenset(alphabet)))
        except RegexSyntaxError:
            continue
        candidates = enumerate_strings(mdfa, max_len=max_search_len, limit=20,
                                        accepting_only=True)
        for c in candidates:
            if not dfa_accepts(dfa, c) and c not in invalid:
                invalid.append(c)
                labels.append(f"logical_{kind}" if kind in ("additional", "omitted")
                               else "logical_error")
                break

    # 4. Syntax Error: literally include the regex's own metacharacters as
    #    if they were input symbols (classic "typed the operator" mistake)
    meta_present = [c for c in pattern if c in "|*+?(){}[]^-"]
    if meta_present:
        syntax_str = valid[:1] + rng.choice(meta_present) + valid[1:2]
        if not dfa_accepts(dfa, syntax_str):
            invalid.append(syntax_str)
            labels.append("syntax_error")

    # Fallback: fill any remaining slots with random rejected strings so we
    # always return exactly 4 distractors, even for very small/simple regexes
    attempts = 0
    while len(invalid) < 4 and attempts < 200:
        attempts += 1
        length = rng.randint(1, max_search_len)
        cand = "".join(rng.choice(alphabet) for _ in range(length))
        if not dfa_accepts(dfa, cand) and cand not in invalid and cand != valid:
            invalid.append(cand)
            labels.append("random_reject")

    return MCQSet(pattern=pattern, valid=valid, invalid=invalid[:4], labels=labels[:4])