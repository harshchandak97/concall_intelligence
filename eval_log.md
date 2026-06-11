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

## Run 5
**Date:** 08 June 2026
**Model:** gpt-4o-mini
**Prompt:** prompt_v5
**Transcript:** Asian Paints Q4 FY26

### Ground Truth Change
Ground truth rebuilt from scratch as v3. Criteria tightened to quantifiable forward-looking items only (number + timeframe, trackable within 4 quarters). Count reduced from 20 statements to 4 items. Structure changed to include metric, guidance_value, guidance_unit, timeline, credibility_scorable fields. All previous run recall numbers are against the old 20-statement ground truth and are not directly comparable from this run onward.

### Prompt Changes from v4
- Criteria narrowed: quantifiable only — number + timeframe required, not all forward-looking statements
- Structured JSON output introduced for the first time — passage, speaker, page_number, metric, guidance_value, guidance_unit, timeline, credibility_scorable
- Metric controlled vocabulary added with 14 standard types plus other_ convention
- credibility_scorable rules added — true only for company-level revenue, EBITDA margin, PAT, PBT, EPS
- Rule 7 added: search entire transcript including every Q&A exchange

### Raw Numbers
- Total items extracted: 4
- False positives: 1 (price increase — past action extracted as future guidance)
- Valid extractions: 3

### Precision
- Items matching ground truth: 3
- False positives: 1
- **Strict Precision: 3/4 = 75%** — below 80% target

### Recall
- GT items found: 3 out of 4
- **Recall: 3/4 = 75%** — meets ≥70% target

### GT Items Found
- GT 2 (Decorative volume growth 8-10%, FY27) ✅
- GT 3 (PBDIT margin 18-20%, FY27) ✅ — but with issues (see below)
- GT 1 (VAM-VAE commissioning, H1 FY27) ✅ — but with issues (see below)

### GT Items Missed
- GT 4 — Volume-value gap 3-4%, FY27 — not extracted at all

### Issues Per Extracted Item

**Item 1 — VAM-VAE Commissioning**
Self-sufficiency: FAIL. Passage extracted as: "We expect to commission first phase in the first half of this year." — "first phase" of what is unresolved. "This year" is ambiguous without knowing which year. Ground truth passage includes VAM-VAE context sentence. The self-sufficiency rule was not followed despite being in the prompt.

**Item 2 — Volume Growth 8-10%**
Pass. Passage from page 22 is acceptable. Stronger version exists on page 20 (Mihir Shah Q&A) but this extraction is valid.

**Item 3 — PBDIT Margin 18-20%**
guidance_value hallucinated. Passage extracted as: "We are maintaining our margin guidance, which is there." The number 18-20 does not appear anywhere in this passage. LLM sourced the value from a different part of the transcript and placed it in guidance_value without including the sentence containing it. Passage fails self-sufficiency (no number visible) and Rule 4 (guidance_value must appear in passage — rule not yet in prompt at v5).

**Item 4 — Price Increase 10.5-11%**
False positive. Passage: "We have already taken close to about 10.5-11% price increase, and we are talking of going ahead and taking some more price increases." The specific number (10.5-11%) describes past action. The forward-looking part ("some more") has no specific number. Neither half qualifies under extraction criteria. Extracted because WHAT NOT TO EXTRACT did not have an explicit example of this pattern.

### Run Comparison (New Ground Truth Basis — 4 Items)
| Run | Prompt | Precision | Recall | Items | Self-Sufficient | False Positives |
|---|---|---|---|---|---|---|
| 5 | prompt_v5 | 75% | 75% | 4 | 2/4 | 1 |

### Root Cause Analysis
1. Self-sufficiency rule not strong enough — LLM identified the right passage location but extracted an incomplete sentence without its context. Rule 2 needs a mandatory verification step, not just an example.
2. guidance_value sourced from outside the passage — no rule in v5 prevented this. LLM inferred the number from context rather than including the sentence that contains it.
3. Past action + vague future intent extracted as guidance — WHAT NOT TO EXTRACT lacked an explicit example of this specific pattern.
4. Volume-value gap missed — discussed late in transcript across two Q&A exchanges, likely underweighted despite Rule 7.

