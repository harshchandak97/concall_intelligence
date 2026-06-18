"""
Stage 4 — Deterministic Validation + Deduplication

Pure Python, no LLM calls. Applies quality filters to List[ClassifiedItem]
from Stage 3 and produces the final List[GuidanceItem] ready for PostgreSQL.

Rules applied in order:
  Rule 1 — Null value rejection (except commissioning_event)
  Rule 2 — Guidance value format + cleaning
  Rule 3 — Past timeline rejection (based on call_date)
  Rule 4 — Passage verbatim check (warning only, never rejects)
  Rule 5 — Deduplication (exact then fuzzy)

Also computes:
  normalize_timeline  — raw string → canonical "FY27" / "H1 FY27" / "Q2 FY27"
  compute_credibility_scorable — metric label → bool, code lookup only

Public API:
    validate(
        items         : List[ClassifiedItem],
        call_date     : date,
        transcript_text: str = "",
    ) -> tuple[List[GuidanceItem], List[dict]]

    Returns (valid_items, rejection_log).
    rejection_log entries: {chunk_id, rule, reason, item_summary}

Indian fiscal year: April 1 – March 31.
    May 2026 call → current FY = FY27 (April 2026 – March 2027), Q1 FY27.
"""

import logging
import re
from datetime import date
from difflib import SequenceMatcher
from typing import List, Optional

from pipeline.models import ClassifiedItem
from schemas import GuidanceItem

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Credibility scorable lookup
# ─────────────────────────────────────────────────────────────────────────────

_CREDIBILITY_SCORABLE_METRICS: frozenset[str] = frozenset({
    "revenue_absolute",
    "revenue_growth_pct",
    "ebitda_margin_pct",
    "pat_absolute",
    "pat_growth_pct",
    "pbt_margin_pct",
    "eps_absolute",
})


def compute_credibility_scorable(metric: str) -> bool:
    if metric.startswith("other_"):
        return False
    return metric in _CREDIBILITY_SCORABLE_METRICS


# ─────────────────────────────────────────────────────────────────────────────
# Fiscal calendar helpers
# ─────────────────────────────────────────────────────────────────────────────

def _current_fy(d: date) -> int:
    """2-digit FY. May 2026 → 27. Jan 2027 → 27. Apr 2027 → 28."""
    return (d.year % 100) + 1 if d.month >= 4 else d.year % 100


def _current_quarter(d: date) -> int:
    m = d.month
    if m in (4, 5, 6):   return 1
    if m in (7, 8, 9):   return 2
    if m in (10, 11, 12): return 3
    return 4


def _quarter_start(d: date) -> date:
    m = d.month
    y = d.year
    if m in (4, 5, 6):   return date(y, 4, 1)
    if m in (7, 8, 9):   return date(y, 7, 1)
    if m in (10, 11, 12): return date(y, 10, 1)
    return date(y, 1, 1)


def _timeline_end_date(normalized: str) -> Optional[date]:
    """
    End date of a normalized timeline string, for past-timeline comparison.
    "FY27"    → 2027-03-31
    "H1 FY27" → 2026-09-30  (Apr–Sep of the FY-start year 2026)
    "H2 FY27" → 2027-03-31  (Oct 2026 – Mar 2027)
    "Q1 FY27" → 2026-06-30
    "Q2 FY27" → 2026-09-30
    "Q3 FY27" → 2026-12-31
    "Q4 FY27" → 2027-03-31
    """
    m = re.fullmatch(r'FY(\d{2})', normalized)
    if m:
        year = 2000 + int(m.group(1))
        return date(year, 3, 31)

    m = re.fullmatch(r'H([12]) FY(\d{2})', normalized)
    if m:
        h, fy2 = int(m.group(1)), int(m.group(2))
        fy_start = 2000 + fy2 - 1   # FY27 starts in 2026
        if h == 1:
            return date(fy_start, 9, 30)   # Apr–Sep of fy_start
        else:
            return date(fy_start + 1, 3, 31)  # Oct fy_start – Mar fy_start+1

    m = re.fullmatch(r'Q([1-4]) FY(\d{2})', normalized)
    if m:
        q, fy2 = int(m.group(1)), int(m.group(2))
        fy_start = 2000 + fy2 - 1
        ends = {1: date(fy_start, 6, 30),
                2: date(fy_start, 9, 30),
                3: date(fy_start, 12, 31),
                4: date(fy_start + 1, 3, 31)}
        return ends[q]

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Timeline normalization
# ─────────────────────────────────────────────────────────────────────────────

