# Eval Log — Concall Intelligence
## Forward-Looking Statement Extraction

This file tracks every prompt version, model run, and evaluation result.
Updated automatically after each run via Claude.

**Ground truth:** 20 statements, manually labelled from Asian Paints Q4 FY26 transcript
**Eval method (v1):** Manual comparison — eyeballing extracted statements against ground truth
**Eval method (v2+):** Automated precision/recall script (to be built in v2)

---

## Run 1
**Date:** 06 June 2026
**Model:** gpt-4o-mini
**Prompt:** prompt_v1
**Transcript:** Asian Paints Q4 FY26

### Raw Numbers
- Total statements extracted: 18
- Duplicates: 1 (statement 12 = exact repeat of statement 4)
- Unique statements: 17
- Hallucinations: 1 (statement about discretionary nature of paint spend — present in transcript but not forward-looking)

### Precision
- Statements matching ground truth: 11 (note: statements 6 and 7 both matched GT 16)
- Borderline (in transcript, forward-looking, but not in GT): 5
- Not forward-looking: 1
- **Strict Precision: 11/17 = 65%**

### Recall
- GT statements found: 10 out of 20
- **Recall: 10/20 = 50%**

### GT Statements Found
GT 1 (VAM-VAE commissioning), GT 7 (demand sustainability), GT 8 (high single-digit volume growth), GT 9 (competitive intensity), GT 11 (calibrated price increases), GT 12 (backward integration timing), GT 13 (retain margin guidance), GT 16 (margin guidance 18-20%), GT 17 (price increases sticky), GT 20 (volume-value gap 3-4%)

### GT Statements Missed
- GT 2 — Industrial coatings growth (management opening remarks)
- GT 3 — International business growth (management opening remarks)
- GT 4 — 10.5-11% price increase, more to come (management opening remarks)
- GT 5 — Further price increases (Q&A)
- GT 6 — Not passing full inflation impact (Q&A)
- GT 10 — Volume growth 8-10% from Mihir Shah Q&A
- GT 14 — A&P rationalization + discounting to continue
- GT 15 — Larger impact in Q1 and Q2
- GT 18 — Open to more price increases H1
- GT 19 — VAM-VAE full benefits 1.5-2 years

### Root Cause Analysis
1. Model pattern-matching on obvious future-signal words only ("we expect", "we feel", "we believe") — missing indirect phrasing like "will continue", "will be sticky", "will have to phase", "is expected to"
2. Statements not self-sufficient — context stripped, subjects dropped. Words like "this", "these benefits", "the segment" appear with no reference to what they mean
3. One duplicate returned — same statement extracted twice from different parts of transcript
4. One hallucination — statement about discretionary nature of paint spend is descriptive, not forward-looking

### Changes Made for Run 2 (prompt_v2)
- Added instruction to extract from ALL sections equally (opening remarks + Q&A)
- Added instruction to include CFO and other finance team speakers
- Added instruction to not return duplicates
- Added generic segment instruction: "extract guidance across all business segments and geographies"
- Removed company-specific segment reference — made generic so prompt works for any company

---

## Run 2
**Date:** 06 June 2026
**Model:** gpt-4o-mini
**Prompt:** prompt_v2
**Transcript:** Asian Paints Q4 FY26

### Raw Numbers
- Total statements extracted: 15
- Duplicates: 0 (improvement from Run 1)
- Unique statements: 15
- Hallucinations: 0 (improvement from Run 1)

### Precision
- Statements matching ground truth: 10
- Borderline (in transcript, forward-looking, but not in GT): 5
- Not forward-looking: 0
- **Strict Precision: 10/15 = 67%**

### Recall
- GT statements found: 9 out of 20
- **Recall: 9/20 = 45%**

