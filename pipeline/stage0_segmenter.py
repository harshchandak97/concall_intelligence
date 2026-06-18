"""
Stage 0 — Deterministic Segmenter (pdfplumber implementation)

Converts a PDF transcript into a list of Chunk objects with speaker metadata.
No LLM involved — pure Python text processing.

Improvements over the pypdf implementation:
  - pdfplumber layout=True preserves paragraph spacing and column order
  - Per-page header/footer stripping (company name, date, page number)
  - Paragraph-boundary speaker detection (no mid-comment false positives)
  - Analyst session grouping: all turns in one analyst's engagement → one QA_SESSION chunk

Pipeline position: Stage 0 of 6 (build first; nothing depends on it yet)

Public API:
    segment(pdf_path, content_start_page=3) -> List[Chunk]
    extract_pages_from_pdf(pdf_path, content_start_page=3) -> Dict[int, str]
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

import pdfplumber

from .models import Chunk, ChunkRole, ChunkType, Turn

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# A. PDF extraction
# ─────────────────────────────────────────────────────────────────────────────

# Type alias: {1-indexed page number: raw page text}
_PageMap = Dict[int, str]


def extract_pages_from_pdf(pdf_path: str, content_start_page: int = 3) -> _PageMap:
    """
    Extract {page_number: raw_text} from a PDF using pdfplumber layout=True.

    Page numbers are positional (1-indexed from the start of the PDF).
    content_start_page is the first page with speaker turns (page 1–2 are
    typically cover letter and participant list).
    """
    result: _PageMap = {}
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            if page_num < content_start_page:
                continue
            result[page_num] = page.extract_text(layout=True) or ""
    return result


def _extract_page2_text(pdf_path: str) -> str:
    """Return raw text of page 2 (participant list page)."""
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) >= 2:
            return pdf.pages[1].extract_text(layout=True) or ""
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# B. Header / footer stripping
# ─────────────────────────────────────────────────────────────────────────────

_MONTHS = (
    "January|February|March|April|May|June|"
    "July|August|September|October|November|December"
)
_DATE_RE        = re.compile(rf"^({_MONTHS})\s+\d{{1,2}},?\s+\d{{4}}$", re.I)
_COMPANY_RE     = re.compile(r"^.+\b(Limited|Ltd\.?|Inc\.?|Corp\.?|Pvt\.?)$", re.I)
_PAGE_NUMBER_RE = re.compile(r"^Page\s+\d+\s+of\s+\d+$", re.I)
_PAGE_PIPE_RE   = re.compile(r"^\d+\s*\|$|^\|\s*\d+$")  # "2 |" or "| 2"


def _is_header_footer_line(s: str) -> bool:
    return bool(_DATE_RE.match(s) or _COMPANY_RE.match(s) or _PAGE_NUMBER_RE.match(s))


def _strip_header_footer(page_text: str) -> str:
    """
    Remove company name, date, and page number lines that appear at the top
    and bottom of each page. Scans inward from each edge — stops the moment
    real content is reached so mid-page lines are never touched.
    """
    lines = page_text.split("\n")

    # Top: skip blanks, remove header lines, stop at first real content
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if _is_header_footer_line(s):
            lines[i] = ""
        else:
            break

    # Bottom: skip blanks, remove footer lines, stop at first real content
    checked_last = False
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].strip()
        if not s:
            continue
        if not checked_last:
            checked_last = True
            if _PAGE_PIPE_RE.match(s) or _is_header_footer_line(s):
                lines[i] = ""
            else:
                break
        elif _is_header_footer_line(s):
            lines[i] = ""
        else:
            break

    # Strip leading/trailing blank lines left by layout=True whitespace
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# C. Participant list extraction (page 2)
# ─────────────────────────────────────────────────────────────────────────────

# Matches: honorific + name (ALL-CAPS or Title Case) + separator (dash or colon)
# Handles both:
#   MS. AARTI JHUNJHUNWALA – EXECUTIVE DIRECTOR  (Fineotex — ALL-CAPS, dash)
#   Mr. Amit Syngle : MD & CEO                   (Asian Paints — Title Case, colon)
_MGMT_NAME_RE = re.compile(
    r"(?:MR|MS|MRS|DR)\.\s+([A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){0,2})\s*[–\-:]",
    re.IGNORECASE,
)


def _extract_names_from_block(page2_text: str, block_label: str) -> set[str]:
    """Extract honorific-prefixed names from a named block (MANAGEMENT, MODERATOR, etc.)."""
    m = re.search(
        rf"^[ \t]*{re.escape(block_label)}\s*:(.*?)(?=^[ \t]*(?:MANAGEMENT|MODERATOR|ANALYST|PARTICIPANTS?|SPEAKERS?)\s*:|\Z)",
        page2_text,
        re.S | re.I | re.MULTILINE,
    )
    if not m:
        return set()
    names: set[str] = set()
    for raw in _MGMT_NAME_RE.findall(m.group(1)):
        name = " ".join(raw.split()).title()
        if name:
            names.add(name)
    return names


def _extract_management_names(page2_text: str) -> set[str]:
    for label in ("MANAGEMENT", "PARTICIPANTS", "PARTICIPANT", "SPEAKERS", "SPEAKER"):
        names = _extract_names_from_block(page2_text, label)
        if names:
            return names
    logger.warning(
        "No management block found on page 2 — all non-moderator speakers "
        "will be labelled analyst"
    )
    return set()


def _extract_moderator_names(page2_text: str) -> set[str]:
    """Named moderators listed under MODERATOR: on page 2 (sell-side host)."""
    return _extract_names_from_block(page2_text, "MODERATOR")


# ─────────────────────────────────────────────────────────────────────────────
# D. Speaker detection utilities
# ─────────────────────────────────────────────────────────────────────────────

# Paragraph-boundary speaker pattern:
#   ^\s*                  — optional indent (0-space Asian Paints, 10-space Fineotex)
#   (?:[A-Z]\.\s+){0,2}  — optional leading initials: "J. " or "R.J. "
#   [A-Z][a-z]+           — first proper word: Title Case (rejects ALL-CAPS, rejects "Q")
#   (...){0,3}            — up to 3 more words
#   \s*:                  — colon, optional space before
_PARA_SPEAKER_RE = re.compile(
    r"^\s*((?:[A-Z]\.\s+){0,2}[A-Z][a-z]+(?:\s+[A-Z][a-z.]*){0,3})\s*:"
)

_SPEAKER_BLOCKLIST = {
    "Note", "Disclaimer", "Background", "Summary", "Conclusion",
    "Important", "Update", "Result", "Overview", "Outlook",
    "Please", "Date", "Venue", "Time", "Subject", "Dear",
    "Thanks", "Regards", "Encl", "Sir", "Madam", "Yours",
}

_MOD_RE = re.compile(r"^(moderator|operator)$", re.I)


def _is_valid_speaker(name: str) -> bool:
    words = name.split()
    if len(words) == 1 and words[0] in _SPEAKER_BLOCKLIST:
        return False
    return True


def _in_roster(name: str, roster: set[str]) -> bool:
    """
    Exact match OR single-word last-name fallback (min 4 chars).

    Multi-word names require exact match to prevent false positives
    (e.g. "Chirag Jain" must not match "Yashpal Jain").
    Single-word names (e.g. "Jeyamurugan") are looked up by last name.
    """
    if name in roster:
        return True
    words = name.split()
    if len(words) == 1 and len(words[0]) >= 4:
        last = words[0].lower()
        return any(m.split()[-1].lower() == last for m in roster)
    return False


def _is_management_speaker(speaker: str, mgmt_names: set[str]) -> bool:
    return _in_roster(speaker, mgmt_names)


def _is_moderator_speaker(speaker: str, moderator_names: set[str]) -> bool:
    """Generic Moderator/Operator keyword OR exact match in named moderator roster."""
    if _MOD_RE.match(speaker.strip()):
        return True
    return speaker in moderator_names  # exact match only — no last-name fallback


# ─────────────────────────────────────────────────────────────────────────────
# E. Speaker name detection from full text
# ─────────────────────────────────────────────────────────────────────────────


def _detect_speaker_names(full_text: str) -> Counter:
    """
    Scan each paragraph's first non-blank line for a speaker-header pattern.
    Returns Counter of {name: occurrence_count}.
    """
    paragraphs = re.split(r"(?:\n[ \t]*){2,}", full_text)
    detected: Counter = Counter()
    for para in paragraphs:
        non_blank = [l for l in para.split("\n") if l.strip()]
        if not non_blank:
            continue
        m = _PARA_SPEAKER_RE.match(non_blank[0])
        if m:
            name = m.group(1).strip()
            if _is_valid_speaker(name):
                detected[name] += 1
    return detected


# ─────────────────────────────────────────────────────────────────────────────
# F. Turn extraction with character offsets
# ─────────────────────────────────────────────────────────────────────────────


def _build_page_boundaries(
    clean_pages: _PageMap, content_start_page: int
) -> Dict[int, Tuple[int, int]]:
    """
    Map each page number to (char_start, char_end) in the concatenated full_text.
    full_text = "\n".join(clean_pages[pn] for pn in sorted(clean_pages))
    so each page separator adds 1 char.
    """
    boundaries: Dict[int, Tuple[int, int]] = {}
    offset = 0
    for pn in sorted(clean_pages.keys()):
        page_text = clean_pages[pn]
        boundaries[pn] = (offset, offset + len(page_text))
        offset += len(page_text) + 1  # +1 for the "\n" join separator
    return boundaries


def _char_to_page(
    char_offset: int, page_boundaries: Dict[int, Tuple[int, int]]
) -> int:
    for pn in sorted(page_boundaries.keys()):
        start, end = page_boundaries[pn]
        if start <= char_offset < end:
            return pn
    return max(page_boundaries.keys(), default=1)


def _normalize_comment(raw_text: str) -> str:
    """Collapse layout whitespace: remove newlines, deduplicate spaces."""
    text = raw_text.replace("\n", " ")
    return re.sub(r" {2,}", " ", text).strip()


def _extract_turns_with_offsets(
    full_text: str,
    split_re: re.Pattern,
    mgmt_names: set[str],
    moderator_names: set[str],
    page_boundaries: Dict[int, Tuple[int, int]],
) -> List[dict]:
    """
    Use finditer on split_re to recover character positions for every turn.
    Returns list of {speaker, role, text, char_start, char_end, page_start, page_end}.
    """
    matches = list(split_re.finditer(full_text))
    result = []
    for idx, m in enumerate(matches):
        speaker = m.group(1).strip()
        text_start = m.end()
        text_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        normalized = _normalize_comment(full_text[text_start:text_end])
        if not normalized:
            continue

        char_start = m.start()
        char_end = text_end

        if _is_moderator_speaker(speaker, moderator_names):
            role = "moderator"
        elif _is_management_speaker(speaker, mgmt_names):
            role = "management"
        else:
            role = "analyst"

        result.append({
            "speaker":    speaker,
            "role":       role,
            "text":       normalized,
            "char_start": char_start,
            "char_end":   char_end,
            "page_start": _char_to_page(char_start, page_boundaries),
            "page_end":   _char_to_page(max(char_end - 1, char_start), page_boundaries),
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# G. Session grouping → Chunk objects
# ─────────────────────────────────────────────────────────────────────────────

_OPENING_WORD_LIMIT = 600


def _format_chunk_text(session_turns: List[dict]) -> str:
    parts = [
        f"{t['role'].title()} ({t['speaker']}): {t['text']}"
        for t in session_turns
    ]
    return "\n\n".join(parts)


def _make_turn_obj(t: dict) -> Turn:
    return Turn(
        speaker=t["speaker"],
        role=ChunkRole(t["role"]),
        text=t["text"],
        page_start=t["page_start"],
        page_end=t["page_end"],
        char_start=t["char_start"],
        char_end=t["char_end"],
    )


def _make_chunk_obj(
    chunk_id: str,
    chunk_type: ChunkType,
    session_turns: List[dict],
    analyst_speaker: Optional[str] = None,
) -> Chunk:
    mgmt_speaker = next(
        (t["speaker"] for t in session_turns if t["role"] == "management"),
        session_turns[0]["speaker"],
    )
    text = _format_chunk_text(session_turns)
    return Chunk(
        chunk_id=chunk_id,
        chunk_type=chunk_type,
        speaker=mgmt_speaker,
        analyst_speaker=analyst_speaker,
        role=ChunkRole.MANAGEMENT,
        page_start=session_turns[0]["page_start"],
        page_end=session_turns[-1]["page_end"],
        char_start=session_turns[0]["char_start"],
        char_end=session_turns[-1]["char_end"],
        word_count=len(text.split()),
        text=text,
        turns=[_make_turn_obj(t) for t in session_turns],
    )


def _split_turn_by_paragraphs(turn_dict: dict, word_limit: int) -> List[dict]:
    """Split a single turn's text at paragraph boundaries if it exceeds word_limit."""
    paras = [p.strip() for p in turn_dict["text"].split("\n\n") if p.strip()]
    groups: List[str] = []
    current: List[str] = []
    current_words = 0
    for para in paras:
        pw = len(para.split())
        if current_words + pw > word_limit and current:
            groups.append("\n\n".join(current))
            current, current_words = [], 0
        current.append(para)
        current_words += pw
    if current:
        groups.append("\n\n".join(current))
    if len(groups) <= 1:
        return [turn_dict]
    return [{**turn_dict, "text": g} for g in groups]


