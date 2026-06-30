---
name: download-transcripts
description: Download Indian earnings-call (concall) transcript PDFs for given companies/tickers from screener.in (with BSE fallback) into transcripts/new_transcripts/. Use when asked to fetch, download, or refresh concall/earnings-call transcripts for one or more companies.
---

# Download concall transcripts

Fetches the last N quarters of earnings-call transcripts and saves them as
`transcripts/new_transcripts/{company_slug}_{Qn}_FY{yy}.pdf`.

## Happy path — just run the script

```bash
source venv/bin/activate
python scripts/download_transcripts.py <TICKER> [<TICKER> ...] --quarters 4
```

- Tickers are NSE/screener tickers (e.g. `FCL`, `APCOTEXIND`). Find them from the
  screener URL the user gives, or `https://www.screener.in/company/<TICKER>/`.
- Force a file slug with `TICKER:slug` (e.g. `IPL:india_pesticides`) when the
  auto-derived name from the page title isn't what you want.
- The script tries screener.in first, then falls back to the BSE announcements
  API, downloads via `AnnPdfOpen.aspx` (works for any age), and page-count-checks
  each PDF. Read its per-quarter status output.

## Read the status output, then handle the exceptions

The script prints one line per quarter. Act on these cases:

- **`OK (Np, KB)`** — done. A real transcript is ~15–25 pages.
- **`COVER?`** — file is <5 pages, i.e. a 1-page cover letter, not the transcript.
  Some BSE "Earnings Call Transcript" attachments are cover-only (seen on Avalon
  Q4 FY26); the real transcript is on the company IR site. Find it there
  (`curl` with a browser UA — WebFetch often gets 403) and overwrite the file.
- **Stale FY labels** (e.g. you asked for the latest 4 but get `FY22`/`FY23`) —
  the company's most recent transcript is years old → it **stopped holding
  concalls**. Don't keep stale files; treat as "no transcripts" (below).
- **Fewer quarters than asked** — often legitimate: some companies do concalls
  **half-yearly** (e.g. Balaji Amines → only Q2+Q4) or **started recently**
  (e.g. Stylam → from Q3 FY26). Web-search to confirm cadence before assuming a
  bug; keep the quarters that exist.
- **`NO transcripts found`** — the company may not hold concalls, files only on
  its own site, or only on paid aggregators (Trendlyne). Web-search
  `"<company>" earnings call transcript` to confirm. If it genuinely doesn't
  publish downloadable transcripts, propose a **replacement** (next section).

## Verify before finishing

- Confirm total file count and that each PDF opens with the expected page count.
- Spot-check a couple of first pages so the quarter/date matches the filename
  (`pdfplumber` → page 1 usually has the filing date).

## Replacing a company that doesn't publish transcripts

When asked to swap out a non-concall company:
1. Pick candidates in **industries not already in the set** (diversify).
2. **Always verify current market cap from screener.in** — do not trust estimates
   or memory; caps move a lot (MTAR looked ~₹4.5k but was ₹24.5k). Honor the
   user's cap band (e.g. < ₹5,000cr).
3. Verify the candidate actually has downloadable transcripts before proposing:
   run the script with `--quarters 4` and confirm 4× `OK`.
4. Confirm the final picks with the user when the choice is consequential.

## Notes / gotchas (see also memory: transcript-download-method)

- An inert `<div>Transcript</div>` on screener = no link for that quarter (NOT a
  login gate; a `sessionid` cookie does **not** reveal it). The script skips these
  and uses BSE instead.
- BSE: use the `AnnSubCategoryGetData` endpoint (the older `AnnGetData` returns
  "No Record Found!"). Download via `AnnPdfOpen.aspx?Pname=<attachment>`.
- Quarter mapping (announce month → quarter): Jul–Sep→Q1, Oct–Dec→Q2,
  Jan–Mar→Q3, Apr–Jun→Q4; FY = the fiscal year ending the following March.
