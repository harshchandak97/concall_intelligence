# Stage 3 — Metric Classifier Spec
## Concall Intelligence Extraction Pipeline

**This file covers: Stage 3 (Metric Classification)**
**Files to create: `pipeline/stage3_classifier.py` + `prompts/stage3_classification_prompt.txt`**
**Build order position: 5 of 6 — requires Stage 2 output (List[RawGuidanceItem])**

Before writing any code, read `CLAUDE.md` in the project root. Follow the behavioural
rules there exactly. Do not write code for any other stage — this file covers Stage 3 only.

**Prerequisite check before starting:**
- Stage 2 acceptance test passed (passage-level recall ≥ 70%)

---

## Architecture Overview

```
PDF Transcript
      │
      ▼
[Stage 0] Deterministic Segmentation (pure Python)
      │  Output: List[Chunk] — Q&A pairs with speaker metadata
      │
      ▼
[Stage 1] Candidate Filter (pure Python, regex + lexicon)
      │  Output: List[Chunk] — only chunks likely to contain guidance
      │
      ▼
[Stage 2] Per-Chunk Extraction (gpt-4o, structured output, 2 runs → union)
      │  Output: List[RawGuidanceItem] — passage + value + timeline, metric as free text
      │
      ▼
[Stage 3] Metric Classification (gpt-4o, one call per item)      ← YOU ARE HERE
      │  Output: List[ClassifiedItem] — final metric label from controlled vocabulary
      │
      ▼
[Stage 4] Deterministic Validation + Dedup (pure Python)
      │  Output: List[GuidanceItem] — final schema, identical to ground truth structure
      │
      ▼
PostgreSQL Storage + Eval
```

**Key architectural principles:**
- LLM is never asked to do two different cognitive tasks in the same call
- Every rule the LLM ignores in a prompt migrates to Stage 4 as code
- Stage 1 is the recall gate — it must never drop a true item; passing too many is fine
- speaker and page_number are computed in Stage 0, never inferred by the LLM
- credibility_scorable is computed in Stage 4 as a pure code lookup, never by the LLM

---

## Data Models

Define these in `pipeline/models.py`. These are internal pipeline models, not the final
output schema. The final output schema (GuidanceItem) is unchanged from existing schemas.py.

```python
# Stage 0 output (shown for context)
class ChunkRole(str, Enum):
    MANAGEMENT = "management"
    ANALYST = "analyst"
    MODERATOR = "moderator"

class Chunk(BaseModel):
    chunk_id: str
    speaker: str
    role: ChunkRole
    page_start: int
    page_end: int
    text: str
    char_start: int
    char_end: int
    is_qa_pair: bool

# Stage 2 output — Stage 3 reads this
class RawGuidanceItem(BaseModel):
    chunk_id: str              # which chunk this came from
    passage: str               # verbatim text, self-sufficient
    speaker: str               # from chunk metadata
    page_number: int           # from chunk metadata
    metric_description: str    # free text e.g. "EBITDA margin improvement of 0.25% over FY27"
    guidance_value: Optional[str]  # "18-20" or "40" or None for binary events
    guidance_unit: Optional[str]   # "%" or "crore" or "$ million" or None
    timeline: str              # raw string e.g. "FY27", "H1 FY27", "second half of next year"
    run_index: int             # 0 or 1

class ChunkExtractionResult(BaseModel):
    chunk_id: str
    items: List[RawGuidanceItem]

# Stage 3 output — THIS IS WHAT THIS STAGE PRODUCES
class ClassifiedItem(BaseModel):
    # All fields from RawGuidanceItem, plus metric:
    chunk_id: str
    passage: str
    speaker: str
    page_number: int
    metric_description: str
    guidance_value: Optional[str]
    guidance_unit: Optional[str]
    timeline: str              # still raw — Stage 4 normalizes it
    metric: str                # final metric label from controlled vocabulary
```

The final output schema (GuidanceItem) is defined in existing schemas.py and is unchanged:
passage, speaker, page_number, metric, guidance_value, guidance_unit, timeline,
credibility_scorable.

---

## File Structure

