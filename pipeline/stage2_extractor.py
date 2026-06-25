"""
Stage 2 — Per-Chunk Extractor

For each candidate chunk from Stage 1, call gpt-4o twice (union self-consistency)
and extract 0–N forward-looking guidance items. The LLM's only job here is finding
passages and pulling out values/timelines — metric classification is Stage 3's job.

speaker and page_number are never asked of the LLM — they are attached from the
chunk's Stage 0 metadata after each call.

Public API:
    extract(
        chunks         : List[Chunk],
        openai_client  : OpenAI | None = None,
        prompt_path    : str | Path | None = None,
    ) -> List[RawGuidanceItem]

Union self-consistency: two identical calls per chunk (temperature=0). Any item
that appears in either run survives. Items with >85% passage similarity across runs
are merged, keeping the longer passage. Precision loss from the union is handled
downstream in Stage 4.
"""

import logging
import os
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional

from openai import OpenAI
from pydantic import BaseModel
from tqdm import tqdm

from pipeline.models import Chunk, RawGuidanceItem

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "stage2_extraction_prompt.txt"
_MODEL       = "gpt-4o"
_TEMPERATURE = 0
_UNION_SIMILARITY_THRESHOLD = 0.85


# ── LLM output schema (private) ───────────────────────────────────────────────
# speaker, page_number, chunk_id, run_index are NOT asked of the LLM.
# They are attached from chunk metadata after the call.

class _LLMItem(BaseModel):
    passage:            str
    metric_description: str
    guidance_value:     Optional[str] = None
    guidance_unit:      Optional[str] = None
    timeline:           str


class _LLMResult(BaseModel):
    items: List[_LLMItem]


# ── Core helpers ──────────────────────────────────────────────────────────────

def _chunk_to_transcript(chunk: Chunk) -> str:
    """
    Build a transcript-like text from chunk turns using "Speaker: text" format.

    This is intentionally different from chunk.text (which uses "Role (Speaker): text").
    Using just "Speaker: text" means the LLM's verbatim extraction matches the
    original transcript, so extracted passages can be matched against GT passages
    that were also written from the original transcript.
    """
    return "\n\n".join(f"{t.speaker}: {t.text}" for t in chunk.turns)


def _extract_single(
    chunk:         Chunk,
    run_index:     int,
    client:        OpenAI,
    system_prompt: str,
) -> List[RawGuidanceItem]:
    """One LLM call for one chunk. Returns items with metadata attached."""
    chunk_text = _chunk_to_transcript(chunk)
    try:
        response = client.beta.chat.completions.parse(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": chunk_text},
            ],
            response_format=_LLMResult,
            temperature=_TEMPERATURE,
        )
        llm_result: _LLMResult = response.choices[0].message.parsed
    except Exception as exc:
        log.error("Stage 2 LLM call failed for %s run %d: %s", chunk.chunk_id, run_index, exc)
        return []

    items = []
    for llm_item in llm_result.items:
        items.append(RawGuidanceItem(
            chunk_id=          chunk.chunk_id,
            passage=           llm_item.passage,
            speaker=           chunk.speaker,
            page_number=       chunk.page_start,
            metric_description=llm_item.metric_description,
            guidance_value=    llm_item.guidance_value,
            guidance_unit=     llm_item.guidance_unit,
            timeline=          llm_item.timeline,
            run_index=         run_index,
        ))
    return items


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _union_merge(
    run0:      List[RawGuidanceItem],
    run1:      List[RawGuidanceItem],
    threshold: float = _UNION_SIMILARITY_THRESHOLD,
) -> List[RawGuidanceItem]:
    """
    Union of two extraction runs.
    Items from run1 that are >threshold similar to any run0 item are merged
    (keeping the longer passage). New items from run1 are appended as-is.
    """
    merged = list(run0)

    for item1 in run1:
        best_idx  = -1
        best_sim  = 0.0
        for i, item0 in enumerate(merged):
            sim = _similarity(item1.passage, item0.passage)
            if sim > best_sim:
                best_sim = sim
                best_idx = i

        if best_sim > threshold:
            # Same item found in both runs — keep longer passage
            if len(item1.passage) > len(merged[best_idx].passage):
                merged[best_idx] = item1
        else:
            merged.append(item1)

    return merged


# ── Public API ────────────────────────────────────────────────────────────────

def extract(
    chunks:        List[Chunk],
    openai_client: Optional[OpenAI] = None,
    prompt_path:   Optional[Path]   = None,
) -> List[RawGuidanceItem]:
    """
    Stage 2 public API.

    Args:
        chunks:        Candidate chunks from Stage 1 filter_chunks().
        openai_client: Optional pre-built OpenAI client. If None, one is created
                       from OPENAI_API_KEY environment variable.
        prompt_path:   Path to stage2_extraction_prompt.txt. Defaults to
                       prompts/stage2_extraction_prompt.txt in the project root.

    Returns:
        Flat List[RawGuidanceItem] across all chunks, after union merge.
        metric_description is free text — Stage 3 maps it to controlled vocabulary.
    """
    if openai_client is None:
        from dotenv import load_dotenv
        load_dotenv()
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    resolved_prompt_path = Path(prompt_path) if prompt_path else _PROMPT_PATH
    system_prompt = resolved_prompt_path.read_text()

    all_items: List[RawGuidanceItem] = []

    for chunk in tqdm(chunks, desc="Stage 2 extraction", unit="chunk"):
        run0 = _extract_single(chunk, run_index=0, client=openai_client, system_prompt=system_prompt)
        run1 = _extract_single(chunk, run_index=1, client=openai_client, system_prompt=system_prompt)

        run_delta = len(run0) != len(run1)
        if run_delta:
            log.info(
                "Run delta on %s: run0=%d items, run1=%d items",
                chunk.chunk_id, len(run0), len(run1),
            )

        merged = _union_merge(run0, run1)
        all_items.extend(merged)

    return all_items
