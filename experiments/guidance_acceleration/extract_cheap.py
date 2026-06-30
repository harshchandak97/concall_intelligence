#!/usr/bin/env python3
"""extract_cheap.py — STEP 3/4 cheap 4-field extraction (GPT-5.4-mini, OpenAI).

The LLM does ONLY the reading: per transcript it returns the single most
aggressive quantified, company-level, forward-looking growth target as four
fields (metric/value/unit/timeframe) plus the verbatim passage. All arithmetic
is downstream in forward_growth.py.

Modes:
  --sample N   process a deterministic stride sample of N companies (the gate)
  --all        process every usable transcript (step 4, full universe)
Run modes:
  --sync       call the API one transcript at a time, live progress (default)
  --batch      build+submit ONE OpenAI Batch job (50% cheaper) -> prints batch id
  --collect ID download a finished batch's results into cheap/

Outputs (under extractions/):
  text/{slug}.txt    extracted transcript text  (identical input for both models)
  cheap/{slug}.json  the model's 4-field target

Reuses the structured-output pattern from the repo's run.py.

Usage:
  python extract_cheap.py --sample 25 --sync
  python extract_cheap.py --all --batch
  python extract_cheap.py --collect batch_abc123
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

import lib_extract as L

load_dotenv(L.HERE.parent.parent / ".env")  # repo-root .env holds OPENAI_API_KEY

MODEL = "gpt-5.4-mini"
PROMPT_PATH = L.HERE / "prompts" / "extract_4field.md"
EXTRACT_DIR = L.HERE / "extractions"
TEXT_DIR = EXTRACT_DIR / "text"
CHEAP_DIR = EXTRACT_DIR / "cheap"
BATCH_DIR = EXTRACT_DIR / "batch"


# Company-level PAT-CAGR drivers. Distinct kinds so Python knows GROWTH vs a margin
# LEVEL (the classification that fixes the "ebitda 25% = margin or growth?" ambiguity).
DriverMetric = Literal[
    "revenue_growth_pct", "revenue_absolute",
    "pat_growth_pct", "pat_absolute",
    "ebitda_margin_pct", "pbt_margin_pct", "net_margin_pct",
]


class Guidance(BaseModel):
    """One forward-looking PAT-CAGR driver. `scope` says whose number it is —
    only scope=='company' feeds the CAGR; segment/geography/subsidiary items are
    extracted+labelled for audit, then filtered out by Python."""
    metric: DriverMetric
    value: str
    unit: str
    currency: Optional[Literal["INR", "USD"]]
    scope: Literal["company", "segment", "geography", "subsidiary"]
    timeline: str
    passage: str


class Extraction(BaseModel):
    """Company-level PAT-CAGR drivers for one transcript (no `other` bucket — only
    the metrics that feed the CAGR are extracted). The LLM extracts + classifies;
    Python ranks (with the Screener base)."""
    call_period: str
    items: List[Guidance]


# Explicit JSON schema for the Batch API (parse() isn't available there).
GUIDANCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["metric", "value", "unit", "currency", "scope", "timeline", "passage"],
    "properties": {
        "metric": {"type": "string", "enum": [
            "revenue_growth_pct", "revenue_absolute", "pat_growth_pct",
            "pat_absolute", "ebitda_margin_pct", "pbt_margin_pct", "net_margin_pct"]},
        "value": {"type": "string"},
        "unit": {"type": "string"},
        "currency": {"type": ["string", "null"], "enum": ["INR", "USD", None]},
        "scope": {"type": "string",
                  "enum": ["company", "segment", "geography", "subsidiary"]},
        "timeline": {"type": "string"},
        "passage": {"type": "string"},
    },
}
EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["call_period", "items"],
    "properties": {
        "call_period": {"type": "string"},
        "items": {"type": "array", "items": GUIDANCE_SCHEMA},
    },
}


def _prompt_for(text: str) -> str:
    return PROMPT_PATH.read_text().replace("{transcript_text}", text)


def _brief(result) -> str:
    """Short one-line summary of a transcript's extraction for the progress log."""
    items = result.items
    if not items:
        return "—"
    co = [g for g in items if g.scope == "company"]
    other = len(items) - len(co)
    parts = [f"{g.metric} {g.value}{g.unit}{(' ' + g.currency) if g.currency else ''}/{g.timeline}"
             for g in co[:3]]
    more = f" (+{len(co) - 3})" if len(co) > 3 else ""
    head = f"[{len(co)} co] " + "  |  ".join(parts) + more if co else "[0 company]"
    return head + (f"   ({other} non-co)" if other else "")


def _text_for(row: dict) -> str:
    """Extract (and cache) the transcript text for one company."""
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    fp = TEXT_DIR / f"{row['slug']}.txt"
    if fp.exists() and fp.stat().st_size > 0:
        return fp.read_text(encoding="utf-8")
    text = L.extract_text(row["path"])
    fp.write_text(text, encoding="utf-8")
    return text


def _select(args) -> list[dict]:
    rows = L.usable_transcripts()
    if args.slugs:
        want = {s.strip() for s in args.slugs.split(",") if s.strip()}
        rows = [r for r in rows if r["slug"] in want]
    elif args.sample:
        rows = L.sample(rows, args.sample)
    return rows


