"""
Stage 0 — Deterministic Segmenter

Converts raw PDF transcript text into Q&A-paired Chunk objects with speaker
metadata attached. No LLM involved — pure Python text processing.

Pipeline position: 1 of 6 (build first, nothing depends on it yet)

Input:
    transcript_text   : str              — full text extracted from PDF via pypdf
    transcript_pages  : Dict[int, str]   — {page_number: page_text}

Output:
    List[Chunk]  — ordered chunks ready for Stage 1 filtering

Public API:
    segment(transcript_text, transcript_pages) -> List[Chunk]
    extract_pages_from_pdf(pdf_path) -> Dict[int, str]   # helper for callers
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from pypdf import PdfReader

from .models import Chunk, ChunkRole

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Speaker header detection
# Patterns applied in priority order — first match wins.
# Applied per line (stripped). Returns speaker name if matched, else None.
# ─────────────────────────────────────────────────────────────────────────────

# Type alias for compiled pattern list
_PatternList = List[Tuple[str, re.Pattern]]

# A "name word" is either a normal capitalised word (Lakshmana, Rao, O'Brien)
# or a cluster of 1-3 initials (J., S.K., S.K.M.). The initials form is needed
# for names like "J. Lakshmana Rao" -- the old [A-Z][a-zA-Z']+ pattern
# required >=2 letters with no period, so "J." never matched anything.
_NAME_WORD = r"(?:[A-Z][a-zA-Z']+|(?:[A-Z]\.){1,3})"
_NAME = rf"{_NAME_WORD}(?:\s+{_NAME_WORD}){{0,3}}"


def _compile_speaker_patterns() -> _PatternList:
    return [
        # Pattern D: exact moderator/operator keywords (case-insensitive)
        (
            "D",
            re.compile(
                r"(MODERATOR|OPERATOR|Moderator|Operator|Operator\s*/\s*Moderator)\s*:",
                re.IGNORECASE,
            ),
        ),
        # Pattern E: generic "Management:"
        (
            "E",
            re.compile(r"(Management)\s*:", re.IGNORECASE),
        ),
        # Pattern A: "First Last – Title:" or "First Last - Title:"
        # Name = 1–4 name-words; title is 1–80 non-colon chars
        (
            "A",
            re.compile(rf"({_NAME})\s*[–\-]\s*[^:\n]{{1,80}}:"),
        ),
        # Pattern B: "First Last (Title):"
        (
            "B",
            re.compile(rf"({_NAME})\s*\([^)]{{1,100}}\)\s*:"),
        ),
        # Pattern C: "First Last:" — requires ≥2 words to avoid false positives
        # (e.g. "Note:" or "Outlook:" would be single-word and rejected)
        (
            "C",
            re.compile(rf"({_NAME})\s*:"),
        ),
    ]


_SPEAKER_PATTERNS: _PatternList = _compile_speaker_patterns()
_MODERATOR_KEYWORDS = frozenset({"moderator", "operator"})
_PATTERN_PRIORITY = {"D": 0, "E": 1, "A": 2, "B": 3, "C": 4}


def _find_speaker_matches(text: str) -> List[Tuple[int, int, str, str]]:
    """
    Find all candidate speaker-header matches anywhere in *text*.

    Returns (start, end, name, pattern_id) tuples sorted by position.
    Overlapping matches at/near the same position are resolved by pattern
    priority (D > E > A > B > C) -- whichever pattern wins "owns" that span,
    and any other match overlapping it is dropped.
    """
    raw: List[Tuple[int, int, str, str]] = []
    for pid, pattern in _SPEAKER_PATTERNS:
        for m in pattern.finditer(text):
            name = m.group(1).strip()
            # Pattern C guard: reject single-word matches like "Outlook:"
            if pid == "C" and len(name.split()) < 2:
                continue
            raw.append((m.start(), m.end(), name, pid))

    raw.sort(key=lambda t: (t[0], _PATTERN_PRIORITY[t[3]]))

    kept: List[Tuple[int, int, str, str]] = []
    last_end = -1
    for start, end, name, pid in raw:
        if start < last_end:
            continue
        kept.append((start, end, name, pid))
        last_end = end

    return kept


def _boundary_kind(text: str, start: int) -> Optional[str]:
    """
    Classify the gap immediately before position *start*:
      "strong" — start of document, or a line break appears in the gap
      "weak"   — gap (whitespace only) is preceded by '.', '?' or '!'
      None     — not a valid turn-boundary position
    """
    j = start
    saw_newline = False
    while j > 0 and text[j - 1] in " \t\r\n":
        if text[j - 1] == "\n":
            saw_newline = True
        j -= 1

    if j == 0 or saw_newline:
        return "strong"
    if text[j - 1] in ".?!":
        return "weak"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Split transcript into raw turns
# ─────────────────────────────────────────────────────────────────────────────

# (speaker_name, turn_text, char_start, char_end)
_RawTurn = Tuple[str, str, int, int]


def _split_into_turns(transcript_text: str) -> List[_RawTurn]:
    """
    Find every valid speaker-header turn boundary in the transcript and
    split the text between consecutive boundaries into turns.

    Boundaries are found anywhere in the text (not just at line starts) via
    _find_speaker_matches + _boundary_kind. "Strong" boundaries (start of
    document or after a line break) are always kept. "Weak" boundaries
    (after sentence-ending punctuation, no line break) are only kept if that
    speaker name recurs at another valid boundary elsewhere -- this is what
    lets transcripts with no inter-speaker line breaks (e.g. Sandhar) still
    be split correctly, without letting a one-off "Capitalised Words:"
    phrase mid-paragraph be mistaken for a speaker change.

    Returns a list of (speaker, text, char_start, char_end).
    """
    candidates = _find_speaker_matches(transcript_text)

    classified: List[Tuple[int, int, str, str]] = []  # start, end, name, kind
    for start, end, name, _pid in candidates:
        kind = _boundary_kind(transcript_text, start)
        if kind is not None:
            classified.append((start, end, name, kind))

    name_counts: Dict[str, int] = {}
    for _, _, name, _ in classified:
        name_counts[name] = name_counts.get(name, 0) + 1

    boundaries = [
        (start, end, name)
        for start, end, name, kind in classified
        if kind == "strong" or name_counts[name] >= 2
    ]

    turns: List[_RawTurn] = []
    for i, (_start, end, name) in enumerate(boundaries):
        text_start = end
        text_end = (
            boundaries[i + 1][0] if i + 1 < len(boundaries) else len(transcript_text)
        )
        turn_text = transcript_text[text_start:text_end].strip()
        if turn_text:
            turns.append((name, turn_text, text_start, text_end))

    return turns


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Role classification
# ─────────────────────────────────────────────────────────────────────────────

# Extends _RawTurn with role
_TurnWithRole = Tuple[str, str, int, int, ChunkRole]

# Matches "MR./MS./MRS./DR. NAME -" inside the participant-list header,
# capturing the ALL-CAPS name before the title text that follows the dash.
_ROSTER_NAME_RE = re.compile(r"(?:MR|MS|MRS|DR)\.\s*([A-Z][A-Z.\s]*?)\s*[–\-]")


def _extract_management_roster(transcript_text: str) -> set[str]:
    """
    Parse the participant-list header near the top of every transcript --
    "MANAGEMENT: MR. X - Title, MR. Y - Title ... MODERATOR: MS. Z - Title"
    -- and return the management speaker names normalised to the Title Case
    form used as speaker headers in the transcript body (e.g. "Jayant Davar",
    "J. Lakshmana Rao").

    Authoritative source for _classify_roles: doesn't depend on WHEN a
    speaker first talks, unlike the "first 4 non-moderator turns" fallback
    below. Returns an empty set if no "MANAGEMENT:" block is found, so
    callers can fall back to that heuristic.
    """
    m = re.search(r"MANAGEMENT\s*:(.*?)(?:MODERATOR\s*:|$)", transcript_text, re.S | re.I)
    if not m:
        return set()

    roster: set[str] = set()
    for raw_name in _ROSTER_NAME_RE.findall(m.group(1)):
        normalized = " ".join(w.title() for w in raw_name.split())
        if normalized:
            roster.add(normalized)

    return roster


def _classify_roles(
    raw_turns: List[_RawTurn], mgmt_roster: Optional[set[str]] = None
) -> List[_TurnWithRole]:
    """
    Assign ChunkRole to each turn.

    Management speakers come from *mgmt_roster* (see
    _extract_management_roster) -- names parsed from the transcript's own
    participant list. This is authoritative and doesn't depend on when a
    speaker first talks, unlike the old "first 4 non-moderator turns"
    heuristic, which got this wrong in both directions: a management speaker
    who only talks late (e.g. a CFO answering Q&A) was misclassified as
    analyst, while a non-management name occupying an early slot (e.g. a
    cover-letter artifact, or the first analyst) was misclassified as
    management.

    If *mgmt_roster* is empty/not provided (participant list not found or
    not in the expected format), fall back to the "first 4 non-moderator
    turns" heuristic so unusual transcripts still get a best-effort
    classification.
    """
    if mgmt_roster:
        mgmt_speakers: set[str] = set(mgmt_roster)
    else:
        # Fallback: first 4 non-moderator speaker names from the opening
        mgmt_speakers = set()
        non_mod_count = 0
        for speaker, _, _, _ in raw_turns:
            sl = speaker.lower()
            if any(kw in sl for kw in _MODERATOR_KEYWORDS) or sl == "management":
                continue
            non_mod_count += 1
            if non_mod_count <= 4:
                mgmt_speakers.add(speaker)
            else:
                break

    logger.debug("Management speakers: %s", mgmt_speakers)

    result: List[_TurnWithRole] = []
    for speaker, text, cs, ce in raw_turns:
        sl = speaker.lower()
        if any(kw in sl for kw in _MODERATOR_KEYWORDS):
            role = ChunkRole.MODERATOR
        elif sl == "management":
            role = ChunkRole.MANAGEMENT
        elif speaker in mgmt_speakers:
            role = ChunkRole.MANAGEMENT
        else:
            role = ChunkRole.ANALYST

        result.append((speaker, text, cs, ce, role))

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Q&A pairing
# ─────────────────────────────────────────────────────────────────────────────

_ChunkDict = dict  # intermediate representation before Chunk model is built


def _create_qa_pairs(turns: List[_TurnWithRole]) -> List[_ChunkDict]:
    """
    Combine ANALYST turn + immediately following MANAGEMENT turn into one
    Q&A-pair chunk so Stage 2 always sees the question context alongside the
    answer.  This is why the Fineotex GT1 item (value accepted in analyst Q)
    can be extracted correctly.

    Rules:
    - ANALYST turn → find next MANAGEMENT turn (skip MODERATOR turns between)
    - MODERATOR turn with "?" in text → treated as analyst question (written submission)
    - Consecutive MANAGEMENT turns after an answer → absorbed into the same chunk
    - Solo MANAGEMENT turn (not preceded by analyst) → standalone chunk
    - Standalone MODERATOR turns → dropped (administrative text)
    """
    consumed: set[int] = set()
    chunks: List[_ChunkDict] = []

    for i, (speaker, text, cs, ce, role) in enumerate(turns):
        if i in consumed:
            continue

        # Moderator reading a written question from the floor
        is_mod_question = role == ChunkRole.MODERATOR and "?" in text

        if role == ChunkRole.ANALYST or is_mod_question:
            # Scan forward for the management response, skipping any moderators
            j = i + 1
            while j < len(turns) and turns[j][4] == ChunkRole.MODERATOR:
                j += 1

            if j < len(turns) and turns[j][4] == ChunkRole.MANAGEMENT:
                mgmt_speaker, mgmt_text, _, mgmt_ce, _ = turns[j]
                consumed.add(j)

                # Absorb consecutive MANAGEMENT turns (multiple-speaker edge case:
                # MD answers first, then CFO adds to it)
                k = j + 1
                while k < len(turns) and turns[k][4] == ChunkRole.MANAGEMENT:
                    mgmt_text += "\n\n" + turns[k][1]
                    mgmt_ce = turns[k][3]
                    consumed.add(k)
                    k += 1

                chunks.append(
                    {
                        "speaker": mgmt_speaker,
                        "role": ChunkRole.MANAGEMENT,
                        "text": text + "\n\n" + mgmt_text,
                        "char_start": cs,
                        "char_end": mgmt_ce,
                        "is_qa_pair": True,
                    }
                )
            # else: analyst question with no following management turn — skip

        elif role == ChunkRole.MANAGEMENT:
            # Solo management turn (opening monologue or unpaired answer)
            chunks.append(
                {
                    "speaker": speaker,
                    "role": ChunkRole.MANAGEMENT,
                    "text": text,
                    "char_start": cs,
                    "char_end": ce,
                    "is_qa_pair": False,
                }
            )

        # Standalone MODERATOR turns: drop entirely

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Long-turn splitting
# ─────────────────────────────────────────────────────────────────────────────

_MAX_WORDS = 1_500     # chunks above this word count are split
_OVERLAP_CHARS = 200   # overlap carried into the next sub-chunk


def _split_chunk(
    chunk: _ChunkDict,
) -> List[Tuple[_ChunkDict, Optional[int]]]:
    """
    Split a chunk exceeding _MAX_WORDS at paragraph ("\n\n") boundaries with
    a _OVERLAP_CHARS character overlap between adjacent sub-chunks.

    Returns [(chunk_dict, sub_index)] where sub_index is:
      - None  → chunk was not split
      - 0, 1, 2, … → zero-based index of this sub-chunk within the parent
    """
    if len(chunk["text"].split()) <= _MAX_WORDS:
        return [(chunk, None)]

    paras = chunk["text"].split("\n\n")
    sub_texts: List[str] = []
    current: List[str] = []
    current_wc: int = 0

    for para in paras:
        pw = len(para.split())
        if current_wc + pw > _MAX_WORDS and current:
            block = "\n\n".join(current)
            sub_texts.append(block)
            # Overlap: last _OVERLAP_CHARS chars of this block seed the next
            overlap = block[-_OVERLAP_CHARS:] if len(block) > _OVERLAP_CHARS else block
            current = [overlap, para] if overlap.strip() else [para]
            current_wc = len("\n\n".join(current).split())
        else:
            current.append(para)
            current_wc += pw

    if current:
        sub_texts.append("\n\n".join(current))

    if len(sub_texts) <= 1:
        # Splitting produced only one block (edge case) — no split needed
        return [(chunk, None)]

    result: List[Tuple[_ChunkDict, Optional[int]]] = []
    for idx, st in enumerate(sub_texts):
        sub = dict(chunk)   # shallow copy preserves speaker/role/page metadata
        sub["text"] = st
        result.append((sub, idx))

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Page attribution
# ─────────────────────────────────────────────────────────────────────────────


def _build_page_boundaries(
    transcript_pages: Dict[int, str],
) -> Dict[int, Tuple[int, int]]:
    """
    Map each page number to (char_start, char_end) in the concatenated text.

    Assumption: transcript_text ≈ "".join(transcript_pages[i] for i in sorted pages).
    In practice pypdf can produce slightly different output per-page vs whole-doc,
    so page attribution is approximate (±1 page).  This is acceptable — page number
    is metadata, not used for text matching.
    """
    boundaries: Dict[int, Tuple[int, int]] = {}
    offset = 0
    for pn in sorted(transcript_pages.keys()):
        pt = transcript_pages[pn]
        boundaries[pn] = (offset, offset + len(pt))
        offset += len(pt)
    return boundaries


def _char_to_page(
    char_offset: int,
    page_boundaries: Dict[int, Tuple[int, int]],
) -> int:
    """Return the page number that contains *char_offset*."""
    for pn in sorted(page_boundaries.keys()):
        start, end = page_boundaries[pn]
        if start <= char_offset < end:
            return pn
    # Fallback: return last page (handles off-by-one at end of document)
    return max(page_boundaries.keys(), default=1)


# ─────────────────────────────────────────────────────────────────────────────
# Fallback: page-level chunking
# Used when speaker detection finds fewer than 5 turns (degraded mode).
# ─────────────────────────────────────────────────────────────────────────────


def _fallback_page_chunks(transcript_pages: Dict[int, str]) -> List[Chunk]:
    logger.warning(
        "Fewer than 5 speaker turns detected. "
        "Falling back to page-level chunking (degraded mode). "
        "Speaker detection regex may need adjustment for this transcript format."
    )
    chunks: List[Chunk] = []
    offset = 0
    for pn in sorted(transcript_pages.keys()):
        pt = transcript_pages[pn]
        text = pt.strip()
        if text:
            chunks.append(
                Chunk(
                    chunk_id=f"chunk_{pn:03d}",
                    speaker="unknown",
                    role=ChunkRole.MANAGEMENT,
                    page_start=pn,
                    page_end=pn,
                    text=text,
                    char_start=offset,
                    char_end=offset + len(pt),
                    is_qa_pair=False,
                )
            )
        offset += len(pt)
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────


def extract_pages_from_pdf(pdf_path: str) -> Dict[int, str]:
    """
    Extract {page_number: page_text} from a PDF using pypdf.
    Page numbers are 1-indexed.
    Use alongside the full-text extraction in main.py to get both inputs
    needed by segment().
    """
    reader = PdfReader(pdf_path)
    return {
        i + 1: (page.extract_text() or "")
        for i, page in enumerate(reader.pages)
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────


def segment(
    transcript_text: str,
    transcript_pages: Dict[int, str],
) -> List[Chunk]:
    """
    Convert raw transcript text into Q&A-paired Chunk objects.

    Steps:
      1. Detect speaker turns (regex, per-line)
      2. Classify roles (management / analyst / moderator)
      3. Pair analyst questions with management answers
      4. Split long management turns at paragraph boundaries
      5. Assign page numbers from char offsets
      6. Assign sequential chunk IDs (chunk_001, chunk_002a, chunk_002b, …)

    Args:
        transcript_text:  Full concatenated PDF text from pypdf.
        transcript_pages: Dict mapping page_number -> page_text.

    Returns:
        Ordered list of Chunk objects, all with role=MANAGEMENT.
        (Analyst-only turns with no following management response are dropped.)
    """
    if not transcript_text.strip():
        logger.warning("Empty transcript text — returning empty chunk list.")
        return []

    page_boundaries = _build_page_boundaries(transcript_pages)

    # ── Step 1: raw turns ────────────────────────────────────────────────────
    raw_turns = _split_into_turns(transcript_text)
    logger.info("Step 1: %d raw speaker turns detected", len(raw_turns))

    if len(raw_turns) < 5:
        return _fallback_page_chunks(transcript_pages)

    # ── Step 2: roles ────────────────────────────────────────────────────────
    mgmt_roster = _extract_management_roster(transcript_text)
    logger.debug("Management roster from participant list: %s", mgmt_roster)
    turns_with_roles = _classify_roles(raw_turns, mgmt_roster)

    mgmt_count = sum(1 for t in turns_with_roles if t[4] == ChunkRole.MANAGEMENT)
    analyst_count = sum(1 for t in turns_with_roles if t[4] == ChunkRole.ANALYST)
    logger.info(
        "Step 2: %d management turns, %d analyst turns, %d moderator turns",
        mgmt_count,
        analyst_count,
        len(turns_with_roles) - mgmt_count - analyst_count,
    )

    # ── Step 3: Q&A pairing ──────────────────────────────────────────────────
    chunk_dicts = _create_qa_pairs(turns_with_roles)
    qa_pairs = sum(1 for c in chunk_dicts if c["is_qa_pair"])
    logger.info(
        "Step 3: %d chunks (%d Q&A pairs, %d solo management)",
        len(chunk_dicts),
        qa_pairs,
        len(chunk_dicts) - qa_pairs,
    )

    # ── Step 4: long-turn splitting ──────────────────────────────────────────
    flat: List[Tuple[_ChunkDict, Optional[int]]] = []
    for cd in chunk_dicts:
        flat.extend(_split_chunk(cd))

    split_count = sum(1 for _, si in flat if si is not None)
    if split_count:
        logger.info(
            "Step 4: %d sub-chunks created by long-turn splitting",
            split_count,
        )

    # ── Steps 5 + 6: page attribution + chunk ID assignment ─────────────────
    chunks: List[Chunk] = []
    parent_num = 0

    for chunk_dict, sub_idx in flat:
        # parent_num increments at each new parent (sub_idx None or 0)
        if sub_idx is None or sub_idx == 0:
            parent_num += 1

        if sub_idx is None:
            chunk_id = f"chunk_{parent_num:03d}"
        else:
            chunk_id = f"chunk_{parent_num:03d}{chr(ord('a') + sub_idx)}"

        if page_boundaries:
            page_start = _char_to_page(chunk_dict["char_start"], page_boundaries)
            page_end = _char_to_page(
                max(chunk_dict["char_end"] - 1, chunk_dict["char_start"]),
                page_boundaries,
            )
        else:
            page_start = page_end = 1

        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                speaker=chunk_dict["speaker"],
                role=chunk_dict["role"],
                page_start=page_start,
                page_end=page_end,
                text=chunk_dict["text"],
                char_start=chunk_dict["char_start"],
                char_end=chunk_dict["char_end"],
                is_qa_pair=chunk_dict["is_qa_pair"],
            )
        )

    final_qa = sum(1 for c in chunks if c.is_qa_pair)
    logger.info(
        "Stage 0 complete: %d chunks total (%d Q&A pairs, %d solo management)",
        len(chunks),
        final_qa,
        len(chunks) - final_qa,
    )

    return chunks
