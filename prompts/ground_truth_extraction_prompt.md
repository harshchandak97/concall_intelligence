# Ground Truth Extraction Prompt

You are extracting forward-looking guidance statements from the attached Indian company earnings call transcript. These items will serve as ground truth for evaluating an automated extraction pipeline. Accuracy is critical — every error here propagates to every eval score downstream.

**Bias toward precision over recall.** If you are uncertain whether a statement qualifies, exclude it and flag it in your notes. A missing item is less harmful than a wrong item.

---

## Extraction Criteria — Two Tracks

A statement qualifies if it fits EITHER track below.

**Track A: Numeric Guidance** — qualifies if ALL of the following:
1. Forward-looking — about the future, not past quarter performance
2. Contains a specific number or numeric range, stated or directly derivable (e.g. "double our INR 20 crore revenue" means INR 40 crore target)
3. Has a timeframe that can be pinned within 4 quarters — explicit (FY27, H1 FY27) or derivable from context ("this financial year" on a May 2026 call = FY27)
4. Trackable — outcome can be verified from the next 1-4 quarterly results or filings
5. Company-specific — management committing to something about their own business, not the industry or economy

**Track B: Commitment Events** — qualifies if ALL of the following:
1. Forward-looking — about the future, not past quarter performance
2. Specific verifiable binary outcome — plant commissioning, project go-live, breakeven achievement, capacity addition
3. Has a timeframe that can be pinned within 4 quarters
4. Trackable — outcome can be verified from quarterly results, filings, or subsequent management commentary
5. Company-specific

---

## What NOT to Extract

- Macro commentary: "India's infrastructure opportunity is large"
- Vague confidence without numbers: "We are very optimistic about the coming year"
- Demand commentary without company-specific numbers: "Demand environment is positive"
- Competitive commentary: "Competition will remain elevated"
- Explanations of past quarter results
- Guidance with a number but no derivable timeframe — "we will reach 20% margins someday" does not qualify

---

## Schema — Every Item Must Have Exactly These 8 Fields

**passage**
Verbatim text from the transcript. Must be self-sufficient — a reader with no other context must understand what is being guided, by whom, and when. Do not paraphrase. Copy exact transcript text including speaker labels. Include as much surrounding context as needed — do not cut for brevity.

For Q&A exchanges: include both the analyst question and management response when the number appears in the analyst's question. Management saying "absolutely", "yes, that's correct", "you are right", or similar in direct response to a specific number constitutes confirmation — include it. Exclude only if management explicitly contradicts, hedges, or redirects away from the number without confirming it.

**speaker**
Name and title of the management respondent. Format: "Name (Title)". For Q&A passages, attribute to the management speaker, not the analyst.

**page_number**
Integer. Use the page number printed in the transcript PDF footer, not your internal count.

**metric**
One value from the controlled vocabulary below. Use the most specific match. If no item fits, use the other_ prefix: e.g. other_ebitda_absolute, other_ev_revenue_absolute.

Controlled Metric Vocabulary:

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

**guidance_value**
Numeric value or range as a string. Examples: "18-20", "8-10", "275-310", "200", "0.25", "40". Set to null for Track B commitment events where no numeric target exists. Always a string, never a float — preserves ranges like "18-20".

**guidance_unit**
Unit of measurement as a string. Examples: "%", "crore", "$ million". Set to null if not applicable.

**timeline**
Clean period string only. No explanatory notes in this field. Examples: "FY27", "H1 FY27", "Q2 FY27", "FY28".
- "This financial year" on a May 2026 call = "FY27"
- "Before 2028" or "before FY28" = "FY28"
- "Going forward" with no year derivable from context = exclude the item entirely

Document any timeline derivation in your post-extraction notes, not in this field.

**credibility_scorable**
true or false. See rules below.

---

## credibility_scorable Rules

Set to TRUE only when ALL three conditions are met:
- Metric is company-level consolidated — not a segment, geography, subsidiary, or product line
- Metric is one of: Revenue (absolute or growth %), EBITDA/PBDIT margin %, PAT/Net Profit, PBT, EPS
- Value is directly matchable against Screener.in quarterly P&L export columns: Net Sales, Operating Profit, OPM%, PBT, Net Profit, EPS

Set to FALSE always for:
- Any segment-level, geography-level, or subsidiary-level metric
- capex_absolute — not a P&L line item
- volume_growth_pct — not in Screener.in P&L
- commissioning_event — binary event, not a P&L metric
- order_book_absolute — not a P&L line item
- price_increase_pct — not a P&L line item
- Any other_ prefixed metric
- Revenue or margin guidance in foreign currency (USD, EUR)
- EBITDA in absolute crore terms (other_ebitda_absolute) — Screener.in shows OPM% only

---

## Edge Cases

**Delta vs absolute guidance:**
If management guides a change in a metric rather than an absolute target — e.g. "margin improvement of 0.25 percentage points" — use other_<metric>_delta as the metric name (e.g. other_ebitda_margin_delta). Do not use the base metric name (e.g. ebitda_margin_pct) for delta guidance; a delta value of 0.25 would be misread as an absolute 0.25% margin target by any downstream eval. guidance_value: "0.25". credibility_scorable: false — a delta cannot be matched directly against Screener.in's reported absolute values.

**Multiplicative guidance:**
"We expect to double revenue from INR 20 crores" means derived target is INR 40 crores. guidance_value: "40". The passage must contain the base number so the derivation is visible.

---

## Output Format

Start with the header line, then list items separated by blank lines:

Extracted Guidance Statements — [Company Name] Q4 FY26

id: 1
guidance: [short label, 5-10 words]
passage: "[verbatim text]"
speaker: [Name (Title)]
page_number: [integer]
metric: [from controlled vocabulary]
guidance_value: [value or null]
guidance_unit: [unit or null]
timeline: [FY27 etc]
credibility_scorable: [true/false]

id: 2
...

---

## After All Items — Add a Notes Section

1. Any borderline items considered but excluded, and why
2. Any items where the number originated in the analyst's question rather than management's own statement
3. Any items where the timeline was derived rather than explicit, and the derivation logic
4. Any ambiguities in the transcript that affected extraction decisions
