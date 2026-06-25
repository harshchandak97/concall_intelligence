"""
Single-Pass Frontier Model Experiment
======================================
Spec: specs/SPEC_EXPERIMENT_SINGLEPASS_FRONTIER.md

Tests whether the documented single-pass ceiling was a weak-model artifact
or a structural limitation, by running gpt-4o (control) and gpt-5.5 (primary)
on all 4 target transcripts using prompt_v8.

Each company × arm is run twice to detect run-to-run oscillation at temp=0.

Output: experiment_output/SINGLEPASS_FRONTIER_RESULTS.md
"""

import os
import re
import sys
import json
import argparse
import datetime
from pathlib import Path
from typing import Optional

from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv

from schemas import GuidanceItem, ExtractionResult

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
PROMPT_PATH = BASE_DIR / "prompts" / "prompt_v8.txt"
OUTPUT_DIR = BASE_DIR / "experiment_output"
OUTPUT_FILE = OUTPUT_DIR / "SINGLEPASS_FRONTIER_RESULTS.md"

COMPANIES = [
    {
        "name": "Asian Paints",
        "quarter": "Q4 FY26",
        "transcript": BASE_DIR / "transcripts" / "asian_paints_Q4_FY26.pdf",
        "ground_truth": BASE_DIR / "data" / "asian_paints_Q4_FY26_ground_truth_v3.txt",
    },
    {
        "name": "Fineotex Chemical",
        "quarter": "Q4 FY26",
        "transcript": BASE_DIR / "transcripts" / "fineotex_chemical_Q4_FY26.pdf",
        "ground_truth": BASE_DIR / "data" / "fineotex_chemical_Q4_FY26_ground_truth_v1.txt",
    },
    {
        "name": "Sandhar Technologies",
        "quarter": "Q4 FY26",
        "transcript": BASE_DIR / "transcripts" / "sandhar_technologies_Q4_FY26.pdf",
        "ground_truth": BASE_DIR / "data" / "sandhar_technologies_Q4_FY26_ground_truth_v1.txt",
    },
    {
        "name": "Mold-Tek Packaging",
        "quarter": "Q4 FY26",
        "transcript": BASE_DIR / "transcripts" / "mold-tek_packaging_Q4_FY26.pdf",
        "ground_truth": BASE_DIR / "data" / "mold-tek_packaging_Q4_FY26_ground_truth_v1.txt",
    },
]

ARMS = [
    {
        "label": "arm0_gpt4o",
        "model": "gpt-4o",
        "temperature": 0,
        "description": "Control — gpt-4o + prompt_v8 (reproduce documented baseline)",
    },
    {
        "label": "arm1_gpt55",
        "model": "gpt-5.5",
        "temperature": None,  # gpt-5.5 only supports default temperature (1)
        "description": "Primary — gpt-5.5 + prompt_v8 (isolate model variable)",
    },
]

RUNS_PER_ARM = 2  # run twice per company to detect temp=0 oscillation

# ── Extraction ────────────────────────────────────────────────────────────────

def load_prompt(transcript_text: str) -> str:
    with open(PROMPT_PATH) as f:
        return f.read().replace("{transcript_text}", transcript_text)


def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "".join(page.extract_text() or "" for page in reader.pages)


def run_extraction(
    client: OpenAI, model: str, transcript_text: str, temperature: Optional[float]
) -> tuple[ExtractionResult, int]:
    """Returns (result, output_tokens). Raises on API error."""
    prompt = load_prompt(transcript_text)
    kwargs: dict = dict(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format=ExtractionResult,
    )
    if temperature is not None:
        kwargs["temperature"] = temperature
    response = client.beta.chat.completions.parse(**kwargs)
    output_tokens = response.usage.completion_tokens if response.usage else 0
    return response.choices[0].message.parsed, output_tokens


# ── Ground-truth parsing ──────────────────────────────────────────────────────