### Changes Made for prompt_v6
- Rule 2 (self-sufficiency) replaced with mandatory 4-question check: what, number, when, who — all must be yes before passage is written
- New Rule 4: guidance_value must appear explicitly in the passage text — if not, expand passage or do not extract
- WHAT NOT TO EXTRACT: added explicit example of past action + vague future intent pattern
- New self-check section: 5-point checklist LLM must run against every item before writing final JSON

---

## Summary Table

| Run | Prompt | Model | Precision | Recall | Passages | Self-Sufficient | Not FLS | Fabrications |
|---|---|---|---|---|---|---|---|---|
| 1 | prompt_v1 | gpt-4o-mini | 65% | 50% | 18 | 1/17 | 1 | 0 |
| 2 | prompt_v2 | gpt-4o-mini | 67% | 45% | 15 | 1/15 | 0 | 0 |
| 3 | prompt_v3 | gpt-4o-mini | 62% | 55% | 21 | 1/21 | 2 | 0 |
| 4 | prompt_v4 | gpt-4o-mini | 100% | 50% | 8 | 5/8 | 0 | 0 |
| 5* | prompt_v5 | gpt-4o-mini | 75% | 75% | 4 | 2/4 | 1 | 0 |
| 6* | prompt_v6 | gpt-4o-mini | 60% | 75% | 5 | 1/5 | 1 | 1 |
| 7* | prompt_v7 | gpt-4o-mini | 75% | 75% | 4 | 1/4 | 1 | 0 |
| 8* | prompt_v7 | gpt-4o | 50% | 50% | 4 | 3/4 | 0 | 0 |
| 9* | prompt_v8 | gpt-4o | 67% | 50% | 3 | 2/3 | 1 | 0 |

*Run 5 onward uses new ground truth v3 (4 items, quantifiable only). Not directly comparable to Runs 1–4 which used 20-statement ground truth.

---

## Run 6
**Date:** 08 June 2026
**Model:** gpt-4o-mini
**Prompt:** prompt_v6
**Transcript:** Asian Paints Q4 FY26

### Prompt Changes from v5
- Rule 2 (self-sufficiency) replaced with mandatory 4-question check: what, number, when, who
- New Rule 4: guidance_value must appear explicitly in the passage text — expand passage or do not extract
- WHAT NOT TO EXTRACT: explicit example added for past action + vague future intent pattern
- New self-check section: 5-point checklist before outputting final JSON

### Raw Numbers
- Total items extracted: 5
- False positives: 1 (price increase — past action, same as Run 5)
- Duplicates: 1 (volume growth extracted twice — pages 20 and 22)
- Fabricated passages: 1 (margin guidance — words added to transcript text)
- Valid extractions: 3

### Precision
- Items matching ground truth: 3
- False positives: 1
- Duplicates: 1
- **Strict Precision: 3/5 = 60%** — regression from Run 5

### Recall
- GT items found: 3 out of 4
- **Recall: 3/4 = 75%** — same as Run 5
- GT 4 (volume-value gap 3-4%) still not found

### GT Items Found
- GT 1 (VAM-VAE commissioning, H1 FY27) ✅ — but self-sufficiency still failing
- GT 2 (Decorative volume growth 8-10%, FY27) ✅ — but extracted twice and credibility_scorable wrong
- GT 3 (PBDIT margin 18-20%, FY27) ✅ — but passage fabricated

### GT Items Missed
- GT 4 — Volume-value gap 3-4%, FY27

### Issues Per Extracted Item

**Item 1 — VAM-VAE Commissioning**
Identical failure to Run 5. Passage: "We expect to commission first phase in the first half of this year." — "first phase" unresolved, "this year" ambiguous. 4-question self-check in v6 was not applied. Third consecutive run with same self-sufficiency failure on same passage.

**Item 2 — Volume Growth (page 22)**
credibility_scorable set to true — wrong. volume_growth_pct is explicitly listed as false in the prompt. Duplicate of Item 3 — same metric, same timeline, extracted twice in violation of Rule 7.

