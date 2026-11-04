# LLM Regex Synthesiser

A notebook-based pipeline for generating alternative regular expressions and multiple-choice answer options, then evaluating their formal correctness and distractor characteristics.

## 1. Project overview

This project investigates whether a large language model (LLM) can generate useful regular-expression assessment items while preserving the language defined by a supplied reference expression.

The pipeline has three main stages:

1. **Benchmark preparation** – extract regular-expression questions and their alphabets from the source benchmark.
2. **LLM-based generation** – ask the model to produce an equivalent regular expression, five answer options, and short rationales.
3. **Symbolic evaluation** – use finite automata to test language equivalence and to classify generated answer options.

> **Important scope note:** The model is given the target regular expression and its alphabet. This experiment therefore evaluates the generation of equivalent expressions and answer options under a fixed question format. It is not a test of generating regular expressions from an independent natural-language description alone.

## 2. Main project file

The main implementation is the Jupyter notebook:

```text
LLM_Regex_Synthesiser.ipynb
```

Run the notebook in an environment that supports Python and Jupyter. Execute its cells in order unless a cell explicitly documents that it can be run independently.

## 3. Requirements and setup

### 3.1 Software

You need:

- Python
- Jupyter Notebook or JupyterLab
- The Python packages imported by the notebook
- Network access to the configured Groq-compatible API endpoint
- A valid API key for that endpoint

The notebook uses an OpenAI-compatible client configured with a Groq API base URL. The executed model identifier recorded by the experiment is:

```text
openai/gpt-oss-120b
```

The executed temperature is:

```text
0.1
```

The notebook contains the authoritative imports, client configuration, API-key variable, and file paths. Check those cells before running the experiment. Supply your API key through the configuration expected by the notebook; do not commit or publish the key.

### 3.2 Open the notebook

From the project directory, start Jupyter:

```bash
jupyter notebook
```

Open `LLM_Regex_Synthesiser.ipynb` in the browser.

If you use JupyterLab instead:

```bash
jupyter lab
```

## 4. Step-by-step pipeline

### Step 1 — Prepare the benchmark

The experiment uses the regular-expression assessment benchmark from Ade-Ibijola (2020).

- The source contains different question formats.
- This experiment uses the **Figure 7 single-choice format**.
- The Figure 8 multi-answer format is outside the scope of this run.
- The extraction stage obtained 500 Figure 7 items.

The extracted task information includes the target regular expression and the alphabet used to interpret it.

Some input normalisation is performed, including conversion of the Unicode asterisk-like star symbol (`∗`) to the ordinary regex `*` symbol and standardisation/removal of epsilon or lambda notation where applicable.

**Output of this stage:** the extracted task records used to construct generation prompts.

### Step 2 — Construct the LLM prompt

For each task, the notebook builds a prompt containing the target expression and its restricted alphabet, together with a description derived from the target expression.

The model is asked to return:

1. A regular expression intended to be equivalent to the target.
2. Five candidate answer strings, labelled A–E.
3. One option marked as the labelled correct answer.
4. Short rationales for the generated expression and options.

The prompt restricts the expression language to the core operators supported by the verifier:

- Concatenation
- Alternation (`|`)
- Kleene star (`*`)
- Kleene plus (`+`)
- Optionality (`?`)
- Parentheses

Features such as lookarounds, backreferences, anchors, and other PCRE-specific extensions are not part of the supported expression language.

**Output of this stage:** a structured model response containing the generated expression, options, and rationales.

### Step 3 — Call the model and save the response

The notebook sends the prompt to the configured OpenAI-compatible API endpoint.

The generation configuration recorded in the executed experiment is:

| Setting | Value |
|---|---|
| Model endpoint | `openai/gpt-oss-120b` |
| API interface | OpenAI-compatible client using a Groq-compatible base URL |
| Temperature | `0.1` |
| Response format | JSON |

The generation code includes retry handling for failed requests and resumes from records already saved. It stores information such as the task identifier, model identifier, generated expression, options, rationales, and available token/latency metadata.

Not every extracted task necessarily has a saved generation. The evaluation dataset used in the reported run contains **415 generated records from 500 extracted tasks**.

**Output of this stage:** the saved generation records used by the evaluation stages.

### Step 4 — Parse each regular expression

The formal verification stage processes both:

- The original target regular expression.
- The LLM-generated regular expression.

The parser handles the supported operators and inserts explicit concatenation operators where needed. It then converts the expression into postfix notation.

Postfix notation makes it possible to construct an automaton using a stack-based procedure.

**Output of this stage:** postfix representations of the target and generated expressions.