_WORD_TO_Q = {
    "first":  1, "1st": 1,
    "second": 2, "2nd": 2,
    "third":  3, "3rd": 3,
    "fourth": 4, "4th": 4,
}

_APPROX_RE = re.compile(
    r'\b(approximately|around|about|circa|nearly|roughly)\s*', re.I
)


def _extract_fy2(text: str, call_date: date) -> Optional[int]:
    """
    Extract 2-digit FY from text. Returns None if cannot determine.
    Handles: FY27, FY2027, FY 27, 2026-27, 2026-2027, relative phrases.
    """
    sl = text.lower()

    # "FY27" / "FY 27" / "FY2027"
    m = re.search(r'\bfy\s*(\d{2,4})\b', sl)
    if m:
        return int(m.group(1)) % 100

    # "2026-27" / "2026-2027" / "2026/27"
    m = re.search(r'\b20(\d{2})[/\-](\d{2,4})\b', text)
    if m:
        return int(m.group(2)) % 100

    # bare 4-digit calendar year ending: "2027" → FY27
    m = re.search(r'\b(20\d{2})\b', text)
    if m:
        return int(m.group(1)) % 100

    cfy = _current_fy(call_date)

    # Relative: this/current fiscal year
    if re.search(
        r'\b(this|current)\s+(financial|fiscal)\s+year\b|'
        r'\bthis\s+fiscal\b|'
        r'\bby\s+(the\s+)?end\s+of\s+(this|the)\s+(financial|fiscal)\s+year\b|'
        r'\bend\s+of\s+this\s+(financial|fiscal)\s+year\b',
        sl,
    ):
        return cfy

    # Relative: next fiscal year / next year / coming year
    if re.search(
        r'\bnext\s+(financial|fiscal)\s+year\b|'
        r'\bnext\s+year\b|\bcoming\s+year\b',
        sl,
    ):
        return cfy + 1

    return None


def _extract_period(text: str) -> tuple[str, Optional[int]]:
    """
    Returns ('q', 1-4) | ('h', 1-2) | ('fy', None).
    Inspect period indicators before explicit year numbers to avoid
    "Q2 2027" having year matched as Q instead of period.
    """
    sl = text.lower()

    # Quarter: "Q2", "second quarter"
    m = re.search(r'\bq([1-4])\b', sl)
    if m:
        return 'q', int(m.group(1))

    m = re.search(
        r'\b(first|1st|second|2nd|third|3rd|fourth|4th)\s+quarter\b', sl
    )
    if m:
        word = m.group(1).lower().rstrip('stndrh')  # strip ordinal suffix
        # map ordinal word → number
        for k, v in _WORD_TO_Q.items():
            if sl[m.start():m.start() + len(k)] == k:
                return 'q', v
        # fallback word map
        wmap = {"first": 1, "second": 2, "third": 3, "fourth": 4}
        base = m.group(1).lower()
        if base in wmap:
            return 'q', wmap[base]

    # Half: "H1", "H1FY27" (no space), "first half", "H2", "second half"
    if re.search(r'\bh1(?:\b|fy)|\bfirst\s+half\b', sl):
        return 'h', 1
    if re.search(r'\bh2(?:\b|fy)|\bsecond\s+half\b', sl):
        return 'h', 2

    return 'fy', None


