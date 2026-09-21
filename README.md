# Evaluating the Formal Correctness, and Pedagogical Realism of LLM-Synthesized Regular Expression Assessment Materials

## Project Overview
This repository contains the complete research pipeline for an Honours Computer Science research project at the University of Pretoria. The research empirically evaluates and compares **Symbolic Context-Free Grammar (CFG) question generation** against **Probabilistic Neural Generation (Large Language Models)** for Regular Expression (Regex) Multiple-Choice Questions (MCQs).

The evaluation is conducted across three primary analytical pillars:
1. **Computational Efficiency:** Generation latency, token consumption profiles (cached vs. uncached inputs), and cost accounting ($USD / ZAR).
2. **Formal Correctness ($\forall uto\exists val$ Framework):** Closed-loop verification of regular expression equivalence via product-automaton symmetric difference, option string execution against target state machines, and **Distractor Leak** detection.
3. **Pedagogical Quality / Realism:** Automated classification of generated distractors against documented student error taxonomies (Okuboyejo et al., 2025), augmented with a supervisor-approved **Machine Noise / Gibberish** classification category.

---

## Key Features & Architecture

- **Unified Google Colab Execution:** The entire end-to-end research pipeline—from PDF ingestion and LLM prompting to formal automata verification and taxonomy classification—runs sequentially inside interactive Jupyter Notebook cells.
- **500 Ground-Truth Benchmark Tasks:** Evaluates LLMs over 500 authentic benchmark problems derived from South African higher education computing education literature (Ade-Ibijola, 2018):
  - **250 Classical Single-Choice Tasks (Figure 7 Wrapper):** 1 correct answer and 4 distractors with explicit answer keys.
  - **250 Multi-Answer Tasks (Figure 8 Wrapper):** "Select ALL that apply" items with variable numbers ($m \in [1,4]$) of correct options.
- **Pure-Python Automata Verification Engine:** Zero-dependency formal verification suite implementing Thompson's NFA construction, Subset Construction (NFA $\rightarrow$ DFA), Hopcroft/Moore DFA minimization, and Product Automaton Symmetric Difference ($\text{L}(r_{\text{target}}) \Delta \text{L}(r_{\text{LLM}}) = \emptyset$).
- **Programmatic Ground-Truth Resolution:** Multi-answer tasks extracted with unresolved keys (`labeled_correct: null`) are programmatically solved and verified by executing candidate strings against the target regex DFA.
- **Comparative Model Benchmarking:** Dual-pipeline architecture supporting open-source models (**Llama 3.1 / Llama 3.3 via Groq**) and closed-source models (**GPT-4o via OpenAI**).
- **Free-Tier Protection & Incremental Progress Logging:** Daily task slicing (`CURRENT_DAY`), rate-limit cool-down guards (`time.sleep(7)`), and continuous JSON state logging (`cumulative_tasks_llama.json` / `cumulative_tasks_openai.json`) prevent data loss during long execution runs or notebook disconnections.

---

## Notebook Structure

| Cell | Name | Purpose | Output File |
| :--- | :--- | :--- | :--- |
| **Cell 1** | Environment Setup | Installs dependencies (`openai`, `fpdf2`, `pypdf`) and configures workspace imports. | — |
| **Cell 2** | Dataset Ingestion & Cleansing | Ingests baseline PDFs, normalizes Unicode star operators ($\ast \rightarrow *$), strips lambda symbols ($\lambda$), and parses 500 tasks. | `baseline_tasks.json` |
| **Cell 3** | Pedagogical Prompt Wrappers | Defines System Prompts enforcing core Formal Languages and Automata (FLA) operator constraints alongside Figure 7 and Figure 8 JSON schemas. | — |
| **Cell 4A**| Groq / Llama-3.1 Pipeline | Executes free, high-speed Llama generation runs on Groq infrastructure with incremental progress logging. | `cumulative_tasks_llama.json` |
| **Cell 4B**| OpenAI / Credit Pipeline | Executes GPT-4o generation runs using departmental credits with daily batch slicing (50 tasks/day). | `cumulative_tasks_openai.json` |
| **Cell 5** | Pure-Python DFA Engine & Option Judge | Compiles state machines, programmatically resolves multi-answer ground-truth keys, checks regex language equivalence, and flags distractor leaks. | `baseline_tasks_resolved.json` |
| **Cell 6** | Distractor Plausibility & Taxonomy Engine | Maps generated distractors against Okuboyejo et al. (2025) error categories (*Syntax*, *Slight*, *Logical*) and the *Machine Noise / Gibberish* bucket. | `final_evaluation_report.json` |

---

## Primary Metrics & Definitions

### 1. Consistency Rate (Formal Correctness)
The percentage of LLM-generated MCQ items that satisfy both of the following formal verification conditions:
1. **Regex Language Equivalence:** The LLM's synthesized regex $r_{\text{LLM}}$ accepts the exact same language as the target specification $r_{\text{target}}$ ($\text{L}(r_{\text{target}}) \Delta \text{L}(r_{\text{LLM}}) = \emptyset$).
2. **Option Soundness:** Every string labeled as correct is accepted by the target DFA, and no distractor string is accepted by the target DFA (**Zero Distractor Leaks**).

$$\text{Consistency Rate} = \frac{\text{Number of Formally Valid MCQs}}{\text{Total Evaluated MCQs}} \times 100$$

### 2. Plausibility Score (Pedagogical Quality)
The percentage of LLM-generated distractor strings that reflect realistic student misconceptions documented in student error taxonomies, as opposed to unclassified machine noise.

$$\text{Plausibility Score} = \frac{\text{Distractors Categorized as Syntax / Slight / Logical Errors}}{\text{Total Generated Distractor Strings}} \times 100$$

### 3. Computational Efficiency
- **Wall-Clock Latency:** Measured generation duration (seconds/item).
- **Token Consumption Profile:** Input tokens (uncached vs. cached) and completion tokens.
- **Estimated Financial Cost:** Transactional cost calculated per micro-cent ($USD / ZAR).

---

## Theoretical Operator Constraints
To isolate the neural model's logical reasoning capabilities rather than its memorization of programming shorthand, models are strictly constrained to core Formal Languages and Automata (FLA) theoretical operators:
- **Concatenation:** Implied (e.g., `ab`)
- **Alternation / Union:** `|` or `+`
- **Kleene Star:** `*`
- **Kleene Plus:** `+`
- **Optionality:** `?`
- **Explicit Grouping:** Parentheses `( )`
- *Prohibited:* Lookarounds, backreferences, anchors (`^`, `$`), and character class shorthand (`\d`, `\w`, `\s`).

---

## References & Literature Foundation
- **Ade-Ibijola, A. (2018).** *Automatic synthesis of regular expression problems and solutions.*
- **Karia, N., et al. (2024).** *Autonomous Assessment of LLMs in Formal Synthesis and Interpretation Tasks ($\forall uto\exists val$).*
- **Okuboyejo, O., et al. (2025).** *Student Error Taxonomies in Regular Expression Learning and Assessment.*
