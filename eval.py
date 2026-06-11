import re
import uuid
import argparse
from datetime import datetime
from schemas import GuidanceItem
from main import extract_text_from_pdf, extract_forward_looking_statements
from database import get_session, init_db
from models import Extraction, EvalRun


# ── ground truth parser ───────────────────────────────────────────────────────
def parse_ground_truth(path: str) -> list[dict]:
    """Parse the ground truth .txt file into a list of dicts."""
    with open(path, "r") as f:
        content = f.read()

    items = []
    blocks = content.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().splitlines()
        item = {}
        for line in lines:
            if ": " in line:
                key, _, value = line.partition(": ")
                key = key.strip().lstrip("- ")
                value = value.strip().strip('"')
                item[key] = value
        if "id" not in item or "metric" not in item:
            continue
        item["page_number"] = int(item.get("page_number", 0))
        item["guidance_value"] = None if item.get("guidance_value") == "null" else item.get("guidance_value")
        item["guidance_unit"] = None if item.get("guidance_unit") == "null" else item.get("guidance_unit")
        item["credibility_scorable"] = item.get("credibility_scorable", "false").lower() == "true"
        item["metric"] = item["metric"].strip()
        items.append(item)
    return items


# ── fuzzy value matching ──────────────────────────────────────────────────────
def parse_midpoint(value: str | None) -> float | None:
    """Convert a guidance_value string to its midpoint.
    "18-20" -> 19.0  |  "8-10" -> 9.0  |  "10.5" -> 10.5  |  None -> None
    """
    if value is None:
        return None
    value = value.strip()
    match = re.match(r"^([\d.]+)\s*[-–]\s*([\d.]+)$", value)
    if match:
        lo, hi = float(match.group(1)), float(match.group(2))
        return (lo + hi) / 2
    try:
        return float(value)
    except ValueError:
        return None


def is_value_match(gt_value: str | None, llm_value: str | None) -> bool:
    """Fuzzy match on guidance_value midpoints within ±10% of GT midpoint."""
    gt_mid = parse_midpoint(gt_value)
    llm_mid = parse_midpoint(llm_value)
    if gt_mid is None and llm_mid is None:
        return True
    if gt_mid is None or llm_mid is None:
        return False
    if gt_mid == 0:
        return llm_mid == 0
    return abs(llm_mid - gt_mid) / gt_mid <= 0.10


# ── core matching ─────────────────────────────────────────────────────────────
def is_match(gt_item: dict, llm_item: GuidanceItem) -> bool:
    """True positive: metric + timeline exact match AND guidance_value fuzzy match."""
    return (
        llm_item.metric.strip() == gt_item["metric"]
        and llm_item.timeline.strip() == gt_item["timeline"].strip()
        and is_value_match(gt_item["guidance_value"], llm_item.guidance_value)
    )


# ── eval computation ──────────────────────────────────────────────────────────
def compute_eval(gt_items: list[dict], llm_items: list[GuidanceItem]) -> dict:
    matched_gt: set[int] = set()
    matched_llm: set[int] = set()

    for i, gt in enumerate(gt_items):
        for j, llm in enumerate(llm_items):
            if j not in matched_llm and is_match(gt, llm):
                matched_gt.add(i)
                matched_llm.add(j)
                break  # one GT item can only be matched once

    tp = len(matched_gt)
    recall = tp / len(gt_items) if gt_items else 0.0
    precision = tp / len(llm_items) if llm_items else 0.0

    return {
        "matched_gt_indices": matched_gt,
        "matched_llm_indices": matched_llm,
        "true_positives": tp,
        "recall": recall,
        "precision": precision,
        "gt_count": len(gt_items),
        "llm_count": len(llm_items),
    }