def normalize_timeline(raw: str, call_date: date) -> str:
    """
    Map raw LLM timeline string to canonical form.

    Canonical forms: "FY27" | "H1 FY27" | "H2 FY27" | "Q1 FY27" … "Q4 FY27"
    FY year is always 2-digit: FY27, FY28.

    Relative expressions resolved using call_date (Indian fiscal April–March).
    If normalization fails, returns raw string unchanged and logs a warning.
    """
    s = raw.strip()
    if not s:
        return s

    sl = s.lower()
    cfy = _current_fy(call_date)
    cq  = _current_quarter(call_date)

    # ── Relative quarter expressions (no year needed) ─────────────────────
    if re.search(r'\bnext\s+quarter\b|\bcoming\s+quarter\b|\bupcoming\s+quarter\b', sl):
        nq = (cq % 4) + 1
        nfy = cfy if nq > cq else cfy + 1
        return f"Q{nq} FY{nfy:02d}"

    if re.search(r'\b(this|current)\s+quarter\b', sl):
        return f"Q{cq} FY{cfy:02d}"

    # ── Extract FY year and period type ───────────────────────────────────
    fy2 = _extract_fy2(s, call_date)
    period_type, period_num = _extract_period(s)

    if fy2 is not None:
        fy_label = f"FY{fy2:02d}"
        if period_type == 'q' and period_num:
            return f"Q{period_num} {fy_label}"
        if period_type == 'h' and period_num:
            return f"H{period_num} {fy_label}"
        return fy_label

    # ── Period type only (no explicit year) — default to current FY ───────
    if period_type == 'q' and period_num:
        # If mentioned quarter < current quarter, it likely refers to next FY
        fy = cfy if period_num >= cq else cfy + 1
        return f"Q{period_num} FY{fy:02d}"

    if period_type == 'h' and period_num:
        # H1 = Q1+Q2, H2 = Q3+Q4 of the FY
        # If the half has already started and is past → next FY
        h_last_q = period_num * 2        # H1→Q2, H2→Q4
        fy = cfy if h_last_q >= cq else cfy + 1
        return f"H{period_num} FY{fy:02d}"

    # ── Unrecognized ──────────────────────────────────────────────────────
    log.warning("timeline_not_normalized: %r", raw)
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Rule 2 — value cleaning
# ─────────────────────────────────────────────────────────────────────────────

_VALUE_PATTERN = re.compile(r'^\d+(\.\d+)?(-\d+(\.\d+)?)?$')
_APPROX_STRIP  = re.compile(r'^[~<>≈≤≥]+\s*|^(approximately|around|about|circa|nearly|roughly)\s+', re.I)


def _clean_value(raw_value: str) -> Optional[str]:
    """
    Try to clean approximation markers from a guidance value string.
    Returns cleaned string if it matches VALUE_PATTERN, else None.
    """
    v = raw_value.strip()
    # Already valid
    if _VALUE_PATTERN.match(v):
        return v
    # Strip approximation prefix
    v2 = _APPROX_STRIP.sub('', v).strip()
    # Replace " to " range separator
    v2 = re.sub(r'\s+to\s+', '-', v2, flags=re.I)
    # Strip % suffix (should be in guidance_unit)
    v2 = v2.rstrip('%').strip()
    if _VALUE_PATTERN.match(v2):
        return v2
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Rule 5 — deduplication helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_value_for_dedup(v: Optional[str]) -> Optional[str]:
    """Normalise value for dedup key: round to 1 decimal, sort range ends."""
    if v is None:
        return None
    try:
        parts = [round(float(p), 1) for p in v.split('-')]
        return '-'.join(str(p) for p in sorted(parts))
    except ValueError:
        return v.strip().lower()


def _passage_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ─────────────────────────────────────────────────────────────────────────────
# Rejection log helpers
# ─────────────────────────────────────────────────────────────────────────────

def _item_summary(item: ClassifiedItem) -> str:
    return (
        f"{item.metric} | {item.guidance_value} {item.guidance_unit or ''} | "
        f"{item.timeline} | p{item.page_number}"
    )


