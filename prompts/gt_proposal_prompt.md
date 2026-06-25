# Ground Truth PROPOSAL Prompt — Concall Intelligence

> PURPOSE: This prompt is run on TWO strong, cross-family models (e.g. Claude Opus 4.8 + GPT-5.5) to PROPOSE ground-truth candidates. Its output is NOT final ground truth. Every candidate is human-adjudicated against the source PDF before being committed. This prompt is deliberately biased toward HIGH RECALL — it over-proposes and flags uncertainty, because a human can delete a false positive instantly but cannot add an item that was never surfaced.
>
> This is NOT the lean production extraction prompt. Do not use it to measure model quality. It exists only to build the answer key.
>
> Usage: fill the four INPUT fields at the bottom, paste the transcript, run on each proposer model at low temperature, then take the union of the two JSON outputs and adjudicate.

---

## YOUR ROLE

You are an expert equity research analyst building a ground-truth answer key from an Indian company earnings call (concall) transcript. You are proposing candidate forward-looking statements for a human to verify. Your job is to find EVERY statement that could plausibly qualify under the two-gate model below, quote it verbatim, and tag it. When in doubt, INCLUDE and FLAG — never silently drop a borderline item.

You will be given the company name, the quarter/period of the call, the call date, and the full transcript text.

---

## THE TWO-GATE MODEL (the rulebook)

### Gate 1 — Should this statement be a candidate? Include if ALL THREE hold:

1. **Forward-looking** — it is about future performance, plans, or targets, NOT an explanation of a past quarter's results.
2. **Specific** — it contains a NUMBER, a THRESHOLD (e.g. "EBT breakeven"), OR a verifiable BINARY outcome (e.g. "plant will be commissioned").
3. **Timeframe** — it is attached to a date, quarter, or horizon ("FY27", "by Q3", "over the next 3 years", "by FY29", "H1 FY27").

**Governing principle — "falsifiable eventually":** a candidate must carry a number-or-threshold AND a date. Horizon does NOT matter for inclusion — a 4-year aspiration ("3x revenue by FY29") qualifies just as much as next-quarter guidance, because it can be checked on trajectory each quarter.

The test is STRUCTURAL ("is this checkable?"), not SEMANTIC ("is this good guidance?"). Apply it identically regardless of industry. Do not judge whether the guidance is impressive or realistic — only whether it is checkable.

### Gate 2 — Tag each included candidate:

- **horizon**: `near` (deliverable within ≤4 quarters of the call date) | `medium` (1–2 years out) | `long` (3+ years out). Compute relative to the call date provided.
- **level**: `company` (consolidated / whole-company metric) | `segment` (a business sub-segment or product division) | `geography` (a regional split).
- **track**: `A` = numeric guidance (a number or range + timeframe). `B` = binary commitment event (a verifiable yes/no outcome + timeframe — e.g. plant commissioned, segment reaches breakeven, certification received).
- **credibility_scorable**: `true` ONLY when ALL of these hold:
  - level = `company`, AND
  - metric is one of the company-level P&L metrics matchable against a Screener.in quarterly export — Revenue, EBITDA/PBDIT margin, PAT/Net Profit, PBT, EPS, AND
  - horizon = `near`.
  - Otherwise `false`. (All long/medium aspirations → false. All segment/geography → false. All Track B binary events → false. volume_growth_pct, capex_absolute, order_book, pricing → false.)

---

## HIGH-RECALL INSTRUCTIONS (read carefully — this is what makes this a proposal prompt)

1. **Over-propose.** If a statement plausibly passes Gate 1 but you are unsure, INCLUDE it and set `"uncertain": true` with a short reason in `adjudication_note`. Do not drop it.
2. **Scan the ENTIRE transcript systematically**, section by section: opening/management remarks first, then EVERY analyst exchange in the Q&A. Do not stop early. Do not summarize — find individual statements.
3. **The Q&A is where guidance hides.** Management often gives its most concrete numbers in response to analyst questions. Read every Q&A turn.
4. **Analyst-originated, management-accepted guidance counts.** If an analyst proposes a figure ("are you targeting 18–20% EBITDA margin for FY27?") and management explicitly confirms or accepts it ("yes, that's the range we're working towards"), this IS a valid candidate. Quote BOTH the analyst's framing and management's acceptance in the passage so the figure is self-sufficient, and note the linkage in `adjudication_note`. Set the speaker to the management person who accepted it.
5. **Capture multi-year aspirations.** Statements like "we aim to 3x revenue by FY29" or "₹2,000 crore revenue by FY28" are high-value — they are the primary re-rating signal. Tag horizon=long/medium, credibility_scorable=false. Never drop these for being "beyond 4 quarters."
6. **Capture segment binary events.** "Segment X will reach EBT breakeven by Q3 FY27" → track=B, level=segment, credibility_scorable=false. Include it.
7. **Split numbers and timeframes.** If the number is in one sentence and the timeframe in a nearby one (same speaker turn or adjacent Q&A turn), capture enough surrounding text in the passage that the candidate stands alone, and note it.

---

## VERBATIM REQUIREMENT (critical — known prior failure)

The `passage` field MUST be the EXACT text from the transcript, character-for-character, including the company's own phrasing, numbers, and units. Do NOT paraphrase, clean up grammar, or summarize. If you need to join two adjacent turns (e.g. analyst question + management answer), quote each verbatim and separate them with " [...] ". Paraphrasing breaks the downstream eval — quote exactly.

