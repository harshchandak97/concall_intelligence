## Metric Vocabulary
Date: 7 June 2026
Decision: Use a controlled list of metric types. If LLM doesn't match, use other_<description> format.
Starting list: revenue_growth_pct, revenue_absolute, ebitda_margin_pct, pat_growth_pct, pat_absolute, pbt_margin_pct, eps_absolute, volume_growth_pct, capex_absolute, capacity_addition, commissioning_event, order_book_absolute, price_increase_pct, volume_value_gap_pct
Reason: Prevents free-text metric sprawl, allows programmatic comparison in V2. other_ prefix lets vocabulary grow organically from real data.

Update (8 June 2026): Added pat_growth_pct, pat_absolute, pbt_margin_pct, eps_absolute after confirming these are all available in Screener.in quarterly P&L exports (Net Sales, Operating Profit, OPM%, Other Income, Depreciation, Interest, PBT, Tax, Net Profit, EPS). These are now credibility_scorable when guided at company level. Volume growth % and capex are explicitly NOT credibility_scorable as they are not in Screener.in quarterly P&L.