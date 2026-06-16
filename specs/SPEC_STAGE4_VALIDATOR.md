# Stage 4 — Validator Spec
## Concall Intelligence Extraction Pipeline

**This file covers: Stage 4 (Deterministic Validation + Deduplication)**
**File to create: `pipeline/stage4_validator.py`**
**Build order position: 3 of 6 — build BEFORE Stage 2, test with synthetic inputs**

Before writing any code, read `CLAUDE.md` in the project root. Follow the behavioural
rules there exactly. Do not write code for any other stage — this file covers Stage 4 only.

**Why Stage 4 is built before Stage 2:** Stage 4's validation rules are standalone Python
functions that can be tested with synthetic inputs before any LLM calls exist. As soon as
Stage 2 produces output, Stage 4 can immediately clean it — no waiting to bolt on cleanup
later.

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
[Stage 3] Metric Classification (gpt-4o, one call per item)
      │  Output: List[ClassifiedItem] — final metric label from controlled vocabulary
      │
      ▼
[Stage 4] Deterministic Validation + Dedup (pure Python)      ← YOU ARE HERE
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

# Stage 2 output (shown for context)
class RawGuidanceItem(BaseModel):
    chunk_id: str
    passage: str
    speaker: str
    page_number: int
    metric_description: str
    guidance_value: Optional[str]
    guidance_unit: Optional[str]
    timeline: str
    run_index: int

class ChunkExtractionResult(BaseModel):
    chunk_id: str
    items: List[RawGuidanceItem]

# Stage 3 output — Stage 4 reads this
class ClassifiedItem(BaseModel):
    chunk_id: str
    passage: str
    speaker: str
    page_number: int
    metric_description: str
    guidance_value: Optional[str]
    guidance_unit: Optional[str]
    timeline: str              # still raw at this point — Stage 4 normalizes it
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
│   ├── stage3_classifier.py
│   ├── stage4_validator.py    ← THIS FILE
│   └── run_pipeline.py
├── prompts/
│   ├── stage2_extraction_prompt.txt
│   └── stage3_classification_prompt.txt
├── schemas.py                 ← unchanged
├── eval.py                    ← updated later
└── ... rest unchanged ...
```

---

## Implementation Order (Full Pipeline)

1. **Stage 0** — Segmenter (complete)
2. **Stage 1** — Filter (complete)
3. **Stage 4** — Validation rules ← YOU ARE HERE
4. **Stage 2** — Per-chunk extractor
5. **Stage 3** — Metric classifier
6. **run_pipeline.py** — Orchestrator + eval

Do not move to Stage 2 until Stage 4's standalone unit tests pass on synthetic inputs.

---

## Stage 4 — Deterministic Validation and Deduplication

### Purpose
Apply all quality filters as deterministic Python code. Every rule that was "in the prompt
but ignored by the LLM" lives here. This stage cannot be bypassed and has no LLM calls.

### Input
`List[ClassifiedItem]` from Stage 3 (after credibility_scorable computed)
Also requires: `transcript_text: str` and `call_date: date` for Rules 3 and 4.

### Output
`List[GuidanceItem]` — final output matching the existing GuidanceItem schema in schemas.py,
ready for PostgreSQL insertion

---

### Implementation Logic

Apply the following rules in order. Each rule either rejects the item or normalizes it.
Log every rejection with: chunk_id, rule_name, item_summary.

#### Rule 1 — Null Value Rejection

```python
if item.metric != "commissioning_event" and item.guidance_value is None:
    REJECT  # reason: "null_value_non_binary_metric"
```

commissioning_event is the ONLY metric where null guidance_value is valid.
Everything else must have a numeric value to qualify as extracted guidance.

#### Rule 2 — Guidance Value Format Check

```python
import re
VALUE_PATTERN = re.compile(r'^\d+(\.\d+)?(-\d+(\.\d+)?)?$')
if item.guidance_value is not None:
    if not VALUE_PATTERN.match(item.guidance_value):
        REJECT  # reason: "malformed_guidance_value"
        # Examples rejected: "~18", "around 40", ">20", "18 to 20"
        # Examples kept: "18", "18-20", "18.5", "18.5-20.5"
```

If the value has approximation markers ("around", "~", ">"), attempt to clean them first:
strip the marker and check if the remainder matches the pattern. If yes, keep with cleaned
value. If no, reject.

#### Rule 3 — Past/Current Timeline Rejection

```python
def is_past_or_current(timeline_normalized: str, call_date: date) -> bool:
    # Normalize timeline first (see Timeline Normalization below)
    # Compare against call_date's fiscal quarter
    # call_date May 2026 → Q1 FY27 (Indian fiscal: April start)
    # Reject if normalized timeline ≤ current quarter
    ...
```

This rejects: `pat_absolute | 44 | Q4 FY26` when the call is in Q1 FY27 — the Q4 FY26
result is historical, not forward-looking guidance.

Current quarter at time of call = the quarter the call falls in. On a Q4 FY26 results call
(May-June 2026), the current quarter is Q1 FY27. Reject timelines ≤ Q4 FY26.

Do NOT reject FY27 full-year guidance on a Q1 FY27 call — "FY27" is still forward-looking.

#### Rule 4 — Passage Verbatim Check (Warning Only, Not Rejection)

```python
# Normalize whitespace in both passage and full transcript text
passage_normalized = re.sub(r'\s+', ' ', item.passage.strip())
transcript_normalized = re.sub(r'\s+', ' ', transcript_text.strip())

