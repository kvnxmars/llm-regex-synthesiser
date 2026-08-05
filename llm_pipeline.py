"""
llm_pipeline.py

Design choices that matter for your methodology section:
- The prompt pins the alphabet and operator set explicitly, to mitigate
  "intent drift" (the model inventing regex features outside your five
  complexity levels, e.g. lookaheads, backreferences, \\d shorthand).
- The model is asked to return strict JSON (regex + 4 distractors + a
  short rationale per distractor), which you parse and hand straight to
  equivalence.py (Phase 1) and plausibility.py (Phase 3).
- Token usage and wall-clock latency are captured on every call for
  Phase 2 (efficiency.py consumes LLMResult.duration_s / token counts).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import json
import time
import re as _re  # only used to strip markdown code fences from responses


SYSTEM_PROMPT = """You are generating regular-expression practice questions for a South African \
Computer Science course. You must stay strictly within the following constraints:

- Alphabet: only the symbols provided in the task (no other characters, no \\d \\w \\s shorthands).
- Operators: only literal concatenation, character classes [ ], alternation |, \
grouping ( ), and the quantifiers * + ? {m,n}. Do not use lookaheads, backreferences, \
anchors (^ $ used as anchors, as opposed to negation inside a class), or any PCRE-only feature.
- Respond with STRICT JSON ONLY, no markdown fences, no commentary, matching exactly:
  {
    "regex": "<the target regex, must match the given complexity level>",
    "correct_string": "<one string that matches the regex>",
    "distractors": [
      {"string": "<string that does NOT match>", "error_type": "slight_error|logical_additional|logical_omitted|syntax_error", "rationale": "<1 sentence>"},
      ... exactly 4 distractor objects ...
    ]
  }
"""

USER_PROMPT_TEMPLATE = """Complexity level: {level} ({level_name})
Alphabet: {alphabet}
Generate one task at this complexity level following the constraints above.
The 4 distractors should mirror authentic student misconceptions (South African \
undergraduate CS pedagogy): one single-edit slip, one over-restrictive logical \
error, one under-restrictive (over-permissive) logical error, and one structural/\
syntax confusion. Return JSON only.
"""


@dataclass
class LLMResult:
    level: int
    level_name: str
    raw_response: str
    parsed: Optional[dict]
    duration_s: float
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    parse_error: Optional[str] = None


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = _re.sub(r"^```(json)?", "", text).strip()
    text = _re.sub(r"```$", "", text).strip()
    return text


def synthesize_mcq(level: int, level_name: str, alphabet: tuple,
                    model: str = "gpt-4o", client=None) -> LLMResult:
    """Calls the OpenAI API once. Pass an already-constructed `client`
    (openai.OpenAI()) so callers can reuse a single connection/session
    across all 50 tasks instead of reconnecting per call."""
    if client is None:
        from openai import OpenAI  # deferred import: only needed when actually calling out
        client = OpenAI()

    user_prompt = USER_PROMPT_TEMPLATE.format(
        level=level, level_name=level_name, alphabet=", ".join(alphabet)
    )

    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    duration = time.perf_counter() - t0

    raw = response.choices[0].message.content
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None

    parsed, err = None, None
    try:
        parsed = json.loads(_strip_fences(raw))
        if "distractors" not in parsed or len(parsed["distractors"]) != 4:
            err = "malformed JSON: expected exactly 4 distractors"
            parsed = None
    except json.JSONDecodeError as e:
        err = f"JSON parse error: {e}"

    return LLMResult(level=level, level_name=level_name, raw_response=raw,
                      parsed=parsed, duration_s=duration,
                      prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                      parse_error=err)


def synthesize_batch(levels_and_counts: dict, alphabet: tuple, model: str = "gpt-4o"):
    """levels_and_counts: e.g. {1: 10, 2: 10, 3: 10, 4: 10, 5: 10}."""
    from openai import OpenAI
    from cfg_generator import LEVEL_NAMES
    client = OpenAI()
    results = []
    for level, count in levels_and_counts.items():
        for _ in range(count):
            results.append(synthesize_mcq(level, LEVEL_NAMES[level], alphabet,
                                           model=model, client=client))
    return results