# ── output ────────────────────────────────────────────────────────────────────
def print_results(
    gt_items: list[dict],
    llm_items: list[GuidanceItem],
    results: dict,
    prompt_version: str,
    company: str,
    quarter: str,
) -> None:
    matched_gt = results["matched_gt_indices"]
    matched_llm = results["matched_llm_indices"]

    print(f"\n{'='*60}")
    print(f"EVAL RESULTS — {company} {quarter} | Prompt: {prompt_version}")
    print(f"{'='*60}")

    print(f"\nGround Truth Coverage ({results['true_positives']}/{results['gt_count']}):")
    for i, gt in enumerate(gt_items):
        status = "✓" if i in matched_gt else "✗"
        val = gt["guidance_value"] or "null"
        print(f"  [{status}] {gt['metric']} | {val} | {gt['timeline']}")

    false_positive_items = [llm for j, llm in enumerate(llm_items) if j not in matched_llm]
    if false_positive_items:
        print(f"\nFalse Positives ({len(false_positive_items)}):")
        for llm in false_positive_items:
            val = llm.guidance_value or "null"
            print(f"  [FP] {llm.metric} | {val} | {llm.timeline}")

    print(f"\nRecall:    {results['true_positives']}/{results['gt_count']} = {results['recall'] * 100:.1f}%")
    print(f"Precision: {results['true_positives']}/{results['llm_count']} = {results['precision'] * 100:.1f}%")
    print(f"{'='*60}\n")


# ── database saving ──────────────────────────────────────────────────────────
def save_extractions(
    llm_items: list[GuidanceItem],
    run_id: str,
    company: str,
    quarter: str,
    prompt_version: str,
) -> None:
    """Save all extracted items from one run to the extractions table."""
    session = get_session()
    try:
        for item in llm_items:
            row = Extraction(
                run_id=run_id,
                company=company,
                quarter=quarter,
                prompt_version=prompt_version,
                extracted_at=datetime.now(),
                passage=item.passage,
                speaker=item.speaker,
                page_number=item.page_number,
                metric=item.metric,
                guidance_value=item.guidance_value,
                guidance_unit=item.guidance_unit,
                timeline=item.timeline,
                credibility_scorable=item.credibility_scorable,
            )
            session.add(row)
        session.commit()
        print(f"Saved {len(llm_items)} extractions to DB (run_id: {run_id})")
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def save_eval_run(
    results: dict,
    run_id: str,
    company: str,
    quarter: str,
    prompt_version: str,
) -> None:
    """Save eval scores from one run to the eval_runs table."""
    session = get_session()
    try:
        row = EvalRun(
            run_id=run_id,
            company=company,
            quarter=quarter,
            prompt_version=prompt_version,
            recall=results["recall"],
            precision=results["precision"],
            gt_count=results["gt_count"],
            llm_count=results["llm_count"],
            true_positives=results["true_positives"],
            run_at=datetime.now(),
        )
        session.add(row)
        session.commit()
        print(f"Saved eval run to DB (run_id: {run_id})")
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Eval script for concall guidance extraction")
    parser.add_argument("--transcript",     required=True,         help="Path to transcript PDF")
    parser.add_argument("--ground-truth",   required=True,         help="Path to ground truth .txt file")
    parser.add_argument("--prompt-version", default="v8",          help="Prompt version label e.g. v8")
    parser.add_argument("--company",        default="Asian Paints", help="Company name")
    parser.add_argument("--quarter",        default="Q4 FY26",     help="Quarter e.g. Q4 FY26")
    args = parser.parse_args()

    init_db()
    run_id = str(uuid.uuid4())

    print(f"Reading transcript: {args.transcript}")
    transcript_text = extract_text_from_pdf(args.transcript)
    print(f"Extracted {len(transcript_text)} characters")

    print("Running extraction...")
    extraction = extract_forward_looking_statements(transcript_text)
    llm_items = extraction.items
    print(f"LLM returned {len(llm_items)} items")

    print(f"Loading ground truth: {args.ground_truth}")
    gt_items = parse_ground_truth(args.ground_truth)
    print(f"Ground truth: {len(gt_items)} items")

    results = compute_eval(gt_items, llm_items)
    print_results(
        gt_items=gt_items,
        llm_items=llm_items,
        results=results,
        prompt_version=args.prompt_version,
        company=args.company,
        quarter=args.quarter,
    )

    save_extractions(llm_items, run_id, args.company, args.quarter, args.prompt_version)
    save_eval_run(results, run_id, args.company, args.quarter, args.prompt_version)


if __name__ == "__main__":
    main()