### GT Statements Found
GT 1 (VAM-VAE commissioning), GT 7 (demand sustainability), GT 8 (high single-digit volume growth), GT 9 (competitive intensity), GT 11 (calibrated price increases), GT 12 (backward integration timing), GT 13 (retain margin guidance), GT 16 (margin guidance 18-20%), GT 20 (volume-value gap 3-4%)

### GT Statements Missed
- GT 2 — Industrial coatings growth
- GT 3 — International business growth
- GT 4 — 10.5-11% price increase, more to come
- GT 5 — Further price increases
- GT 6 — Not passing full inflation impact
- GT 10 — Volume growth 8-10% from Mihir Shah Q&A
- GT 14 — A&P rationalization + discounting to continue
- GT 15 — Larger impact in Q1 and Q2
- GT 17 — Price increases sticky
- GT 18 — Open to more price increases H1
- GT 19 — VAM-VAE full benefits 1.5-2 years

### Run 1 vs Run 2 Comparison
| Metric | Run 1 | Run 2 | Change |
|---|---|---|---|
| Statements extracted | 18 | 15 | -3 |
| Duplicates | 1 | 0 | ✅ fixed |
| Hallucinations | 1 | 0 | ✅ fixed |
| Precision | 65% | 67% | +2% |
| Recall | 50% | 45% | -5% |

### Root Cause Analysis
- Duplicates and hallucinations eliminated — prompt additions worked for quality
- Recall dropped slightly despite adding recall-focused instructions
- Root cause now clearer: model is still only catching statements with obvious future-signal words
- Token count confirmed at ~13,000 (51,972 characters ÷ 4) — truncation ruled out as cause
- Consistent pattern of missed statements: all use indirect phrasing ("will continue", "will be sticky", "will have to phase", "is expected to", "do not intend")
- Second major problem identified: extracted statements are not self-sufficient — context stripped, subjects dropped

### Self-Sufficiency Audit (Run 2 output)
- ✅ Fully self-sufficient: 1 out of 15
- ⚠️ Partially clear: 5 out of 15
- ❌ Missing critical context: 9 out of 15

Examples of context failure:
- "We will have to observe these benefits over a year" — benefits of what?
- "We think this is a very high-growth segment" — which segment?
- "We are looking at maintaining our margin band given." — incomplete sentence

### Changes Planned for prompt_v4
- prompt_v3 skipped — see note below

---

## prompt_v3 — SKIPPED

**Reason:** After Run 2, a self-sufficiency audit revealed that extracted statements were missing critical context — subjects were dropped, "this", "these", "it" appeared with no reference. Decided that adding more recall instructions without fixing context would compound the problem. Skipped directly to prompt_v4 which addresses both issues together.

**Learning:** Recall and context quality are linked — the model extracts the forward-looking sentence in isolation but leaves the subject behind. Both need to be fixed in the same prompt version.

---

## Run 3
**Date:** 06 June 2026
**Model:** gpt-4o-mini
**Prompt:** prompt_v3
**Transcript:** Asian Paints Q4 FY26

### Raw Numbers
- Total statements extracted: 21
- Duplicates: 0
- Unique statements: 21
- Not forward-looking: 2 (statement 13 — general cost excellence capability; statement 19 — descriptive about paint spend, not a commitment)

### Precision
- Statements matching ground truth: 13
- Borderline (in transcript, forward-looking, but not in GT): 6
- Not forward-looking: 2
- **Strict Precision: 13/21 = 62%**

### Recall
- GT statements found: 11 out of 20
- **Recall: 11/20 = 55%**

### GT Statements Found
GT 1 (VAM-VAE commissioning), GT 7 (demand sustainability), GT 8 (high single-digit volume growth), GT 9 (competitive intensity), GT 10 (volume growth 8-10% Mihir Shah Q&A), GT 11 (calibrated price increases), GT 12 (backward integration timing), GT 13 (retain margin guidance), GT 16 (margin guidance 18-20%), GT 17 (price increases sticky), GT 20 (volume-value gap 3-4%)

