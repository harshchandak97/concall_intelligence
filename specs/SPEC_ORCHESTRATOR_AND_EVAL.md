# Orchestrator + Eval Spec
## Concall Intelligence Extraction Pipeline

**This file covers: `run_pipeline.py` (orchestrator) + `eval.py` (two-level recall update)**
**Build order position: 6 of 6 — all five stages must be complete and tested before starting**

Before writing any code, read `CLAUDE.md` in the project root. Follow the behavioural
rules there exactly.

**Prerequisite check before starting:**
- Stage 0 acceptance test passed (GT item chunk containment = 100%)
- Stage 1 acceptance test passed (GT item filter recall = 100%)
- Stage 4 standalone unit tests passed
- Stage 2 acceptance test passed (passage-level recall ≥ 70%)
- Stage 3 acceptance test passed (full-match recall ≥ 60%)

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
[Stage 4] Deterministic Validation + Dedup (pure Python)
      │  Output: List[GuidanceItem] — final schema, identical to ground truth structure
      │
      ▼
PostgreSQL Storage + Eval      ← YOU ARE HERE
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
# Stage 0 output
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

# Stage 2 output
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

# Stage 3 output
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
│   ├── stage2_extractor.py
│   ├── stage3_classifier.py
│   ├── stage4_validator.py
│   └── run_pipeline.py        ← THIS FILE
├── prompts/
│   ├── stage2_extraction_prompt.txt
│   └── stage3_classification_prompt.txt
├── schemas.py                 ← unchanged
├── eval.py                    ← ALSO UPDATE THIS FILE
└── ... rest unchanged ...
```

`run_pipeline.py` is the new entry point. It replaces the current single-pass `main.py`
for the multi-stage architecture. `main.py` is retained for reference and comparison.

---

## Implementation Order (Full Pipeline)

1. **Stage 0** — Segmenter (complete)
2. **Stage 1** — Filter (complete)
3. **Stage 4** — Validation rules (complete)
4. **Stage 2** — Per-chunk extractor (complete)
5. **Stage 3** — Metric classifier (complete)
6. **run_pipeline.py + eval.py** ← YOU ARE HERE

---

## Part A — run_pipeline.py (Orchestrator)

### Purpose
Wire all five stages together into a single command. Accept a transcript PDF path and
call_date, run the full pipeline, save results to PostgreSQL, and print eval scores.

### Interface

```
python pipeline/run_pipeline.py \
    --pdf transcripts/fineotex_Q4_FY26.pdf \
    --call_date 2026-05-15 \
    --company "Fineotex Chemical" \
    --quarter "Q4 FY26" \
    --ground_truth data/fineotex_Q4_FY26_ground_truth.txt
```

`--ground_truth` is optional. If provided, eval runs automatically after extraction.
If not provided, pipeline runs extraction and saves to DB only.

### Orchestration Logic

```python
def run_pipeline(pdf_path, call_date, company, quarter, ground_truth_path=None):

    # 1. Extract text from PDF (existing pypdf implementation)
    transcript_text, transcript_pages = extract_pdf(pdf_path)

    # 2. Stage 0 — Segmentation
    chunks: List[Chunk] = segment(transcript_text, transcript_pages, call_date)
    log(f"Stage 0: {len(chunks)} chunks produced")

    # 3. Stage 1 — Filter
    candidate_chunks: List[Chunk] = filter_chunks(chunks)
    log(f"Stage 1: {len(candidate_chunks)} candidate chunks (of {len(chunks)} total)")

    # 4. Stage 2 — Per-chunk extraction (2 runs per chunk, union merge)
    raw_items: List[RawGuidanceItem] = extract_all_chunks(candidate_chunks)
    log(f"Stage 2: {len(raw_items)} raw items extracted")

    # 5. Stage 3 — Metric classification
    classified_items: List[ClassifiedItem] = classify_all(raw_items)
    log(f"Stage 3: {len(classified_items)} items classified")

    # 6. Stage 4 — Validation + dedup
    final_items: List[GuidanceItem] = validate_and_dedup(
        classified_items, transcript_text, call_date
    )
    log(f"Stage 4: {len(final_items)} items after validation and dedup")

    # 7. Save to PostgreSQL (existing DB + SQLAlchemy implementation)
    save_to_db(final_items, company, quarter)

    # 8. Run eval if ground truth provided
    if ground_truth_path:
        scores = run_eval(final_items, ground_truth_path)
        print_eval_report(scores)

    return final_items