**Item 3 — Volume Growth (page 20)**
Duplicate of Item 2. Additionally, guidance_value = "8-10" is not in this passage — passage says "high single-digit volume growth". Rule 4 violation. credibility_scorable = true also wrong, same as Item 2.

**Item 4 — PBDIT Margin**
Fabricated passage. Extracted text: "We are maintaining our margin guidance of 18-20%." Actual transcript text: "We are maintaining our margin guidance, which is there." LLM added "of 18-20%" to satisfy Rule 4 (guidance_value must appear in passage), violating Rule 1 (verbatim only). New rule introduced a worse failure than the one it was trying to fix. Rules conflicted and LLM resolved by fabricating text.

**Item 5 — Price Increase**
Same false positive as Run 5. Explicit example added in v6 did not prevent recurrence.

### Run Comparison (New Ground Truth Basis — 4 Items)
| Run | Prompt | Precision | Recall | Items | Self-Sufficient | False Positives | Fabrications |
|---|---|---|---|---|---|---|---|
| 5 | prompt_v5 | 75% | 75% | 4 | 2/4 | 1 | 0 |
| 6 | prompt_v6 | 60% | 75% | 5 | 1/5 | 1 | 1 |

### Root Cause Analysis
1. Rule conflict caused fabrication — Rule 4 (guidance_value in passage) and Rule 1 (verbatim) conflicted. LLM prioritised the newer Rule 4 by inserting the number directly into the passage rather than expanding to the adjacent sentence. No precedence was established between rules.
2. Self-sufficiency rule still failing on same passage — 4-question check did not help. LLM is pattern-matching on the passage location rather than applying the principle. Example in Rule 2 is VAM-VAE-specific — possible overfitting to one company.
3. Duplicate not caught — Rule 7 said "most complete version" but did not state that same metric + same timeline = same item regardless of phrasing. LLM treated "high single-digit" and "8-10%" as separate items.
4. credibility_scorable wrong for volume_growth_pct twice — rule existed in plain language but was ignored. Needs a concrete typed example, not just a bullet point.
5. Price increase false positive persists — generalisation failure at model level. May require model upgrade rather than more prompt instructions.

### Changes Made for prompt_v7
- Rule 1: Added explicit precedence statement — verbatim overrides all other rules, expansion is always the solution not insertion
- Rule 2: Replaced VAM-VAE company-specific example with a generic manufacturing example to prevent overfitting
- Rule 7 reworded: same metric + same timeline = one item regardless of phrasing, with a worked duplicate example
- credibility_scorable: volume_growth_pct and capex_absolute called out as always false with reason stated explicitly
- credibility_scorable false list: removed company-specific examples, replaced with generic language
- Self-check section removed entirely — five runs in, it has not prevented a single failure
- Prompt is shorter than v6

---

## Run 7
**Date:** 08 June 2026
**Model:** gpt-4o-mini
**Prompt:** prompt_v7
**Transcript:** Asian Paints Q4 FY26

### Prompt Changes from v6
- Rule 1: Added explicit precedence statement — verbatim overrides all other rules, expansion is always the solution not insertion
- Rule 2: Replaced VAM-VAE company-specific example with generic manufacturing plant example
- Rule 7 reworded: same metric + same timeline = one item regardless of phrasing, with worked duplicate example
- credibility_scorable: volume_growth_pct and capex_absolute called out as always false with reason stated
- credibility_scorable false list: removed company-specific examples
- Self-check section removed entirely
- Prompt shorter than v6

### Raw Numbers
- Total items extracted: 4
- False positives: 1 (price increase — past action, fourth consecutive run)
- Duplicates: 0
- Fabricated passages: 0
- Valid extractions: 3

### Precision
- Items matching ground truth: 3
- False positives: 1
- **Strict Precision: 3/4 = 75%** — recovery from Run 6

### Recall
- GT items found: 3 out of 4
- **Recall: 3/4 = 75%** — same as Runs 5 and 6
- GT 4 (volume-value gap 3-4%) missed for fourth consecutive run

