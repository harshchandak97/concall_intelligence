#!/usr/bin/env python3
"""score.py — STEP 5: ACCELERATION = forward PAT CAGR − trailing PAT CAGR.

For each extracted transcript:
  1. company-scope items only -> derive horizon -> split near / long blocks
  2. forward PAT CAGR per block via decision.compute_block_cagr (Base/Bull)
  3. trailing PAT CAGR (3yr ending the call FY) via lib_screener
  4. ACCELERATION = forward CAGR − trailing CAGR  (the experiment's ranking metric)

The "forward" number is max(near, long) by Base CAGR — the boldest promise on
either horizon — while both blocks stay visible on the row. Output:
results/acceleration_ranked.{csv,md}, sorted by Base acceleration.

Usage:  python score.py --candidate gpt54_scope
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

import lib_extract as L
import lib_screener as S
import lib_fx as FX
import decision as D

UNIVERSE = L.HERE / "universe_with_concalls.csv"
CACHE = L.HERE / "extractions" / "screener_cache.json"


def _universe_index() -> dict:
    idx = {}
    with open(UNIVERSE) as f:
        for r in csv.DictReader(f):
            idx[r["slug"]] = r
    return idx


def _load_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {}


def _screener_for(scrip: str, ticker: str, call_fy: int, cache: dict, refresh: bool) -> dict:
    """Fetch (and cache) the FY-anchored base + trailing for one company."""
    key = f"{scrip}@{call_fy}"
    if not refresh and key in cache:
        return cache[key]
    series = S.fetch_series(scrip, ticker, base_fy=call_fy)
    bt = S.base_and_trailing(series, base_fy=call_fy)
    rec = {**bt, "basis": series.get("basis"), "name": series.get("name"),
           "pe": series.get("pe"), "n_fy": len(series.get("fy_series", {})),
           "prior_source": series.get("prior_source"),
           "overlap_div_pct": series.get("overlap_div_pct")}
    cache[key] = rec
    return rec


def score_one(fp: Path, uni: dict, cache: dict, refresh: bool) -> dict | None:
    d = json.loads(fp.read_text())
    slug = fp.stem
    meta = uni.get(slug)
    if not meta:
        print(f"  [skip] {slug}: not in universe")
        return None
    call_fy = S.base_fy_from_call_period(d.get("call_period", ""))

    company = [i for i in d.get("items", []) if i.get("scope") == "company"]
    for i in company:
        i["_horizon"] = D.derive_horizon(i.get("timeline"), call_fy)
    near = [i for i in company if i["_horizon"] == "near"]
    long_ = [i for i in company if i["_horizon"] in ("medium", "long")]

    sc = _screener_for(meta["bse_scrip"], meta.get("nse_ticker"), call_fy, cache, refresh)
    usdinr = FX.usdinr_on(meta.get("concall_date", ""))

    nb, nbull, nbasis, _ = D.compute_block_cagr(near, sc, call_fy, usdinr)
    lb, lbull, lbasis, _ = D.compute_block_cagr(long_, sc, call_fy, usdinr)

    # forward = whichever block implies the higher BASE CAGR (max(near, long));
    # both blocks are kept on the row so the near/long split stays visible.
    usable = [c for c in ((nb, nbull, "near"), (lb, lbull, "long")) if c[0] is not None]
    fwd_base, fwd_bull, which = max(usable, key=lambda c: c[0]) if usable else (None, None, "—")
    trailing = sc.get("trailing_pat_cagr_pct")
    tstatus = sc.get("trailing_status")

    accel_base = accel_bull = None
    if tstatus == "ok" and fwd_base is not None:
        accel_base = round(fwd_base - trailing, 1)
        if fwd_bull is not None:
            accel_bull = round(fwd_bull - trailing, 1)

    return {
        "slug": slug, "company": meta.get("company_name", slug),
        "sector": meta.get("sector", ""), "industry": meta.get("industry", ""),
        "call_fy": call_fy, "basis": sc.get("basis"), "n_fy": sc.get("n_fy"),
        "prior_source": sc.get("prior_source"), "overlap_div_pct": sc.get("overlap_div_pct"),
        "current_rev_cr": sc.get("current_revenue_cr"), "current_pat_cr": sc.get("current_pat_cr"),
        "trailing_pat_cagr": trailing, "trailing_status": tstatus,
        "near_base": nb, "near_bull": nbull,
        "long_base": lb, "long_bull": lbull,
        "fwd_horizon": which, "fwd_base": fwd_base, "fwd_bull": fwd_bull,
        "accel_base": accel_base, "accel_bull": accel_bull,
        "near_basis": nbasis, "long_basis": lbasis,
    }


def _f(v, suf="%"):
    return f"{v:.1f}{suf}" if isinstance(v, (int, float)) else "—"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default="gpt54_scope")
    ap.add_argument("--refresh", action="store_true", help="ignore the screener cache")
    args = ap.parse_args()

    uni = _universe_index()
    cache = _load_cache()
    src = L.HERE / "extractions" / args.candidate
    rows = []
    for fp in sorted(src.glob("*.json")):
        r = score_one(fp, uni, cache, args.refresh)
        if r:
            rows.append(r)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=2))

    # rank: computable acceleration first (desc), then the flagged/uncomputable tail
    rows.sort(key=lambda r: (r["accel_base"] is not None, r["accel_base"] or 0), reverse=True)

    print(f"\n{'COMPANY':<34}{'SECTOR':<22}{'FWD CAGR(B/Bull)':>20}{'TRAIL':>9}{'ACCEL(B/Bull)':>18}  note")
    print("-" * 122)
    for r in rows:
        fwd = f"{_f(r['fwd_base'])}/{_f(r['fwd_bull'])} ({r['fwd_horizon']})"
        trail = _f(r["trailing_pat_cagr"]) if r["trailing_status"] == "ok" else r["trailing_status"][:8]
        accel = f"{_f(r['accel_base'])}/{_f(r['accel_bull'])}" if r["accel_base"] is not None else "—"
        note = "" if r["trailing_status"] == "ok" else f"trailing {r['trailing_status']}"
        if r["fwd_base"] is None:
            note = (note + " · no fwd CAGR").strip(" ·")
        print(f"{r['company'][:33]:<34}{(r['sector'] or '')[:21]:<22}{fwd:>20}{trail:>9}{accel:>18}  {note}")

    out_csv = L.HERE / "results" / f"acceleration_{args.candidate}.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    cols = ["company", "sector", "industry", "call_fy", "basis", "n_fy",
            "prior_source", "overlap_div_pct",
            "current_rev_cr", "current_pat_cr", "trailing_pat_cagr", "trailing_status",
            "near_base", "near_bull", "long_base", "long_bull",
            "fwd_horizon", "fwd_base", "fwd_bull", "accel_base", "accel_bull",
            "near_basis", "long_basis"]
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    # markdown report with the evidence basis, so numbers are auditable by eye
    out_md = L.HERE / "results" / f"acceleration_{args.candidate}.md"
    def _table(rs):
        out = ["| # | Company | Sector | Near B/Bull | Long B/Bull | Fwd CAGR B/Bull | "
               "Trailing | **Accel B/Bull** | Driver |",
               "|---|---|---|---|---|---|---|---|---|"]
        for n, r in enumerate(rs, 1):
            nearc = f"{_f(r['near_base'])}/{_f(r['near_bull'])}"
            longc = f"{_f(r['long_base'])}/{_f(r['long_bull'])}"
            fwd = f"{_f(r['fwd_base'])}/{_f(r['fwd_bull'])} ({r['fwd_horizon']})"
            trail = _f(r["trailing_pat_cagr"]) if r["trailing_status"] == "ok" else f"_{r['trailing_status']}_"
            accel = f"**{_f(r['accel_base'])}/{_f(r['accel_bull'])}**" if r["accel_base"] is not None else "—"
            drv = ((r["long_basis"] if r["fwd_horizon"] == "long" else r["near_basis"])
                   or r["long_basis"] or r["near_basis"] or "").replace("|", "·")[:90]
            out.append(f"| {n} | {r['company'][:34]} | {r['sector']} | {nearc} | {longc} | "
                       f"{fwd} | {trail} | {accel} | {drv} |")
        return out

    flagged = [r for r in rows if r["trailing_status"] != "ok"]
    ml = [f"# Guidance acceleration — `{args.candidate}` ({len(rows)} companies)\n",
          "ACCELERATION = forward PAT CAGR − trailing 3yr PAT CAGR (ending the call FY). "
          "Forward = max(near, long) by Base CAGR — the boldest promise on either horizon "
          "— with both blocks shown. Sorted by Base acceleration.\n"]
    ml += _table(rows)
    if flagged:
        ml.append(f"\n## Trailing-unrankable ({len(flagged)}) — undefined trailing CAGR "
                  "(missing history or near-zero/loss base). Also listed above; collected "
                  "here for the human top-tail check.\n")
        ml += _table(flagged)
    ml.append("\n## Per-company evidence\n")
    for r in rows:
        ml.append(f"### {r['company']}  ·  call FY{r['call_fy']%100} · {r['basis']} basis "
                  f"({r['n_fy']} FY cols)")
        div = r.get("overlap_div_pct")
        src = f"prior_source={r.get('prior_source')}" + (f" (overlap div {div}%)" if div is not None else "")
        ml.append(f"- base: rev ₹{r['current_rev_cr']}cr · PAT ₹{r['current_pat_cr']}cr · "
                  f"trailing PAT CAGR {_f(r['trailing_pat_cagr'])} "
                  f"[{r['trailing_status']}] · {src}")
        ml.append(f"- near CAGR: {_f(r['near_base'])}/{_f(r['near_bull'])}  ·  "
                  f"long CAGR: {_f(r['long_base'])}/{_f(r['long_bull'])}")
        if r["near_basis"]:
            ml.append(f"- near driver: {r['near_basis']}")
        if r["long_basis"]:
            ml.append(f"- long driver: {r['long_basis']}")
        ml.append("")
    out_md.write_text("\n".join(ml) + "\n", encoding="utf-8")
    print(f"\n[written] {out_csv}\n[written] {out_md}")


if __name__ == "__main__":
    main()
