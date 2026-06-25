# plan.md — Next Steps: Scope, Ground Truth, Model & Architecture Bake-off

Context doc for the current phase. Read alongside CLAUDE.md (Two-Gate Model section) and PROJECT.md (v1.1).

The goal of this phase: pick the **cheapest model + simplest architecture that clears a pre-set quality bar** for falsifiable-FLS extraction under the new two-gate scope. Decisions are eval-driven, not assumed.

---

## Guardrails (apply to every step below)

1. **Acceptance thresholds are set BEFORE running anything.** No moving goalposts. Proposed bar (tune to taste before starting): recall ≥ 0.85, precision ≥ 0.80, classification/tag accuracy ≥ 0.90. The first config that clears the bar wins — stop there even if a fancier config might be marginally better.
2. **Control variance.** LLM output is stochastic. Use low temperature, an eval set large enough to matter (8–15 transcripts), and 2–3 runs per config. Compare averages, not single lucky draws. A 2-point gap on 4 transcripts is noise.
3. **Hold reasoning effort constant across models** (or test it as an explicit variable). Don't compare "Sonnet 4.6 medium" against an unspecified GPT-5.4 effort level.
4. **Diagnose failure mode, then move the matching axis** — do not climb the escalation ladder blindly (see Step 4).
5. **Keep 1–2 transcripts fully held-out.** Never look at them during prompt iteration. They are the overfitting guard.
6. **Cost is near-irrelevant at this scale** (gap between cheapest and flagship ≈ $20/quarter batched). Optimize for "cheapest that passes the bar," not absolute cheapest. Your time debugging false positives is the expensive resource.

---

## Step 1 — Write the two-gate spec + tag schema (the keystone artifact)

The real deliverable is not a doc edit — it is a precise, written **inclusion test + tag schema** that the prompt, the ground truth, and the eval all reference. The CLAUDE.md / PROJECT.md updates are just where it lives.

- Gate 1 (extract): forward-looking + number/threshold/binary + timeframe. Any horizon. Industry-agnostic.
- Gate 2 (tag): horizon (near/medium/long), level (company/segment/geography), track (A numeric / B binary), credibility_scorable (true only for near + company-level + Screener-matchable P&L metric).
- Governing principle: falsifiable eventually (number-or-threshold AND a date), else noise.

Status: DONE in CLAUDE.md + PROJECT.md v1.1. Keep them as the single source of truth.

---

## Step 2 — Build the eval set + ground truth (LLM-PROPOSED, HUMAN-ADJUDICATED)

GT exists only for the eval set (~8–15 transcripts), NOT for all 600 production transcripts. See "Step 2 detailed playbook" at the bottom of this file.

Non-negotiable: GT is **human-adjudicated**. Do NOT generate GT with an LLM and trust it — scoring a cheap model against LLM-generated GT measures "does the cheap model agree with the expensive one," not correctness. Worse, if the GT-generator shares a family with the model under test, the tested model looks artificially good (shared blind spots). The human is the final authority.

---

## Step 3 — Set acceptance thresholds

Lock precision / recall / tag-accuracy targets now, before any run (see Guardrail 1).

---

## Step 4 — Baseline run, then diagnose

Run the SIMPLEST config first:
- **1-step (extraction + classification in one prompt), whole transcript**, both candidate models (Sonnet 4.6, GPT-5.4), low temp, controlled effort, 2–3 runs each.
- Use a clean extraction prompt aligned to the two-gate spec — NOT the old prompt_v8 (built for the old single-pass scope) and NOT the GT-proposal prompt.
- Measure: precision, recall, tag accuracy, cost/transcript, run-to-run variance.

Then read the failure mode and move the AXIS that fixes it (do not walk the ladder rung by rung):

| Symptom | Diagnosis | Fix (axis to move) |
|---|---|---|
| Items being missed (recall low) | Context / attention problem | Chunk by Stage 0 segments (Axis B) — but see note |
| Items mislabeled, wrong tags, junk let in (precision / tag accuracy low) | Task too complex for one call | Split extraction and classification into 2 calls (Axis A) |
| Both | Move both axes | — |

