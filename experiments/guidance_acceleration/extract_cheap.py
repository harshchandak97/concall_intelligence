#!/usr/bin/env python3
"""extract_cheap.py — STEP 3/4 batch-ready 4-field extraction (OpenAI).

The LLM does ONLY the reading: per transcript it returns the single most
aggressive quantified, company-level, forward-looking growth target as four
fields (metric/value/unit/timeframe) plus the verbatim passage. All arithmetic
is downstream in forward_growth.py.

Modes:
  --sample N   process a deterministic stride sample of N companies (the gate)
  --all        process every usable transcript from download_log.csv
  --all-files  process every top-level PDF in transcripts/
Run modes:
  --sync       call the API one transcript at a time, live progress (default)
  --batch      build+submit ONE OpenAI Batch job (50% cheaper) -> prints batch id
  --dry-run    build the Batch JSONL + manifest only; do not upload
  --status ID  print Batch status/counts
  --collect ID download a finished batch's results into cheap/

Outputs (under extractions/):
  text/{slug}.txt    extracted transcript text  (identical input for both models)
  cheap/{slug}.json  the model's 4-field target
  batch/*.jsonl      submitted Batch request files
  batch/*.manifest.json  request manifest: model, prompt/schema hashes, slugs

Reuses the structured-output pattern from the repo's run.py.

Usage:
  python extract_cheap.py --sample 25 --sync
  python extract_cheap.py --all --batch --model gpt-5.4 --out-name gpt54_full
  python extract_cheap.py --all-files --batch --model gpt-5.4 --out-name gpt54_all_files
  python extract_cheap.py --all --dry-run --model gpt-5.4 --out-name gpt54_full
  python extract_cheap.py --status batch_abc123
  python extract_cheap.py --collect batch_abc123
"""
from __future__ import annotations
import argparse
import hashlib
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

MODEL = "gpt-5.4"
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


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _prompt_for(text: str) -> str:
    return _prompt_template().replace("{transcript_text}", text)


def _request_body(text: str, model: str, prompt_template: str) -> dict:
    """One Batch API request body.

    Keep the static prompt/schema byte-stable and put only transcript text at the
    placeholder near the end of the prompt. That preserves OpenAI automatic prompt
    caching across the common prefix.
    """
    return {
        "model": model,
        "temperature": 0,  # match sync mode; ignored by reasoning models if unsupported
        "messages": [
            {
                "role": "user",
                "content": prompt_template.replace("{transcript_text}", text),
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "guidance_acceleration_extraction",
                "strict": True,
                "schema": EXTRACTION_SCHEMA,
            },
        },
    }


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
    rows = _all_transcript_files() if args.all_files else L.usable_transcripts()
    if args.slugs:
        want = {s.strip() for s in args.slugs.split(",") if s.strip()}
        rows = [r for r in rows if r["slug"] in want]
    elif args.sample:
        rows = L.sample(rows, args.sample)
    return rows


