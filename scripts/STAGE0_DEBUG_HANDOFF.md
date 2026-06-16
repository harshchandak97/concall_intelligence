# Stage 0 Segmenter — Debug Handoff

**Purpose of this file:** Context dump for continuing Stage 0 debugging in a new chat.
Paste this file's content (or upload it) at the start of the new chat. The new chat
should also read `CLAUDE.md` and `specs/SPEC_STAGE0_SEGMENTER.md` for full background
and behavioural rules (do not write code unless explicitly asked, etc.).

---

## What Stage 0 is

Deterministic (non-LLM) segmenter that converts a raw PDF transcript into a list of
`Chunk` objects — Q&A pairs (analyst question + management answer combined) or solo
management monologue segments, each tagged with speaker, role, and page numbers.
This is stage 1 of 6 in the new two-pass extraction pipeline. Spec is at
`specs/SPEC_STAGE0_SEGMENTER.md`.

---

## Files created so far

| File | Purpose |
|---|---|
| `pipeline/__init__.py` | empty — makes `pipeline` a package |
| `pipeline/models.py` | `Chunk`, `ChunkRole`, `RawGuidanceItem`, `ChunkExtractionResult`, `ClassifiedItem` (Pydantic models for all 6 stages) |
| `pipeline/stage0_segmenter.py` | the segmenter implementation — `segment()`, `extract_pages_from_pdf()`, plus internal helpers `_split_into_turns`, `_classify_roles`, `_create_qa_pairs`, `_split_chunk` |
| `test_stage0_acceptance.py` | runs Tests 2, 3, 4 from the spec's acceptance test across all 3 companies (Fineotex, Sandhar, Mold-Tek) |
| `raw_turns_check.py` | debug script — prints raw (speaker, role) pairs BEFORE Q&A pairing (this is the correct way to run "Test 1" from the spec) |
| `raw_text_check.py` | debug script — prints raw pypdf-extracted text page by page |
| `diagnose_stage0_failures.py` | **written but NOT YET RUN** — diagnoses the Test 4 failures below (see "Pending next step") |

All files are at:
`/Users/harshchandak/Projects/Building/AI_engineer/concall_intelligence/`

---

## Test results so far

### Test 1 (Fineotex) — PASSED
Ran `raw_turns_check.py` on Fineotex. All 4 known management names (Aarti Jhunjhunwala,
Arindam Choudhuri, Yusuf Contractor, Sanjay Tibrewala) correctly tagged `management`.
Moderator correctly tagged `moderator`. 10 analyst names correctly tagged `analyst`.
One cosmetic issue: a literal `"MANAGEMENT:"` header line (from the participant-list
block at the top of the transcript) gets picked up as a fake speaker named "MANAGEMENT"
and tagged `management`. Harmless — becomes its own chunk that Stage 1 will filter out.
**Decision: leave as-is for now, not blocking.**

### Tests 2/3/4 — `test_stage0_acceptance.py` output:

```
  Fineotex Chemical
Test 2 — Chunk count: 33
  PASS — within typical 30-80 range
Test 3 — Q&A pairing: 28/33 = 85%
  PASS — meets >=60% threshold
Test 4 — GT item containment (2 GT items)
  FAIL  GT id 1: not found in any chunk
  FAIL  GT id 2: not found in any chunk
  Test 4 FAILED — 2/2 GT items not found

  Sandhar Technologies
Fewer than 5 speaker turns detected. Falling back to page-level chunking (degraded mode).
Test 2 — Chunk count: 21
  OK — within 10-200, outside typical 30-80 (check if expected)
Test 3 — Q&A pairing: 0/21 = 0%
  WARNING — below 60% threshold
Test 4 — GT item containment (8 GT items)
  PASS  GT id 1: found in chunk_005
  FAIL  GT id 2: not found in any chunk
  PASS  GT id 3: found in chunk_009
  FAIL  GT id 4: not found in any chunk
  PASS  GT id 5: found in chunk_011
  PASS  GT id 6: found in chunk_007
  PASS  GT id 7: found in chunk_007
  PASS  GT id 8: found in chunk_007
  Test 4 FAILED — 2/8 GT items not found

  Mold-Tek Packaging
Test 2 — Chunk count: 5
  WARNING: <10 chunks — speaker regex may be too strict
Test 3 — Q&A pairing: 0/5 = 0%
  WARNING — below 60% threshold
Test 4 — GT item containment (10 GT items)
  FAIL  GT id 1 through 10: not found in any chunk
  Test 4 FAILED — 10/10 GT items not found

OVERALL: FAIL
```

---

## Diagnosis / hypotheses (not yet confirmed)

