# plan.md — Phase 1 Close-out + v1 Decision Layer (Scenario-Scored Screener)

Context doc for the current phase. Read alongside CLAUDE.md (Two-Gate Model section) and PROJECT.md (v1.2).

**What changed (v1.2):** The project goal is no longer "extract forward-looking guidance." That was always a means, not an end. The end is a **ranked, usable screener output** that converts extracted guidance into a comparable PAT-growth number per company, so the tool actually drives investment decisions instead of just printing structured data. This file now carries the close-out of the extraction work (Steps 1–5, mostly done) PLUS the new decision layer (Steps 6–8) that turns extraction into a usable v1.

**The v1 definition of done:** a single ranked table, one row per company, sorted by implied PAT CAGR, with the guidance evidence shown inline and unconvertible signals flagged for manual reading. Buildable in 2 days. If v1 is genuinely useful, future versions get built. If not, the project stops here — so v1 must stand on its own.

---

## Why this is the right v1 (research-grounded)

These findings, not intuition, drive the design. They are recorded here so the rationale survives.

1. **Forward earnings expectation is the dominant driver of stock returns at the 1–2 year horizon.** Chen & Zhao decomposition: cash-flow news explains ~37% of return variance at 1 year, ~54% at 2 years, exceeding discount-rate news beyond two years. The screener is a machine for surfacing the cash-flow-news signal (management's forward guidance) before the market reprices it.

2. **The edge is structurally real in the sub-₹15,000cr universe.** Limited analyst coverage → pricing inefficiencies. And the guidance-vs-delivery gap is the whole game: ~40% of Indian small caps missed analyst expectations in recent quarters vs ~25% for large caps. This is why credibility (later) is the highest-alpha layer — but it is also why v1 must show its working so every number can be sanity-checked.

3. **Ranges → use the bounds, not the midpoint.** Empirical research (analysts' reaction to range forecasts) shows the lower bound carries more predictive weight, AND that management pads the upper bound by pairing it with a sandbagged lower bound. These pull in opposite directions — so do not collapse to a single biased point. Use the range itself: lower bound drives the conservative scenario, upper bound drives the optimistic one.

4. **Conflicting guidance → scenarios, not averaging.** Standard equity-research practice converts multi-input uncertainty into coherent Base / Bull cases (not a blended single number). Each scenario is an internally consistent combination of assumptions. Revenue and margin are correlated, so combine them as management stated them together.

5. **No fabricated downside in v1.** A true bear case requires modeling a guidance *miss* — a downside event the transcript does not contain data for. Building it would mean inventing numbers (violates the no-hallucination rule). Downside is handled later, correctly, by the credibility layer discounting a chronic misser's Base case. v1 ships Base + Bull only.

---

## The v1 output structure (LOCKED — build this)

One row per company. Two horizon blocks. Two scenarios per block (bounds, not midpoints).

| Company | Near CAGR (Base–Bull) | Long CAGR (Base–Bull) | Current P/E | Guidance Used (verbatim) | Other Signals |
|---|---|---|---|---|---|

Column definitions:
- **Near CAGR (Base–Bull):** implied PAT CAGR from all company-level guidance with horizon ≤ 1 year (near). Base = lower revenue bound × current trailing net margin. Bull = upper revenue bound × upper guided net-margin bound.
- **Long CAGR (Base–Bull):** same calc for all company-level guidance with horizon > 1 year (medium + long), including aspirations ("3x by FYxx") annualised via the n-th root. Base = slower/conservative end. Bull = faster/guided end.
- **Current P/E:** Screener.in, manual for v1. Surfaces the mispricing gap at a glance.
- **Guidance Used (verbatim):** every quote that produced the CAGR numbers, so extraction errors are caught instantly and the number is trustable.
- **Other Signals:** everything that could NOT be converted (segment/geography guidance, capacity additions, order book, new geographies, binary commissioning events). Raw text. Read by eye.

**Why two horizon blocks (the keystone design decision):** near-term and long-term guidance answer different questions, have different trust levels, and feed different parts of the thesis (near-term = quarterly tracking checkpoint; long-term = the re-rating story). They are also a consistency check on each other — e.g. "18–20% next year" compounded 4 years ≈ 2x, but management also says "3x in 4 years," so growth must accelerate later. That gap is a flag: find the capacity/product/market catalyst that explains it, or treat the 3x as talk.

---

## The single conversion rule (deterministic Python, NEVER the LLM)

```
Future PAT = Guided Revenue (bound) × Guided Net Margin (bound)
Implied PAT CAGR = (Future PAT / Current PAT) ^ (1 / years) − 1
```

Applied twice per horizon block:
- **Base** = lower revenue bound × current trailing net margin (margins prove nothing until delivered)
- **Bull** = upper revenue bound × upper guided net-margin bound (both delivered together)

Ranges annualise via `^(1/years)`. "3x in 3–4 years" → Base 32% (4yr) to Bull 44% (3yr). Base numbers (Current Revenue, Current PAT, Current P/E) come from Screener.in.

**The five rules that keep it accurate:**
1. LLM extracts and classifies only. Python does ALL arithmetic. (Primary hallucination guard.)
2. Use bounds, never midpoints.
3. Only `level = company` guidance goes into CAGR numbers. `segment` / `geography` → Other Signals.
4. Empty cells are valid. Never interpolate or ask the LLM to estimate a number management didn't give. A company you can't score is correctly flagged "needs manual reading," not a failure.
5. Verbatim evidence always shown inline.

---

## GUARDRAILS (unchanged, still apply to the extraction work)

1. **Acceptance thresholds set BEFORE running.** No moving goalposts. Proposed bar: recall ≥ 0.85, precision ≥ 0.80, tag accuracy ≥ 0.90. First config that clears the bar wins.
2. **Control variance.** Low temperature, eval set large enough to matter, 2–3 runs per config. Compare averages.
3. **Hold reasoning effort constant across models** (or test it as an explicit variable).
4. **Diagnose failure mode, then move the matching axis** — don't climb the ladder blindly.
5. **Keep 1–2 transcripts fully held-out** as the overfitting guard.
6. **Cost is near-irrelevant at this scale.** Optimize for "cheapest that passes the bar." Your debugging time is the expensive resource.

---

## Steps 1–5 — Extraction work (carried over, mostly done)

### Step 1 — Two-gate spec + tag schema — DONE
Status: DONE in CLAUDE.md + PROJECT.md. Single source of truth. The `level` and `horizon` tags are exactly what the v1 decision layer keys on (see Step 6), so the architecture already supports v1 — no schema change needed.

### Step 2 — Eval set + ground truth (LLM-PROPOSED, HUMAN-ADJUDICATED)
GT exists only for the eval set (~8–15 transcripts), not all production transcripts. Non-negotiable: GT is human-adjudicated. Full playbook at the bottom of this file. **For v1 specifically: do NOT block on perfect GT for all transcripts.** GT on the 5 existing eval transcripts is enough to trust extraction; the v1 ranked table runs on real transcripts with accepted imperfect recall.

### Step 3 — Set acceptance thresholds
Lock precision / recall / tag-accuracy targets now, before any run.

### Step 4 — Baseline run, then diagnose
Simplest config first: 1-step (extraction + classification in one prompt), whole transcript, both candidate models (Sonnet 4.6, GPT-5.4), low temp, 2–3 runs each. Clean extraction prompt aligned to the two-gate spec — NOT old prompt_v8, NOT the GT-proposal prompt. Measure precision, recall, tag accuracy, cost, variance.

| Symptom | Diagnosis | Fix (axis to move) |
|---|---|---|
| Items missed (recall low) | Context / attention | Chunk by Stage 0 segments (Axis B) — but see note |
| Items mislabeled / junk in (precision / tag accuracy low) | Task too complex for one call | Split extraction and classification into 2 calls (Axis A) |
| Both | Move both axes | — |

**Note on chunking:** likely UNNECESSARY now. 15–20k-token transcript is tiny vs a 1M window. Reach for it only if recall genuinely drops on long transcripts.

### Step 5 — Stop at lowest-complexity config that clears the bar
Escalation order (only as far as needed): (1) 1-step whole transcript → (2) 2-step whole transcript → (3) chunked 1-step → (4) chunked 2-step. Validate winner on held-out transcripts. Commit prompt + config + eval numbers to git.

---

## Steps 6–8 — The v1 decision layer (NEW — the 2-day build)

### Step 6 — Write the conversion script (~50 lines, the only genuinely new code)
- Reads extraction output (the tagged guidance items you already produce).
- Filters to `level = company` items only.
- Splits items by `horizon`: near (≤1yr) into the Near block, medium+long into the Long block.
- Applies the conversion rule above twice per block (Base, Bull) using bounds.
- Passes `level = segment/geography` items and capacity/order-book/binary items through as raw text into Other Signals — NO conversion attempted.
- Pure Python arithmetic. Zero LLM. Test on the 5 eval transcripts where you know the right answer.

### Step 7 — Wire in Screener.in base numbers (manual for v1)
- One CSV, filled once per company: Current Revenue, Current PAT (trailing), Current net margin, Current P/E.
- 5 minutes per company. Do NOT automate this yet — premature.
- These are the denominators / base values the conversion rule needs.

### Step 8 — Generate the ranked table + run on real transcripts
- Run extraction on 20–30 real Q4 FY26 transcripts from BSE (companies below ₹15,000cr). Accept imperfect recall.
- Run the conversion script. Output a sorted CSV (open in Excel) or a ~40-line script that writes a simple static HTML table.
- Sort by Near CAGR Base primarily. Scan Long CAGR for re-rating stories, P/E for cheapness, Other Signals for missed upside.
- **v1 is now usable.** A company with high Near CAGR, high Long CAGR, low P/E, and a big capacity addition in Other Signals = top research candidate.

---

## The 2-day build sequence (concrete)

- **Day 1 AM:** Extraction running cleanly on the 5 eval transcripts. Functional, not perfect. (Mostly already done.)
- **Day 1 PM:** Write the conversion script (Step 6). Test against the 5 known transcripts.
- **Day 2 AM:** Run extraction on 20–30 real Q4 FY26 BSE transcripts (sub-₹15,000cr). Accept imperfect recall.
- **Day 2 PM:** Fill Screener.in columns manually (Step 7). Run conversion. Generate sorted table (Step 8).
- **End of Day 2:** Ranked list of 20–30 companies by implied PAT CAGR, evidence visible, signals flagged. Done.

**The motivation milestone:** a company showing high Base PAT CAGR, trading at a low P/E, that no analyst covers — appearing in the table on Day 2. That is the moment the project becomes real and worth continuing.

---

## The validation loop (run alongside v1 — proves the thesis to yourself)

For each company in the top 10: record concall date, Near/Long Base–Bull CAGR, and stock price on that date. Check price at +3 months and +6 months. After one quarter cycle across 15–20 companies you have your OWN empirical answer to "does this guidance signal predict returns in Indian small/mid-caps" — worth more than trusting research on US stocks.

---

## Future versions — IDEAS ONLY (do not plan or build until v1 satisfies)

Deliberately not scoped. Recorded so the path is visible; each is built only if v1 proves useful. Rough order of value:

- **Credibility layer (highest alpha).** The real edge: separate guidance-deliverers from over-promisers. Requires extracting PAST concall guidance and matching against Screener actuals (delivery ratio over 4 quarters). Hard gate, not just a weight. Almost certainly v2 — but only after v1's extraction→number loop works, because it builds directly on top of it.
- **Valuation / mispricing integration.** Forward PEG = P/E ÷ implied CAGR. Turns the manual P/E glance into a computed mispricing score. Forward price target = guided EPS × conservative sector/own-historical multiple.
- **Automated Screener.in pull.** Replace the manual base-number CSV. Needs a name→ticker mapping table.
- **The acceleration-gap flag, automated.** Auto-detect when Long CAGR implies acceleration vs Near CAGR, and surface "find the catalyst" prompts — the consistency check, computed.
- **Extraction signal enhancements (research-backed):** Q&A-vs-prepared-remarks tagging (Q&A guidance more predictive); tone-delta tracking quarter-over-quarter (rising negativity is a strong signal); analyst-pushback pattern detection; uncertainty-hedging language scoring to discount confidence.
- **Composite scoring + weights** across Specificity, Ambition, Credibility, Valuation (the original 4-layer framework) — only once each layer individually proves useful.
- **Productionisation:** browsable dashboard, BSE/NSE auto-download (200→600 companies), AWS deployment.

---

## Step 2 detailed playbook — How to build ground truth (carried over, unchanged)

### Prerequisite
The two-gate spec (Step 1) must exist in writing — it is the rulebook for adjudication.

### A. Select the eval set (8–15 transcripts) — diversity over count
- Spread across sectors: specialty chemicals, auto-ancillary, packaging, IT/services, capital-goods. Cross-industry coverage makes the structural filter trustworthy.
- Include 2–3 companies you know well.
- Include at least one HARD transcript: multi-segment with segment-level guidance (exercises level=segment, track=B).
- Ensure some transcripts contain long-horizon aspirations ("3x revenue by FYxx").
- Set aside 1–2 transcripts as fully held-out.

### B. Propose candidates with TWO strong, cross-family models
- Use Opus 4.8 + GPT-5.5 as proposers. Cross-family minimizes shared blind spots; high capability minimizes misses.
- Deliberately STRONGER and DIFFERENT-family from models under test (Sonnet 4.6, GPT-5.4).
- Dedicated GT-proposal prompt, aligned to the two-gate spec, biased toward HIGH RECALL — over-propose and flag uncertain items. Runs once; can be long/expensive.
- Keep the proposal prompt SEPARATE from the lean extraction prompt under test.
- Run each transcript through both proposers at low temperature, GT structure with all tags. Take the union, deduplicated.

### C. Adjudicate — the human part (irreducible)
- Verbatim check: passage exactly as in PDF? Fix paraphrased quotes.
- Gate 1 check: forward-looking + number/threshold/binary + timeframe? Keep or cut.
- Gate 2 check: horizon / level / track / credibility_scorable correct? Fix tags.
- Disagreement cases first: where the two proposers disagree are highest-value — scrutinize hardest.
- Completeness pass: skim for any number+date both models missed. Pay special attention to Q&A — valid GT can originate in an analyst question management explicitly accepts.

### D. Lock and version
- Save one GT file per transcript: `data/{company}_{quarter}_ground_truth_v{n}.txt`, matching the exact format eval.py parses.
- Record which spec version the GT was built against, and the date.
- Commit to git with a descriptive message. GT frozen during an eval run; re-version if scope changes.

### Effort / cost
- ~8–15 transcripts × 2 proposers ≈ 16–30 API calls (~$1–2 total).
- Human adjudication ≈ 20–40 min/transcript ≈ a few focused hours. The irreducible cost. 12 well-adjudicated transcripts beat 100 sloppy ones.
