# EXPERIMENT — Single-Pass Extraction with a Frontier Model
## Concall Intelligence Extraction Pipeline

**Status:** Proposed experiment, not yet run
**Owner:** Harsh
**Relates to:** the multi-stage pipeline (Stage 0–4) currently under construction at Stage 2

> Read `CLAUDE.md` before acting on this file. This spec contains **instructions and design only — no implementation code**. Do not write code for this experiment until explicitly asked ("give me the code").

---

## 1. Why this experiment exists (plain language)

The multi-stage pipeline (Stage 0 segmenter → Stage 1 filter → Stage 2 per-chunk extractor → Stage 3 classifier → Stage 4 validator) was built because **single-pass extraction hit a quality ceiling**: under-extraction, metric misclassification, null-value false positives, run-to-run oscillation, and Mold-Tek overflowing the 16,384 output-token limit.

But every one of those single-pass runs used **gpt-4o or gpt-4o-mini** — the only two models ever tried on this task. Those are now roughly two generations behind OpenAI's current frontier (the GPT-5.x family). Several of the documented "structural" failures are exactly the kind of thing a stronger model fixes:

| Documented single-pass failure | Is it structural, or model-driven? |
|---|---|
| Mold-Tek hit the 16,384 output-token wall | **Model-driven** — current models have far larger output ceilings; this failure disappears by construction |
| Attention dilution over a 50k-char transcript (under-extraction) | **Mostly model-driven** — long-context attention has improved sharply |
| Recall regression when switching to structured output | **Mostly model-driven** — newer models handle `response_format` far better |
| Hallucinated / past-quarter numbers | **Mostly model-driven** — frontier models report materially lower factual-error rates |
| Metric misclassification (the biggest recall blocker under strict eval) | **Partly model** — a reasoning model classifies better in one pass, but this is also a task-decomposition issue |

**The question this experiment answers:** *Was the single-pass ceiling structural, or was it a weak-model artifact?*

The answer decides whether the five-stage architecture is justified or whether it is complexity built to compensate for a model you would now replace. This is high-value to resolve **before** finishing Stage 2, because the entire pipeline's justification rests on it.

---

## 2. Core design decision — standalone, NOT integrated into the pipeline

**This is a standalone single-pass experiment: raw transcript text → one LLM call → 8-field structured output → existing eval. It does NOT reuse Stage 0, 1, 2, or 4.**

Reasoning:

- **Scientific cleanliness.** The whole point is to test the *simplest possible architecture* against a frontier model. If you fed it Stage 0/Stage 1 chunks, any improvement would be confounded — you would not know whether the model or the chunking caused it. Keep the architecture variable pinned to "single pass, full transcript."
- **It reuses the existing single-pass harness almost unchanged.** `main.py`'s `extract_forward_looking_statements()` already does exactly this. Only two things change: the **model** string and the **prompt** path. `eval.py` runs on top of it with no changes.
- **The two architectures compete on the same measuring stick.** Same `eval.py`, same ground-truth files, same `GuidanceItem` schema. That is what makes the comparison fair.

### What the experiment reuses vs. leaves untouched

| Reuse (shared measuring stick) | Do NOT reuse (belongs to the competing architecture) |
|---|---|
| `eval.py` (unchanged) | `pipeline/stage0_segmenter.py` |
| Ground-truth files in `data/` (unchanged) | `pipeline/stage1_filter.py` |
| `schemas.py` → `GuidanceItem` / `ExtractionResult` (unchanged) | `pipeline/stage2_extractor.py` + `stage2_extraction_prompt.txt` |
| `main.py` single-pass call path (model + prompt swapped) | `pipeline/stage4_validator.py` |

The multi-stage work is **paused and shelved** during the experiment, not deleted. The experiment runs alongside it as a rival, and the result decides which one survives.

---

## 3. Integration point in the current code

The single-pass path already exists. There is exactly one function to touch:

- **`main.py` → `extract_forward_looking_statements(transcript_text)`**
  - It already calls `client.beta.chat.completions.parse(...)` with `response_format=ExtractionResult`, `temperature=0`.
  - **Change 1 — model:** today it is hardcoded `model="gpt-4o"`. Parameterise it so the experiment can sweep models.
  - **Change 2 — prompt:** today `load_prompt(...)` points at **`prompts/prompt_v9.txt`**. ⚠️ This is the *regressed* prompt (see §5). Point it at **`prompts/prompt_v8.txt`** for the baseline arm.
