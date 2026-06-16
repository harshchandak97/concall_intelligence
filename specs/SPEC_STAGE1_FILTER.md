# Stage 1 — Candidate Filter Spec
## Concall Intelligence Extraction Pipeline

**This file covers: Stage 1 (Candidate Filter)**
**File to create: `pipeline/stage1_filter.py`**
**Build order position: 2 of 6 — requires Stage 0 output (List[Chunk])**

Before writing any code, read `CLAUDE.md` in the project root. Follow the behavioural
rules there exactly. Do not write code for any other stage — this file covers Stage 1 only.

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
[Stage 1] Candidate Filter (pure Python, regex + lexicon)      ← YOU ARE HERE
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
# Stage 0 output — Stage 1 reads this
class ChunkRole(str, Enum):
    MANAGEMENT = "management"
    ANALYST = "analyst"
    MODERATOR = "moderator"

class Chunk(BaseModel):
    chunk_id: str              # sequential: "chunk_001", "chunk_002", etc.
    speaker: str               # extracted from transcript header
    role: ChunkRole            # management / analyst / moderator
    page_start: int            # first page this chunk appears on
    page_end: int              # last page (may span pages)
    text: str                  # full chunk text including Q&A context
    char_start: int            # character offset in full transcript text
    char_end: int              # character offset in full transcript text
    is_qa_pair: bool           # True if this chunk is analyst Q + management A combined

# Stage 2 output (shown for context only — not needed in this stage)
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

# Stage 3 output (shown for context only — not needed in this stage)
class ClassifiedItem(BaseModel):
    chunk_id: str
    passage: str
    speaker: str
    page_number: int
    metric_description: str
    guidance_value: Optional[str]
    guidance_unit: Optional[str]
    timeline: str
    metric: str
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
│   ├── stage1_filter.py       ← THIS FILE
│   ├── stage2_extractor.py
│   ├── stage3_classifier.py
│   ├── stage4_validator.py
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

1. **Stage 0** — Segmenter (complete before starting this)
2. **Stage 1** — Filter ← YOU ARE HERE
3. **Stage 4** — Validation rules (built before Stage 2, tested with synthetic inputs)
4. **Stage 2** — Per-chunk extractor
5. **Stage 3** — Metric classifier
6. **run_pipeline.py** — Orchestrator + eval

Do not move to Stage 4 until the Stage 1 acceptance test passes.

---

## Stage 1 — Candidate Filter

### Purpose
Discard chunks that cannot possibly contain qualifying guidance. This is a precision-
optimizing step only — it must never drop a true item. A false positive (passing a
non-guidance chunk) costs one cheap Stage 2 call. A false negative (dropping a GT item's
chunk) is an unrecoverable recall loss.

### Input
`List[Chunk]` from Stage 0

### Output
`List[Chunk]` — subset that passes the filter

---

### Implementation Logic

Pass a chunk if it satisfies **ANY** of the following three conditions (three-way OR):

**Condition 1 — Digit present:**
```python
re.search(r'\d', chunk.text)
```
Catches all Track A numeric guidance and most Track B items (which usually contain a year,
a percentage, or a rupee figure somewhere in the chunk).

**Condition 2 — Worded temporal expression:**
```python
TEMPORAL_LEXICON = [
    "first half", "second half", "first quarter", "second quarter",
    "third quarter", "fourth quarter", "h1 ", "h2 ", "q1 ", "q2 ", "q3 ", "q4 ",
    "this financial year", "this fiscal year", "this fiscal", "next financial year",
    "next fiscal year", "next year", "coming year", "current year",
    "by end of", "by the end of", "year-end", "year end",
    "coming quarter", "upcoming quarter", "going forward",
    "full year", "annual", "next quarter", "next few quarters",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
# Case-insensitive substring match against any entry
any(phrase in chunk.text.lower() for phrase in TEMPORAL_LEXICON)
```
Catches Track B items stated entirely in words: "we expect the plant to commission in
the second half of this financial year."

**Condition 3 — Commitment verb:**
```python
COMMITMENT_VERBS = [
    "commission", "commissioned", "commissioning",
    "go live", "goes live", "went live",
    "operationalize", "operationalized", "operational",
    "commence operations", "commencement",
    "breakeven", "break even", "break-even",
    "stabilize", "stabilized", "ramp up", "ramping up",
    "complete", "completion", "complete the",
    "launch", "launched", "launching",
]
any(verb in chunk.text.lower() for verb in COMMITMENT_VERBS)
```
Catches binary commitment events that may have no digit and a vague timeframe.

**Filter logic:**
```python
def passes_filter(chunk: Chunk) -> bool:
    text_lower = chunk.text.lower()
    has_digit = bool(re.search(r'\d', chunk.text))
    has_temporal = any(phrase in text_lower for phrase in TEMPORAL_LEXICON)
    has_commitment = any(verb in text_lower for verb in COMMITMENT_VERBS)
    return has_digit or has_temporal or has_commitment
```

Skip MODERATOR-role chunks entirely regardless of filter result — they never contain guidance.

---

### Edge Cases

**"Second half of this financial year" with no digit:** Covered by Condition 2 (temporal
lexicon matches "second half") and Condition 3 (if the same sentence contains "commission").
Either condition alone is sufficient.

**Pure historical chunks with digits:** A chunk saying "Q4 FY26 revenue was ₹450 crore"
passes Condition 1 (has digits). This is intentional — Stage 4 rejects past-timeline items.
The filter is not the place to detect historical context.

**Analyst question with forward-looking language but no management answer yet:** Already
handled — Stage 0 produces Q&A pairs, so the analyst's question text and management's
answer are in the same chunk. If the analyst asks "do you expect 20% growth?" and management
says yes, the digit 20 is in the chunk via the question.

---

### Acceptance Test — Stage 1

**GT item filter recall [critical — must be 100%]:**
For every GT item across all three companies:
1. Find the chunk from Stage 0 that contains its passage
2. Confirm that chunk passes the Stage 1 filter

If any GT item's chunk fails the filter, identify which condition should have caught it
and add the missing phrase to the appropriate lexicon. Re-run until filter recall = 100%.

**Filter pass rate:**
Log what percentage of total chunks pass the filter for each transcript.
Expected range: 30–60%. If >80%, the filter is too loose (acceptable but wasteful).
If <20%, the filter may be too strict — re-examine MODERATOR exclusion and run the GT check.