```
concall-intelligence/
├── pipeline/
│   ├── __init__.py
│   ├── models.py              ← Chunk, RawGuidanceItem, ClassifiedItem (internal models)
│   ├── stage0_segmenter.py
│   ├── stage1_filter.py
│   ├── stage2_extractor.py
│   ├── stage3_classifier.py   ← THIS FILE
│   ├── stage4_validator.py
│   └── run_pipeline.py
├── prompts/
│   ├── stage2_extraction_prompt.txt
│   └── stage3_classification_prompt.txt   ← ALSO CREATE THIS
├── schemas.py                 ← unchanged
├── eval.py                    ← updated later
└── ... rest unchanged ...
```

---

## Implementation Order (Full Pipeline)

1. **Stage 0** — Segmenter (complete)
2. **Stage 1** — Filter (complete)
3. **Stage 4** — Validation rules (complete)
4. **Stage 2** — Per-chunk extractor (complete)
5. **Stage 3** — Metric classifier ← YOU ARE HERE
6. **run_pipeline.py** — Orchestrator + eval

Do not move to the orchestrator until the Stage 3 acceptance test passes.

---

## Stage 3 — Metric Classification

### Purpose
Assign each extracted item a metric label from the controlled vocabulary. This is a
separate, focused task — the model's only input is the passage + metric_description, and
its only job is picking the right label following an explicit decision tree.

### Input
`List[RawGuidanceItem]` from Stage 2

### Output
`List[ClassifiedItem]` — same fields plus `metric: str`

---

### Controlled Vocabulary

```
revenue_growth_pct         — Company-level revenue growth rate (%)
revenue_absolute           — Company-level revenue as absolute figure (crore)
ebitda_margin_pct          — Company-level EBITDA/PBDIT margin as % of revenue
pat_growth_pct             — Company-level PAT growth rate (%)
pat_absolute               — Company-level PAT as absolute figure (crore)
pbt_margin_pct             — Company-level PBT margin as % of revenue
eps_absolute               — Company-level EPS (₹ per share)
volume_growth_pct          — Volume growth rate (%, any product/segment)
capex_absolute             — Capital expenditure commitment (crore)
capacity_addition          — New capacity addition (units, MT, KLPD, etc.)
commissioning_event        — Plant/facility/project go-live or commissioning
order_book_absolute        — Order book or contract value (crore)
price_increase_pct         — Pricing increase (%)
volume_value_gap_pct       — Difference between volume growth and value growth rates
other_[descriptor]         — Everything else; descriptor must be 2-4 words, snake_case
```

---

### Implementation Logic

#### LLM Call Design

**Model:** gpt-4o
**Temperature:** 0
**Structured output:** Yes — schema returns single string field `metric`
**Input per call:** passage (str) + metric_description (str)
**One call per item** (not batched — each classification is independent and short)

#### System Prompt (Stage 3)

Structure the prompt as an explicit decision tree. The model follows it top-to-bottom:

```
DECISION TREE:

Step 1 — Is this metric company-level or sub-company-level?
  Sub-company includes: a specific product segment, a subsidiary, a geography,
  a per-unit measure (per kg, per tonne, per unit).

  IF sub-company-level → MUST use other_[descriptor]. Do not use any standard label.
  Examples of sub-company → other_:
    - "EV segment revenue" → other_ev_revenue_absolute
    - "Institutional segment margins" → other_institutional_ebitda_margin_pct
    - "EBITDA per kg" → other_ebitda_per_kg
    - "Romania subsidiary breakeven" → commissioning_event (breakeven is binary event)

  IF company-level → continue to Step 2.

Step 2 — Is this a growth rate / delta, or an absolute level?
  Growth rate / delta = a change expressed as %, percentage points, or basis points.
  Absolute level = a target value (₹X crore, X%, X EPS).

  IF growth rate for revenue → revenue_growth_pct
  IF absolute level for revenue → revenue_absolute
  IF growth rate for PAT → pat_growth_pct
  IF absolute level for PAT → pat_absolute

  Special case — margin DELTA vs margin LEVEL:
    "We expect margins to improve by 200 bps" → delta → other_ebitda_margin_delta
    "We expect margins of 18-20%" → absolute level → ebitda_margin_pct
    This is the single most common misclassification. Apply carefully.

Step 3 — Match remaining metrics:
  EBITDA/PBDIT margin (absolute %) → ebitda_margin_pct
  PBT margin (%) → pbt_margin_pct
  EPS (₹/share) → eps_absolute
  Capex commitment (₹ crore) → capex_absolute
  Capacity addition (units/MT) → capacity_addition
  Plant commissioning / go-live / breakeven binary event → commissioning_event
  Order book / contract value → order_book_absolute
  Price increase (%) → price_increase_pct
  Volume growth (%) → volume_growth_pct
  Volume vs value growth gap → volume_value_gap_pct

Step 4 — Anything not matched above → other_[descriptor]
  Descriptor must be 2-4 words, snake_case, specific.
  Good: other_ev_revenue_absolute, other_new_project_revenue, other_ebitda_per_kg
  Bad: other_financial_metric, other_guidance, other_revenue (too vague)
```

