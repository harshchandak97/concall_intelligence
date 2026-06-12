# Extraction Pipeline Architecture — Request for Technical Design

## Who I Am and What I'm Building

I am building a personal tool for Indian retail equity investing. The tool downloads earnings call transcripts from Indian listed companies, extracts every quantifiable forward-looking guidance statement made by management, and later scores each company on whether management delivered on its guidance (credibility scoring).

Target universe: Indian listed companies with market cap between INR 500 crore and INR 10,000 crore. These are mostly single-segment businesses where management guidance maps cleanly to company-level P&L metrics. Transcripts are in English, PDF format, typically 40-80 pages, 40,000-80,000 characters of text.

---

## The Extraction Task

From a single earnings call transcript, I need to extract every statement where management is:
- Guiding a specific numeric target (revenue, margins, profit, volume growth, capex) with a timeframe
- OR committing to a specific verifiable event (plant commissioning, project go-live, breakeven) with a timeframe

Both types must be verifiable within 4 quarters of the call date.

### What qualifies:

**Numeric guidance (Track A):** Must have a specific digit or range + a timeframe pinnable within 4 quarters.
- "We expect EBITDA margins of 18-20% in FY27" — qualifies
- "We are targeting revenue of INR 800-900 crore in FY27" — qualifies
- "We expect to double our EV revenue from INR 20 crore this year" — qualifies (derived target = INR 40 crore)
- "We expect high single-digit growth" — does NOT qualify (no digit)
- "Margins will improve going forward" — does NOT qualify (no number, no timeframe)

**Commitment events (Track B):** Specific verifiable binary outcome + timeframe.
- "We expect to commission our new VAM-VAE plant in H1 FY27" — qualifies
- "Romania operations expected to reach breakeven by FY28" — qualifies

### Required output schema per item (8 fields):
- **passage**: verbatim text from transcript, self-sufficient, includes Q&A context if needed
- **speaker**: name and title of management speaker
- **page_number**: integer
- **metric**: from controlled vocabulary (revenue_growth_pct, revenue_absolute, ebitda_margin_pct, pat_growth_pct, pat_absolute, pbt_margin_pct, eps_absolute, volume_growth_pct, capex_absolute, capacity_addition, commissioning_event, order_book_absolute, price_increase_pct, volume_value_gap_pct, other_[descriptor])
- **guidance_value**: numeric string or range e.g. "18-20", "275-310", null for binary events
- **guidance_unit**: "%" or "crore" or "$ million" or null
- **timeline**: clean string e.g. "FY27", "H1 FY27", "FY28"
- **credibility_scorable**: true/false (true only for company-level Revenue, EBITDA margin%, PAT, PBT, EPS)

---

## Current Approach and Why It Is Failing

### What I am doing now:

Single-pass extraction: I send the full transcript text (50,000+ characters) to gpt-4o in one API call with a detailed prompt. The prompt instructs the model to read the entire transcript and return a structured JSON array of all qualifying guidance items via OpenAI's structured output mode (Pydantic schema via `response_format`).

I have iterated through 9 prompt versions (v1–v9). The current production prompt is v8. v9 was an attempted improvement that made things worse (explained below).

---

### Performance measured against hand-labelled ground truth:

**Primary test companies (target universe — single-segment, INR 1,000–8,000 crore market cap):**

| Company | GT Items | v8 Recall | v8 Precision | v8 LLM Items | v9 Recall | v9 Precision | v9 LLM Items |
|---|---|---|---|---|---|---|---|
| Fineotex Chemical Q4 FY26 | 2 | 50% | 33.3% | 3 | 50% | 10% | 10 |
| Sandhar Technologies Q4 FY26 | 8 | 12.5% | 33.3% | 3 | 12.5% | 14.3% | 7 |
| Mold-Tek Packaging Q4 FY26 | 10 | 20% | 28.6% | 7 | — | — | hit token limit |

Mold-Tek hit the 16,384 completion token limit on v9 — the model ran out of output space before completing the response. This makes Mold-Tek unrunnable with the current single-pass approach.

**Earlier test company (large cap, multi-segment — used for initial development only):**

Asian Paints Q4 FY26, 4 GT items: v8 recall 75%, precision 67% (best result). After switching from free-text to structured output, recall dropped to 25–50% across runs even at temperature=0.

---

### What changed between v8 and v9 (and why v9 made things worse):

v9 made three changes to v8:

1. Added "A single transcript typically contains 5 to 15 qualifying statements — extract all of them without stopping early" to the opening paragraph — intended to fix under-extraction
2. Clarified that null guidance_value is only valid for commissioning_event and binary events, not other metrics — intended to fix null-value false positives
3. Added a note that segment-level, subsidiary-level, and per-unit metrics must use the `other_` prefix — intended to fix metric label misclassification

**Result:** Under-extraction fix backfired. The LLM treated "5 to 15" as a quota to hit, not a floor, and lowered its quality bar to reach the count. Fineotex went from 3 to 10 items, 9 of which were false positives. Recall stayed identical (the right items were already found), precision collapsed. The null-value and vocabulary fixes had no measurable effect.