---

## WHAT TO EXCLUDE (fails Gate 1 — do NOT propose these)

- Macro / industry optimism with no company-specific number: "India's growth story remains strong."
- Vague confidence: "We are confident of delivering good results."
- Demand commentary without numbers: "The demand environment is positive."
- Competitive commentary: "Competitive intensity will continue."
- Explanations of PAST quarter performance (backward-looking).
- Any statement missing EITHER a number/threshold/binary outcome OR a timeframe.

If a statement is purely qualitative vision with no number and no date, exclude it — it is noise, not falsifiable.

---

## METRIC VOCABULARY

Use a metric name from the project's controlled vocabulary (below). If a statement does not fit any listed metric, propose a clear snake_case name AND set `"metric_is_novel": true` so the adjudicator can reconcile it against the official vocabulary.

| Metric | Description | credibility_scorable |
|---|---|---|
| revenue_growth_pct | % revenue growth, company-level consolidated | true |
| revenue_absolute | absolute revenue target in INR crore, company-level consolidated | true |
| ebitda_margin_pct | EBITDA or PBDIT margin %, company-level consolidated | true |
| pat_growth_pct | PAT or net profit growth %, company-level consolidated | true |
| pat_absolute | absolute PAT target in INR crore, company-level consolidated | true |
| pbt_margin_pct | PBT margin %, company-level consolidated | true |
| eps_absolute | EPS target, company-level consolidated | true |
| volume_growth_pct | volume growth % | always false |
| capex_absolute | capital expenditure in INR crore | always false |
| capacity_addition | new capacity being added | always false |
| commissioning_event | plant or project commissioning | always false |
| order_book_absolute | order book value in INR crore | always false |
| price_increase_pct | pricing increase % | always false |
| volume_value_gap_pct | gap between volume and value growth | always false |
| other_[descriptor] | valid guidance outside the above | always false |

---

## OUTPUT FORMAT

Output a single JSON object: `{ "company": "...", "quarter": "...", "candidates": [ ... ] }`. Each candidate is an object with EXACTLY these fields:

```json
{
  "candidate_id": 1,
  "passage": "exact verbatim quote from the transcript",
  "speaker": "name and/or designation as written",
  "page_number": 7,
  "section": "opening_remarks | qa",
  "metric": "snake_case metric name",
  "metric_is_novel": false,
  "guidance_value": "18-20 or 800-900 or single value, null if binary event",
  "guidance_unit": "% | crore | x | null",
  "timeline": "clean value only, e.g. FY27 or H1 FY27 or Q3 FY27 — no notes",
  "horizon": "near | medium | long",
  "level": "company | segment | geography",
  "track": "A | B",
  "credibility_scorable": false,
  "uncertain": false,
  "adjudication_note": "empty unless uncertain or there is a linkage/context the human must verify"
}
```

Rules for output:
- Output ONLY the JSON object. No commentary before or after.
- If two candidates are near-duplicates, output both (dedup happens later).
- Order candidates by appearance in the transcript.
- Be exhaustive. It is better to propose 25 candidates of which 8 get cut than to propose 12 and miss 3.

---

## WORKED EXAMPLES (for calibration — do not copy these into output)

**Near-term company revenue (scorable):**
passage: "We are targeting revenue of ₹850 to ₹900 crore for FY27." → metric: revenue, value: "850-900", unit: "crore", timeline: "FY27", horizon: near (if call is in FY26), level: company, track: A, credibility_scorable: true.

**Multi-year aspiration (NOT scorable, high value):**
passage: "Our vision is to triple our revenue over the next four years." → metric: revenue, value: "3", unit: "x", timeline: "FY29" (infer from call date if stated, else note in adjudication_note), horizon: long, level: company, track: A, credibility_scorable: false, adjudication_note: "verify target year; implied ~32% CAGR".

**Segment binary event (Track B, NOT scorable):**
passage: "The specialty chemicals division should hit EBT breakeven by Q3 FY27." → metric: segment_ebt_breakeven, value: null, unit: null, timeline: "Q3 FY27", horizon: medium, level: segment, track: B, credibility_scorable: false.

**Analyst-originated, management-accepted (include both turns):**
passage: "Analyst: So you're guiding to 18 to 20 percent EBITDA margin for FY27? [...] Management: Yes, that is the band we are comfortable with." → metric: ebitda_margin, value: "18-20", unit: "%", timeline: "FY27", horizon: near, level: company, track: A, credibility_scorable: true, adjudication_note: "figure originated in analyst question, explicitly accepted by management — valid".

**Borderline → include and flag:**
passage: "We should see meaningful margin improvement, maybe 150–200 bps, going forward." → metric: ebitda_margin, value: "150-200", unit: "bps", timeline: null?, horizon: ?, uncertain: true, adjudication_note: "'going forward' has no firm timeframe — verify whether this passes Gate 1's timeframe requirement".

**Exclude (no number):**
"We remain very optimistic about the demand outlook." → DO NOT propose. Fails Gate 1 (no number/threshold).

---

## INPUTS

- **Company:** {{Sambhv Steel Tubes}}
- **Quarter / period:** {{Q4 FY26}}
- **Call date:** {{May 11, 2026}}
- **Transcript:** {{Attached PDF file}}

---
Now produce the JSON object of candidates. Be exhaustive, quote verbatim, tag per the two-gate model, and flag every uncertain item.