### Step 5 — Build epsilon-NFAs with Thompson construction

Each postfix expression is converted into an epsilon-NFA using Thompson-style construction.

At a high level:

- A literal symbol creates a transition.
- Concatenation joins the relevant automaton fragments.
- Alternation creates branching paths.
- Kleene star allows zero or more repetitions.
- Kleene plus allows one or more repetitions.
- Optionality allows the expression to occur zero or one time.
- Epsilon transitions connect fragments without consuming an input symbol.

This produces an epsilon-NFA for the target expression and another for the generated expression.

**Output of this stage:** two epsilon-NFAs.

### Step 6 — Convert the NFAs into DFAs

The notebook applies subset construction to determinise each epsilon-NFA.

The resulting deterministic finite automata (DFAs) operate over the task's restricted alphabet.

When a transition is missing, the equivalence-checking procedure treats it as a transition to an implicit rejecting sink state. This ensures that both automata can be compared consistently.

**Output of this stage:** deterministic automata for the target and generated expressions.

### Step 7 — Check language equivalence

The notebook compares the languages of the target and generated expressions using a product-automaton search.

The key question is whether there is any string accepted by exactly one of the two automata. Such a string belongs to their symmetric difference.

If the product-automaton search finds no reachable state that distinguishes acceptance between the two automata, the expressions are language-equivalent over the task alphabet.

In mathematical terms, the desired condition is:

```text
L(target) △ L(generated) = ∅
```

where `△` denotes symmetric difference.

- **Equivalent:** no distinguishing string is found.
- **Not equivalent:** a distinguishing string exists.

> **Implementation clarification:** The executed notebook uses parsing/postfix conversion, Thompson construction, subset construction, and product-automaton equivalence checking. Do not describe this implementation as performing Hopcroft DFA minimisation unless that functionality is added and run separately.

**Output of this stage:** a formal equivalence result for each evaluated task.

### Step 8 — Test the answer options

The generated answer options are evaluated against the **target/reference language**.

Each option is run through the target DFA:

- If the DFA accepts the option, the option belongs to the target language.
- If the DFA rejects the option, it does not belong to the target language.

This stage checks whether the option labelled correct is accepted and whether any intended distractor is accidentally accepted.

An accepted distractor is a **distractor leak**: the item may have more than one correct answer.

The notebook's audit also records whether the generated expression is equivalent to the target and whether the answer-option checks satisfy its implemented consistency conditions.

**Output of this stage:** option-level acceptance results and item-level audit fields.

### Step 9 — Classify distractors

The pedagogical audit classifies intended distractors using heuristic categories adapted from the student-error taxonomy used in the research.

The categories are:

1. **Machine Noise** – an option contains a symbol outside the task alphabet or exceeds the configured length threshold.
2. **Distractor Leak** – an intended distractor is accepted by the target DFA.
3. **Slight Error** – an option is rejected by the target DFA but is at Levenshtein distance of at most one from at least one accepted string in the bounded sample used by the notebook.
4. **Logical Error** – an alphabet-valid option is rejected by the target DFA and does not meet the Slight Error condition.

The notebook's Slight Error heuristic uses a bounded sample of accepted strings (up to 100 strings, with a maximum sampled length of 4). The Logical Error category is a residual category; it does not independently identify a precise misconception such as an omitted or additional restriction.

**Output of this stage:** a category assigned to each intended distractor.

### Step 10 — Aggregate the evaluation results

The notebook aggregates item-level and distractor-level results into counts and percentages.

The reported evaluation contains:

| Measure | Result |
|---|---:|
| Extracted Figure 7 tasks | 500 |
| Generated/evaluated records | 415 |
| Exact expression equivalence | 409 / 415 (98.6%) |
| Option soundness | 412 / 415 (99.3%) |
| `fully_consistent` audit field | 408 / 415 (98.3%) |
| Distractor leaks | 3 |
| Intended distractors | 1,633 |
| Slight Error | 1,383 (84.7%) |
| Logical Error | 247 (15.1%) |
| Machine Noise | 0 |
| Distractor leaks as a share of intended distractors | 3 (0.2%) |

Interpret these measures separately:

- **Exact expression equivalence** measures whether the generated expression recognises the same language as the target.
- **Option soundness** is the notebook's option-level audit measure.
- **`fully_consistent`** is the notebook's combined implementation-specific audit field.

There is an important limitation in the saved output: it contains **442 options labelled correct across 415 tasks**, even though the intended single-choice format requires exactly one labelled-correct option per task. The notebook did not explicitly enforce or report that invariant for every item. Therefore, the 98.3% `fully_consistent` result should be described as the pass rate of the implemented audit, not as proof that every generated item is a valid single-answer question.