---

### Specific failure patterns observed across v8 and v9 runs:

**1. Under-extraction:** Sandhar has 8 GT items but the LLM consistently returns 3. Mold-Tek has 10 GT items, LLM returns 7 and hits the output token limit. The LLM is not reading or attending to the full transcript.

**2. Metric misclassification (the biggest recall blocker):** The LLM finds the right passage but assigns the wrong metric label, so it counts as a false positive rather than a true positive. Examples:
- `revenue_absolute | 40` extracted instead of `other_ev_revenue_absolute | 40` — subsidiary-level revenue mapped to standard vocabulary
- `ebitda_margin_pct | 0.25` extracted instead of `other_ebitda_margin_delta | 0.25` — a delta improvement mapped to an absolute margin metric
- `revenue_absolute | 750` extracted instead of `other_new_projects_revenue_absolute | 700-750` — wrong label and wrong value range
- `ebitda_margin_pct | 42-43` extracted instead of `other_ebitda_per_kg | 42-43` — per-kg figure confused with a percentage margin
- Duplicate extractions: `revenue_absolute | 40` appeared twice in the same run, violating the deduplication rule

**3. Null-value false positives:** `capacity_addition | null`, `commissioning_event | null`, `other_expansion_strategy | null`, `other_industry_trend | null` extracted despite no numeric value and no verifiable commitment. The rule says to reject items without numbers, but the LLM ignores it.

**4. Past results extracted:** `pat_absolute | 44 | Q4 FY26` — a past quarter result, not forward-looking guidance. The rejection rule exists in the prompt but is not followed.

**5. Output token limit:** Mold-Tek's transcript produces enough qualifying items that the structured output response overflows the 16,384 token limit. This is a hard failure mode, not a quality issue.

**6. Run variation:** Even at temperature=0, the same prompt on the same transcript returns different item counts across runs. An item oscillates in and out across consecutive runs. This makes single-run eval unreliable.

---

### My diagnosis:

The core problem is task overload in a single pass. The LLM is being asked to simultaneously: (a) read and attend to 50,000+ characters, (b) identify candidate passages, (c) apply extraction rules, (d) classify metrics from a vocabulary, (e) fill 8 structured fields per item, (f) deduplicate across the full transcript, all in one shot. Each of these is a distinct cognitive step and the compound error rate is high.

---

## Technical Stack and Constraints

- Language: Python
- LLM API: OpenAI (gpt-4o as primary model, gpt-4o-mini available for cheaper stages)
- PDF text extraction: pypdf (already implemented)
- Database: PostgreSQL via SQLAlchemy (already implemented)
- Eval pipeline: Already built — precision/recall computed programmatically against ground truth
- Cost constraint: Low to medium. Running on 600+ transcripts per quarter eventually. Single-pass gpt-4o on a 50K char transcript costs roughly $0.15-0.25 per transcript. A 2-stage pipeline that uses gpt-4o-mini for Stage 1 and gpt-4o only for Stage 2 candidates would be acceptable if it meaningfully improves recall.
- Latency: Not a constraint. Batch processing, not real-time.
- **Most important constraint**: Maximize recall. Every missed guidance item is a false negative that reduces credibility scoring accuracy downstream. Precision matters but recall is the primary objective.

---

## What I Need From You

Design the best possible technical architecture for this extraction task. Be specific and actionable. I am an experienced Python/data engineer, comfortable with LLM APIs, but relatively new to LLM system design.

Answer these questions:

**1. Architecture:**
What is the optimal multi-stage pipeline for this task? Where should I use deterministic code vs LLM? Where should I use a cheap model vs an expensive model? Draw out the stages clearly with the input and output of each stage.

**2. Chunking strategy:**
Should I chunk the transcript, and if so, how? By speaker turn? By paragraph? By page? What are the tradeoffs? How does chunking interact with the self-sufficiency requirement for passages (a passage must include enough context to be independently understandable)?

**3. Structured output vs free text:**
I observed a significant recall regression when switching to structured output mode (Pydantic schema via response_format). How do I get structured JSON output without sacrificing recall? Is there a better approach than forcing structured output at the extraction stage?

**4. Run variation:**
How do I handle non-determinism at temperature=0? Is self-consistency (run multiple times, merge results) the right fix? What is the cheapest way to improve reliability?

**5. Prompt design:**
Given the specific failure patterns above (metric misclassification, null-value FPs, past results extracted, deduplication failures), what are the most impactful prompt changes? Are these fixable with better prompting in a single-pass approach, or is the architecture itself the bottleneck?

**6. Expected improvement:**
For each architectural approach you recommend, give a rough estimate of the recall improvement I should expect relative to my current single-pass baseline of 12.5–50% recall across companies.

**7. Implementation order:**
What should I build first? I want the highest recall improvement per unit of implementation effort. Give me a prioritised sequence.

Do not give generic LLM advice. Give me a specific, opinionated recommendation for this exact problem — long financial documents, high-recall structured extraction, Python implementation, cost-conscious.
