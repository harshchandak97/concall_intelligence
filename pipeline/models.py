"""
pipeline/models.py — Internal pipeline data models

These are Pydantic models used between pipeline stages.
They are distinct from:
  - schemas.py (LLM output schema / GuidanceItem — unchanged)
  - models.py at root (SQLAlchemy ORM models for PostgreSQL)
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# Stage 0 — Segmenter output
# ─────────────────────────────────────────────────────────────────────────────


class ChunkRole(str, Enum):
    MANAGEMENT = "management"
    ANALYST = "analyst"
    MODERATOR = "moderator"


class ChunkType(str, Enum):
    OPENING_REMARKS = "opening_remarks"
    QA_SESSION      = "qa_session"
    MANAGEMENT_SOLO = "management_solo"


class Turn(BaseModel):
    """A single speaker turn within a chunk."""
    speaker:    str
    role:       ChunkRole
    text:       str
    page_start: int
    page_end:   int
    char_start: int
    char_end:   int


class Chunk(BaseModel):
    chunk_id:        str             # e.g. "chunk_001"
    chunk_type:      ChunkType       # opening_remarks / qa_session / management_solo
    speaker:         str             # management speaker who answered
    analyst_speaker: Optional[str]   # analyst who asked (None for opening/solo chunks)
    role:            ChunkRole       # always MANAGEMENT for Stage 0 output
    page_start:      int
    page_end:        int
    text:            str             # "Role (Speaker): text\n\n..." per turn
    char_start:      int
    char_end:        int
    word_count:      int
    turns:           List[Turn]      # ordered raw turns that make up this chunk


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Per-chunk extractor output
# ─────────────────────────────────────────────────────────────────────────────


class RawGuidanceItem(BaseModel):
    chunk_id: str                        # which chunk this came from
    passage: str                         # verbatim text, self-sufficient
    speaker: str                         # confirmed from chunk metadata
    page_number: int                     # from chunk metadata
    metric_description: str             # free text e.g. "EBITDA margin improvement over FY27"
    guidance_value: Optional[str] = None # "18-20" or "40" or None for binary events
    guidance_unit: Optional[str] = None  # "%" or "crore" or "$ million" or None
    timeline: str                        # raw string e.g. "FY27", "H1 FY27", "next year"
    run_index: int                       # 0 or 1 — which of the two extraction runs produced this


class ChunkExtractionResult(BaseModel):
    chunk_id: str
    items: List[RawGuidanceItem]  # 0 to ~3 items per chunk


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — Metric classifier output
# ─────────────────────────────────────────────────────────────────────────────


class ClassifiedItem(BaseModel):
    # All fields from RawGuidanceItem, plus metric label from controlled vocabulary
    chunk_id: str
    passage: str
    speaker: str
    page_number: int
    metric_description: str
    guidance_value: Optional[str] = None
    guidance_unit: Optional[str] = None
    timeline: str            # still raw at this stage — normalised in Stage 4
    metric: str              # final metric label e.g. "ebitda_margin_pct"