#### Few-Shot Examples (embed in prompt — covering known misclassification cases)

| passage excerpt | metric_description | WRONG label | CORRECT label |
|---|---|---|---|
| "Our EV revenue is ₹20 crore, we expect it to double" | EV subsidiary revenue target ₹40 crore FY27 | revenue_absolute | other_ev_revenue_absolute |
| "EBITDA margins should improve by 25 basis points" | EBITDA margin improvement 0.25% delta FY27 | ebitda_margin_pct | other_ebitda_margin_delta |
| "We target revenue of ₹800-900 crore in FY27" | Company-level revenue target FY27 | — | revenue_absolute ✓ |
| "EBITDA per kg should be ₹42-43 in FY27" | EBITDA per kg target (not a margin %) | ebitda_margin_pct | other_ebitda_per_kg |
| "New plant commissioning in H1 FY27" | VAM-VAE plant go-live binary event | commissioning_event with value | commissioning_event, value=null ✓ |
| "We expect new projects to contribute ₹700-750 crore" | Revenue from new project pipeline | revenue_absolute | other_new_projects_revenue_absolute |

Include all six examples in the prompt.

---

### credibility_scorable — Computed in Code, Not by LLM

After Stage 3 assigns the metric label, compute credibility_scorable in Python.
This happens at the boundary of Stage 3 output / Stage 4 input:

```python
CREDIBILITY_SCORABLE_METRICS = {
    "revenue_absolute",
    "revenue_growth_pct",
    "ebitda_margin_pct",
    "pat_absolute",
    "pat_growth_pct",
    "pbt_margin_pct",
    "eps_absolute",
}

def compute_credibility_scorable(metric: str) -> bool:
    # other_* metrics are never credibility_scorable (sub-company or non-standard)
    if metric.startswith("other_"):
        return False
    return metric in CREDIBILITY_SCORABLE_METRICS
```

---

### Edge Cases

**"Other" descriptor collisions:** Two different items may be assigned `other_revenue_absolute`
even if they refer to different things. The descriptor should be specific enough to be unique
within a transcript — enforce minimum 2-word descriptor (e.g., `other_ev_revenue_absolute`
not `other_revenue_absolute`). If the descriptor would be too generic, include the
segment/product name in it.

**commissioning_event value field:** This metric always has guidance_value=null. The decision
tree makes this explicit in Step 3. If a commissioning item arrives from Stage 2 with a
non-null value (the LLM extracted a capacity figure alongside the commissioning), accept
the classification — Stage 4 will set guidance_value=null.

**Ambiguous metric_description:** If metric_description is genuinely ambiguous (e.g., just
"revenue guidance FY27" without specifying if it's company-level), the LLM should default
to the standard vocabulary label (revenue_absolute) and NOT use other_. The other_ prefix
is only for confirmed sub-company metrics.

---

### Acceptance Test — Stage 3

Run Stage 3 on Stage 2 output for all three target transcripts.
Compute **full-match recall** (this is the first time we can measure this):

**Full-match definition:** An extracted item matches a GT item if:
- Passage fuzzy match > 85% against GT passage, AND
- metric == GT metric, AND
- guidance_value matches GT value (within ±10% of midpoint, existing eval logic), AND
- timeline == GT timeline (normalized)

**Target:** Full-match recall ≥ 60% across the three companies (up from 12.5-50% baseline).

**Delta analysis:** For items that have correct passage but wrong metric (passage-level
recall hit, full-match miss), print the passage + metric_description + assigned label +
GT label. Use this output to identify missing few-shot examples and update the Stage 3
prompt before declaring Stage 3 complete. Iterate until full-match recall ≥ 70%.
