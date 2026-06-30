You are reading an Indian company's Q4 FY24 earnings call transcript (the call was held around April–May 2024). Extract management's forward-looking guidance on the metrics that drive **PAT (net profit) CAGR**, as structured data. You only READ and CLASSIFY — you do NO arithmetic.

Return:
- **`call_period`** — the fiscal quarter+year of THIS call (e.g. "Q4 FY24"), read from the transcript header. Used to resolve relative timeframes.
- **`items`** — every quantified, forward-looking guidance on revenue, PAT, or a margin LEVEL. For each, you also label **`scope`** (whose number it is). Only `company`-scope items feed the analysis downstream, but you must still extract and correctly label `segment` / `geography` / `subsidiary` items — do NOT force them into `company`, and do NOT silently drop a number just because it is not company-level.

## `items` — what qualifies (ALL three must hold)

1. **Forward-looking** — a future target/plan/aspiration, not a past or current-state fact.
2. **Quantified** — a real number: a percentage, a multiple ("double", "3x"), or an absolute amount. Vague magnitude ("strong growth", "high single digits") does NOT qualify.
3. **Has a timeframe** — a year/FY/horizon ("by FY27", "in 3 years").

(Capex, order book, volumes, capacity, store counts, AUM, pre-sales, EPS, dividends are NOT in scope — ignore them entirely. Only revenue / PAT / margin metrics.)

**Critical:** `revenue_absolute` is ONLY a total **revenue / sales / turnover / topline** target. An **order-book value, contract value, capex, AUM, or any other large rupee/dollar figure is NOT `revenue_absolute`** — even if it has a number and a date. If a ₹X-crore figure is not the company's revenue, do not extract it at all.

## `metric` — classify each into exactly ONE (GROWTH vs a margin LEVEL)

| `metric` | What it is | Examples |
|---|---|---|
| `revenue_growth_pct` | revenue/sales **growth** — a % or a multiple | "grow 20–25%", "double", "3x" |
| `revenue_absolute` | revenue/sales **target amount** | "₹1,000 crore by FY28", "$200 million" |
| `pat_growth_pct` | PAT/net-profit **growth** rate | "PAT to grow 20%", "bottom line 10–15% growth" |
| `pat_absolute` | PAT/net-profit **target amount** | "₹500 crore PAT by FY28" |
| `ebitda_margin_pct` | EBITDA/operating-margin **LEVEL** (% of revenue) | "maintain 25% EBITDA margin", "15% EBITDA" |
| `pbt_margin_pct` | PBT-margin **LEVEL** | "PBT margin around 12%" |
| `net_margin_pct` | net/PAT-margin **LEVEL** (% of revenue) | "PAT will be 10–13% of revenue" |

Disambiguation: "PAT will be ~10–13%" / "10%-plus PAT" → a **margin** (`net_margin_pct`), not pat_growth. "PAT to **grow** 20%" → `pat_growth_pct`. "EBITDA margin 25%" / "maintain 25%" → `ebitda_margin_pct` (a level; "maintain" = flat, still a level). A bare basis-points improvement with NO stated level → ignore. Basis points ≠ percent (100 bps = 1%). EBITDA/PBT *growth* → ignore (these metrics are used only as margin levels).

## `scope` — what does the number cover? (this is the key new judgment)

Set `scope` by tracing what the number is the total **of**:

- **`company`** — the WHOLE company: consolidated or standalone total. This includes an **overall / total figure that management builds by combining its parts** (e.g. "segment A 15% + segment B 25%, so overall 18–20%" → the 18–20% is `company`).
- **`segment`** — one business segment / product line / vertical only.
- **`geography`** — one region / country only (a single geography in isolation).
- **`subsidiary`** — one subsidiary / associate / plant only.

A number is `company` ONLY if it refers to the entire entity. If it refers to **one part in isolation** — any single segment, region, product, subsidiary, or plant — it is that part's scope, **whatever the part is**. Do not generalize a part's number to the whole.

**Question-scope rule:** a number given in answer to a question inherits the **scope of the question**. If the question asked about a specific part ("what growth do you expect in [that region / that segment]?"), the answer is about that part — `scope` is `geography` / `segment`, NOT `company` — unless management explicitly broadens it to the whole company.

## Per-field rules

- `value` — **digits only.** A number or range ("18-20", "1000", "2", "3-4"). The number exactly as spoken next to the unit — never convert units ("$1 billion" → value="1", unit="billion"). Strip qualifiers/symbols ("plus", "around", "~", "+", "odd", "minimum"): "15%-plus" → "15".
- `unit` — "%", "times", or the money word as written ("crore", "lakh", "million", "billion").
- `currency` — "INR" or "USD" for ABSOLUTE money targets only; `null` for %, times, and all margin levels.
- `scope` — `company` | `segment` | `geography` | `subsidiary` (per the test above).
- `timeline` — machine-parseable FY or range, relative phrases resolved from `call_period` ("next year" from FY24 → "FY25"; "over 3 years" → "FY27"; "3–4 years" → "FY28-FY29"). For a margin "going forward"/"steady state" with no date, use the next FY.
- `passage` — **exact, verbatim, self-sufficient** quote: subject, number-as-digits, currency/unit, and timeframe all inside it. Expand to resolve "that number" or a bare "Yes/Correct" (include the analyst question). For a Q&A number, include enough of the question that the SCOPE is unambiguous in the quote. Copy word-for-word; never paraphrase.

## One item per DISTINCT target — dedupe hard

Output each distinct target **once**. A target is identified by `(metric, value, timeline, scope)`. The same number is almost always repeated across the call — in opening remarks AND several Q&A answers. Do **NOT** emit one item per mention: pick the single clearest passage and drop the rest. Most companies have only a **handful** of distinct targets (typically 2–6). If your list has many items with the same value and timeline, you are over-extracting restatements — collapse them.

## Output

Return ONLY: `{"call_period": "...", "items": [ {metric, value, unit, currency, scope, timeline, passage}, ... ] }`.

### Worked example
*"We expect 40–50% revenue growth this year, PAT around 10–13% of sales, ₹1,000 crore by FY28. Our US business should grow ~10%. EXIM 15% and domestic 25%, so overall ~18–20%."* →
```
items:
  {metric:"revenue_growth_pct", value:"40-50", unit:"%",     currency:null, scope:"company",   timeline:"FY25", passage:"..."}
  {metric:"net_margin_pct",     value:"10-13", unit:"%",     currency:null, scope:"company",   timeline:"FY25", passage:"..."}
  {metric:"revenue_absolute",   value:"1000",  unit:"crore", currency:"INR", scope:"company",  timeline:"FY28", passage:"..."}
  {metric:"revenue_growth_pct", value:"10",    unit:"%",     currency:null, scope:"geography", timeline:"FY25", passage:"...US business..."}
  {metric:"revenue_growth_pct", value:"18-20", unit:"%",     currency:null, scope:"company",   timeline:"FY25", passage:"...overall..."}
```
(The US figure is labeled `geography` — not company — and EXIM/domestic are not extracted separately because the company-level "overall 18–20%" already captures them.)

---

Transcript:

{transcript_text}
