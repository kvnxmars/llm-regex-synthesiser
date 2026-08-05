# Regex Synthesis & Evaluation Pipeline

Implementation scaffold for the Honours project comparing an LLM
(GPT-4o)-synthesized regex-MCQ pipeline against the Ade-Ibijola (2018)
symbolic CFG baseline, evaluated across three phases: formal correctness,
success-filtered efficiency, and pedagogical plausibility
(Okuboyejo et al., 2025 taxonomy).

## Files

| File | Role |
|---|---|
| `regex_engine.py` | Regex parser -> Thompson NFA -> subset construction -> minimal DFA. No dependencies. This is the foundation everything else sits on. |
| `equivalence.py` | Phase 1 (Consistency Rate): DFA language-equivalence via product-automaton symmetric difference. |
| `cfg_generator.py` | Part 1: CFG regex generator for the 5 complexity levels (Literal, Character Classes, Quantifiers, Alternation, Nested). |
| `mcq_search.py` | The Algorithm-5 analogue: state-space search for 1 valid + 4 invalid strings per regex, with distractors deliberately constructed to hit slight-error / logical / syntax-error categories. |
| `llm_pipeline.py` | Part 2: GPT-4o prompting scaffold (JSON-structured output, token/latency capture). **Needs your own machine + API key** -- this sandbox can't reach api.openai.com. |
| `efficiency.py` | Phase 2: timing/logging, shared schema for both systems, success-filtered aggregation. |
| `plausibility.py` | Phase 3: rule-based classifier mapping distractors onto the Okuboyejo taxonomy; produces the Plausibility Score. |
| `pipeline.py` | Orchestrator: runs the full 50-task experiment for one or both systems and writes combined results. |

## Quick start (fully offline, CFG baseline only)

```bash
python3 pipeline.py
```

This generates 50 tasks (10 per complexity level), searches for MCQ
answer sets, times every step, scores plausibility, and writes:
- `cfg_baseline_results.json` -- one row per task, all three phases
- `cfg_baseline_efficiency.csv` -- flat timing log

## Running the LLM side (on your own machine)

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...
python3 -c "
from pipeline import run_llm_pipeline, save_results
rows, log = run_llm_pipeline()
save_results(rows, 'gpt4o_results.json')
log.to_csv('gpt4o_efficiency.csv')
"
```

## Important methodological note on Phase 1 for the LLM arm

As scaffolded, `synthesize_mcq` lets GPT-4o pick its own regex per
complexity level (matching the brief's "generate 50 regex tasks" framing).
That means Phase 1 currently checks internal consistency (does the model's
`correct_string` actually match its own `regex`?) rather than agreement
with a fixed target specification. If your protocol instead wants GPT-4o
to synthesize distractors *for a target regex you supply* (arguably closer
to "$\forall uto\exists val$-style" DFA equivalence checking against a
ground truth), generate your 50 target patterns with `cfg_generator.py`
first, then feed each target's pattern into a modified prompt and check
`check_equivalence(target_pattern, llm_pattern)` -- the equivalence
checker already supports this; only the prompt template needs a
`target_regex` field added. This is a one-line prompt change and worth
deciding explicitly for your methodology chapter, since it changes what
"Consistency Rate" is actually measuring.

## Design notes for your write-up

- **Why a hand-rolled regex-DFA engine instead of `automata-lib`/`greenery`**:
  full control over the exact operator subset (matches the five
  complexity levels), no dependency risk, and every step (Thompson
  construction, subset construction, Moore minimization, product-automaton
  equivalence) is inspectable/citable in a
  methodology appendix.
- **Equivalence via symmetric difference, not isomorphism**: isomorphism
  checking is more fragile to implement correctly and isn't actually
  what "same language" requires; symmetric-difference emptiness over the
  product automaton is the standard proof technique and is what's
  implemented here, with a returned counterexample string on failure
  (useful for qualitative error analysis of *why* an LLM regex was wrong).
- **`plausibility.py` is a heuristic first pass**, not a ground-truth
  coder. Recommended protocol: run it over all distractors, then have a
  human (or a second LLM-as-judge pass, clearly labelled as such in your
  methodology) validate/adjust a sample, and report agreement.
- **Time complexity**: `mcq_search.py`'s search is the O(n^3)-flavoured
  cost cited in Ade-Ibijola (2018) as the symbolic baseline's bottleneck --
  it's timed independently of CFG *generation* (which is linear) so your
  efficiency comparison against GPT-4o isolates the right cost.