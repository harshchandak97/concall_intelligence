# Ground Truth JUDGE Prompt — Pass 2 (Concall Intelligence)

> PURPOSE: This is the SECOND pass of automated ground-truth generation. Pass 1
> (`gt_proposal_prompt.md`) ran on a powerful model and deliberately OVER-PROPOSED every
> plausibly-quantifiable forward-looking statement to maximise recall. Your job is to act as a
> strict judge: for each proposed candidate, decide whether it genuinely belongs in the ground
> truth under the two-gate model, and if so, finalise its classification. You REPLACE the human
> adjudicator. Be rigorous — a wrong item here corrupts every downstream eval score.

You are given the full transcript and a JSON array of CANDIDATES proposed in Pass 1. Each
candidate is a forward-looking statement quoted verbatim from the transcript, with a draft
classification and (sometimes) an `uncertain` flag and `adjudication_note`.

---

## YOUR TWO JOBS

### Job 1 — JUDGE (keep or drop). Keep a candidate ONLY if ALL hold:

1. **Forward-looking** — about future performance, plans, or targets, NOT an explanation of a
  past quarter's results.
2. **Quantifiable / falsifiable** — it carries a NUMBER, a THRESHOLD (e.g. "EBT breakeven"), OR a
  verifiable BINARY outcome (e.g. "plant will be commissioned"). A purely qualitative vision with
   no number and no checkable event does NOT qualify.
3. **Timeframe** — attached to a date, quarter, or horizon ("FY27", "by Q3", "over 3 years").
4. **Verbatim and self-sufficient** — the `passage` must be exact transcript text, and must itself
  contain the number AND the timeframe. If the candidate's number or date is only implied by
   surrounding context not present in the passage, either DROP it or (if the supporting text
   exists in the transcript) widen the passage to include it.

**Governing principle — "falsifiable eventually."** Horizon does NOT matter for inclusion: a
4-year aspiration ("3x revenue by FY29") is kept just like next-quarter guidance. The test is
STRUCTURAL ("is this checkable?"), not whether the guidance is impressive or realistic.

Drop a candidate if it fails any of the four tests above, or is a near-duplicate of another kept
candidate covering the same (metric, value, timeline) — keep the single best-quoted instance.

### Job 2 — CLASSIFY (finalise tags for every kept candidate).

Re-derive each tag from the transcript; do not blindly trust Pass 1's draft. Compute `horizon`
relative to the call period.

- **metric** — from the controlled vocabulary below. If none fits, use `other_<snake_case>`.
- **guidance_value** — numeric digits or range as a string ("18-20", "200", "3"); `null` for a
binary event with no number.
- **guidance_unit** — exactly as written ("%", "crore", "million", "times", "x"); `null` if n/a.
- **currency** — "INR" | "USD" | null.
- **timeline** — clean period only ("FY27", "H1 FY27", "FY28-FY29"); no notes.
- **horizon** — `near` (≤4 quarters of the call) | `medium` (1–2 years) | `long` (3+ years).
- **level** — `company` (consolidated / whole-company) | `segment` | `geography`.
- **track** — `A` (numeric guidance) | `B` (binary commitment event).
- **credibility_scorable** — `true` ONLY when ALL hold: `level` = company, AND metric ∈
{revenue_growth_pct, revenue_absolute, ebitda_margin_pct, pat_growth_pct, pat_absolute,
pbt_margin_pct, eps_absolute}, AND `horizon` = near, AND value is in INR (not USD/EUR).
Otherwise `false` (all medium/long, all segment/geography, all Track B, volume_growth_pct,
capex_absolute, order_book, pricing, and any `other`_ metric → false).

### Metric controlled vocabulary

`revenue_growth_pct`, `revenue_absolute`, `ebitda_margin_pct`, `pat_growth_pct`, `pat_absolute`,
`pbt_margin_pct`, `eps_absolute`, `volume_growth_pct`, `capex_absolute`, `capacity_addition`,
`commissioning_event`, `order_book_absolute`, `price_increase_pct`, `volume_value_gap_pct`,
`other_<description>`.

---

## OUTPUT FORMAT

Output a SINGLE JSON object and nothing else — no prose before or after, no markdown fences:

```json
{
  "items": [
    {
      "passage": "exact verbatim text from transcript",
      "speaker": "Name and title",
      "page_number": 7,
      "metric": "revenue_absolute",
      "guidance_value": "3000",
      "guidance_unit": "crore",
      "currency": "INR",
      "timeline": "FY29-FY30",
      "horizon": "long",
      "level": "company",
      "track": "A",
      "credibility_scorable": false
    }
  ]
}
```

Include ONLY kept candidates. Drop the Pass-1-only fields (`candidate_id`, `section`,
`metric_is_novel`, `uncertain`, `adjudication_note`). Order items by appearance in the transcript.

---

## INPUTS

- **Company:** {{company}}
- **Call period:** {{call_period}}
- **Pass-1 candidates (JSON):**

{{candidates_json}}

- **Transcript:**

{{transcript_text}}

---

Now judge each candidate and output the final `{ "items": [...] }` ground-truth object.