### NEW vs Run 2
- GT 10 found for first time — volume growth 8-10% from Mihir Shah Q&A
- GT 17 found for first time — price increases will be sticky

### GT Statements Still Missed
- GT 2 — Industrial coatings growth
- GT 3 — International business growth
- GT 4 — 10.5-11% price increase, more to come
- GT 5 — Further price increases
- GT 6 — Not passing full inflation impact
- GT 14 — A&P rationalization + discounting to continue
- GT 15 — Larger impact in Q1 and Q2
- GT 18 — Open to more price increases H1
- GT 19 — VAM-VAE full benefits 1.5-2 years

### Run Comparison
| Metric | Run 1 | Run 2 | Run 3 | Change (R2→R3) |
|---|---|---|---|---|
| Statements extracted | 18 | 15 | 21 | +6 |
| Duplicates | 1 | 0 | 0 | — |
| Not forward-looking | 1 | 0 | 2 | +2 |
| Precision | 65% | 67% | 62% | -5% |
| Recall | 50% | 45% | 55% | +10% |

### Root Cause Analysis
- Recall improved by 10% — the intent-based phrasing instruction worked, catching GT 10 and GT 17 that were missed in both previous runs
- Precision dropped slightly — expected tradeoff when broadening recall. The 2 non-forward-looking statements slipped through because they use soft future-tense language but express general capability rather than specific guidance
- Self-sufficiency instruction (Fix 2) did not fully work — statements like "We will have to observe these benefits over a year" still missing context (benefits of what?), "We think this is a very high-growth segment" still missing which segment
- Consistent pattern of 9 missed GT statements — all from management opening remarks (GT 2, 3, 4, 5, 6) suggesting the model is still underweighting that section despite the instruction

### Changes Planned for prompt_v4
- Investigate why opening remarks statements (GT 2, 3, 4, 5, 6) are consistently missed across all 3 runs
- Strengthen self-sufficiency instruction — current version not being followed reliably
- Full prompt rethink — patch-based approach not working, rebuild from scratch

---

## Run 4
**Date:** 06 June 2026
**Model:** gpt-4o-mini
**Prompt:** prompt_v4
**Transcript:** Asian Paints Q4 FY26

### Prompt Changes from v3
Complete rewrite — moved away from patch-based approach. Key structural changes:
- Output unit changed from "statement" to "passage" — signals multi-sentence extraction
- Definition expanded to cover company, industry, and macro future predictions
- Self-sufficiency elevated to rule 2 of output format, not a footnote
- Context inclusion given its own explicit rule with specific reference word examples
- Q&A handling made explicit with its own rule
- Removed all enumerated phrasing patterns — replaced with intent-based definition

### Raw Numbers
- Total passages extracted: 8
- Duplicates: 0
- Not forward-looking: 0

### Precision
- All 8 passages are genuinely forward-looking
- **Strict Precision: 8/8 = 100%** — first clean precision across all runs

### Recall
- GT statements found: 10 out of 20
- **Recall: 10/20 = 50%**

### GT Statements Found
GT 2 (industrial coatings growth) NEW, GT 3 (international business growth) NEW, GT 5 (further price increases) NEW, GT 6 (not passing full inflation impact) NEW, GT 7 (demand sustainability), GT 8 (high single-digit volume growth), GT 10 (volume growth 8-10%), GT 13 (retain margin guidance), GT 16 (margin guidance partial), GT 20 (volume-value gap partial)

### GT Found For First Time Ever
- GT 2 — Industrial coatings growth (was missed in all 3 previous runs)
- GT 3 — International business growth (was missed in all 3 previous runs)
- GT 5 — Further price increases (was missed in all 3 previous runs)
- GT 6 — Not passing full inflation impact (was missed in all 3 previous runs)