- **`eval.py`** — no logic changes. It calls the function above, parses GT, computes precision/recall (on metric + timeline + value), and writes to Postgres. Use its existing `--prompt-version` flag to tag each arm (e.g. `v8_gpt54`).

That is the entire integration surface. No new pipeline files.

---

## 4. Recommended model(s)

The project is committed to OpenAI, so stay in-family. As of mid-2026 the relevant options:

- **Primary arm — GPT-5.4.** Reported lower factual-error rate than its predecessor and a large context window. Lower hallucination directly targets the "past-quarter number" and fabricated-value failures; the large output ceiling eliminates the Mold-Tek truncation hard-fail by construction.
- **Optional second arm — GPT-5.2 (reasoning).** This task is judgment-heavy (is it trackable within 4 quarters? is it company-level? which metric label?). A reasoning model is well suited to doing extraction + classification correctly in one pass. Worth a run if the primary arm is close but not clearing the bar.

> ⚠️ Model IDs and availability shift. Confirm the exact current API model strings in the OpenAI docs before running — do not assume the names above are the live identifiers.

**Optional stretch (low priority):** one non-OpenAI frontier model (current long-context leaders) purely to read the *absolute achievable ceiling*. Skip unless the OpenAI arms are ambiguous — it adds integration work and the practical decision stays within OpenAI.

---

## 5. Which prompt to use — and why

**Use `prompts/prompt_v8.txt` for the primary arm.**

Rationale:

- **v8 is the strongest *complete* single-pass prompt.** It produces the full 8-field schema (`metric` from the controlled vocabulary, `credibility_scorable`, etc.) that `eval.py` needs. It carries all extraction rules, the verbatim/self-sufficiency rules, the Q&A-context rule, and the credibility logic.
- **It is the documented baseline.** The v8 numbers in `extraction_architecture_request.md` are your control. Running v8 on a frontier model isolates the *model* variable cleanly against a known reference.

**Do NOT use these:**

- **`prompt_v9.txt`** — it added "a transcript typically contains 5 to 15 qualifying statements." The model treated that as a **quota**, padded output with false positives, and precision collapsed (Fineotex precision fell to 10%). Its other two changes were no-ops. v9 is a worse baseline, not a better one. (Note: `main.py` currently loads v9 — fix this before running.)
- **`stage2_extraction_prompt.txt`** — designed for *chunks*, outputs a free-text `metric_description` with **no vocabulary classification and no `credibility_scorable`**. It cannot produce the final schema `eval.py` scores, and it assumes the Stage 0/1 chunking you are deliberately excluding.

### Optional secondary prompt arm (only if v8 underperforms)

The architecture-request doc notes a recall regression specifically from forcing structured output at extraction time. If the v8 + frontier arm finds the right passages but loses them to the schema, run one variant that **decouples reasoning from formatting**: let the model extract/reason in free text first, then emit structured JSON — either as a two-message exchange or via a "think first, then output the JSON object" instruction. Keep this as a *separate arm* so it does not contaminate the clean model-isolation result.

---

## 6. Experiment matrix

Hold everything constant except the named variable. Run on **all three target companies** (Fineotex, Sandhar, Mold-Tek) for every arm.

| Arm | Model | Prompt | Purpose |
|---|---|---|---|
| **0 (control)** | gpt-4o | prompt_v8 | Reproduce the documented baseline; confirm harness + GT are stable today |
| **1 (primary)** | GPT-5.4 | prompt_v8 | Isolate the model variable — the headline test |
| **2 (optional)** | GPT-5.2 (reasoning) | prompt_v8 | Does reasoning help the classification/judgment steps? |
| **3 (optional)** | best arm so far | decoupled-output variant | Only if structured output is the bottleneck |

Keep `temperature=0` everywhere. Run each arm **twice** per company and note whether item counts differ between runs — run-to-run oscillation at temp 0 was a documented failure, and whether a frontier model fixes it is itself a result.