def _group_into_chunks(raw_turns: List[dict]) -> List[Chunk]:
    """
    Convert the flat turn sequence into Chunk objects:
      - OPENING_REMARKS: management turns before the first analyst, split at 600 words
      - QA_SESSION: all turns in one analyst's engagement (questions, follow-ups, answers)
      - MANAGEMENT_SOLO: solo management turn not preceded by an analyst

    Moderator turns between sessions are buffered and prepended to the next session.
    Trailing moderator turns at end of opening are seeded into the first QA session.
    """
    chunks: List[Chunk] = []
    chunk_seq = 0

    first_analyst = next(
        (i for i, t in enumerate(raw_turns) if t["role"] == "analyst"),
        len(raw_turns),
    )

    # ── Opening remarks ───────────────────────────────────────────────────────
    opening_pool: List[dict] = []
    mod_buffer: List[dict] = []

    for t in raw_turns[:first_analyst]:
        if t["role"] == "management":
            opening_pool.extend(mod_buffer)
            mod_buffer = []
            opening_pool.extend(_split_turn_by_paragraphs(t, _OPENING_WORD_LIMIT))
        else:
            mod_buffer.append(t)

    # Trailing moderator turns after last management opening turn → prepend to first QA
    pending_mod = mod_buffer

    current_group: List[dict] = []
    current_words = 0
    for sub in opening_pool:
        sw = len(sub["text"].split())
        if current_words + sw > _OPENING_WORD_LIMIT and current_group:
            chunk_seq += 1
            chunks.append(
                _make_chunk_obj(f"chunk_{chunk_seq:03d}", ChunkType.OPENING_REMARKS, current_group)
            )
            current_group, current_words = [], 0
        current_group.append(sub)
        current_words += sw
    if current_group:
        chunk_seq += 1
        chunks.append(
            _make_chunk_obj(f"chunk_{chunk_seq:03d}", ChunkType.OPENING_REMARKS, current_group)
        )

    # ── Q&A sessions and management solo turns ────────────────────────────────
    i = first_analyst
    n = len(raw_turns)

    while i < n:
        t = raw_turns[i]

        if t["role"] == "analyst":
            analyst_name = t["speaker"]
            session = pending_mod + [t]
            pending_mod = []
            i += 1

            local_mod: List[dict] = []

            while i < n:
                curr = raw_turns[i]
                if curr["role"] == "moderator":
                    local_mod.append(curr)
                    i += 1
                elif curr["role"] == "analyst" and curr["speaker"] != analyst_name:
                    # Different analyst — flush local_mod to pending for next session
                    pending_mod = local_mod
                    local_mod = []
                    break
                else:
                    # Management or same analyst continuing — absorb local_mod into session
                    session.extend(local_mod)
                    local_mod = []
                    session.append(curr)
                    i += 1

            # End of transcript: flush remaining local_mod into this session
            session.extend(local_mod)

            chunk_seq += 1
            chunks.append(
                _make_chunk_obj(
                    f"chunk_{chunk_seq:03d}",
                    ChunkType.QA_SESSION,
                    session,
                    analyst_name,
                )
            )

        elif t["role"] == "moderator":
            pending_mod.append(t)
            i += 1

        elif t["role"] == "management":
            session = pending_mod + [t]
            pending_mod = []
            chunk_seq += 1
            chunks.append(
                _make_chunk_obj(f"chunk_{chunk_seq:03d}", ChunkType.MANAGEMENT_SOLO, session)
            )
            i += 1

    # Trailing moderator closing remarks — append to last chunk
    if pending_mod and chunks:
        last = chunks[-1]
        extra = "\n\n" + "\n\n".join(
            f"{t['role'].title()} ({t['speaker']}): {t['text']}" for t in pending_mod
        )
        last.text += extra
        last.word_count = len(last.text.split())
        last.turns.extend(_make_turn_obj(t) for t in pending_mod)
        last.page_end = pending_mod[-1]["page_end"]
        last.char_end = pending_mod[-1]["char_end"]

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def segment(pdf_path: str, content_start_page: int = 3) -> List[Chunk]:
    """
    Convert a PDF transcript into an ordered list of Chunk objects.

    Steps:
      1. Extract page 2 text — parse management and moderator names
      2. Extract content pages with pdfplumber layout=True
      3. Strip header/footer from each page
      4. Concatenate cleaned pages into full_text
      5. Detect speaker names from paragraph boundaries
      6. Build split regex and extract turns with char offsets
      7. Group turns into OPENING_REMARKS / QA_SESSION / MANAGEMENT_SOLO chunks

    Args:
        pdf_path:           Path to the PDF file.
        content_start_page: First page with speaker turns (default 3; pages 1–2 are
                            cover letter and participant list in standard Indian concalls).

    Returns:
        Ordered list of Chunk objects, all with role=MANAGEMENT.
    """
    # ── Step 1: participant list ──────────────────────────────────────────────
    page2_text = _extract_page2_text(pdf_path)
    mgmt_names = _extract_management_names(page2_text)
    moderator_names = _extract_moderator_names(page2_text)
    logger.info(
        "Page 2 roster: %d management, %d named moderators",
        len(mgmt_names),
        len(moderator_names),
    )
    logger.debug("Management names: %s", mgmt_names)

    # ── Steps 2 + 3: extract and clean content pages ──────────────────────────
    raw_pages = extract_pages_from_pdf(pdf_path, content_start_page)
    clean_pages: _PageMap = {pn: _strip_header_footer(text) for pn, text in raw_pages.items()}
    logger.info("Content pages: %d (starting at page %d)", len(clean_pages), content_start_page)

    # ── Step 4: concatenate ───────────────────────────────────────────────────
    full_text = "\n".join(clean_pages[pn] for pn in sorted(clean_pages.keys()))
    logger.info("Full text: %d chars, %d words", len(full_text), len(full_text.split()))

    if not full_text.strip():
        logger.warning("Empty transcript text — returning empty chunk list.")
        return []

    # ── Step 5: detect speaker names ─────────────────────────────────────────
    detected = _detect_speaker_names(full_text)
    exclude: set[str] = set()  # extend if a false positive needs manual exclusion
    speaker_names = [name for name in detected if name not in exclude]
    logger.info("Detected %d unique speaker names", len(speaker_names))

    if not speaker_names:
        logger.warning(
            "No speaker names detected — falling back to full-page chunks (degraded mode)."
        )
        return _fallback_page_chunks(clean_pages)

    # ── Step 6: extract turns with offsets ───────────────────────────────────
    # Longest names first to avoid partial matches (e.g. "Aarti" before "Aarti Jhunjhunwala")
    name_alts = "|".join(
        re.escape(n) for n in sorted(speaker_names, key=len, reverse=True)
    )
    split_re = re.compile(rf"^\s*({name_alts})\s*:", re.MULTILINE)

    page_boundaries = _build_page_boundaries(clean_pages, content_start_page)
    raw_turns = _extract_turns_with_offsets(
        full_text, split_re, mgmt_names, moderator_names, page_boundaries
    )
    logger.info("Raw turns: %d", len(raw_turns))

    if len(raw_turns) < 5:
        logger.warning(
            "Fewer than 5 turns detected — falling back to page-level chunks (degraded mode)."
        )
        return _fallback_page_chunks(clean_pages)

    role_counts = Counter(t["role"] for t in raw_turns)
    logger.info(
        "Roles: %d management, %d analyst, %d moderator",
        role_counts["management"],
        role_counts["analyst"],
        role_counts["moderator"],
    )

    # ── Step 7: session grouping ──────────────────────────────────────────────
    chunks = _group_into_chunks(raw_turns)

    type_counts = Counter(c.chunk_type.value for c in chunks)
    logger.info(
        "Stage 0 complete: %d chunks (%s)",
        len(chunks),
        ", ".join(f"{v} {k}" for k, v in type_counts.most_common()),
    )
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Fallback: page-level chunking (degraded mode)
# ─────────────────────────────────────────────────────────────────────────────


def _fallback_page_chunks(clean_pages: _PageMap) -> List[Chunk]:
    chunks: List[Chunk] = []
    offset = 0
    for pn in sorted(clean_pages.keys()):
        text = clean_pages[pn].strip()
        if not text:
            offset += len(clean_pages[pn]) + 1
            continue
        turn = {
            "speaker":    "unknown",
            "role":       "management",
            "text":       text,
            "char_start": offset,
            "char_end":   offset + len(clean_pages[pn]),
            "page_start": pn,
            "page_end":   pn,
        }
        chunks.append(
            _make_chunk_obj(f"chunk_{pn:03d}", ChunkType.MANAGEMENT_SOLO, [turn])
        )
        offset += len(clean_pages[pn]) + 1
    return chunks