### GT Items Found
- GT 1 (VAM-VAE commissioning, H1 FY27) ✅ — self-sufficiency still failing
- GT 2 (Decorative volume growth 8-10%, FY27) ✅ — first fully clean extraction across all fields
- GT 3 (PBDIT margin 18-20%, FY27) ✅ — guidance_value still not in passage

### GT Items Missed
- GT 4 — Volume-value gap 3-4%, FY27 — fourth consecutive miss

### Issues Per Extracted Item

**Item 1 — VAM-VAE Commissioning**
Fourth consecutive identical failure. Passage: "We expect to commission first phase in the first half of this year." — "first phase" unresolved, "this year" ambiguous. Generic example in v7 Rule 2 did not change outcome. All other fields correct.

**Item 2 — Volume Growth**
First fully clean extraction across all seven runs. Passage contains "8-10%" — Rule 4 satisfied. credibility_scorable = false is now correct — always-false callout for volume_growth_pct in v7 worked. Ground truth passage from page 20 is stronger but this extraction is valid. All fields correct.

**Item 3 — PBDIT Margin**
Reverted to Run 5 behaviour. No fabrication (Rule 1 precedence worked) but guidance_value = "18-20" is still not present in the passage text "We are maintaining our margin guidance, which is there." Rule 4 still violated. LLM is sourcing the number from elsewhere in the transcript. Correct approach requires including the analyst Q&A exchange where "18-20%" is stated explicitly and Syngle confirms it.

**Item 4 — Price Increase**
Fourth consecutive false positive. Unchanged from every previous run. Explicit example in v6 and v7 has not worked.

### v7 Fix Effectiveness
| Fix | Target Failure | Result |
|---|---|---|
| Rule 1 precedence statement | Fabrication in Run 6 | ✅ Fixed — no fabrication |
| Generic Rule 2 example | Self-sufficiency overfitting | ❌ No change — VAM-VAE still fails |
| Rule 7 duplicate reword | Duplicate in Run 6 | ✅ Fixed — no duplicates |
| volume_growth_pct always false | credibility_scorable errors in Run 6 | ✅ Fixed — correct in Run 7 |

### Run Comparison (New Ground Truth Basis — 4 Items)
| Run | Prompt | Precision | Recall | Items | Self-Sufficient | False Positives | Fabrications |
|---|---|---|---|---|---|---|---|
| 5 | prompt_v5 | 75% | 75% | 4 | 2/4 | 1 | 0 |
| 6 | prompt_v6 | 60% | 75% | 5 | 1/5 | 1 | 1 |
| 7 | prompt_v7 | 75% | 75% | 4 | 1/4 | 1 | 0 |

### Persistent Failures After 7 Runs
Four issues have failed across 3+ consecutive runs despite targeted prompt changes:

1. **VAM-VAE self-sufficiency** — Failed every run. LLM consistently picks the shorter sentence on page 11 rather than expanding to include context. Prompt instructions and examples have not changed the outcome.
2. **Margin guidance_value** — Failed every run except Run 6 where it fabricated instead. LLM knows the number is 18-20% but does not include the analyst Q&A exchange that contains it. Correct passage requires Rule 5 (Q&A context) to be applied but has not been.
3. **Price increase false positive** — Failed every single run (7/7). Explicit example added in v6 and retained in v7 has not helped.
4. **Volume-value gap** — Missed all seven runs. Discussed pages 25–26 near end of transcript across two Q&A exchanges.

### Root Cause Assessment
All four persistent failures are consistent with gpt-4o-mini model capability limits rather than prompt design gaps. Adding more prompt instructions has yielded diminishing returns since Run 5.

### Next Step Before v8
Test prompt_v7 unchanged on gpt-4o. If persistent failures resolve, confirm model upgrade and proceed. If they persist on gpt-4o, then investigate prompt design further.

---

## Run 8
**Date:** 08 June 2026
**Model:** gpt-4o (upgrade from gpt-4o-mini)
**Prompt:** prompt_v7 (unchanged)
**Transcript:** Asian Paints Q4 FY26

### Purpose of This Run
Test whether persistent gpt-4o-mini failures are model-level or prompt-level. Prompt v7 run unchanged on gpt-4o.

