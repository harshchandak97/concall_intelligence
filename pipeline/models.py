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


class Chunk(BaseModel):
    chunk_id: str        # e.g. "chunk_001" or "chunk_003b" for split sub-chunks
    speaker: str         # extracted from transcript speaker header
    role: ChunkRole      # management / analyst / moderator
    page_start: int      # first page this chunk appears on
    page_end: int        # last page (may span multiple pages)
    text: str            # full chunk text — Q&A pair or solo management monologue
    char_start: int      # character offset in the full transcript text
    char_end: int        # character offset in the full transcript text
    is_qa_pair: bool     # True = analyst question + management answer combined


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