## 5. Pipeline at a glance

```text
Ade-Ibijola benchmark
        |
        v
Extract Figure 7 single-choice tasks
        |
        v
Normalise expressions and collect alphabets
        |
        v
Construct prompts with target regex + alphabet
        |
        v
LLM generation (expression + five options + rationales)
        |
        v
Save structured generation records
        |
        +-------------------------------+
        |                               |
        v                               v
Parse target and generated regexes      Test options on target DFA
        |                               |
        v                               v
Postfix conversion                      Accepted / rejected options
        |
        v
Thompson epsilon-NFA construction
        |
        v
Subset construction (DFA)
        |
        v
Product-automaton equivalence check
        |
        +---------------+
                        |
                        v
              Aggregate formal results
                        |
                        v
              Distractor heuristic audit
                        |
                        v
              Aggregate and report metrics
```

## 6. How to run the experiment

1. Obtain the project notebook and the benchmark input files expected by it.
2. Install the Python packages imported by the notebook.
3. Configure the API key and endpoint using the notebook's configuration cell.
4. Confirm that the configured model identifier is the intended model.
5. Open `LLM_Regex_Synthesiser.ipynb` in Jupyter.
6. Run the benchmark extraction and preprocessing cells.
7. Run the generation cells. If resuming, make sure the existing output file is the one you intend to continue.
8. Run the parsing and automata verification cells.
9. Run the answer-option and distractor-audit cells.
10. Run the final aggregation and reporting cells.
11. Keep the generated records and evaluation outputs so that results can be traced back to individual task identifiers.

For a clean reproduction, use a fresh output location or archive the previous generated records first. Otherwise, the notebook's resume logic may continue from earlier saved results rather than starting from zero.

## 7. Interpreting the results responsibly

The results support claims about formal equivalence and the notebook's heuristic distractor classifications for the 415 evaluated records.

They do **not**, by themselves, establish that:

- All 500 extracted tasks received a generated response.
- Every item has exactly one labelled-correct option.
- The generated distractors have been validated by students or lecturers.
- The heuristic categories reliably identify the underlying misconception of a student.
- The experiment demonstrates improved learning or teaching outcomes.
- The LLM outperforms the CFG baseline in a matched experiment.
- Minimal-DFA state complexity was measured. The executed pipeline does not perform DFA minimisation.

The CFG-based benchmark is useful background and a source of comparison in the research discussion, but the notebook does not run a separate matched CFG baseline experiment.

## 8. Troubleshooting

### API request fails

- Check that the API key is configured in the location expected by the notebook.
- Check network access and API account limits.
- Confirm that the base URL and model identifier are valid.
- Retry failed requests using the notebook's retry/resume mechanism.

### A generation record is missing

- Check the saved output file and task identifier.
- Check whether the request failed after the retry attempts.
- Remember that the reported run contains 415 records, not all 500 extracted tasks.

### A regex cannot be parsed

- Check whether it uses only the operators supported by the parser.
- Check parentheses and operator placement.
- Check whether unsupported PCRE features such as lookarounds, anchors, or backreferences were generated.

### A generated expression is not equivalent

- Inspect the target and generated expressions.
- Check the parser output and automata construction for the task.
- Use the equivalence result as a formal failure rather than assuming that a plausible-looking expression is correct.

### More than one answer is accepted

- Inspect each option's acceptance result against the target DFA.
- Treat accepted intended distractors as leaks.
- Check the labelled-correct field separately; do not assume that the model's label guarantees a unique correct answer.

## 9. Reproducibility and reporting checklist

Before reporting a new run, record:

- Benchmark version and extraction count.
- Number of tasks successfully generated.
- Model endpoint and API configuration.
- Temperature and other generation settings.
- Prompt version.
- Supported regex operators.
- Number of parse failures and API failures.
- Number of equivalent and non-equivalent expressions.
- Number of options labelled correct.
- Number of options accepted by the target DFA.
- Number of distractor leaks.
- Counts for each distractor category.
- Any changes to the verifier or heuristic thresholds.

Do not compare metrics across runs unless the benchmark subset, prompt, model configuration, verifier, and classification rules are sufficiently consistent.

## 10. Summary

The project combines LLM generation with a symbolic verification pipeline. The LLM proposes equivalent regular expressions and answer options; the automata implementation checks language equivalence and evaluates answer strings against the reference language; and a heuristic audit groups distractors into pedagogical categories. This separation makes it possible to report formal correctness and distractor characteristics as distinct dimensions, while keeping the limitations of the heuristics and the single-choice format visible.