---

## 7. How to run (operational steps — uses existing tooling)

1. Fix `main.py` to load `prompt_v8.txt` and to accept a model parameter.
2. For each arm, set the model, then run the existing eval per company, e.g.:
   - `python eval.py --transcript transcripts/fineotex_chemical_Q4_FY26.pdf --ground-truth data/fineotex_chemical_Q4_FY26_ground_truth_v1.txt --prompt-version v8_gpt54 --company "Fineotex Chemical" --quarter "Q4 FY26"`
   - Repeat for Sandhar and Mold-Tek.
3. Each run prints recall/precision and writes to the `extractions` / `eval_runs` tables, tagged by the `--prompt-version` label. Use a distinct label per arm so results are queryable later.
4. Record every arm in `eval_log.md` as a new run block (same format as existing runs), with model + prompt + per-company recall/precision/item-count.

---

## 8. Metrics to capture

For each arm × company:

1. **Full-match recall / precision** — straight from `eval.py` (metric + timeline + value match). This is the headline.
2. **Semantic / passage-level recall on misses** — manual, ~2 minutes per company. For each GT item `eval.py` scored as missed, check the raw LLM output: did the model **find the passage but mislabel the metric/timeline**, or did it **not find it at all**? This separates a *find-failure* (real recall ceiling) from a *label-failure* (a classification problem a frontier model or a Stage-3-style classifier fixes). Without this split, strict eval will understate single-pass capability.
3. **Truncation check** — did Mold-Tek complete without hitting the output-token limit? Binary, decisive.
4. **Item count per transcript** — under-extraction (≪ GT count) vs noise-padding (≫ GT count).
5. **Run-to-run delta** — item-count difference between the two runs at temp 0.

> Note on GT quality: `eval.py`'s matcher uses metric + timeline + value, **not** passage text, so paraphrased GT passages do **not** distort these scores (unlike the Stage 0 containment test). What still matters is that GT **metric labels and values** are correct — sanity-check those before trusting a "miss."

---

## 9. Decision rule

Compare each arm against (a) your v1 bar — **recall ≥ 70%, precision ≥ 80%, self-sufficient passages** — and (b) the multi-stage pipeline's current trajectory.

- **Single-pass wins** — frontier arm clears ~≥70% recall and ~≥70–80% precision across all three companies, **and** Mold-Tek does not truncate:
  → Adopt single-pass as the core extractor. Collapse the architecture. Optionally keep only the cheap deterministic guards — Stage 0 for clean `speaker`/`page` metadata and Stage 4 for null-rejection/dedup — bolted onto the single-pass output. Shelve Stages 1–3. Defer cost optimisation (batch API) to scale time.

- **Hybrid signal** — recall jumps well past the v8 baseline but precision is poor, **or** misses are mostly *label-failures* not *find-failures*:
  → Frontier single-pass for the **find** step + Stage 4 (and possibly a Stage-3-style classifier) for cleanup. You keep most of the recall win without the full five-stage cost.

- **Multi-stage validated** — no meaningful lift over the v8 baseline, or Mold-Tek still truncates:
  → The ceiling was structural after all. Resume the Stage 2 build with confidence and a **documented** justification (a much stronger interview narrative than assuming single-pass fails).

---

## 10. Why this is worth doing before finishing Stage 2

- **Cost is irrelevant here.** Three transcripts, a handful of dollars. The per-chunk-cost argument only matters at 600 companies/quarter, and even then a single frontier call per transcript may be cheaper than 40+ chunk calls (Stage 2 runs each chunk ×2 and re-sends the prompt every time). Batch API (~50% off for overnight jobs) is the real scale lever, not chunking.
- **It de-risks the biggest architectural bet in the project** for a few hours of work on tooling you already have.
- **Either outcome is a win:** you either delete a lot of complexity, or you validate it with evidence instead of assumption.

---

## 11. Out of scope

- No changes to scoring, credibility, valuation, or downstream stages.
- No new pipeline files; no rewrite of Stage 0/1/2/4.
- No prompt engineering beyond pointing at v8 (and the optional decoupled-output variant). Resist iterating the prompt during this experiment — the variable under test is the **model**, not the prompt.
