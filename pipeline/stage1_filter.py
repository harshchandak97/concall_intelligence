"""
Stage 1 — Candidate Filter

Pure Python, no LLM calls. Discards chunks that cannot possibly contain
qualifying forward-looking guidance. This is a recall gate — it must never
drop a true item. Passing too many chunks is fine; the cost is one extra
Stage 2 LLM call. Dropping a GT item's chunk is an unrecoverable recall loss.

Three-way OR filter — a chunk passes if it satisfies ANY condition:
  Condition 1: contains a digit  (catches numeric guidance: revenue, margins, %)
  Condition 2: worded temporal expression  (catches word-only timeframes)
  Condition 3: commitment verb  (catches binary events: commissioning, launch, etc.)

Stage 0 does not produce standalone moderator chunks (all chunks are
MANAGEMENT-driven), but ChunkRole.MODERATOR is checked as a safety guard
in case that changes.

Public API:
    filter_chunks(chunks: List[Chunk]) -> List[Chunk]
"""

import re
from typing import List

from pipeline.models import Chunk, ChunkRole


# ── Temporal lexicon ─────────────────────────────────────────────────────────
# Worded time expressions that appear in guidance without a numeric year.
# All entries are lowercase; matching is done on chunk.text.lower().

TEMPORAL_LEXICON: list[str] = [
    "first half", "second half",
    "first quarter", "second quarter", "third quarter", "fourth quarter",
    "h1 ", "h2 ",
    "q1 ", "q2 ", "q3 ", "q4 ",
    "this financial year", "this fiscal year", "this fiscal",
    "next financial year", "next fiscal year",
    "next year", "coming year", "current year",
    "by end of", "by the end of",
    "year-end", "year end",
    "coming quarter", "upcoming quarter",
    "going forward",
    "full year", "annual",
    "next quarter", "next few quarters",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]

# ── Commitment verb lexicon ──────────────────────────────────────────────────
# Binary commitment events with no digit and possibly a vague timeframe.

COMMITMENT_VERBS: list[str] = [
    "commission", "commissioned", "commissioning",
    "go live", "goes live", "went live",
    "operationalize", "operationalized", "operational",
    "commence operations", "commencement",
    "breakeven", "break even", "break-even",
    "stabilize", "stabilized",
    "ramp up", "ramping up",
    "complete", "completion", "complete the",
    "launch", "launched", "launching",
]


# ── Filter logic ─────────────────────────────────────────────────────────────

def passes_filter(chunk: Chunk) -> bool:
    """Return True if the chunk should be passed to Stage 2."""
    if chunk.role == ChunkRole.MODERATOR:
        return False

    text_lower = chunk.text.lower()

    has_digit      = bool(re.search(r'\d', chunk.text))
    has_temporal   = any(phrase in text_lower for phrase in TEMPORAL_LEXICON)
    has_commitment = any(verb in text_lower for verb in COMMITMENT_VERBS)

    return has_digit or has_temporal or has_commitment


def filter_chunks(chunks: List[Chunk]) -> List[Chunk]:
    """
    Stage 1 public API.

    Args:
        chunks: List[Chunk] from Stage 0 segment()

    Returns:
        Subset of chunks that pass the candidate filter.
    """
    return [c for c in chunks if passes_filter(c)]