if passage_normalized not in transcript_normalized:
    # Do NOT reject — PDF extraction may alter spacing/encoding
    # Log as WARNING: "passage_not_found_verbatim"
    # Flag item with `verbatim_verified = False` for manual review
```

This catches LLM hallucination but doesn't cause false rejections from PDF encoding
artifacts. Items flagged here should be spot-checked manually.

#### Rule 5 — Deduplication

```python
# After all rejection rules, dedup across all items from all chunks
# Group by: (metric, normalized_value, normalized_timeline)
# Within each group, keep the item with the longest passage (most context)
# "normalized_value": round both ends of a range to 1 decimal, sort
# e.g. "18-20" and "18.0-20.0" are the same; "18-20" and "17-20" are different

from difflib import SequenceMatcher

def fuzzy_deduplicate(items: List[ClassifiedItem]) -> List[ClassifiedItem]:
    # Primary dedup: exact (metric, guidance_value, timeline) match
    # Secondary dedup: for items with same metric + timeline, check if passages
    # are >90% similar — these are the same item from two overlapping sub-chunks
    # Keep the item with the longer passage
    ...
```

#### Timeline Normalization

Normalize raw timeline strings from Stage 2 to canonical form before all comparisons.
This is also the place to resolve relative references using call_date.

```python
def normalize_timeline(raw_timeline: str, call_date: date) -> str:
    """
    Examples:
    "FY27" → "FY27"
    "FY 27", "FY2027", "2026-27" → "FY27"
    "H1 FY27", "H1FY27", "first half FY27", "first half of FY27" → "H1 FY27"
    "H2 FY27", "second half of FY27", "second half of this financial year"* → "H2 FY27"
    "Q1 FY27", "first quarter FY27", "first quarter of FY27" → "Q1 FY27"
    "Q2 FY27", "second quarter" → "Q2 FY27"
    "this financial year", "this fiscal year"* → current fiscal year from call_date
    "next financial year", "next fiscal year"* → next fiscal year from call_date
    "next quarter"* → next quarter from call_date
    "by end of this financial year"* → last quarter of current FY from call_date

    * = relative expressions resolved using call_date

    If normalization fails (no recognizable pattern): return raw string as-is,
    log WARNING: "timeline_not_normalized"
    """
    # Indian fiscal year: April 1 to March 31
    # call_date in May-June 2026 → current FY is FY27 (April 2026 - March 2027)
    # current quarter on a May 2026 call = Q1 FY27
    ...
```

#### credibility_scorable — Computed Here as a Code Lookup

After Stage 3 assigns the metric label (available on ClassifiedItem), compute
credibility_scorable before writing to the final GuidanceItem:

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

**"This financial year" on a Q4 call:** On a Q4 FY26 call (May-June 2026), "this financial
year" = FY27 (the year that just started). Normalize to "FY27". Not FY26 (which just ended).

**"By end of this financial year" on a Q4 call:** = March 2027 = end of FY27 → normalize
to "FY27". If the call were in Q2 FY27 (October 2026), the same phrase → "FY27" again.

**"18 months":** Cannot be reliably normalized to a fiscal period without more context.
Normalize to "18 months from call_date" and flag as WARNING. Store raw string if no clean
normalization possible.

**commissioning_event with a capacity figure:** Some commissioning statements include the
new capacity: "We expect to commission our 50,000 MT plant in H1 FY27." The guidance_value
for commissioning_event should be null (the commissioning is the event, not the capacity).
Set guidance_value=null on any commissioning_event item regardless of what Stage 2 extracted.

**Overlapping sub-chunks both produce the same item:** Sub-chunk overlap (200-char) is
specifically designed to catch cross-boundary items. The dedup step (Rule 5) handles this —
both extractions are identical or near-identical and merge into one item.

---

### Acceptance Test — Stage 4

Test with synthetic inputs first (before Stage 2 exists):
- Create a list of hand-crafted ClassifiedItem objects covering each rejection rule
- Verify Rule 1 rejects null-value non-commissioning items
- Verify Rule 2 rejects "~18" and "around 40" but keeps "18-20" and "18.5"
- Verify Rule 3 rejects Q4 FY26 timeline on a May 2026 call date
- Verify Rule 3 does NOT reject FY27 on a May 2026 call date
- Verify Rule 5 deduplicates identical (metric, value, timeline) items, keeping longest passage
- Verify normalize_timeline maps all example strings in the spec correctly

**After Stage 2 and 3 are complete — run on real pipeline output:**

**Rejection counts:**
Run Stage 4 and print a rejection summary per rule:
- Rule 1 (null value): expect to eliminate most null-value false positives from v1
- Rule 2 (malformed value): expect 0-3 per transcript
- Rule 3 (past timeline): expect to eliminate past-quarter result extractions
- Rule 5 (dedup): expect some reduction; if dedup removes >30% of items, sub-chunk overlap
  may be too large

**Final eval — full-match recall and precision:**
Run the existing eval.py against Stage 4 output (final GuidanceItem list).
Targets:
- Recall ≥ 70% across all three target companies
- Precision ≥ 60% across all three target companies

**Null FP elimination:** All items of type `capacity_addition | null`,
`commissioning_event | null` (the null-value false positive pattern from v1) should be
either correctly retained (commissioning_event is valid with null) or rejected (all others
with null values). Zero null-value false positives for non-commissioning metrics.