def parse_ground_truth(path: Path) -> list[dict]:
    with open(path) as f:
        content = f.read()
    items = []
    for block in content.strip().split("\n\n"):
        lines = block.strip().splitlines()
        item: dict = {}
        for line in lines:
            if ": " in line:
                key, _, value = line.partition(": ")
                key = key.strip().lstrip("- ")
                value = value.strip().strip('"')
                item[key] = value
        if "id" not in item or "metric" not in item:
            continue
        item["page_number"] = int(item.get("page_number", 0))
        item["guidance_value"] = None if item.get("guidance_value") in (None, "null") else item.get("guidance_value")
        item["guidance_unit"] = None if item.get("guidance_unit") in (None, "null") else item.get("guidance_unit")
        item["credibility_scorable"] = item.get("credibility_scorable", "false").lower() == "true"
        item["metric"] = item["metric"].strip()
        items.append(item)
    return items


# ── Eval logic ────────────────────────────────────────────────────────────────

def parse_midpoint(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    m = re.match(r"^([\d.]+)\s*[-–]\s*([\d.]+)$", value)
    if m:
        return (float(m.group(1)) + float(m.group(2))) / 2
    try:
        return float(value)
    except ValueError:
        return None


def is_value_match(gt_value: Optional[str], llm_value: Optional[str]) -> bool:
    gt_mid = parse_midpoint(gt_value)
    llm_mid = parse_midpoint(llm_value)
    if gt_mid is None and llm_mid is None:
        return True
    if gt_mid is None or llm_mid is None:
        return False
    if gt_mid == 0:
        return llm_mid == 0
    return abs(llm_mid - gt_mid) / gt_mid <= 0.10


def is_match(gt: dict, llm: GuidanceItem) -> bool:
    return (
        llm.metric.strip() == gt["metric"]
        and llm.timeline.strip() == gt["timeline"].strip()
        and is_value_match(gt["guidance_value"], llm.guidance_value)
    )


def compute_eval(gt_items: list[dict], llm_items: list[GuidanceItem]) -> dict:
    matched_gt: set[int] = set()
    matched_llm: set[int] = set()
    for i, gt in enumerate(gt_items):
        for j, llm in enumerate(llm_items):
            if j not in matched_llm and is_match(gt, llm):
                matched_gt.add(i)
                matched_llm.add(j)
                break
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


# ── Report builder ────────────────────────────────────────────────────────────

def format_items_table(items: list[GuidanceItem]) -> str:
    if not items:
        return "_No items extracted._\n"
    rows = ["| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |",
            "|---|--------|-------|------|----------|----------|---------------------------|"]
    for i, it in enumerate(items, 1):
        passage_preview = it.passage.replace("\n", " ")[:120].replace("|", "\\|")
        rows.append(
            f"| {i} | {it.metric} | {it.guidance_value or 'null'} | "
            f"{it.guidance_unit or 'null'} | {it.timeline} | "
            f"{'yes' if it.credibility_scorable else 'no'} | {passage_preview}… |"
        )
    return "\n".join(rows) + "\n"


def format_gt_coverage(gt_items: list[dict], matched_gt: set[int]) -> str:
    rows = ["| # | metric | value | timeline | matched |",
            "|---|--------|-------|----------|---------|"]
    for i, gt in enumerate(gt_items):
        rows.append(
            f"| {i+1} | {gt['metric']} | {gt.get('guidance_value') or 'null'} | "
            f"{gt.get('timeline','')} | {'✓' if i in matched_gt else '✗'} |"
        )
    return "\n".join(rows) + "\n"


def format_false_positives(items: list[GuidanceItem], matched_llm: set[int]) -> str:
    fps = [(j, it) for j, it in enumerate(items) if j not in matched_llm]
    if not fps:
        return "_None_\n"
    rows = ["| # | metric | value | timeline | passage (first 120 chars) |",
            "|---|--------|-------|----------|---------------------------|"]
    for j, it in fps:
        passage_preview = it.passage.replace("\n", " ")[:120].replace("|", "\\|")
        rows.append(
            f"| {j+1} | {it.metric} | {it.guidance_value or 'null'} | "
            f"{it.timeline} | {passage_preview}… |"
        )
    return "\n".join(rows) + "\n"


# ── Main experiment runner ────────────────────────────────────────────────────

def run_experiment(arms_to_run: list[dict]) -> None:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    OUTPUT_DIR.mkdir(exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Results structure: arm_label → company_name → run_number → result dict
    all_results: dict[str, dict[str, list[dict]]] = {}

    for arm in arms_to_run:
        arm_label = arm["label"]
        model = arm["model"]
        temperature = arm.get("temperature")
        all_results[arm_label] = {}

        print(f"\n{'='*60}")
        print(f"ARM: {arm_label} | model={model} | temperature={temperature if temperature is not None else 'default'}")
        print(f"{'='*60}")

        for company in COMPANIES:
            name = company["name"]
            all_results[arm_label][name] = []

            print(f"\n  Loading transcript: {company['transcript'].name}")
            try:
                transcript_text = extract_text_from_pdf(company["transcript"])
            except FileNotFoundError:
                print(f"  ERROR: transcript not found — {company['transcript']}")
                for run_num in range(1, RUNS_PER_ARM + 1):
                    all_results[arm_label][name].append({
                        "run": run_num, "error": "transcript not found",
                        "items": [], "eval": None, "output_tokens": 0,
                    })
                continue

            char_count = len(transcript_text)
            print(f"  Transcript: {char_count:,} chars")

            gt_items = parse_ground_truth(company["ground_truth"])
            print(f"  Ground truth: {len(gt_items)} items")

            for run_num in range(1, RUNS_PER_ARM + 1):
                print(f"  Run {run_num}/{RUNS_PER_ARM}...", end=" ", flush=True)
                try:
                    result, output_tokens = run_extraction(client, model, transcript_text, temperature)
                    llm_items = result.items
                    eval_result = compute_eval(gt_items, llm_items)
                    print(
                        f"extracted={len(llm_items)} | "
                        f"recall={eval_result['recall']*100:.0f}% | "
                        f"precision={eval_result['precision']*100:.0f}% | "
                        f"tokens_out={output_tokens}"
                    )
                    all_results[arm_label][name].append({
                        "run": run_num,
                        "error": None,
                        "items": llm_items,
                        "gt_items": gt_items,
                        "eval": eval_result,
                        "output_tokens": output_tokens,
                        "char_count": char_count,
                    })
                except Exception as e:
                    print(f"ERROR: {e}")
                    all_results[arm_label][name].append({
                        "run": run_num, "error": str(e),
                        "items": [], "gt_items": gt_items, "eval": None, "output_tokens": 0,
                        "char_count": char_count,
                    })

    # ── Write markdown report ─────────────────────────────────────────────────

    lines: list[str] = []

    lines += [
        "# Single-Pass Frontier Model Experiment — Results",
        "",
        f"**Generated:** {timestamp}  ",
        f"**Spec:** `specs/SPEC_EXPERIMENT_SINGLEPASS_FRONTIER.md`  ",
        f"**Prompt:** `prompts/prompt_v8.txt` (all arms)  ",
        f"**Temperature:** 0 (all arms)  ",
        f"**Runs per arm per company:** {RUNS_PER_ARM}  ",
        "",
    ]

    # Arms summary table
    lines += ["## Arms", ""]
    lines += ["| Arm | Model | Temperature | Description |", "|-----|-------|-------------|-------------|"]
    for arm in arms_to_run:
        temp_str = str(arm.get("temperature")) if arm.get("temperature") is not None else "default (1)"
        lines.append(f"| {arm['label']} | `{arm['model']}` | {temp_str} | {arm['description']} |")
    lines += [""]

    # Companies summary table
    lines += ["## Target Companies", ""]
    lines += ["| Company | Quarter | GT Items |", "|---------|---------|----------|"]
    for co in COMPANIES:
        gt = parse_ground_truth(co["ground_truth"])
        lines.append(f"| {co['name']} | {co['quarter']} | {len(gt)} |")
    lines += [""]

    # Decision bar
    lines += [
        "## Decision Thresholds (from spec §9)",
        "",
        "| Threshold | Value |",
        "|-----------|-------|",
        "| Recall (win) | ≥ 70% |",
        "| Precision (win) | ≥ 70–80% |",
        "| Mold-Tek truncation | must NOT truncate |",
        "",
    ]

    # ── Per-arm summary scorecard ─────────────────────────────────────────────
    lines += ["---", "", "## Summary Scorecard", ""]

    for arm in arms_to_run:
        arm_label = arm["label"]
        lines += [f"### {arm_label} — `{arm['model']}`", ""]
        lines += [
            "| Company | Run | GT | Extracted | TP | Recall | Precision | Tokens Out | Truncated? |",
            "|---------|-----|----|-----------|----|--------|-----------|------------|------------|",
        ]
        for company in COMPANIES:
            name = company["name"]
            runs = all_results[arm_label].get(name, [])
            for run_data in runs:
                if run_data["error"]:
                    lines.append(f"| {name} | {run_data['run']} | — | ERROR | — | — | — | — | — |")
                    continue
                ev = run_data["eval"]
                tok = run_data["output_tokens"]
                truncated = "⚠️ YES" if tok >= 16000 else "no"
                lines.append(
                    f"| {name} | {run_data['run']} | {ev['gt_count']} | {ev['llm_count']} | "
                    f"{ev['true_positives']} | {ev['recall']*100:.0f}% | "
                    f"{ev['precision']*100:.0f}% | {tok} | {truncated} |"
                )
        lines += [""]

    # ── Oscillation check ─────────────────────────────────────────────────────
    lines += ["---", "", "## Oscillation Check (run-to-run delta at temp=0)", ""]
    lines += [
        "| Arm | Company | Run 1 items | Run 2 items | Delta |",
        "|-----|---------|-------------|-------------|-------|",
    ]
    for arm in arms_to_run:
        arm_label = arm["label"]
        for company in COMPANIES:
            name = company["name"]
            runs = all_results[arm_label].get(name, [])
            valid = [r for r in runs if not r["error"]]
            if len(valid) >= 2:
                c1 = valid[0]["eval"]["llm_count"]
                c2 = valid[1]["eval"]["llm_count"]
                delta = abs(c2 - c1)
                flag = " ⚠️" if delta > 0 else ""
                lines.append(f"| {arm_label} | {name} | {c1} | {c2} | {delta}{flag} |")
            elif len(valid) == 1:
                c1 = valid[0]["eval"]["llm_count"]
                lines.append(f"| {arm_label} | {name} | {c1} | — | — |")
            else:
                lines.append(f"| {arm_label} | {name} | ERROR | ERROR | — |")
    lines += [""]

    # ── Aggregate recall/precision per arm ────────────────────────────────────
    lines += ["---", "", "## Aggregate Metrics (average across all companies, run 1)", ""]
    lines += [
        "| Arm | Avg Recall | Avg Precision | Companies Clearing ≥70% Recall | Companies Clearing ≥70% Precision |",
        "|-----|------------|---------------|-------------------------------|----------------------------------|",
    ]
    for arm in arms_to_run:
        arm_label = arm["label"]
        recalls, precisions = [], []
        r_pass, p_pass = 0, 0
        for company in COMPANIES:
            runs = all_results[arm_label].get(company["name"], [])
            valid = [r for r in runs if not r["error"]]
            if valid:
                ev = valid[0]["eval"]
                recalls.append(ev["recall"])
                precisions.append(ev["precision"])
                if ev["recall"] >= 0.70:
                    r_pass += 1
                if ev["precision"] >= 0.70:
                    p_pass += 1
        if recalls:
            avg_r = sum(recalls) / len(recalls)
            avg_p = sum(precisions) / len(precisions)
            lines.append(
                f"| {arm_label} | {avg_r*100:.1f}% | {avg_p*100:.1f}% | "
                f"{r_pass}/{len(recalls)} | {p_pass}/{len(precisions)} |"
            )
        else:
            lines.append(f"| {arm_label} | — | — | — | — |")
    lines += [""]

    # ── Per-company detailed breakdown ────────────────────────────────────────
    lines += ["---", "", "## Detailed Extraction Results", ""]

    for company in COMPANIES:
        name = company["name"]
        lines += [f"### {name} — {company['quarter']}", ""]

        for arm in arms_to_run:
            arm_label = arm["label"]
            runs = all_results[arm_label].get(name, [])

            for run_data in runs:
                run_num = run_data["run"]
                lines += [f"#### {arm_label} | Run {run_num}", ""]

                if run_data["error"]:
                    lines += [f"**ERROR:** {run_data['error']}", ""]
                    continue

                ev = run_data["eval"]
                lines += [
                    f"**Transcript chars:** {run_data.get('char_count', '?'):,}  ",
                    f"**LLM output tokens:** {run_data['output_tokens']}  ",
                    f"**Items extracted:** {ev['llm_count']}  ",
                    f"**True positives:** {ev['true_positives']} / {ev['gt_count']}  ",
                    f"**Recall:** {ev['recall']*100:.1f}%  ",
                    f"**Precision:** {ev['precision']*100:.1f}%  ",
                    "",
                ]

                lines += ["**Ground-truth coverage:**", ""]
                lines += [format_gt_coverage(run_data["gt_items"], ev["matched_gt_indices"])]

                lines += ["**False positives:**", ""]
                lines += [format_false_positives(run_data["items"], ev["matched_llm_indices"])]

                lines += ["**All extracted items:**", ""]
                lines += [format_items_table(run_data["items"])]

    # ── Full verbatim extracted passages ─────────────────────────────────────
    lines += ["---", "", "## Full Extracted Passages (verbatim)", ""]
    lines += ["> These are the raw passage texts returned by the model — for manual pass/fail review.", ""]

    for arm in arms_to_run:
        arm_label = arm["label"]
        lines += [f"### {arm_label} — `{arm['model']}`", ""]

        for company in COMPANIES:
            name = company["name"]
            runs = all_results[arm_label].get(name, [])
            valid_runs = [r for r in runs if not r["error"]]
            if not valid_runs:
                continue
            run_data = valid_runs[0]  # show run 1 passages

            lines += [f"#### {name}", ""]
            for i, item in enumerate(run_data["items"], 1):
                lines += [
                    f"**[{i}] {item.metric}** | `{item.guidance_value or 'null'}` "
                    f"{item.guidance_unit or ''} | `{item.timeline}` | "
                    f"scorable={'yes' if item.credibility_scorable else 'no'}  ",
                    f"Speaker: {item.speaker}  ",
                    f"Page: {item.page_number}  ",
                    "",
                    f"> {item.passage}",
                    "",
                ]

    # ── Decision summary ──────────────────────────────────────────────────────
    lines += ["---", "", "## Decision Summary", ""]
    lines += [
        "Evaluate each arm against the spec §9 thresholds:",
        "",
        "- **Single-pass wins**: frontier arm clears ~≥70% recall AND ~≥70–80% precision across all companies, AND Mold-Tek does not truncate",
        "- **Hybrid signal**: recall jumps well past baseline but precision is poor, OR misses are mostly label-failures not find-failures",
        "- **Multi-stage validated**: no meaningful lift over baseline, OR Mold-Tek still truncates",
        "",
        "**Fill this in after reviewing the numbers above:**",
        "",
        "| Arm | Verdict | Notes |",
        "|-----|---------|-------|",
        "| arm0_gpt4o | (control — reproduce baseline) | |",
        "| arm1_gpt55 | (to be filled in) | |",
        "",
        "_See spec §8 for the manual semantic recall analysis (find-failure vs label-failure) on misses._",
    ]

    report = "\n".join(lines) + "\n"
    OUTPUT_FILE.write_text(report)
    print(f"\n\nReport written to: {OUTPUT_FILE}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Single-pass frontier model experiment")
    parser.add_argument(
        "--arms",
        nargs="+",
        choices=[a["label"] for a in ARMS] + ["all"],
        default=["all"],
        help="Which arms to run. Default: all",
    )
    parser.add_argument(
        "--companies",
        nargs="+",
        help="Filter to specific companies by name substring (case-insensitive). Default: all",
    )
    args = parser.parse_args()

    selected_arms = ARMS if "all" in args.arms else [a for a in ARMS if a["label"] in args.arms]

    global COMPANIES
    if args.companies:
        filters = [c.lower() for c in args.companies]
        COMPANIES = [c for c in COMPANIES if any(f in c["name"].lower() for f in filters)]

    if not selected_arms:
        print("No arms selected.")
        sys.exit(1)
    if not COMPANIES:
        print("No companies matched the filter.")
        sys.exit(1)

    print(f"Experiment: {len(selected_arms)} arm(s) × {len(COMPANIES)} company(ies) × {RUNS_PER_ARM} runs")
    print(f"Arms: {[a['label'] for a in selected_arms]}")
    print(f"Companies: {[c['name'] for c in COMPANIES]}")
    print(f"Prompt: {PROMPT_PATH}")

    run_experiment(selected_arms)


if __name__ == "__main__":
    main()
