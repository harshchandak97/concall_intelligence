## Metric Vocabulary
Date: 7 June 2026
Decision: Use a controlled list of metric types. If LLM doesn't match, use other_<description> format.
Starting list: revenue_growth_pct, ebitda_margin_pct, volume_growth_pct, capex_absolute, capacity_addition, commissioning_event, order_book_absolute, price_increase_pct, volume_value_gap_pct, revenue_absolute
Reason: Prevents free-text metric sprawl, allows programmatic comparison in V2. other_ prefix lets vocabulary grow organically from real data.