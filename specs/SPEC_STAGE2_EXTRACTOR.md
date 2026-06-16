# Stage 2 — Per-Chunk Extractor Spec
## Concall Intelligence Extraction Pipeline

**This file covers: Stage 2 (Per-Chunk Extraction)**
**Files to create: `pipeline/stage2_extractor.py` + `prompts/stage2_extraction_prompt.txt`**
**Build order position: 4 of 6 — requires Stage 0, Stage 1, and Stage 4 to be complete**

Before writing any code, read `CLAUDE.md` in the project root. Follow the behavioural
rules there exactly. Do not write code for any other stage — this file covers Stage 2 only.

**Prerequisite check before starting:**
- Stage 0 acceptance test passed (GT item chunk containment = 100%)
- Stage 1 acceptance test passed (GT item filter recall = 100%)
- Stage 4 standalone unit tests passed (all rejection rules verified on synthetic inputs)

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
[Stage 2] Per-Chunk Extraction (gpt-4o, structured output, 2 runs → union)      ← YOU ARE HERE
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
# Stage 0 output — Stage 2 receives filtered List[Chunk] from Stage 1
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

# Stage 2 output — THIS IS WHAT THIS STAGE PRODUCES
class RawGuidanceItem(BaseModel):
    chunk_id: str              # which chunk this came from
    passage: str               # verbatim text, self-sufficient
    speaker: str               # confirmed from chunk metadata
    page_number: int           # from chunk metadata
    metric_description: str    # free text e.g. "EBITDA margin improvement of 0.25% over FY27"
    guidance_value: Optional[str]  # "18-20" or "40" or None for binary events
    guidance_unit: Optional[str]   # "%" or "crore" or "$ million" or None
    timeline: str              # raw string e.g. "FY27", "H1 FY27", "second half of next year"
    run_index: int             # 0 or 1 (which of the two extraction runs produced this)

class ChunkExtractionResult(BaseModel):
    chunk_id: str
    items: List[RawGuidanceItem]  # 0 to ~3 items per chunk

# Stage 3 output (shown for context only — not produced by this stage)
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
│   ├── stage1_filter.py
│   ├── stage2_extractor.py    ← THIS FILE
│   ├── stage3_classifier.py
│   ├── stage4_validator.py
│   └── run_pipeline.py
├── prompts/
│   ├── stage2_extraction_prompt.txt   ← ALSO CREATE THIS
│   └── stage3_classification_prompt.txt
├── schemas.py                 ← unchanged
├── eval.py                    ← updated later
└── ... rest unchanged ...
```

---

## Implementation Order (Full Pipeline)

1. **Stage 0** — Segmenter (complete)
2. **Stage 1** — Filter (complete)
3. **Stage 4** — Validation rules (complete)
4. **Stage 2** — Per-chunk extractor ← YOU ARE HERE
5. **Stage 3** — Metric classifier
6. **run_pipeline.py** — Orchestrator + eval

Do not move to Stage 3 until the Stage 2 acceptance test passes.

---

## Stage 2 — Per-Chunk Extraction

### Purpose
For each candidate chunk, extract 0 to ~3 guidance items. The LLM's only job here is
finding passages and extracting values — NOT classifying metrics. Separating these two
cognitive tasks is the primary architectural fix for recall regression and misclassification.

### Input
`List[Chunk]` from Stage 1 (candidate chunks only)

### Output
`List[RawGuidanceItem]` — flat list of all extracted items across all chunks, with
metric left as free-text description, before vocabulary classification

---

### Implementation Logic

#### LLM Call Design

**Model:** gpt-4o (gpt-4o-mini is insufficient for extraction quality — confirmed in v1)
**Temperature:** 0 for both runs
**Structured output:** Yes — use `client.beta.chat.completions.parse()` with Pydantic schema
**Schema per call:** `ChunkExtractionResult` (small schema, 0-3 items, no metric enum)
**Runs per chunk:** 2 (union self-consistency — explained below)

The structured output schema for this stage (LLM output only — speaker/page added after):
```python
class RawGuidanceItem(BaseModel):
    passage: str               # verbatim from transcript, self-sufficient
    metric_description: str   # free text description of what is being guided
    guidance_value: Optional[str]  # "18-20" or "40" or None
    guidance_unit: Optional[str]   # "%" or "crore" or None
    timeline: str              # raw string from transcript

class ChunkExtractionResult(BaseModel):
    items: List[RawGuidanceItem]