**Important context on transcript sizes:** all 3 test transcripts are ~20 pages, not
60 pages. For mid/small-cap Indian companies (₹500cr-₹10,000cr, the target universe),
12-25 page transcripts are normal and representative — the spec's "30-80 chunks for a
60-page transcript" benchmark was likely calibrated against a large-cap reference
(Asian Paints was the original test company before being replaced). Fineotex's 33
chunks for ~20 pages (~1.65 chunks/page) is actually proportionally *higher* density
than the 60-page benchmark, so **Fineotex's Test 2 result is fine** — the real issues
are Test 4 (Fineotex) and Tests 2/3/4 (Sandhar, Mold-Tek).

### Fineotex (33 chunks, 85% QA pairing — structure looks healthy, but both GT items fail)
Hypothesis: **GT-text issue, not a Stage 0 chunking bug.**
- GT1 passage contains an en-dash (`–`) in "as soon as – as quickly as possible" —
  pypdf extraction may render this differently than however the GT file was typed,
  causing a normalized-string mismatch even if the chunk itself is correct.
- GT2 passage contains a literal `…` ellipsis in the middle of Sanjay Tibrewala's
  answer — this strongly suggests the GT passage was *edited/truncated* when written
  (non-verbatim), which would make exact-substring matching impossible regardless of
  Stage 0's correctness.
- **Not yet confirmed** — `diagnose_stage0_failures.py` Part A checks each GT
  sub-passage against the FULL transcript text (not individual chunks) and does a
  binary search to pinpoint exactly where the normalized text diverges. This will
  tell us definitively: GT-file problem (fix the GT file) vs. genuine Stage 0
  chunking/pairing problem (fix the segmenter).

### Sandhar (fallback triggered — <5 raw speaker turns detected)
Hypothesis: **Sandhar's transcript uses a different speaker-header format** than
Fineotex's `"Name:"` / `"Name – Title:"` style, so none of the 5 regex patterns in
`_compile_speaker_patterns()` (stage0_segmenter.py) match. Result: <5 raw turns →
fallback to page-level chunking (one chunk per PDF page, `is_qa_pair=False` always,
which explains the 0% QA pairing and the 2 GT misses).
- **Not yet confirmed** — `diagnose_stage0_failures.py` Part B prints all raw
  (speaker, role) turns detected plus the first ~2500 chars of raw extracted text,
  to reveal the actual header format used in this transcript.

### Mold-Tek (5 final chunks, no fallback triggered — so ≥5 raw turns exist, but something collapsed almost everything into 5 chunks)
Hypothesis: similar to Sandhar — **most of the transcript's speaker headers aren't
matching the regex**, so the few turns that ARE detected are huge (opening monologue
type), and the long-turn splitter (`_split_chunk`, >1500 words → split at `\n\n`)
produced ~5 sub-chunks from very few parent turns. Need to see the actual raw turns
to confirm.
- **Not yet confirmed** — `diagnose_stage0_failures.py` Part C does the same raw-turn
  inspection for Mold-Tek.

---

## PENDING NEXT STEP

Run this and paste the full output into the new chat:

```bash
python diagnose_stage0_failures.py
```

This produces:
- **Part A** (Fineotex): for GT1 and GT2, whether each sub-passage is found anywhere
  in the full transcript text, and if not, the longest matching prefix + where the
  mismatch starts (pinpoints the exact differing character/phrase).
- **Part B** (Sandhar): raw turn count, full (speaker, role) list, all turns with text
  snippets, and first 2500 chars of raw extracted text.
- **Part C** (Mold-Tek): same as Part B.

From that output, the next chat should be able to determine:
1. Whether Fineotex's GT1/GT2 failures require fixing the GT file (re-generate
   verbatim passages) vs. fixing Stage 0 logic.
2. What new speaker-header regex pattern(s) need to be added to
   `_compile_speaker_patterns()` in `pipeline/stage0_segmenter.py` to handle
   Sandhar's and Mold-Tek's formats — and whether one fix covers both companies
   or each needs its own pattern.

---

## Key implementation details to remember when fixing

- Speaker patterns are in `_compile_speaker_patterns()`, tried in priority order
  D → E → A → B → C (moderator/operator → "Management:" → "Name – Title:" →
  "Name (Title):" → "Name:" with ≥2 words required).
- Fallback to page-level chunking triggers when `len(raw_turns) < 5`
  (see `segment()` in `pipeline/stage0_segmenter.py`).
- Per project conventions (see `CLAUDE.md` / memory): fix existing rules/regex before
  adding new ones where possible, avoid overfitting to a single company, don't grow
  complexity for edge cases — but a missing header-format pattern that breaks 2 of 3
  test companies is a core correctness issue, not an edge case.
- Ground truth files: `data/{company}_Q4_FY26_ground_truth_v1.txt`. Parsed by
  `parse_ground_truth()` in `test_stage0_acceptance.py` — passage field is
  `passage: "..."` (multi-line, DOTALL), followed by `speaker:` field on next line.
