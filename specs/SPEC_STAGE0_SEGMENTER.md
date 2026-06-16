# Stage 0 — Segmenter Spec
## Concall Intelligence Extraction Pipeline

**This file covers: Stage 0 (Deterministic Segmentation)**
**File to create: `pipeline/stage0_segmenter.py`**
**Build order position: 1 of 6 — build this first, nothing depends on it yet**

Before writing any code, read `CLAUDE.md` in the project root. Follow the behavioural
rules there exactly. Do not write code for any other stage — this file covers Stage 0 only.

---

## Architecture Overview

```
PDF Transcript
      │
      ▼
[Stage 0] Deterministic Segmentation (pure Python)      ← YOU ARE HERE
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
# Stage 0 output
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

# Stage 2 output (one per item found within a chunk)
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

# Stage 3 output (metric label added to each raw item)
class ClassifiedItem(BaseModel):
    # All fields from RawGuidanceItem, plus:
    chunk_id: str
    passage: str
    speaker: str
    page_number: int
    metric_description: str
    guidance_value: Optional[str]
    guidance_unit: Optional[str]
    timeline: str              # still raw at this point
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
│   ├── stage0_segmenter.py    ← THIS FILE
│   ├── stage1_filter.py
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

1. **Stage 0** — Segmenter ← YOU ARE HERE
2. **Stage 1** — Filter
3. **Stage 4** — Validation rules (built before Stage 2, tested with synthetic inputs)
4. **Stage 2** — Per-chunk extractor
5. **Stage 3** — Metric classifier
6. **run_pipeline.py** — Orchestrator + eval

Do not move to Stage 1 until the Stage 0 acceptance test passes.

---

## Stage 0 — Deterministic Segmentation

### Purpose
Convert raw PDF text into Q&A-paired chunks with speaker metadata attached. This eliminates
the LLM's need to track speaker identity or search across a 50K-character document.

### Input
- `transcript_text: str` — full text extracted from PDF via pypdf (already implemented)
- `transcript_pages: Dict[int, str]` — mapping of page_number → page_text (for page attribution)
- `call_date: date` — date of the earnings call (from filename or metadata)

### Output
`List[Chunk]` — ordered list of chunks. Each chunk is either:
- A management monologue segment (opening remarks, long answer)
- A Q&A pair: analyst question + immediately following management response combined into
  one chunk so the management answer always has its question context

---

### Implementation Logic

#### Step 1: Speaker Turn Detection

Indian concall transcripts use several speaker header formats. Detect them all:

```
Regex pattern (apply per line, case-insensitive):
Pattern A: "FirstName LastName – Title:" or "FirstName LastName - Title:"
           e.g. "Harsh Chandak – Managing Director:"
Pattern B: "FirstName LastName (Title):"
           e.g. "Harsh Chandak (MD & CEO):"
Pattern C: "FirstName LastName:" (name only, no title)
           e.g. "Harsh Chandak:"
Pattern D: "MODERATOR:" or "OPERATOR:" or "Moderator:" (exact keywords)
Pattern E: "Management:" (generic — treat as management role)
```

Build a master regex that matches all patterns and captures the speaker name.
Split the full transcript text on these speaker headers to produce raw turns.
Each turn = (speaker_name, turn_text, char_start_in_transcript).

#### Step 2: Role Classification

```
Role assignment rules (in priority order):
1. If speaker name contains "Moderator", "Operator", "Operator/Moderator" → MODERATOR
2. If speaker name is "Management" → MANAGEMENT  
3. Identify management speakers: the first 3-4 turns of the call are always management
   (CEO/MD/CFO opening remarks). Collect these speaker names as the management_speakers set.
   Any speaker name appearing in management_speakers in later turns → MANAGEMENT