def _all_transcript_files() -> list[dict]:
    """Every top-level transcript PDF on disk, joined to universe metadata when possible.

    This is intentionally separate from lib_extract.usable_transcripts(), which trusts
    download_log.csv. Use this when recovered PDFs exist but the log has not yet been
    updated, or when the user explicitly wants every PDF in transcripts/.
    """
    universe = {}
    if L.COHORT_CSV.exists():
        import csv
        with open(L.COHORT_CSV, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("slug"):
                    universe[r["slug"]] = r

    rows = []
    suffix = "_Q4_FY24.pdf"
    for path in sorted(L.TRANSCRIPTS.glob("*.pdf")):
        slug = path.name[:-len(suffix)] if path.name.endswith(suffix) else path.stem
        meta = universe.get(slug, {})
        try:
            mcap = float(meta.get("market_cap_cr", "inf"))
        except ValueError:
            mcap = float("inf")
        rows.append({
            **meta,
            "slug": slug,
            "file": path.name,
            "path": path,
            "market_cap_cr": mcap,
        })
    rows.sort(key=lambda x: (x["market_cap_cr"], x["slug"]))
    return rows


def _filtered_for_output(rows: list[dict], out_dir: Path, skip_existing: bool) -> list[dict]:
    if not skip_existing:
        return rows
    return [row for row in rows if not (out_dir / f"{row['slug']}.json").exists()]


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
def build_batch_files(rows: list[dict], model: str, out_name: str) -> tuple[Path, Path]:
    """Build the Batch JSONL and manifest without submitting.

    The manifest is local-only bookkeeping so a later collection/audit can verify
    the exact prompt/schema/model and selected transcript set.
    """
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_out = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in out_name)
    jsonl = BATCH_DIR / f"{safe_out}_{ts}_requests.jsonl"
    manifest = BATCH_DIR / f"{safe_out}_{ts}_manifest.json"
    prompt_template = _prompt_template()
    schema_text = json.dumps(EXTRACTION_SCHEMA, sort_keys=True, separators=(",", ":"))

    with open(jsonl, "w", encoding="utf-8") as f:
        for row in rows:
            text = _text_for(row)
            body = _request_body(text, model, prompt_template)
            f.write(json.dumps({
                "custom_id": row["slug"], "method": "POST",
                "url": "/v1/chat/completions", "body": body,
            }, ensure_ascii=False) + "\n")

    manifest.write_text(json.dumps({
        "created_at": ts,
        "model": model,
        "out_name": out_name,
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h",
        "request_count": len(rows),
        "prompt_path": str(PROMPT_PATH.relative_to(L.HERE)),
        "prompt_sha256": _sha256_text(prompt_template),
        "schema_sha256": _sha256_text(schema_text),
        "jsonl_file": jsonl.name,
        "cost_notes": [
            "Batch API is async and cheaper than sync calls.",
            "Prompt caching is automatic when static prefix/schema are byte-stable.",
            "Transcript text is inserted at the end placeholder to preserve common-prefix cache hits.",
        ],
        "requests": [
            {
                "custom_id": row["slug"],
                "company_name": row.get("company_name"),
                "file": row.get("file"),
                "market_cap_cr": row.get("market_cap_cr"),
            }
            for row in rows
        ],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[batch] wrote {len(rows)} requests -> {jsonl}")
    print(f"[batch] wrote manifest -> {manifest}")
    return jsonl, manifest


def run_batch(rows: list[dict], model: str, out_name: str, dry_run: bool) -> None:
    """Build a JSONL of chat requests (custom_id=slug), upload, create a batch."""
    jsonl, manifest = build_batch_files(rows, model, out_name)
    if dry_run:
        print("[batch] dry run only; not uploaded.")
        print(f"        inspect JSONL: {jsonl}")
        print(f"        inspect manifest: {manifest}")
        return

    client = OpenAI()
    with open(jsonl, "rb") as fh:
        up = client.files.create(file=fh, purpose="batch")
    batch = client.batches.create(
        input_file_id=up.id, endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"experiment": "guidance_acceleration", "step": "4",
                  "model": model, "out_name": out_name,
                  "manifest": manifest.name, "jsonl": jsonl.name})
    print(f"[batch] submitted: {batch.id}  (status={batch.status})  model={model}  out={out_name}/")
    print(f"        status:  python extract_cheap.py --status {batch.id}")
    print(f"        collect: python extract_cheap.py --collect {batch.id}")


def batch_status(batch_id: str) -> None:
    client = OpenAI()
    batch = client.batches.retrieve(batch_id)
    print(f"[status] {batch.id} status={batch.status} endpoint={batch.endpoint}")
    print(f"         counts={batch.request_counts}")
    print(f"         input_file={batch.input_file_id} output_file={batch.output_file_id} error_file={batch.error_file_id}")
    print(f"         metadata={batch.metadata}")


def _usage_summary(body: dict) -> tuple[int, int, int]:
    usage = body.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    details = usage.get("prompt_tokens_details") or {}
    cached_tokens = int(details.get("cached_tokens") or 0)
    return prompt_tokens, cached_tokens, completion_tokens


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

    if batch.error_file_id:
        err = client.files.content(batch.error_file_id).text
        err_path = BATCH_DIR / f"{batch_id}_errors.jsonl"
        err_path.write_text(err, encoding="utf-8")
        print(f"  wrote error file -> {err_path}")

    content = client.files.content(batch.output_file_id).text
    raw_path = BATCH_DIR / f"{batch_id}_output.jsonl"
    raw_path.write_text(content, encoding="utf-8")
    print(f"  wrote raw output -> {raw_path}")

    n = 0
    failed = 0
    usage_totals = {"prompt": 0, "cached": 0, "completion": 0}
    for line in content.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        slug = rec["custom_id"]
        try:
            if rec.get("error"):
                raise RuntimeError(rec["error"])
            body = rec["response"]["body"]
            prompt_tokens, cached_tokens, completion_tokens = _usage_summary(body)
            usage_totals["prompt"] += prompt_tokens
            usage_totals["cached"] += cached_tokens
            usage_totals["completion"] += completion_tokens
            raw = body["choices"][0]["message"]["content"]
            result = Extraction.model_validate_json(raw)
            (out_dir / f"{slug}.json").write_text(
                result.model_dump_json(indent=2), encoding="utf-8")
            n += 1
        except Exception as e:
            failed += 1
            print(f"  ! {slug}: {str(e)[:70]}")

    summary = {
        "batch_id": batch_id,
        "status": batch.status,
        "out_name": out_name,
        "written": n,
        "failed": failed,
        "request_counts": batch.request_counts.model_dump() if batch.request_counts else None,
        "usage": usage_totals,
        "cached_prompt_token_pct": (
            round(100 * usage_totals["cached"] / usage_totals["prompt"], 2)
            if usage_totals["prompt"] else None
        ),
        "raw_output": raw_path.name,
        "error_file": f"{batch_id}_errors.jsonl" if batch.error_file_id else None,
        "metadata": batch.metadata,
    }
    summary_path = BATCH_DIR / f"{batch_id}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[collect] wrote {n} results -> {out_dir}")
    print(f"[collect] failed={failed} prompt_tokens={usage_totals['prompt']:,} "
          f"cached={usage_totals['cached']:,} completion={usage_totals['completion']:,} "
          f"cached_pct={summary['cached_prompt_token_pct']}")
    print(f"[collect] wrote summary -> {summary_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch-ready 4-field guidance extraction.")
    sel = ap.add_mutually_exclusive_group()
    sel.add_argument("--sample", type=int, help="process a stride sample of N (gate)")
    sel.add_argument("--all", action="store_true", help="process every usable transcript")
    sel.add_argument("--all-files", action="store_true",
                     help="process every top-level PDF in transcripts/, ignoring download_log status")
    sel.add_argument("--slugs", help="comma-separated slugs to process (spot check)")
    ap.add_argument("--sync", action="store_true", help="call the API live (default)")
    ap.add_argument("--batch", action="store_true", help="submit one OpenAI Batch job")
    ap.add_argument("--dry-run", action="store_true",
                    help="build Batch JSONL + manifest but do not upload or submit")
    ap.add_argument("--status", metavar="BATCH_ID", help="print OpenAI Batch status")
    ap.add_argument("--collect", metavar="BATCH_ID", help="download a finished batch")
    ap.add_argument("--model", default=MODEL,
                    help=f"OpenAI model id (default {MODEL})")
    ap.add_argument("--out-name", default="cheap",
                    help="subfolder under extractions/ to write into (default 'cheap')")
    ap.add_argument("--skip-existing", action="store_true",
                    help="sync: skip companies whose {out-name}/{slug}.json exists")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    if args.status:
        batch_status(args.status)
        return
    if args.collect:
        collect_batch(args.collect)
        return
    if not args.sample and not args.all and not args.all_files and not args.slugs:
        ap.error("one of --sample N, --all, --all-files, --slugs, or --collect BATCH_ID is required")

    out_dir = EXTRACT_DIR / args.out_name
    rows = _select(args)
    if args.batch or args.dry_run:
        rows = _filtered_for_output(rows, out_dir, args.skip_existing)
    print(f"selected {len(rows)} transcripts "
          f"({'sample ' + str(args.sample) if args.sample else 'all files' if args.all_files else 'full universe'})  "
          f"model={args.model}  out={args.out_name}/")
    if args.batch or args.dry_run:
        if not rows:
            print("nothing to submit")
            return
        run_batch(rows, args.model, args.out_name, dry_run=args.dry_run)
    else:
        run_sync(rows, args.model, out_dir, args.skip_existing)


if __name__ == "__main__":
    main()