### GT Statements Missed
- GT 1 — VAM-VAE commissioning timeline (Passage 5 covers benefits but not the H1 commissioning date)
- GT 4 — 10.5-11% price increase from opening remarks
- GT 9 — Competitive intensity to continue
- GT 11 — Calibrated price increases
- GT 12 — Backward integration timing
- GT 14 — A&P rationalization + discounting
- GT 15 — Larger impact in Q1 and Q2
- GT 17 — Price increases sticky
- GT 18 — Open to more price increases H1
- GT 19 — VAM-VAE full benefits 1.5-2 years

### Regression vs Run 3
GT 9, 11, 12, 17 were found in Run 3 but lost in Run 4. The model consolidated into fewer, higher-quality passages and skipped standalone Q&A guidance statements in the process.

### Self-Sufficiency Audit (Run 4)
- ✅ Fully self-sufficient: 5 out of 8 (major improvement from Run 3: 1/21)
- ⚠️ Partially sufficient: 2 out of 8 (Passage 7 missing 18-20% number; Passage 8 missing what trajectory refers to)
- ❌ Missing context: 1 out of 8 (Passage 5 about VAM-VAE benefits missing commissioning timeline)

### Root Cause Analysis
- Precision improvement is real — passage format works, model includes multi-sentence context naturally
- Recall held at 50% — same number as Run 1 but completely different GT statements found
- Core tension identified: quality and coverage pull in opposite directions. Run 3 had broad coverage (21 statements) but poor quality. Run 4 has high quality (8 passages) but misses standalone Q&A guidance
- Model is now consolidating related guidance into single passages — good for self-sufficiency, bad for recall of individual GT statements
- Passage 7 and 8 still partially incomplete — Q&A context instruction not fully followed

### Changes Planned for prompt_v5
- Keep passage format (working well for quality)
- Add explicit instruction to not consolidate — each distinct forward-looking topic should be its own passage
- Strengthen Q&A context rule — Passage 7 missing 18-20% because analyst context not included
- Add instruction to cover every Q&A exchange individually, not just the opening remarks

---

## Summary Table

| Run | Prompt | Model | Precision | Recall | Passages | Self-Sufficient | Not FLS |
|---|---|---|---|---|---|---|---|
| 1 | prompt_v1 | gpt-4o-mini | 65% | 50% | 18 | 1/17 | 1 |
| 2 | prompt_v2 | gpt-4o-mini | 67% | 45% | 15 | 1/15 | 0 |
| 3 | prompt_v3 | gpt-4o-mini | 62% | 55% | 21 | 1/21 | 2 |
| 4 | prompt_v4 | gpt-4o-mini | 100% | 50% | 8 | 5/8 | 0 |

---

## Key Learnings So Far

1. **Ground truth labelling is expensive.** Took ~2.5 hours to label 20 statements from one transcript. This is why automated eval (v2) is critical — you cannot scale manual comparison.

2. **Recall and precision pull in opposite directions.** A prompt that catches everything returns junk. A cautious prompt misses real guidance. Both metrics needed together.

3. **Indirect phrasing is the hardest problem.** Management says the same thing many ways — "will continue", "is expected to", "we do not intend." Keyword matching fails. An LLM understands meaning but still needs explicit instruction to look beyond obvious signal words.

4. **Context stripping is a real failure mode.** Extracting the forward-looking sentence in isolation produces meaningless fragments. The model needs to be explicitly told to preserve subject context.

5. **Token count ≠ truncation.** 51,972 characters (~13,000 tokens) is well within the context window. Always verify before blaming the model for missed statements.

6. **Prompt versioning matters.** Without separate files per version, you cannot diagnose what change caused what effect. Every prompt change must be its own file.

7. **One change at a time is ideal — but related fixes can be batched.** Recall fixes and context fixes were batched in v4 because they address the same root cause.

8. **Prompts must be generic.** Company-specific instructions (mentioning industrial coatings, backward integration by name) break the prompt for other companies. Always abstract to the general case.