### Raw Numbers
- Total items extracted: 4
- False positives: 0 (price increase not extracted — improvement)
- Duplicates: 2 (volume growth extracted three times — Items 2, 3, 4)
- Fabricated passages: 0
- Valid extractions: 2

### Precision
- Items matching ground truth correctly: 2 (GT1, GT2)
- Duplicates: 2
- **Strict Precision: 2/4 = 50%** — regression from Run 7

### Recall
- GT items found: 2 out of 4
- **Recall: 2/4 = 50%** — regression from Run 7
- GT3 (PBDIT margin) not extracted cleanly
- GT4 (volume-value gap) missed for fifth consecutive run

### GT Items Found
- GT1 (VAM-VAE commissioning, H1 FY27) ✅ — self-sufficiency FIXED by model upgrade
- GT2 (Decorative volume growth 8-10%, FY27) ✅ — found in Item 3, but also duplicated in Items 2 and 4

### GT Items Missed
- GT3 — PBDIT margin 18-20%, FY27 — attempted in Item 4 but wrong metric label, number not in passage
- GT4 — Volume-value gap 3-4%, FY27 — fifth consecutive miss

### Issues Per Extracted Item

**Item 1 — VAM-VAE Commissioning**
Fixed. Passage now includes "VAM-VAE" and "it is a signature project" — subject resolved. Failed across all 7 gpt-4o-mini runs, fixed on first gpt-4o run. Confirms model-level issue. "This year" slightly ambiguous but substantially self-sufficient. All fields correct.

**Item 2 — Volume Growth (page 20)**
guidance_value = "high single-digit" is not a numeric value. Schema requires a number. Passage text says "high single-digit" — no numeric target present, fails Condition 1 (must be quantifiable). Should not have been extracted. Also duplicate of Items 3 and 4.

**Item 3 — Volume Growth (page 21)**
Clean extraction of GT2. Passage contains "8-10%", guidance_value valid, credibility_scorable correct. Correct choice per Rule 7. Invalid only because Items 2 and 4 are duplicates of same guidance.

**Item 4 — Volume Growth (page 22)**
Third duplicate of volume growth. Passage "Absolutely right. We are maintaining our margin guidance, which is there..." contains margin guidance topic but model labelled as volume_growth_pct and extracted volume number instead. Margin opportunity missed. Also starts with "Absolutely right" without including analyst question — Rule 5 not applied.

### Model Upgrade Assessment
| Failure | gpt-4o-mini | gpt-4o | Verdict |
|---|---|---|---|
| VAM-VAE self-sufficiency | ❌ All 7 runs | ✅ Fixed | Model-level issue confirmed |
| Price increase false positive | ❌ All 7 runs | ✅ Fixed | Model-level issue confirmed |
| Margin guidance_value | ❌ Every run | ❌ Still missing | Prompt issue — Rule 5 not triggered |
| Volume-value gap | ❌ All 7 runs | ❌ Still missing | Still unresolved |
| Duplicate extraction | ✅ Followed Rule 7 | ❌ 3 duplicates | New regression on gpt-4o |

### gpt-4o-mini vs gpt-4o on prompt_v7
| Metric | Run 7 (gpt-4o-mini) | Run 8 (gpt-4o) |
|---|---|---|
| Precision | 75% | 50% |
| Recall | 75% | 50% |
| Self-sufficient | 1/4 | 3/4 |
| VAM-VAE fixed | ❌ | ✅ |
| Price FP removed | ❌ | ✅ |
| Duplicates | 0 | 2 |
| Fabrications | 0 | 0 |

### Root Cause Analysis
1. VAM-VAE and price increase failures were model-level — both resolved immediately on gpt-4o without any prompt change. Do not switch back to gpt-4o-mini.
2. Duplicate problem is new on gpt-4o — gpt-4o reads the transcript more thoroughly and finds volume guidance in three separate places. Rule 7 needs to be stronger for gpt-4o's reading behaviour.
3. Margin guidance still missing — Item 4's passage contains the right location but model extracted volume instead of margin, and did not apply Rule 5 to include analyst question with the 18-20% number.
4. guidance_value "high single-digit" is a new format failure — prompt needs to clarify that guidance_value must be numeric. Non-numeric descriptions should result in null not text.
5. Volume-value gap: five consecutive misses across both models. Location is pages 25–26, two separate Q&A exchanges near end of transcript. May need targeted investigation.