4. All other speakers → ANALYST (assumes everyone not identified as management is an analyst)
```

This heuristic works for Indian concalls where management speakers are introduced by name at
the start and use the same name throughout. Edge case: a guest speaker or IR contact may be
misclassified — acceptable, Stage 2 will still find their guidance if any.

#### Step 3: Q&A Pairing

After splitting into turns with roles:

```
For each ANALYST turn:
    Find the MANAGEMENT turn that immediately follows it (skip MODERATOR turns between them)
    Create a combined Q&A chunk:
        text = analyst_turn_text + "\n\n" + management_turn_text
        speaker = management_speaker_name  (the answer-giver, not the questioner)
        page_start = page of analyst turn start
        page_end = page of management turn end
        is_qa_pair = True

For each standalone MANAGEMENT turn (not immediately preceded by an ANALYST turn):
    Create a solo management chunk:
        text = management_turn_text
        speaker = management_speaker_name
        is_qa_pair = False

Skip standalone MODERATOR turns entirely (administrative text, no guidance content).
```

**Why Q&A pairing matters:** The Fineotex GT1 case — a guidance figure appears in the
analyst's question and management explicitly accepts it. If the analyst question is excluded
from the chunk, Stage 2 cannot see the figure and cannot extract the item. The Q&A pair
as atomic unit solves this.

#### Step 4: Long Turn Splitting

A management opening monologue can be 3,000+ tokens. Single-pass attention degrades over
long inputs. Split any chunk whose text exceeds 1,500 tokens at paragraph boundaries:

```
IF len(chunk.text.split()) > 1500:
    Split at double-newline ("\n\n") boundaries
    Maintain 200-character overlap between adjacent sub-chunks
        (last 200 chars of sub-chunk N become first 200 chars of sub-chunk N+1)
    Assign each sub-chunk the same speaker/role/page metadata as the parent
    Label sub-chunks: chunk_001a, chunk_001b, chunk_001c
```

The 200-character overlap ensures a guidance item that straddles a split point appears in
at least one sub-chunk's context. Stage 4 dedup handles the case where both sub-chunks
extract the same item.

#### Step 5: Page Attribution

For each chunk, assign page_start and page_end by scanning char_start and char_end against
the page boundary offsets computed during pypdf extraction. Store the mapping of character
offset → page number as a helper data structure built once during PDF loading.

---

### Edge Cases

**Multiple management speakers in one Q&A:** Some Indian concalls have the MD answer part
of a question and the CFO add to it. These appear as two consecutive MANAGEMENT turns. Combine
them into one chunk with speaker = first management speaker. The passage in Stage 2 will
capture whichever speaker made the guidance statement; Stage 3 classification is unaffected.

**Moderator reads out a question from written submission:** The moderator quotes an analyst
question verbatim. Treat the entire moderator turn as an ANALYST turn for pairing purposes if
it contains a question mark and is followed by a management turn.

**No explicit speaker headers:** Some older BSE transcripts lack consistent formatting. If
the speaker detection regex matches fewer than 5 turns in the entire document, fall back to
page-level chunking (each PDF page = one chunk, is_qa_pair=False) and log a warning. This
is a degraded mode but prevents a complete Stage 0 failure.

**Management introduction turn:** First ~2 turns typically include "Good morning everyone,
thank you for joining" with no guidance. These still pass to Stage 1 (no special handling
needed — Stage 1 will filter them).

---

### Acceptance Test — Stage 0

Before moving to Stage 1, verify Stage 0 output on all three target transcripts:

**Test 1 — Speaker detection completeness:**
Print all unique (speaker_name, role) pairs. Manually verify:
- All known management names are assigned MANAGEMENT role
- No management speaker is misclassified as ANALYST
- Moderator is correctly identified

**Test 2 — Chunk count sanity:**
- A typical 60-page transcript should produce 30–80 chunks
- If chunk count < 10: regex is too strict, failing to find speaker headers
- If chunk count > 200: regex is too loose, splitting on non-headers

**Test 3 — Q&A pairing coverage:**
- At least 60% of total chunks should be Q&A pairs (is_qa_pair=True)
- Solo management chunks should be predominantly the opening monologue (first 2-3 chunks)

**Test 4 — GT item chunk containment [critical]:**
For each GT item across all three companies, locate its passage text and confirm it appears
in exactly one chunk's text field. A GT item not found in any chunk = Stage 0 failure.
This must be 100%. No exceptions.