**Note on chunking:** likely UNNECESSARY now. A 15–20k-token transcript is tiny against a 1M-token window; the "lost in the middle" problem that justified chunking on gpt-4o is far weaker on current models, and chunking raises cost via prompt duplication. Reach for it only if recall genuinely drops on long transcripts. Its real remaining value is per-chunk eval granularity and parallel latency — neither is the current bottleneck.

---

## Step 5 — Stop at the lowest-complexity config that clears the bar

Escalation order of complexity (only go as far as needed):
1. 1-step, whole transcript
2. 2-step (extract → classify), whole transcript  [if precision/tag accuracy fails]
3. chunked, 1-step  [only if recall fails on long transcripts]
4. chunked, 2-step  [last resort]

Validate the winner on the held-out transcripts before declaring done. Commit prompt + config + eval numbers to git.

---

## Step 2 detailed playbook — How to build ground truth

### Prerequisite
The two-gate spec (Step 1) must exist in writing — it is the rulebook for adjudication. Without it, GT decisions are arbitrary.

### A. Select the eval set (8–15 transcripts) — diversity over count
- Spread across sectors: e.g. specialty chemicals, auto-ancillary, packaging, an IT/services name, a capital-goods name. Cross-industry coverage is what makes the structural filter trustworthy.
- Include 2–3 companies you know well (easy to sanity-check during adjudication).
- Include at least one HARD transcript: a multi-segment company with segment-level guidance (exercises level=segment, track=B tags).
- Ensure some transcripts contain long-horizon aspirations ("3x revenue by FYxx") so the new scope is actually tested.
- Set aside 1–2 transcripts as fully held-out (never used during prompt iteration).

### B. Propose candidates with TWO strong, cross-family models
- Use **Opus 4.8 + GPT-5.5 (Pro if budget allows)** as proposers. Cross-family (Anthropic + OpenAI) minimizes shared blind spots; high capability minimizes misses.
- These proposers are deliberately STRONGER and DIFFERENT-family from the models under test (Sonnet 4.6, GPT-5.4). Testing the cheaper sibling against GT built by the stronger sibling + human is exactly the question you want answered.
- Use a dedicated **GT-proposal prompt** (replaces the old ground_truth_extraction_prompt.md), aligned to the two-gate spec, biased toward HIGH RECALL — tell it to over-propose and flag uncertain items. The human cuts false positives easily but cannot add items never surfaced. This prompt can be long/expensive/multi-instruction; it runs once.
- The proposal prompt is NOT the lean extraction prompt under test — keep them separate, or you are testing a prompt against itself.
- Run each transcript through both proposers at low temperature, output in the GT structure (incl. all tags). Take the **union**, deduplicated.

### C. Adjudicate — the human part (irreducible)
For each candidate, verify against the actual transcript:
- **Verbatim check:** is the passage exactly as written in the PDF? Fix paraphrased quotes to exact text (known prior GT issue).
- **Gate 1 check:** forward-looking + number/threshold/binary + timeframe? Keep or cut.
- **Gate 2 check:** are horizon / level / track / credibility_scorable correct? Fix tags.
- **Disagreement cases first:** where the two proposers disagree (one included, one didn't) are the highest-value items — scrutinize hardest.

Then a **completeness pass** (the safety net for shared false-negatives): skim the transcript yourself for any number+date the models both missed. Pay special attention to the Q&A — guidance often surfaces in analyst exchanges, and a valid GT item can originate in an analyst's question that management explicitly accepts.

### D. Lock and version
- Save one GT file per transcript: `data/{company}_{quarter}_ground_truth_v{n}.txt`, matching the exact existing format eval.py parses (double-quoted multi-line `passage:` followed by `speaker:` on the next line) so the eval doesn't break.
- Record which spec version the GT was built against and the date.
- Commit to git with a descriptive multi-line message.
- GT is frozen during an eval run. If scope changes later, re-version GT.

### Effort / cost
- ~8–15 transcripts × 2 proposers ≈ 16–30 API calls — trivial cost (~$1–2 total).
- Human adjudication ≈ 20–40 min/transcript ≈ a few focused hours total. This is the real cost and the irreducible part. 12 well-adjudicated transcripts beat 100 sloppy ones.