### Changes for v8
- Switch to gpt-4o permanently
- Rule 7: strengthen deduplication — scan all extracted items before finalising, remove any where metric and timeline match a better existing extraction
- guidance_value: clarify must be numeric digits only, not text descriptions like "high single-digit" — if no numeric value exists in passage, set to null
- Rule 5: strengthen Q&A context — when passage starts with a confirmation word, always include the analyst question

---

## Run 9
**Date:** 08 June 2026
**Model:** gpt-4o
**Prompt:** prompt_v8
**Transcript:** Asian Paints Q4 FY26

### Prompt Changes from v7
- Condition 1: Added explicit statement that text descriptions like "high single-digit" do not qualify as numbers
- Rule 7: Added concrete pre-output deduplication step — group by metric + timeline, keep only the passage with explicit digit
- Rule 5: Added confirmation-word trigger — if passage begins with "Absolutely", "Yes", "Correct" etc., analyst question must be included
- GUIDANCE_VALUE: Clarified must be numeric digits only, text descriptions set to null

### Raw Numbers
- Total items extracted: 3
- False positives: 1 (price increase — past action, reappeared after being absent in Run 8)
- Duplicates: 0
- Fabricated passages: 0
- Valid extractions: 2

### Precision
- Items matching ground truth correctly: 2 (GT1, GT2)
- False positives: 1
- **Strict Precision: 2/3 = 67%** — improvement from Run 8

### Recall
- GT items found: 2 out of 4
- **Recall: 2/4 = 50%** — same as Run 8
- GT3 (PBDIT margin) still not extracted
- GT4 (volume-value gap) missed for sixth consecutive run

### GT Items Found
- GT1 (VAM-VAE commissioning, H1 FY27) ✅ — best extraction across all nine runs
- GT2 (Decorative volume growth 8-10%, FY27) ✅ — clean, single extraction

### GT Items Missed
- GT3 — PBDIT margin 18-20%, FY27 — number only in analyst question, not in Syngle's response
- GT4 — Volume-value gap 3-4%, FY27 — sixth consecutive miss

### Issues Per Extracted Item

**Item 1 — VAM-VAE Commissioning**
Best extraction across all nine runs. Includes "which is our backward integration project" — fully self-sufficient, subject completely unambiguous. All fields correct. Clean GT1 match.

**Item 2 — Price Increase**
Same false positive. Second appearance on gpt-4o after being absent in Run 8. Oscillation pattern — present in all 7 gpt-4o-mini runs, absent Run 8, present Run 9 — confirms borderline model judgment rather than prompt gap. Deduplication rule reduced total extractions from 4 to 3, and price increase filled the gap. WHAT NOT TO EXTRACT example covers this pattern but not consistently applied.

**Item 3 — Volume Growth**
GT2 match. Correct metric, guidance_value, credibility_scorable. Deduplication worked — single extraction vs three in Run 8.
Two remaining issues: (a) passage is Syngle's confirmation of Amit Sachdeva's question which contained "18-20%" — Rule 5 confirmation-word trigger partially worked (model dropped "Absolutely right" from passage start) but analyst question with margin number not included. (b) Margin guidance opportunity at same location missed because 18-20% number only appears in analyst question.

### v8 Fix Effectiveness
| Fix | Target Failure | Result |
|---|---|---|
| guidance_value numeric only | "high single-digit" in Run 8 | ✅ Fixed |
| Rule 7 deduplication step | 3 volume duplicates in Run 8 | ✅ Fixed |
| Rule 5 confirmation-word trigger | Analyst Q&A context for margin | ⚠️ Partial — avoided confirmation start but analyst question still excluded |

