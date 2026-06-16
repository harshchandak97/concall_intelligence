# Extraction Pipeline Specification — Concall Intelligence

## Purpose of This Document

This spec is the single source of truth for implementing the multi-stage guidance extraction
pipeline. It is self-sufficient — Claude can generate code for each stage using only this
document plus the project's existing files (schemas.py, eval.py, main.py).

Each stage has: purpose, input/output contract, full implementation logic, edge cases,
and an acceptance test that must pass before moving to the next stage.

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

The structured output schema for this stage:
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

After Stage 3 assigns the metric label, compute credibility_scorable in Python:

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
the classification but set guidance_value=null in Stage 4.

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
prompt before declaring Stage 3 complete.

---

## Stage 4 — Deterministic Validation and Deduplication

### Purpose
Apply all quality filters as deterministic Python code. Every rule that was "in the prompt
but ignored by the LLM" lives here. This stage cannot be bypassed and has no LLM calls.

### Input
`List[ClassifiedItem]` from Stage 3 (after credibility_scorable computed)

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
The capacity number is a separate guidance item if management explicitly guided on it. Do not
extract the capacity into the commissioning item's value field.

**Overlapping sub-chunks both produce the same item:** Sub-chunk overlap (200-char) is
specifically designed to catch cross-boundary items. The dedup step (Rule 5) handles this —
both extractions are identical or near-identical and merge into one item.

---

### Acceptance Test — Stage 4

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

These are the v1 exit criteria applied to the new pipeline. If these are not met, identify
whether misses are Stage 2 failures (passage not found) or Stage 3 failures (wrong label)
using the two-level recall split from Stage 2's acceptance test.

**Null FP elimination:** All items of type `capacity_addition | null`,
`commissioning_event | null` (the null-value false positive pattern from v1) should be
either correctly retained (commissioning_event is valid with null) or rejected (all others
with null values). Zero null-value false positives for non-commissioning metrics.

---

## End-to-End Eval — Two-Level Recall Measurement

Update `eval.py` to measure two separate recall levels:

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
    This is the existing eval logic.

The gap between passage-level recall and full-match recall = items found but mislabelled.
If gap > 15 percentage points: Stage 3 is the bottleneck. Add few-shot examples.
If passage-level recall is low: Stage 2 (or Stage 0/1) is the bottleneck. Fix extraction.
```

---

## File Structure Changes

Add the following to the existing project structure:

```
concall-intelligence/
├── pipeline/
│   ├── __init__.py
│   ├── models.py              ← Chunk, RawGuidanceItem, ClassifiedItem (internal models)
│   ├── stage0_segmenter.py    ← PDF → List[Chunk]
│   ├── stage1_filter.py       ← List[Chunk] → List[Chunk] (filtered)
│   ├── stage2_extractor.py    ← List[Chunk] → List[RawGuidanceItem]
│   ├── stage3_classifier.py   ← List[RawGuidanceItem] → List[ClassifiedItem]
│   ├── stage4_validator.py    ← List[ClassifiedItem] → List[GuidanceItem]
│   └── run_pipeline.py        ← orchestrator: calls stages 0-4, saves to DB, runs eval
├── prompts/
│   ├── ... existing v1-v8 prompts ...
│   ├── stage2_extraction_prompt.txt   ← system prompt for Stage 2
│   └── stage3_classification_prompt.txt  ← system prompt for Stage 3
├── schemas.py                 ← unchanged (GuidanceItem, ExtractionResult, GuidanceRecord)
├── eval.py                    ← updated with two-level recall measurement
└── ... rest unchanged ...
```

`run_pipeline.py` is the new entry point. It replaces the current single-pass `main.py` for
the multi-stage architecture. `main.py` is retained for reference and comparison.

---

## Implementation Order

Build in this sequence. Do not move to the next stage until the acceptance test passes.

1. **Stage 0** — Segmenter. Pure Python, no LLM. Fastest to build and test.
   Acceptance: GT item chunk containment = 100%, chunk count sanity check.

2. **Stage 1** — Filter. Pure Python. Build immediately after Stage 0.
   Acceptance: GT item filter recall = 100%.

3. **Stage 4 validation rules** — Build BEFORE Stage 2. Define the rejection rules as
   standalone functions that can be tested with synthetic inputs. This way, as soon as
   Stage 2 produces output, Stage 4 can immediately clean it.

4. **Stage 2** — Per-chunk extractor with union self-consistency.
   Acceptance: Passage-level recall ≥ 70%.

5. **Stage 3** — Metric classifier.
   Acceptance: Full-match recall ≥ 60%, then iterate few-shot examples until ≥ 70%.

6. **run_pipeline.py** — Wire all stages together, add PostgreSQL storage, run full eval.
   Acceptance: End-to-end full-match recall ≥ 70%, precision ≥ 60%.

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