def _reject(log_list: list, item: ClassifiedItem, rule: str, reason: str) -> None:
    entry = {
        "chunk_id":     item.chunk_id,
        "rule":         rule,
        "reason":       reason,
        "item_summary": _item_summary(item),
    }
    log_list.append(entry)
    log.debug("REJECT [%s/%s]: %s", rule, reason, _item_summary(item))


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def validate(
    items: List[ClassifiedItem],
    call_date: date,
    transcript_text: str = "",
) -> tuple[List[GuidanceItem], List[dict]]:
    """
    Apply all validation rules to a list of ClassifiedItems.

    Args:
        items:           Output from Stage 3 metric classifier.
        call_date:       Date of the earnings call (used for timeline resolution
                         and past-timeline rejection).
        transcript_text: Full concatenated transcript text (used for Rule 4 verbatim
                         check). Pass empty string to skip Rule 4.

    Returns:
        (valid_items, rejection_log)
        valid_items:    List[GuidanceItem] ready for PostgreSQL insertion.
        rejection_log:  List of dicts describing each rejected item and why.
    """
    rejection_log: list[dict] = []
    surviving: list[ClassifiedItem] = []

    transcript_norm = re.sub(r'\s+', ' ', transcript_text.strip())

    for item in items:
        # ── Rule 1: null value (non-commissioning) ────────────────────────
        if item.metric != "commissioning_event" and item.guidance_value is None:
            _reject(rejection_log, item, "rule1", "null_value_non_binary_metric")
            continue

        # ── Rule 2: guidance value format ─────────────────────────────────
        cleaned_value = item.guidance_value
        if item.guidance_value is not None:
            cleaned = _clean_value(item.guidance_value)
            if cleaned is None:
                _reject(rejection_log, item, "rule2", "malformed_guidance_value")
                continue
            cleaned_value = cleaned

        # ── commissioning_event: force null value (spec edge case) ────────
        if item.metric == "commissioning_event":
            cleaned_value = None

        # ── Rule 3: past timeline ─────────────────────────────────────────
        norm_timeline = normalize_timeline(item.timeline, call_date)
        end_date = _timeline_end_date(norm_timeline)
        if end_date is not None and end_date < _quarter_start(call_date):
            _reject(
                rejection_log, item, "rule3",
                f"past_timeline: {norm_timeline!r} ended {end_date} "
                f"before call quarter start {_quarter_start(call_date)}",
            )
            continue

        # ── Rule 4: passage verbatim check (warning only) ─────────────────
        if transcript_norm:
            passage_norm = re.sub(r'\s+', ' ', item.passage.strip())
            if passage_norm not in transcript_norm:
                log.warning(
                    "passage_not_found_verbatim [%s]: %r…",
                    item.chunk_id, item.passage[:80],
                )

        # ── All rules passed — mutate item with cleaned values ────────────
        surviving.append(
            ClassifiedItem(
                chunk_id=item.chunk_id,
                passage=item.passage,
                speaker=item.speaker,
                page_number=item.page_number,
                metric_description=item.metric_description,
                guidance_value=cleaned_value,
                guidance_unit=item.guidance_unit,
                timeline=norm_timeline,
                metric=item.metric,
            )
        )

    # ── Rule 5: deduplication ─────────────────────────────────────────────
    deduped = _deduplicate(surviving, rejection_log)

    # ── Build final GuidanceItem list ─────────────────────────────────────
    valid_items = [
        GuidanceItem(
            passage=c.passage,
            speaker=c.speaker,
            page_number=c.page_number,
            metric=c.metric,
            guidance_value=c.guidance_value,
            guidance_unit=c.guidance_unit,
            timeline=c.timeline,
            credibility_scorable=compute_credibility_scorable(c.metric),
        )
        for c in deduped
    ]

    return valid_items, rejection_log


def _deduplicate(
    items: List[ClassifiedItem],
    rejection_log: list[dict],
) -> List[ClassifiedItem]:
    """
    Rule 5 — two-pass deduplication.

    Pass 1 (exact): group by (metric, normalized_value, normalized_timeline).
                    Within each group, keep the item with the longest passage.
    Pass 2 (fuzzy): for remaining items with the same (metric, timeline),
                    if any two passages are >90% similar, keep the longer one.
    """
    # Pass 1 — exact
    groups: dict[tuple, list[ClassifiedItem]] = {}
    for item in items:
        key = (
            item.metric,
            _normalize_value_for_dedup(item.guidance_value),
            item.timeline,  # already normalized by this point
        )
        groups.setdefault(key, []).append(item)

    pass1_survivors: list[ClassifiedItem] = []
    for key, group in groups.items():
        if len(group) == 1:
            pass1_survivors.append(group[0])
        else:
            keeper = max(group, key=lambda x: len(x.passage))
            pass1_survivors.append(keeper)
            for dropped in group:
                if dropped is not keeper:
                    rejection_log.append({
                        "chunk_id":     dropped.chunk_id,
                        "rule":         "rule5_exact",
                        "reason":       "duplicate",
                        "item_summary": _item_summary(dropped),
                    })

    # Pass 2 — fuzzy
    kept: list[ClassifiedItem] = []
    for item in pass1_survivors:
        merged = False
        for i, existing in enumerate(kept):
            if existing.metric != item.metric or existing.timeline != item.timeline:
                continue
            if _passage_similarity(item.passage, existing.passage) > 0.90:
                if len(item.passage) > len(existing.passage):
                    rejection_log.append({
                        "chunk_id":     existing.chunk_id,
                        "rule":         "rule5_fuzzy",
                        "reason":       "near_duplicate_passage",
                        "item_summary": _item_summary(existing),
                    })
                    kept[i] = item
                else:
                    rejection_log.append({
                        "chunk_id":     item.chunk_id,
                        "rule":         "rule5_fuzzy",
                        "reason":       "near_duplicate_passage",
                        "item_summary": _item_summary(item),
                    })
                merged = True
                break
        if not merged:
            kept.append(item)

    return kept