```

### Logging Requirements

At each stage boundary, print:
- Item count in / item count out
- For Stage 2: total LLM calls made (chunks × 2 runs)
- For Stage 4: rejection count per rule
- Total wall time per stage

This is the primary debugging interface — when eval scores are wrong, stage-boundary
counts reveal which stage is failing.

---

## Part B — eval.py Updates (Two-Level Recall Measurement)

### Purpose
Update the existing eval.py to measure two separate recall levels. This is the diagnostic
tool for identifying whether failures are Stage 2 (finding) or Stage 3 (labelling).

### Two-Level Recall Definition

```
Passage-level recall (Stage 2 responsibility):
    For each GT item: was a passage found that matches the GT passage?
    Match criterion: difflib.SequenceMatcher ratio > 0.85 between extracted passage
    and GT passage.
    Numerator: GT items with at least one matching extracted passage
    Denominator: total GT items

Full-match recall (pipeline end-to-end):
    For each GT item: is there a final GuidanceItem that matches on passage + metric
    + value (±10% midpoint) + timeline?
    This is the existing eval logic — keep it unchanged.

Gap = passage-level recall − full-match recall
    = items found by Stage 2 but lost in Stage 3 (mislabelled) or Stage 4 (rejected)
```

### Diagnostic Output

When eval runs, print:

```
=== EVAL REPORT: Fineotex Chemical Q4 FY26 ===

GT items: 2
Extracted items (after Stage 4): 4

Passage-level recall:  2/2 = 100%
Full-match recall:     1/2 = 50%
Precision:             1/4 = 25%

Gap (found but lost): 1 item
  → GT item: ebitda_margin_pct | 18-20 | FY27
    Closest extracted: other_ebitda_margin_delta | 18-20 | FY27
    Miss reason: metric mismatch (Stage 3 failure)

Missed GT items (not found at all):
  → None

False positives (extracted, no GT match):
  → revenue_absolute | 40 | FY27 (chunk_003)
  → commissioning_event | null | H1 FY27 (chunk_007)
  → other_ev_revenue_absolute | 40 | FY27 (chunk_003) [duplicate]
```

The "miss reason" field identifies the failure stage:
- metric mismatch → Stage 3 failure → add few-shot example
- passage not found → Stage 2 failure → investigate extraction prompt
- timeline mismatch → Stage 4 normalization failure → fix normalize_timeline
- value mismatch → Stage 2 extraction failure → investigate value parsing

### Eval Function Signatures

```python
def run_eval(
    extracted_items: List[GuidanceItem],   # Stage 4 final output
    stage2_raw_items: List[RawGuidanceItem],  # Stage 2 output (for passage-level recall)
    ground_truth_path: str,
    call_date: date,
) -> EvalScores:
    ...

class EvalScores(BaseModel):
    company: str
    quarter: str
    gt_count: int
    extracted_count: int
    passage_level_recall: float    # new
    full_match_recall: float       # existing
    precision: float               # existing
    gap: float                     # new: passage_level_recall - full_match_recall
    missed_gt_items: List[str]     # GT items with no passage match
    mislabelled_items: List[dict]  # found but wrong metric/value/timeline
    false_positives: List[str]     # extracted items with no GT match
```

---

## End-to-End Acceptance Test

Run the full pipeline on all three target transcripts.

**Primary targets:**
- Full-match recall ≥ 70% across all three companies
- Precision ≥ 60% across all three companies

**Diagnostic targets:**
- Passage-level recall ≥ 70% (if this is low, Stage 2 or Stage 0/1 is the bottleneck)
- Gap ≤ 15 percentage points (if gap is large, Stage 3 needs more few-shot examples)

**Null FP elimination:** Zero items of type `[any non-commissioning metric] | null`
in the final output. The Rule 1 rejection in Stage 4 must have caught them all.

**If targets are not met:**
1. Check passage-level recall first. If low → the Stage 2 extraction prompt needs work.
2. Check the gap. If gap > 15 points → Stage 3 few-shot examples need expansion.
3. Check precision. If low → Stage 4 rejection rules need tightening or Stage 1 filter
   is passing too many irrelevant chunks.

Use the diagnostic output from eval.py to identify exactly which items are failing and why
before making any changes.

---

## Cost Estimate at Scale (600 Transcripts/Quarter)

| Stage | Model | Calls per transcript | Approx tokens/call | Cost per transcript |
|---|---|---|---|---|
| Stage 2 | gpt-4o | ~40 chunks × 2 runs = 80 | 800 input + 200 output | ~$0.15 |
| Stage 3 | gpt-4o | ~15 items × 1 = 15 | 400 input + 50 output | ~$0.02 |
| **Total** | | | | **~$0.17–0.20** |
| At 600 transcripts | | | | **~$100–120/quarter** |

This is acceptable for personal use. If cost becomes a concern at scale, Stage 1's
gpt-4o-mini binary classifier can reduce Stage 2 calls by 30-40%, saving ~$30-40/quarter.
Do not add the gpt-4o-mini layer until you have baseline recall numbers from the full
pipeline — do not introduce a new bottleneck before measuring the current ones.