# ----------------------------------------------------------------- sync mode
def run_sync(rows: list[dict], model: str, out_dir: Path, skip_existing: bool) -> None:
    client = OpenAI()
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(rows)
    print(f"[sync] {model} on {n} transcripts -> {out_dir.name}/\n")
    counts = {"target": 0, "none": 0, "fail": 0, "skip": 0}
    for i, row in enumerate(rows, 1):
        out = out_dir / f"{row['slug']}.json"
        if skip_existing and out.exists():
            counts["skip"] += 1
            print(f"  [{i}/{n}] {row['slug'][:42]:42} SKIP")
            continue
        try:
            text = _text_for(row)
            resp = client.beta.chat.completions.parse(
                model=model,
                # temperature is honored only on non-reasoning models (e.g. -mini);
                # gpt-5.4's reasoning ignores it. Reproducibility comes from running
                # once and freezing the output (PLAN §6), not from temperature.
                temperature=0,
                messages=[{"role": "user", "content": _prompt_for(text)}],
                response_format=Extraction,
            )
            result = resp.choices[0].message.parsed
            out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
            kind = "target" if result.items else "none"
            counts[kind] += 1
            tag = _brief(result)
            print(f"  [{i}/{n}] {row['slug'][:42]:42} {tag}")
        except Exception as e:  # keep going; one bad transcript shouldn't stop the run
            counts["fail"] += 1
            print(f"  [{i}/{n}] {row['slug'][:42]:42} FAIL {str(e)[:60]}")
        time.sleep(0.2)
    print(f"\nDone. target={counts['target']} none={counts['none']} "
          f"fail={counts['fail']} skip={counts['skip']}  -> {out_dir}")


# ----------------------------------------------------------------- batch mode
def run_batch(rows: list[dict], model: str, out_name: str) -> None:
    """Build a JSONL of chat requests (custom_id=slug), upload, create a batch."""
    client = OpenAI()
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    jsonl = BATCH_DIR / f"requests_{int(time.time())}.jsonl"
    with open(jsonl, "w", encoding="utf-8") as f:
        for row in rows:
            body = {
                "model": model,
                "temperature": 0,  # match the sync path (ignored by gpt-5.4 reasoning)
                "messages": [{"role": "user", "content": _prompt_for(_text_for(row))}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "extraction", "strict": True,
                                    "schema": EXTRACTION_SCHEMA},
                },
            }
            f.write(json.dumps({
                "custom_id": row["slug"], "method": "POST",
                "url": "/v1/chat/completions", "body": body,
            }) + "\n")
    print(f"[batch] wrote {len(rows)} requests -> {jsonl.name}")
    up = client.files.create(file=open(jsonl, "rb"), purpose="batch")
    batch = client.batches.create(
        input_file_id=up.id, endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"experiment": "guidance_acceleration", "step": "4",
                  "model": model, "out_name": out_name})
    print(f"[batch] submitted: {batch.id}  (status={batch.status})  model={model}  out={out_name}/")
    print(f"        poll/collect later:  python extract_cheap.py --collect {batch.id}")


def collect_batch(batch_id: str) -> None:
    client = OpenAI()
    batch = client.batches.retrieve(batch_id)
    # results land in the folder the batch was submitted for (metadata.out_name)
    out_name = (batch.metadata or {}).get("out_name", "cheap")
    out_dir = EXTRACT_DIR / out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[collect] {batch_id} status={batch.status} -> {out_name}/ "
          f"counts={batch.request_counts}")
    if batch.status != "completed":
        print("  not finished yet — re-run --collect when status=completed.")
        return
    content = client.files.content(batch.output_file_id).text
    n = 0
    for line in content.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        slug = rec["custom_id"]
        try:
            raw = rec["response"]["body"]["choices"][0]["message"]["content"]
            result = Extraction.model_validate_json(raw)
            (out_dir / f"{slug}.json").write_text(
                result.model_dump_json(indent=2), encoding="utf-8")
            n += 1
        except Exception as e:
            print(f"  ! {slug}: {str(e)[:70]}")
    print(f"[collect] wrote {n} results -> {out_dir}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Cheap 4-field extraction (GPT-5.4-mini).")
    sel = ap.add_mutually_exclusive_group()
    sel.add_argument("--sample", type=int, help="process a stride sample of N (gate)")
    sel.add_argument("--all", action="store_true", help="process every usable transcript")
    sel.add_argument("--slugs", help="comma-separated slugs to process (spot check)")
    ap.add_argument("--sync", action="store_true", help="call the API live (default)")
    ap.add_argument("--batch", action="store_true", help="submit one OpenAI Batch job")
    ap.add_argument("--collect", metavar="BATCH_ID", help="download a finished batch")
    ap.add_argument("--model", default=MODEL,
                    help=f"OpenAI model id (default {MODEL})")
    ap.add_argument("--out-name", default="cheap",
                    help="subfolder under extractions/ to write into (default 'cheap')")
    ap.add_argument("--skip-existing", action="store_true",
                    help="sync: skip companies whose {out-name}/{slug}.json exists")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    if args.collect:
        collect_batch(args.collect)
        return
    if not args.sample and not args.all and not args.slugs:
        ap.error("one of --sample N, --all, --slugs, or --collect BATCH_ID is required")

    out_dir = EXTRACT_DIR / args.out_name
    rows = _select(args)
    print(f"selected {len(rows)} transcripts "
          f"({'sample ' + str(args.sample) if args.sample else 'full universe'})  "
          f"model={args.model}  out={args.out_name}/")
    if args.batch:
        run_batch(rows, args.model, args.out_name)
    else:
        run_sync(rows, args.model, out_dir, args.skip_existing)


if __name__ == "__main__":
    main()