```

speaker and page_number are NOT in the LLM output schema — they are added from chunk
metadata after the call. The LLM never needs to determine them.

#### System Prompt (Stage 2)

The prompt must be SHORT. Include only:

1. **Task definition (2 sentences):**
   Extract every statement where management gives a specific numeric target OR commits to a
   specific verifiable event, both requiring a timeframe verifiable within 4 quarters.

2. **Two-track qualification rule:**
   Track A: Must have a specific digit or numeric range AND a timeframe.
   Track B: Must be a specific verifiable binary event (plant commissioning, go-live,
   breakeven) AND a timeframe. A worded timeframe ("second half of this year") qualifies.

3. **Self-sufficiency rule:**
   The passage must be fully understandable without reading any other part of the transcript.
   If management accepts a figure from an analyst's question, include the analyst's question
   in the passage. Include enough context so the guidance is unambiguous.

4. **metric_description instruction:**
   Describe what is being guided in plain English. Do NOT use any label vocabulary.
   Examples: "EBITDA margin improvement of 25 basis points over FY27",
   "EV subsidiary revenue target of 40 crore in FY27",
   "New VAM-VAE plant commissioning in H1 FY27"

5. **3 positive examples + 2 negative examples:**

   Positive:
   - "We expect EBITDA margins of 18-20% in FY27"
     → passage: full sentence, metric_description: "Company-level EBITDA margin target for
       FY27", value: "18-20", unit: "%", timeline: "FY27"

   - "Our EV segment is currently at ₹20 crore and we expect it to double this year"
     → passage: full sentence, metric_description: "EV segment revenue target (derived:
       double of ₹20 crore = ₹40 crore)", value: "40", unit: "crore", timeline: "FY27"

   - "We expect to commission our VAM-VAE plant in H1 FY27"
     → passage: full sentence, metric_description: "VAM-VAE plant commissioning event",
       value: null, unit: null, timeline: "H1 FY27"

   Negative:
   - "We are confident of delivering good results" → NO extraction (no number, no timeframe)
   - "Demand environment remains positive" → NO extraction (no company-specific commitment)

6. **Output instruction:**
   Return an empty items list if no qualifying statements exist in this chunk.
   Do not extract past-quarter results, sector commentary, or unquantified statements.

**Do NOT include in this prompt:**
- The metric vocabulary list (that belongs in Stage 3)
- Deduplication rules (that belongs in Stage 4)
- Rejection rules for null values (that belongs in Stage 4)
- Any expected count or range ("typically 5-15 items") — this creates quota effects

#### Union Self-Consistency

Run the same LLM call twice per chunk (temperature=0, same prompt, same input).
Collect both results, then union them:

```python
all_items_run0: List[RawGuidanceItem] = extract_chunk(chunk, run_index=0)
all_items_run1: List[RawGuidanceItem] = extract_chunk(chunk, run_index=1)

# Union: keep an item if it appeared in EITHER run
# Fuzzy dedup within the union: if two items from different runs have >85% passage
# similarity (use difflib.SequenceMatcher), they are the same item — keep the one
# with the longer passage
combined = union_merge(all_items_run0, all_items_run1, similarity_threshold=0.85)
```

This directly fixes the oscillation problem observed in v1 (an item appearing in one run
but not another at temperature=0). Union means any item that appears in any run survives.
Precision loss from union is handled in Stage 4.

#### Post-Call: Attach Metadata from Chunk

After each LLM call returns a ChunkExtractionResult, populate speaker and page_number
from the chunk object (not from LLM output):

```python
for item in result.items:
    item.speaker = chunk.speaker
    item.page_number = chunk.page_start
    item.chunk_id = chunk.chunk_id
    item.run_index = run_index
```

#### Handling the Token Limit Problem (Mold-Tek)

The per-chunk approach eliminates the token limit failure by construction. Each chunk is
200-800 tokens. The extraction schema for a single chunk returns at most 3 items. There is
no risk of overflowing the 16,384 completion token limit.

---

### Edge Cases

**Derived numeric targets:** "Our EV revenue is currently ₹20 crore and we expect to
double it" — the target is ₹40 crore (not explicitly stated). The prompt's positive example
covers this: extract value="40", include derivation in metric_description.

**Range expressions:** "We expect revenue between ₹800 and ₹900 crore" → value="800-900".
"We expect revenue in the range of ₹800-900 crore" → same. Both cases → "800-900".

**Multiple items in one chunk:** A management answer may address two questions or volunteer
two guidance items. The schema `items: List[RawGuidanceItem]` with no max constraint handles
this naturally.

**Chunk is an analyst question with no management response yet:** Rare but possible if Stage 0
pairing had no following management turn. The LLM will return an empty items list (the
analyst's question alone is not guidance). No special handling needed.

**Percent vs percentage points:** "We expect margins to improve by 200 basis points" vs
"We expect margins of 18%". The metric_description captures this distinction in plain English
("200 basis point improvement" vs "absolute margin target of 18%"). Stage 3 classifies
accordingly.

---

### Acceptance Test — Stage 2

Run Stage 2 on all three target transcripts. Measure **passage-level recall** separately
from full-match recall.

**Passage-level recall definition:**
For each GT item, check if any extracted item's passage contains the GT item's passage text
as a substring (or fuzzy match >85%). This measures whether the LLM FOUND the right content,
regardless of whether it labelled it correctly. This is Stage 2's responsibility alone.

**Targets:**
- Passage-level recall across all three companies: ≥ 70% (baseline from single-pass was
  finding correct passages but mislabelling them, so this target starts higher than full-match)
- Items extracted per transcript: reasonable count (10-30 total before dedup).
  If <5 per transcript, under-extraction is still occurring — investigate prompt.
  If >60, Stage 1 filter is too loose or prompt is extracting noise.

**Run delta:**
Compare item counts between run 0 and run 1 per chunk. If >30% of chunks have different
item counts between runs (at temperature=0), log it — this indicates systematic instability
that Stage 3+4 alone may not fix.