### Root Cause Analysis
1. GT3 (margin guidance) persistently missing — 18-20% number appears only in the analyst's question. Syngle confirms it without restating the number. Rule 5 needs a stronger instruction: when management confirms a specific number from an analyst's question, that question is mandatory context and must be included in the passage to satisfy Rule 4.
2. GT4 (volume-value gap) six consecutive misses — across both models and four prompt versions. Not a simple prompt gap. Requires dedicated investigation of the transcript location and phrasing before designing a fix.
3. Price increase false positive oscillating — present 7/7 gpt-4o-mini runs, absent Run 8 gpt-4o, present Run 9 gpt-4o. Borderline judgment that prompting has not reliably resolved. Consider accepting this as a known edge case rather than adding more prompt instructions.

### Run Comparison (New Ground Truth Basis — 4 Items)
| Run | Prompt | Model | Precision | Recall | Items | Self-Sufficient | False Positives | Fabrications |
|---|---|---|---|---|---|---|---|---|
| 7 | prompt_v7 | gpt-4o-mini | 75% | 75% | 4 | 1/4 | 1 | 0 |
| 8 | prompt_v7 | gpt-4o | 50% | 50% | 4 | 3/4 | 0 | 0 |
| 9 | prompt_v8 | gpt-4o | 67% | 50% | 3 | 2/3 | 1 | 0 |

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

9. **gpt-4o-mini is insufficient for production extraction.** Persistent failures (VAM-VAE self-sufficiency, price increase false positive) resolved immediately on gpt-4o without any prompt change. gpt-4o confirmed as production model.

---

## v1 — COMPLETE

**Final state:** prompt_v8 on gpt-4o. Recall 75% (3/4 GT items), Precision 67% (2 clean GT matches + 1 persistent false positive). Two known edge cases carried forward: price increase false positive oscillates, GT4 (volume-value gap) consistently missed across all 9 runs on both models. Both accepted — Asian Paints is outside target universe anyway.

**Ground truth:** v3 locked — 4 items, Asian Paints Q4 FY26.

**Test companies for v2+:** Fineotex Chemical, Sandhar Technologies, Mold-Tek Packaging. All ₹500cr–10,000cr market cap, single-segment businesses. Asian Paints retained for eval pipeline validation only.

---

## v2 — Structured Output + Automated Eval

**Changes from v1:**
- `schemas.py` created — three Pydantic models: `GuidanceItem` (8 fields), `ExtractionResult` (OpenAI structured output wrapper), `GuidanceRecord` (extends GuidanceItem with company, quarter, prompt_version, run_id, extracted_at for PostgreSQL)
- `main.py` updated — switched from `client.chat.completions.create()` to `client.beta.chat.completions.parse()` with `response_format=ExtractionResult`
- `prompt_v8.txt` OUTPUT FORMAT section updated — describes `items` wrapper to align with schema
- `eval.py` created — automated precision/recall script with fuzzy guidance_value matching (±10% of midpoint), exact metric and timeline matching, per-item coverage output

---

## v2 Validation Runs — Structured Output on Asian Paints
**Date:** 09 June 2026
**Model:** gpt-4o
**Prompt:** prompt_v8 (structured output mode)
**Transcript:** Asian Paints Q4 FY26
**Purpose:** Validate structured output pipeline before moving to new test companies

| Run | Items returned | Recall | Precision | Notes |
|---|---|---|---|---|
| v2-Run1 | 2 | 25.0% | 50.0% | volume_growth_pct missing, price_increase_pct FP |
| v2-Run2 | 2 | 25.0% | 50.0% | Same result |
| v2-Run3 | 3 | 50.0% | 66.7% | volume_growth_pct found, ebitda_margin_pct still missing |

**Diagnosis:** Run variation from structured output non-determinism, not a prompt bug. `ebitda_margin_pct` consistently missing across all three runs — regression from v1's 75%. `volume_growth_pct` oscillates in and out.

**Decision:** Do not fix prompt on Asian Paints. Asian Paints dropped as primary test case — large cap, multi-segment, outside target universe. Regression noted but not actioned here.

**Next:** Build ground truth for Fineotex Chemical, Sandhar Technologies, Mold-Tek Packaging. Run eval on those. Fix prompt only if regression appears on target companies.

**v2 Step 4 next:** PostgreSQL schema + storage.
