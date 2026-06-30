# Gate Adjudication — 25-company sample (GPT-5.4-mini vs Opus 4.8 reference)

Headline vs pre-registered bars:
- Has-target agreement: 20/25 = 80%  (bar >=85%)  -> marginal miss
- Derived-number (annualisable, within 5pp): 9/11 = 82%
- Top-3 overlap by forward_growth: 1/3 (bar >=2/3) -> miss
- Top-5 overlap: 3/5

## Adjudication of the 11 flagged disagreements

### A. Cheap OVER-READ — reference correctly said `none` (5) — all cheap errors
- aether-industries: cheap "2x at maturity" = asset turnover (2x of *investment*), plant-level, not revenue growth. REF right.
- flair-writing: cheap "₹100-120cr by FY27" = steel-bottle SEGMENT, not company. REF right.
- healthcare-global: cheap "500 beds in 3 yrs" = capacity, not P&L. REF right.
- ifb-industries: cheap "490,000 AC units FY25" = volume/segment; mgmt declined guidance. REF right. (Also mis-parsed as "490000 times" -> 24-billion-% in the converter.)
- restaurant-brands: cheap "700 restaurants by FY27" = store count, not P&L. REF right.

### B. Genuine number disagreement (2)
- bls-international: cheap 25-30% vs ref 10-15% (FY25). Both numbers are in the call; "those operations 25-30%" vs conservative "10-15% normal basis". Ambiguous — needs the transcript. Lean reference (more clearly company-level), low confidence.
- kaynes-technology: cheap "2x by FY28" (~19% CAGR) vs ref ">60% for FY25". Both real; the prompt says pick the MOST AGGRESSIVE -> 60% wins. REF better follows the rule.

### C. Spurious — same substance, flagged only by string/representation diffs (4)
- kellton-tech: "in the next 2-3 years" vs "the next 2-3 years" — identical ($200M). AGREE.
- sobha: "this year" vs "FY25" — identical (₹8500cr). AGREE.
- yatra-online: "from 1Q onwards" vs "...(current fiscal year)" — identical (₹20cr PAT). AGREE.
- satin-creditcare: cheap 25% CAGR vs ref ₹29,000cr AUM by 2028 — SAME guidance, two representations. AGREE.

## Verdict
Direction of error = cheap OVER-READS non-P&L numbers (store-count, unit volumes,
bed capacity, asset-turnover, segment lines) and mis-parses them. This pollutes the
TOP of the ranking: cheap's top-3 = [aether(err), ifb(err), kalyani] — 2 of 3 are
over-read errors. The reference (Opus 4.8) is correctly stricter.

Substantive agreement once spurious string-diffs are collapsed and over-reads are
recognised as cheap errors:
- has-target: 5/5 disagreements are cheap over-reading (prompt-fixable).
- both-target substantive agreement ~17/19.

This is the §5a "FAIL -> fix the prompt, re-run" path, NOT a model-capability failure.

## Recommended fixes before re-running the gate
1. PROMPT: explicitly exclude store/outlet counts, unit/volume targets, bed/seat
   capacity, and asset-turnover ("Nx of investment") multiples; reinforce
   company-level vs segment. These are the entire has-target disagreement set.
2. CONVERTER (forward_growth.py): sanity-guard multiples (a "multiple" > ~20 is a
   mis-tag -> unparseable, not 24-billion-%).
3. VALIDATOR (validate_extraction.py): make the raw-field timeframe comparison
   lenient (normalise "this year"->FY25 etc.), so kellton/sobha/yatra/satin stop
   showing as disagreements; optionally treat %-vs-absolute of the same guidance
   as agreement.
