# Single-Pass Frontier Model Experiment — Results

**Generated:** 2026-06-19 12:35  
**Spec:** `specs/SPEC_EXPERIMENT_SINGLEPASS_FRONTIER.md`  
**Prompt:** `prompts/prompt_v8.txt` (all arms)  
**Temperature:** 0 (all arms)  
**Runs per arm per company:** 2  

## Arms

| Arm | Model | Temperature | Description |
|-----|-------|-------------|-------------|
| arm0_gpt4o | `gpt-4o` | 0 | Control — gpt-4o + prompt_v8 (reproduce documented baseline) |
| arm1_gpt55 | `gpt-5.5` | default (1) | Primary — gpt-5.5 + prompt_v8 (isolate model variable) |

## Target Companies

| Company | Quarter | GT Items |
|---------|---------|----------|
| Asian Paints | Q4 FY26 | 4 |
| Fineotex Chemical | Q4 FY26 | 2 |
| Sandhar Technologies | Q4 FY26 | 8 |
| Mold-Tek Packaging | Q4 FY26 | 10 |

## Decision Thresholds (from spec §9)

| Threshold | Value |
|-----------|-------|
| Recall (win) | ≥ 70% |
| Precision (win) | ≥ 70–80% |
| Mold-Tek truncation | must NOT truncate |

---

## Summary Scorecard

### arm0_gpt4o — `gpt-4o`

| Company | Run | GT | Extracted | TP | Recall | Precision | Tokens Out | Truncated? |
|---------|-----|----|-----------|----|--------|-----------|------------|------------|
| Asian Paints | 1 | 4 | 2 | 1 | 25% | 50% | 204 | no |
| Asian Paints | 2 | 4 | 2 | 1 | 25% | 50% | 204 | no |
| Fineotex Chemical | 1 | 2 | 5 | 1 | 50% | 20% | 867 | no |
| Fineotex Chemical | 2 | 2 | 8 | 1 | 50% | 12% | 818 | no |
| Sandhar Technologies | 1 | 8 | 4 | 1 | 12% | 25% | 420 | no |
| Sandhar Technologies | 2 | 8 | 4 | 1 | 12% | 25% | 421 | no |
| Mold-Tek Packaging | 1 | 10 | 7 | 2 | 20% | 29% | 1636 | no |
| Mold-Tek Packaging | 2 | 10 | 4 | 1 | 10% | 25% | 667 | no |

### arm1_gpt55 — `gpt-5.5`

| Company | Run | GT | Extracted | TP | Recall | Precision | Tokens Out | Truncated? |
|---------|-----|----|-----------|----|--------|-----------|------------|------------|
| Asian Paints | 1 | 4 | 4 | 3 | 75% | 75% | 3279 | no |
| Asian Paints | 2 | 4 | 4 | 3 | 75% | 75% | 5389 | no |
| Fineotex Chemical | 1 | 2 | 2 | 1 | 50% | 50% | 5085 | no |
| Fineotex Chemical | 2 | 2 | 2 | 1 | 50% | 50% | 2999 | no |
| Sandhar Technologies | 1 | 8 | 7 | 2 | 25% | 29% | 7044 | no |
| Sandhar Technologies | 2 | 8 | 8 | 2 | 25% | 25% | 9578 | no |
| Mold-Tek Packaging | 1 | 10 | 17 | 8 | 80% | 47% | 12339 | no |
| Mold-Tek Packaging | 2 | 10 | 20 | 6 | 60% | 30% | 13866 | no |

---

## Oscillation Check (run-to-run delta at temp=0)

| Arm | Company | Run 1 items | Run 2 items | Delta |
|-----|---------|-------------|-------------|-------|
| arm0_gpt4o | Asian Paints | 2 | 2 | 0 |
| arm0_gpt4o | Fineotex Chemical | 5 | 8 | 3 ⚠️ |
| arm0_gpt4o | Sandhar Technologies | 4 | 4 | 0 |
| arm0_gpt4o | Mold-Tek Packaging | 7 | 4 | 3 ⚠️ |
| arm1_gpt55 | Asian Paints | 4 | 4 | 0 |
| arm1_gpt55 | Fineotex Chemical | 2 | 2 | 0 |
| arm1_gpt55 | Sandhar Technologies | 7 | 8 | 1 ⚠️ |
| arm1_gpt55 | Mold-Tek Packaging | 17 | 20 | 3 ⚠️ |

---

## Aggregate Metrics (average across all companies, run 1)

| Arm | Avg Recall | Avg Precision | Companies Clearing ≥70% Recall | Companies Clearing ≥70% Precision |
|-----|------------|---------------|-------------------------------|----------------------------------|
| arm0_gpt4o | 26.9% | 30.9% | 0/4 | 0/4 |
| arm1_gpt55 | 57.5% | 50.2% | 2/4 | 1/4 |

---

## Detailed Extraction Results

### Asian Paints — Q4 FY26

#### arm0_gpt4o | Run 1

**Transcript chars:** 51,972  
**LLM output tokens:** 204  
**Items extracted:** 2  
**True positives:** 1 / 4  
**Recall:** 25.0%  
**Precision:** 50.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | commissioning_event | null | H1 FY27 | ✓ |
| 2 | volume_growth_pct | 8-10 | FY27 | ✗ |
| 3 | ebitda_margin_pct | 18-20 | FY27 | ✗ |
| 4 | volume_value_gap_pct | 3-4 | FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 2 | price_increase_pct | 10.5-11 | FY27 | When I spoke about pricing, despite very strong inflation, where we have already taken close to about 10.5-11% price inc… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | commissioning_event | null | null | H1 FY27 | no | Today, worldwide, there are very limited players who are making VAM-VAE, and for us, it is a signature project and we ex… |
| 2 | price_increase_pct | 10.5-11 | % | FY27 | no | When I spoke about pricing, despite very strong inflation, where we have already taken close to about 10.5-11% price inc… |

#### arm0_gpt4o | Run 2

**Transcript chars:** 51,972  
**LLM output tokens:** 204  
**Items extracted:** 2  
**True positives:** 1 / 4  
**Recall:** 25.0%  
**Precision:** 50.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | commissioning_event | null | H1 FY27 | ✓ |
| 2 | volume_growth_pct | 8-10 | FY27 | ✗ |
| 3 | ebitda_margin_pct | 18-20 | FY27 | ✗ |
| 4 | volume_value_gap_pct | 3-4 | FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 2 | price_increase_pct | 10.5-11 | FY27 | When I spoke about pricing, despite very strong inflation, where we have already taken close to about 10.5-11% price inc… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | commissioning_event | null | null | H1 FY27 | no | Today, worldwide, there are very limited players who are making VAM-VAE, and for us, it is a signature project and we ex… |
| 2 | price_increase_pct | 10.5-11 | % | FY27 | no | When I spoke about pricing, despite very strong inflation, where we have already taken close to about 10.5-11% price inc… |

#### arm1_gpt55 | Run 1

**Transcript chars:** 51,972  
**LLM output tokens:** 3279  
**Items extracted:** 4  
**True positives:** 3 / 4  
**Recall:** 75.0%  
**Precision:** 75.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | commissioning_event | null | H1 FY27 | ✓ |
| 2 | volume_growth_pct | 8-10 | FY27 | ✓ |
| 3 | ebitda_margin_pct | 18-20 | FY27 | ✓ |
| 4 | volume_value_gap_pct | 3-4 | FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 4 | volume_value_gap_pct | 3-4 | next few quarters | Pratik Gothi: Got it. And a related question is the volume value gap. The volume value gap of 3 -4%. Did you mention tha… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | commissioning_event | null | null | H1 FY27 | no | The area of VAM-VAE, which is our backward integration project, is something which we are looking forward to strongly. T… |
| 2 | ebitda_margin_pct | 18-20 | % | FY27 | yes | Amit Sachdeva: Just to understand clearly that in doing so, you would like to maintain your margin guidance, which has a… |
| 3 | volume_growth_pct | 8-10 | % | FY27 | no | Amit Sachdeva: Just to understand clearly that in doing so, you would like to maintain your margin guidance, which has a… |
| 4 | volume_value_gap_pct | 3-4 | % | next few quarters | no | Pratik Gothi: Got it. And a related question is the volume value gap. The volume value gap of 3 -4%. Did you mention tha… |

#### arm1_gpt55 | Run 2

**Transcript chars:** 51,972  
**LLM output tokens:** 5389  
**Items extracted:** 4  
**True positives:** 3 / 4  
**Recall:** 75.0%  
**Precision:** 75.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | commissioning_event | null | H1 FY27 | ✓ |
| 2 | volume_growth_pct | 8-10 | FY27 | ✓ |
| 3 | ebitda_margin_pct | 18-20 | FY27 | ✓ |
| 4 | volume_value_gap_pct | 3-4 | FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 4 | volume_value_gap_pct | 3-4 | next few quarters | Pratik Gothi: Got it. And a related question is the volume value gap. The volume value gap of 3 -4%. Did you mention tha… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | commissioning_event | null | null | H1 FY27 | no | The area of VAM-VAE, which is our backward integration project, is something which we are looking forward to strongly. T… |
| 2 | ebitda_margin_pct | 18-20 | % | FY27 | yes | Amit Sachdeva: Just to understand clearly that in doing so, you would like to maintain your margin guidance, which has a… |
| 3 | volume_growth_pct | 8-10 | % | FY27 | no | Amit Sachdeva: Just to understand clearly that in doing so, you would like to maintain your margin guidance, which has a… |
| 4 | volume_value_gap_pct | 3-4 | % | next few quarters | no | Pratik Gothi: Got it. And a related question is the volume value gap. The volume value gap of 3 -4%. Did you mention tha… |

### Fineotex Chemical — Q4 FY26

#### arm0_gpt4o | Run 1

**Transcript chars:** 56,744  
**LLM output tokens:** 867  
**Items extracted:** 5  
**True positives:** 1 / 2  
**Recall:** 50.0%  
**Precision:** 20.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | ebitda_margin_pct | 18-20 | FY27 | ✓ |
| 2 | other_revenue_usd_subsidiary | 200 | FY28 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 1 | capacity_addition | null | FY27 | In the line with increasing demand outlook and strong customer traction in the US oilfield chemicals market, we are now … |
| 2 | revenue_absolute | 200 | FY28 | Sanjay Tibrewala: Yes. Thank you so much for this question. This is something, which we have been answering very often. … |
| 3 | capacity_addition | null | FY28 | Sanjay Tibrewala: So as such, already, we have been increasing the capacities from December onwards. This month also, we… |
| 5 | capex_absolute | 7 | FY27 | Sanjay Tibrewala: So there has been a lot of capex being done. In fact, after the acquisition also, the Fineotex has alr… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | capacity_addition | null | null | FY27 | no | In the line with increasing demand outlook and strong customer traction in the US oilfield chemicals market, we are now … |
| 2 | revenue_absolute | 200 | million | FY28 | no | Sanjay Tibrewala: Yes. Thank you so much for this question. This is something, which we have been answering very often. … |
| 3 | capacity_addition | null | null | FY28 | no | Sanjay Tibrewala: So as such, already, we have been increasing the capacities from December onwards. This month also, we… |
| 4 | ebitda_margin_pct | 18-20 | % | FY27 | yes | Sanjay Tibrewala: So, all along, Fineotex has been proven for operational efficiencies in the last 15 years of being lis… |
| 5 | capex_absolute | 7 | million | FY27 | no | Sanjay Tibrewala: So there has been a lot of capex being done. In fact, after the acquisition also, the Fineotex has alr… |

#### arm0_gpt4o | Run 2

**Transcript chars:** 56,744  
**LLM output tokens:** 818  
**Items extracted:** 8  
**True positives:** 1 / 2  
**Recall:** 50.0%  
**Precision:** 12.5%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | ebitda_margin_pct | 18-20 | FY27 | ✓ |
| 2 | other_revenue_usd_subsidiary | 200 | FY28 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 1 | capacity_addition | null | FY27 | In the line with increasing demand outlook and strong customer traction in the US oilfield chemicals market, we are now … |
| 2 | pat_absolute | 44 | Q4 FY26 | Our profit after tax for the quarter grew by 118% to INR44 crores, compared to INR20 crores in quarter four financial ye… |
| 3 | other_expansion_strategy | null | FY27 | Going forward, the company remains actively focused on expanding its global specialty chemical portfolio through a combi… |
| 4 | revenue_absolute | 200 | FY28 | So yes, already, if you see the run rate at what we are in quarter four, if you annualize it, it's already touching almo… |
| 5 | ebitda_margin_pct | 15 | FY27 | So going forward, I think comfortably, we should be at EBITDA of 15% more or less.… |
| 6 | other_industry_trend | null | FY27 | So, I would not be able to share any forward-looking statements here. But in general, this is what is the trend, and we … |
| 8 | capex_absolute | 7 | FY27 | So there has been a lot of capex being done. In fact, after the acquisition also, the Fineotex has already done a capex … |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | capacity_addition | null | null | FY27 | no | In the line with increasing demand outlook and strong customer traction in the US oilfield chemicals market, we are now … |
| 2 | pat_absolute | 44 | crore | Q4 FY26 | yes | Our profit after tax for the quarter grew by 118% to INR44 crores, compared to INR20 crores in quarter four financial ye… |
| 3 | other_expansion_strategy | null | null | FY27 | no | Going forward, the company remains actively focused on expanding its global specialty chemical portfolio through a combi… |
| 4 | revenue_absolute | 200 | million | FY28 | no | So yes, already, if you see the run rate at what we are in quarter four, if you annualize it, it's already touching almo… |
| 5 | ebitda_margin_pct | 15 | % | FY27 | yes | So going forward, I think comfortably, we should be at EBITDA of 15% more or less.… |
| 6 | other_industry_trend | null | null | FY27 | no | So, I would not be able to share any forward-looking statements here. But in general, this is what is the trend, and we … |
| 7 | ebitda_margin_pct | 18-20 | % | FY27 | yes | On a blended level, we would always look at getting to an easy EBITDA of around 18% to 20%, and that's what we are headi… |
| 8 | capex_absolute | 7 | million | FY27 | no | So there has been a lot of capex being done. In fact, after the acquisition also, the Fineotex has already done a capex … |

#### arm1_gpt55 | Run 1

**Transcript chars:** 56,744  
**LLM output tokens:** 5085  
**Items extracted:** 2  
**True positives:** 1 / 2  
**Recall:** 50.0%  
**Precision:** 50.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | ebitda_margin_pct | 18-20 | FY27 | ✓ |
| 2 | other_revenue_usd_subsidiary | 200 | FY28 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 1 | ebitda_margin_pct | 15 | going forward | Amit Mehendale: Thank you, and congrats on great set of numbers. My first question is on our US acquisition of CCT. Are … |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | ebitda_margin_pct | 15 | % | going forward | no | Amit Mehendale: Thank you, and congrats on great set of numbers. My first question is on our US acquisition of CCT. Are … |
| 2 | ebitda_margin_pct | 18-20 | % | FY27 | yes | Vinay Nadkarni: Great. I think it's a great acquisition. Just one last question for you. When you said 18% to 20% of ble… |

#### arm1_gpt55 | Run 2

**Transcript chars:** 56,744  
**LLM output tokens:** 2999  
**Items extracted:** 2  
**True positives:** 1 / 2  
**Recall:** 50.0%  
**Precision:** 50.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | ebitda_margin_pct | 18-20 | FY27 | ✓ |
| 2 | other_revenue_usd_subsidiary | 200 | FY28 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 1 | ebitda_margin_pct | 15 | going forward | Amit Mehendale: Thank you, and congrats on great set of numbers. My first question is on our US acquisition of CCT. Are … |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | ebitda_margin_pct | 15 | % | going forward | no | Amit Mehendale: Thank you, and congrats on great set of numbers. My first question is on our US acquisition of CCT. Are … |
| 2 | ebitda_margin_pct | 18-20 | % | FY27 | yes | Vinay Nadkarni: Great. I think it's a great acquisition. Just one last question for you. When you said 18% to 20% of ble… |

### Sandhar Technologies — Q4 FY26

#### arm0_gpt4o | Run 1

**Transcript chars:** 55,453  
**LLM output tokens:** 420  
**Items extracted:** 4  
**True positives:** 1 / 8  
**Recall:** 12.5%  
**Precision:** 25.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | revenue_growth_pct | 15 | FY27 | ✓ |
| 2 | other_ebitda_margin_delta | 0.25 | FY27 | ✗ |
| 3 | capex_absolute | 275-310 | FY27 | ✗ |
| 4 | other_ev_revenue_absolute | 40 | FY27 | ✗ |
| 5 | other_new_projects_revenue_absolute | 700-750 | FY27 | ✗ |
| 6 | other_ebt_breakeven | null | Q2 FY27 | ✗ |
| 7 | other_ebt_breakeven | null | Q3 FY27 | ✗ |
| 8 | other_ebt_breakeven | null | Q2 FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 2 | revenue_absolute | 40 | FY27 | We are expecting now to double this revenue in the current financial year. During Financial Year 2026, 41,000 battery ch… |
| 3 | commissioning_event | null | H1 FY27 | We expect to commission Phase 1 by end of H1 FY27.… |
| 4 | revenue_absolute | 750 | FY27 | We expect to do so. 2.5% you can say INR 700 crores, INR 750 crores something. I mean, it is a range sir has given. 2.5x… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | revenue_growth_pct | 15 | % | FY27 | yes | I am happy to give a guidance of over a 15% growth in the overall revenue. This is without taking a price retrigger, whi… |
| 2 | revenue_absolute | 40 | crore | FY27 | no | We are expecting now to double this revenue in the current financial year. During Financial Year 2026, 41,000 battery ch… |
| 3 | commissioning_event | null | null | H1 FY27 | no | We expect to commission Phase 1 by end of H1 FY27.… |
| 4 | revenue_absolute | 750 | crore | FY27 | no | We expect to do so. 2.5% you can say INR 700 crores, INR 750 crores something. I mean, it is a range sir has given. 2.5x… |

#### arm0_gpt4o | Run 2

**Transcript chars:** 55,453  
**LLM output tokens:** 421  
**Items extracted:** 4  
**True positives:** 1 / 8  
**Recall:** 12.5%  
**Precision:** 25.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | revenue_growth_pct | 15 | FY27 | ✓ |
| 2 | other_ebitda_margin_delta | 0.25 | FY27 | ✗ |
| 3 | capex_absolute | 275-310 | FY27 | ✗ |
| 4 | other_ev_revenue_absolute | 40 | FY27 | ✗ |
| 5 | other_new_projects_revenue_absolute | 700-750 | FY27 | ✗ |
| 6 | other_ebt_breakeven | null | Q2 FY27 | ✗ |
| 7 | other_ebt_breakeven | null | Q3 FY27 | ✗ |
| 8 | other_ebt_breakeven | null | Q2 FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 2 | revenue_absolute | null | FY27 | We are expecting now to double this revenue in the current financial year. During Financial Year 2026, 41,000 battery ch… |
| 3 | commissioning_event | null | H1 FY27 | We expect to commission Phase 1 by end of H1 FY27.… |
| 4 | revenue_absolute | 700-750 | FY27 | We expect to do so. 2.5% you can say INR 700 crores, INR 750 crores something. I mean, it is a range sir has given. 2.5x… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | revenue_growth_pct | 15 | % | FY27 | yes | I am happy to give a guidance of over a 15% growth in the overall revenue. This is without taking a price retrigger, whi… |
| 2 | revenue_absolute | null | null | FY27 | no | We are expecting now to double this revenue in the current financial year. During Financial Year 2026, 41,000 battery ch… |
| 3 | commissioning_event | null | null | H1 FY27 | no | We expect to commission Phase 1 by end of H1 FY27.… |
| 4 | revenue_absolute | 700-750 | crore | FY27 | no | We expect to do so. 2.5% you can say INR 700 crores, INR 750 crores something. I mean, it is a range sir has given. 2.5x… |

#### arm1_gpt55 | Run 1

**Transcript chars:** 55,453  
**LLM output tokens:** 7044  
**Items extracted:** 7  
**True positives:** 2 / 8  
**Recall:** 25.0%  
**Precision:** 28.6%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | revenue_growth_pct | 15 | FY27 | ✓ |
| 2 | other_ebitda_margin_delta | 0.25 | FY27 | ✗ |
| 3 | capex_absolute | 275-310 | FY27 | ✓ |
| 4 | other_ev_revenue_absolute | 40 | FY27 | ✗ |
| 5 | other_new_projects_revenue_absolute | 700-750 | FY27 | ✗ |
| 6 | other_ebt_breakeven | null | Q2 FY27 | ✗ |
| 7 | other_ebt_breakeven | null | Q3 FY27 | ✗ |
| 8 | other_ebt_breakeven | null | Q2 FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 2 | revenue_absolute | 5500 | FY27 | And in the earlier calls, our Chairman has mentioned that we keep our CapEx limited to 5% to 7% of our revenues. So, tak… |
| 4 | other_ebitda_margin_expansion_pct | 0.1-0.4 | FY27 | And like as we discussed and we discussed in earlier calls also, every year we want to grow and improve our EBITDA level… |
| 5 | other_cwip_capitalization_absolute | 115 | Q2 FY27 | In terms of Sanaswadi also, the lead date is end of Quarter 2. So, mostly the INR 115 crore, this is something revolving… |
| 6 | revenue_absolute | 700-750 | FY27 | Ashutosh Tiwari: So, this INR 468 crore revenue that you did in this year can go to INR 800 crore plus in FY '27? Yashpa… |
| 7 | other_debt_repayment_absolute | 103 | FY27 | This year we have a repayment commitment of around close to INR 103 crores with various banks. So, term debt will start … |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | revenue_growth_pct | 15-16 | % | FY27 | yes | We will, of course, have to wait and see, and therefore that is the reason why I am giving you a conservative estimate o… |
| 2 | revenue_absolute | 5500 | crore | FY27 | yes | And in the earlier calls, our Chairman has mentioned that we keep our CapEx limited to 5% to 7% of our revenues. So, tak… |
| 3 | capex_absolute | 275-310 | crore | FY27 | no | And in the earlier calls, our Chairman has mentioned that we keep our CapEx limited to 5% to 7% of our revenues. So, tak… |
| 4 | other_ebitda_margin_expansion_pct | 0.1-0.4 | % | FY27 | no | And like as we discussed and we discussed in earlier calls also, every year we want to grow and improve our EBITDA level… |
| 5 | other_cwip_capitalization_absolute | 115 | crore | Q2 FY27 | no | In terms of Sanaswadi also, the lead date is end of Quarter 2. So, mostly the INR 115 crore, this is something revolving… |
| 6 | revenue_absolute | 700-750 | crore | FY27 | no | Ashutosh Tiwari: So, this INR 468 crore revenue that you did in this year can go to INR 800 crore plus in FY '27? Yashpa… |
| 7 | other_debt_repayment_absolute | 103 | crore | FY27 | no | This year we have a repayment commitment of around close to INR 103 crores with various banks. So, term debt will start … |

#### arm1_gpt55 | Run 2

**Transcript chars:** 55,453  
**LLM output tokens:** 9578  
**Items extracted:** 8  
**True positives:** 2 / 8  
**Recall:** 25.0%  
**Precision:** 25.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | revenue_growth_pct | 15 | FY27 | ✓ |
| 2 | other_ebitda_margin_delta | 0.25 | FY27 | ✗ |
| 3 | capex_absolute | 275-310 | FY27 | ✓ |
| 4 | other_ev_revenue_absolute | 40 | FY27 | ✗ |
| 5 | other_new_projects_revenue_absolute | 700-750 | FY27 | ✗ |
| 6 | other_ebt_breakeven | null | Q2 FY27 | ✗ |
| 7 | other_ebt_breakeven | null | Q3 FY27 | ✗ |
| 8 | other_ebt_breakeven | null | Q2 FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 2 | revenue_absolute | 5500 | FY27 | And in the earlier calls, our Chairman has mentioned that we keep our CapEx limited to 5% to 7% of our revenues. So, tak… |
| 4 | ebitda_margin_pct | 0.1-0.4 | FY27 | And like as we discussed and we discussed in earlier calls also, every year we want to grow and improve our EBITDA level… |
| 5 | revenue_absolute | 700-750 | FY27 | Ashutosh Tiwari: Yes. I think it was mentioned by sir that from investment of INR 342 crores on new projects, you can do… |
| 6 | commissioning_event | null | Q2 FY27 | So, like as we mentioned in our earlier participants' question, we expect our Sundaram-Clayton project to get shifted by… |
| 7 | commissioning_event | null | Q2 FY27 | Secondly, the Khed City project will also be capitalized by end of Quarter 2. So, major portion will be done away in ter… |
| 8 | other_debt_repayment_absolute | 103 | FY27 | So, I mean, the term loans are INR 384 crores, which will be automatically paid with the due schedules. This year we hav… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | revenue_growth_pct | 15-16 | % | FY27 | yes | Therefore that is the reason why I am giving you a conservative estimate of 15% plus, 15% to 16% plus of revenue growth … |
| 2 | revenue_absolute | 5500 | crore | FY27 | yes | And in the earlier calls, our Chairman has mentioned that we keep our CapEx limited to 5% to 7% of our revenues. So, tak… |
| 3 | capex_absolute | 275-310 | crore | FY27 | no | And in the earlier calls, our Chairman has mentioned that we keep our CapEx limited to 5% to 7% of our revenues. So, tak… |
| 4 | ebitda_margin_pct | 0.1-0.4 | % | FY27 | no | And like as we discussed and we discussed in earlier calls also, every year we want to grow and improve our EBITDA level… |
| 5 | revenue_absolute | 700-750 | crore | FY27 | no | Ashutosh Tiwari: Yes. I think it was mentioned by sir that from investment of INR 342 crores on new projects, you can do… |
| 6 | commissioning_event | null | null | Q2 FY27 | no | So, like as we mentioned in our earlier participants' question, we expect our Sundaram-Clayton project to get shifted by… |
| 7 | commissioning_event | null | null | Q2 FY27 | no | Secondly, the Khed City project will also be capitalized by end of Quarter 2. So, major portion will be done away in ter… |
| 8 | other_debt_repayment_absolute | 103 | crore | FY27 | no | So, I mean, the term loans are INR 384 crores, which will be automatically paid with the due schedules. This year we hav… |

### Mold-Tek Packaging — Q4 FY26

#### arm0_gpt4o | Run 1

**Transcript chars:** 51,586  
**LLM output tokens:** 1636  
**Items extracted:** 7  
**True positives:** 2 / 10  
**Recall:** 20.0%  
**Precision:** 28.6%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | other_pharma_revenue_absolute | 50-55 | FY27 | ✗ |
| 2 | capex_absolute | 80-85 | FY27 | ✓ |
| 3 | capacity_addition | 67000-68000 | FY27 | ✗ |
| 4 | revenue_absolute | 1000 | FY27 | ✗ |
| 5 | revenue_growth_pct | 13-15 | FY27 | ✓ |
| 6 | volume_growth_pct | 10-13 | FY27 | ✗ |
| 7 | other_ebitda_per_kg | 42-43 | FY27 | ✗ |
| 8 | other_ebitda_absolute | 210 | FY27 | ✗ |
| 9 | other_roce_pct | 13.5-14 | FY27 | ✗ |
| 10 | other_food_fmcg_revenue_growth_pct | 20 | FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 1 | revenue_absolute | 50-55 | FY27 | J. Lakshmana Rao: No, INR55 crores is our target for the next financial year '26-'27. We hit almost INR34.4 crores for t… |
| 3 | capacity_addition | 67-70 | FY27 | J. Lakshmana Rao: Yes, I think we should be close to 68, 67 because capacity-wise in Pharma, the number of tons won't be… |
| 4 | capex_absolute | 80-85 | FY27 | J. Lakshmana Rao: Yes. We are planning it will be in the region of around INR80 crores to INR85 crores overall. It could… |
| 5 | commissioning_event | null | FY27 | J. Lakshmana Rao: Yes, '27. '27, before end of the financial year, I think we may start the new plant because of the del… |
| 7 | ebitda_margin_pct | 42-43 | FY27 | J. Lakshmana Rao: FY '27, as I expected, we are aiming at, at least 42 to 43, 42.5 could be a good estimate for the full… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | revenue_absolute | 50-55 | crore | FY27 | yes | J. Lakshmana Rao: No, INR55 crores is our target for the next financial year '26-'27. We hit almost INR34.4 crores for t… |
| 2 | capex_absolute | 80-85 | crore | FY27 | no | J. Lakshmana Rao: Yes, capacity is 63,000 tons and utilization is hardly 43,000. So we have a long way to go to make use… |
| 3 | capacity_addition | 67-70 | tons | FY27 | no | J. Lakshmana Rao: Yes, I think we should be close to 68, 67 because capacity-wise in Pharma, the number of tons won't be… |
| 4 | capex_absolute | 80-85 | crore | FY27 | no | J. Lakshmana Rao: Yes. We are planning it will be in the region of around INR80 crores to INR85 crores overall. It could… |
| 5 | commissioning_event | null | null | FY27 | no | J. Lakshmana Rao: Yes, '27. '27, before end of the financial year, I think we may start the new plant because of the del… |
| 6 | revenue_growth_pct | 13-15 | % | FY27 | yes | J. Lakshmana Rao: See, I can see 2 ways of looking at in future because volume growth comes from mere kgs, then Pharma, … |
| 7 | ebitda_margin_pct | 42-43 | % | FY27 | yes | J. Lakshmana Rao: FY '27, as I expected, we are aiming at, at least 42 to 43, 42.5 could be a good estimate for the full… |

#### arm0_gpt4o | Run 2

**Transcript chars:** 51,586  
**LLM output tokens:** 667  
**Items extracted:** 4  
**True positives:** 1 / 10  
**Recall:** 10.0%  
**Precision:** 25.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | other_pharma_revenue_absolute | 50-55 | FY27 | ✗ |
| 2 | capex_absolute | 80-85 | FY27 | ✓ |
| 3 | capacity_addition | 67000-68000 | FY27 | ✗ |
| 4 | revenue_absolute | 1000 | FY27 | ✗ |
| 5 | revenue_growth_pct | 13-15 | FY27 | ✗ |
| 6 | volume_growth_pct | 10-13 | FY27 | ✗ |
| 7 | other_ebitda_per_kg | 42-43 | FY27 | ✗ |
| 8 | other_ebitda_absolute | 210 | FY27 | ✗ |
| 9 | other_roce_pct | 13.5-14 | FY27 | ✗ |
| 10 | other_food_fmcg_revenue_growth_pct | 20 | FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 1 | capacity_addition | 67,000-70,000 | FY27 | Chirag: And that will lead to almost like 70,000 MTPA capacity by the end of FY '27. Is my assumption correct? J. Lakshm… |
| 2 | revenue_absolute | 50-55 | FY27 | J. Lakshmana Rao: No, INR55 crores is our target for the next financial year '26-'27. We hit almost INR34.4 crores for t… |
| 4 | capacity_addition | 63,000 | FY27 | J. Lakshmana Rao: Yes, capacity is 63,000 tons and utilization is hardly 43,000. So we have a long way to go to make use… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | capacity_addition | 67,000-70,000 | tons | FY27 | no | Chirag: And that will lead to almost like 70,000 MTPA capacity by the end of FY '27. Is my assumption correct? J. Lakshm… |
| 2 | revenue_absolute | 50-55 | crore | FY27 | yes | J. Lakshmana Rao: No, INR55 crores is our target for the next financial year '26-'27. We hit almost INR34.4 crores for t… |
| 3 | capex_absolute | 80-85 | crore | FY27 | no | J. Lakshmana Rao: Yes. We are planning it will be in the region of around INR80 crores to INR85 crores overall. It could… |
| 4 | capacity_addition | 63,000 | tons | FY27 | no | J. Lakshmana Rao: Yes, capacity is 63,000 tons and utilization is hardly 43,000. So we have a long way to go to make use… |

#### arm1_gpt55 | Run 1

**Transcript chars:** 51,586  
**LLM output tokens:** 12339  
**Items extracted:** 17  
**True positives:** 8 / 10  
**Recall:** 80.0%  
**Precision:** 47.1%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | other_pharma_revenue_absolute | 50-55 | FY27 | ✗ |
| 2 | capex_absolute | 80-85 | FY27 | ✓ |
| 3 | capacity_addition | 67000-68000 | FY27 | ✓ |
| 4 | revenue_absolute | 1000 | FY27 | ✓ |
| 5 | revenue_growth_pct | 13-15 | FY27 | ✓ |
| 6 | volume_growth_pct | 10-13 | FY27 | ✓ |
| 7 | other_ebitda_per_kg | 42-43 | FY27 | ✓ |
| 8 | other_ebitda_absolute | 210 | FY27 | ✓ |
| 9 | other_roce_pct | 13.5-14 | FY27 | ✓ |
| 10 | other_food_fmcg_revenue_growth_pct | 20 | FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 1 | revenue_absolute | 50-55 | FY27 | Samarth Jain: So you gave us the guidance of INR55 crores to INR60 crores in Pharma for FY '27. So is this including thi… |
| 2 | revenue_growth_pct | 50 | FY27 | Samarth Jain: So you gave us the guidance of INR55 crores to INR60 crores in Pharma for FY '27. So is this including thi… |
| 3 | capacity_addition | 2500 | FY27 | Richa: And sir, capacity-wise, how much additional capacity are we targeting for Grasim and in Pharma as well because we… |
| 6 | other_gross_margin_pct | 46-47 | coming quarters | Chirag: And sir, will it be fair to assume, though you have mentioned in your press release that all the cost increase w… |
| 7 | commissioning_event | null | FY27 | Sandeep Modi: Yes. Sir, there was a Pharma packaging we are trying to start some new this thing? J. Lakshmana Rao: Yes, … |
| 10 | revenue_growth_pct | 20 | FY27 | If you combine the thick wall also, food is around 18%. But this 15.4%, I'm sure it will be looking at least 20% growth … |
| 11 | capacity_addition | 4 | July 2026 | See, in ABG plant, that is mainly meant for Paints and Qpack, we are hardly reaching around 60% capacity utilization in … |
| 13 | other_capacity_utilization_pct | 70 | FY27 | And ABG plants, even today are hardly around 60% capacity utilization. And I hope next year, they will be reaching 70% p… |
| 15 | revenue_absolute | 35-40 | FY27 | Definitely, I'm very confident that more and more number of clients will be added in '26-27 than last year, basically, b… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | revenue_absolute | 50-55 | crore | FY27 | no | Samarth Jain: So you gave us the guidance of INR55 crores to INR60 crores in Pharma for FY '27. So is this including thi… |
| 2 | revenue_growth_pct | 50 | % | FY27 | no | Samarth Jain: So you gave us the guidance of INR55 crores to INR60 crores in Pharma for FY '27. So is this including thi… |
| 3 | capacity_addition | 2500 | tons | FY27 | no | Richa: And sir, capacity-wise, how much additional capacity are we targeting for Grasim and in Pharma as well because we… |
| 4 | capex_absolute | 80-85 | crore | FY27 | no | So these 3 areas, but we have a sharp lesser budget of capital investment in this current financial year, which was INR1… |
| 5 | capacity_addition | 67000-68000 | tons | FY27 | no | Chirag: And that will lead to almost like 70,000 MTPA capacity by the end of FY '27. Is my assumption correct? J. Lakshm… |
| 6 | other_gross_margin_pct | 46-47 | % | coming quarters | no | Chirag: And sir, will it be fair to assume, though you have mentioned in your press release that all the cost increase w… |
| 7 | commissioning_event | null | null | FY27 | no | Sandeep Modi: Yes. Sir, there was a Pharma packaging we are trying to start some new this thing? J. Lakshmana Rao: Yes, … |
| 8 | revenue_growth_pct | 13-15 | % | FY27 | yes | Dipak Saha: And sir, FY '27 full year point of view, how should we understand the growth numbers? And if you can broadly… |
| 9 | revenue_absolute | 1000 | crore | FY27 | yes | Dipak Saha: And sir, FY '27 full year point of view, how should we understand the growth numbers? And if you can broadly… |
| 10 | revenue_growth_pct | 20 | % | FY27 | no | If you combine the thick wall also, food is around 18%. But this 15.4%, I'm sure it will be looking at least 20% growth … |
| 11 | capacity_addition | 4 | machines | July 2026 | no | See, in ABG plant, that is mainly meant for Paints and Qpack, we are hardly reaching around 60% capacity utilization in … |
| 12 | other_ebitda_per_kg | 42-43 | INR/kg | FY27 | no | Akhil Parekh: Many congratulations, sir, on a very good set of numbers. My first question on the EBITDA per kg, right? W… |
| 13 | other_capacity_utilization_pct | 70 | % | FY27 | no | And ABG plants, even today are hardly around 60% capacity utilization. And I hope next year, they will be reaching 70% p… |
| 14 | volume_growth_pct | 10-13 | % | FY27 | no | Akhil Parekh: Sir, and just reconfirm your growth guidance for '27, you suggested 10% to 15% volume growth and 13% to 15… |
| 15 | revenue_absolute | 35-40 | crore | FY27 | no | Definitely, I'm very confident that more and more number of clients will be added in '26-27 than last year, basically, b… |
| 16 | other_roce_pct | 13.5-14 | % | FY27 | no | Coming back to ROCE, yes, the ROCE has leaped by about 14% from 10.2% to 12.4% and probably it may hit around 13.5% to 1… |
| 17 | other_ebitda_absolute | 210 | crore | FY27 | no | Shanskar: Sir, most of my questions have been answered. Just wanted to understand on the growth perspective, while you h… |

#### arm1_gpt55 | Run 2

**Transcript chars:** 51,586  
**LLM output tokens:** 13866  
**Items extracted:** 20  
**True positives:** 6 / 10  
**Recall:** 60.0%  
**Precision:** 30.0%  

**Ground-truth coverage:**

| # | metric | value | timeline | matched |
|---|--------|-------|----------|---------|
| 1 | other_pharma_revenue_absolute | 50-55 | FY27 | ✗ |
| 2 | capex_absolute | 80-85 | FY27 | ✓ |
| 3 | capacity_addition | 67000-68000 | FY27 | ✗ |
| 4 | revenue_absolute | 1000 | FY27 | ✗ |
| 5 | revenue_growth_pct | 13-15 | FY27 | ✓ |
| 6 | volume_growth_pct | 10-13 | FY27 | ✓ |
| 7 | other_ebitda_per_kg | 42-43 | FY27 | ✓ |
| 8 | other_ebitda_absolute | 210 | FY27 | ✓ |
| 9 | other_roce_pct | 13.5-14 | FY27 | ✓ |
| 10 | other_food_fmcg_revenue_growth_pct | 20 | FY27 | ✗ |

**False positives:**

| # | metric | value | timeline | passage (first 120 chars) |
|---|--------|-------|----------|---------------------------|
| 1 | revenue_absolute | 50-55 | FY27 | Samarth Jain: So you gave us the guidance of INR55 crores to INR60 crores in Pharma for FY '27. So is this including thi… |
| 2 | revenue_growth_pct | 50 | FY27 | Samarth Jain: So you gave us the guidance of INR55 crores to INR60 crores in Pharma for FY '27. So is this including thi… |
| 3 | capacity_addition | 2,500 | FY27 | Yes. Currently, Pharma is hardly about 1,500 tons, and we have to still make new investments in that segment to take it … |
| 5 | capacity_addition | 67,000-68,000 | end FY27 | Chirag: And that will lead to almost like 70,000 MTPA capacity by the end of FY '27. Is my assumption correct? J. Lakshm… |
| 6 | other_gross_margin_pct | 46-47 | coming quarters | Chirag: And sir, will it be fair to assume, though you have mentioned in your press release that all the cost increase w… |
| 7 | commissioning_event | null | before end FY27 | Sandeep Modi: Yes. Sir, there was a Pharma packaging we are trying to start some new this thing? J. Lakshmana Rao: Yes, … |
| 9 | revenue_absolute | 1,000 | FY27 | So in terms of just volume, it might look like 10% to 15%, anywhere between 10% to 15% of growth is possible. But in ter… |
| 10 | revenue_growth_pct | 20 | FY27 | If you combine the thick wall also, food is around 18%. But this 15.4%, I'm sure it will be looking at least 20% growth … |
| 11 | capacity_addition | 4 | July 2026 | See, in ABG plant, that is mainly meant for Paints and Qpack, we are hardly reaching around 60% capacity utilization in … |
| 12 | other_capacity_utilization_pct | 40-50 | FY27 | So we are getting ready for the festive season that starts sometime in July. So I think next year, there will be a good … |
| 14 | other_capacity_utilization_pct | 70 | FY27 | And ABG plants, even today are hardly around 60% capacity utilization. And I hope next year, they will be reaching 70% p… |
| 16 | revenue_absolute | 35-40 | FY27 | So going forward, that itself is indication that INR35 crores to INR40 crores of new addition in business can come from … |
| 19 | other_ebitda_growth_pct | 20 | FY27 | Shanskar: Sir, most of my questions have been answered. Just wanted to understand on the growth perspective, while you h… |
| 20 | pat_growth_pct | 20 | FY27 | Shanskar: Sir, most of my questions have been answered. Just wanted to understand on the growth perspective, while you h… |

**All extracted items:**

| # | metric | value | unit | timeline | scorable | passage (first 120 chars) |
|---|--------|-------|------|----------|----------|---------------------------|
| 1 | revenue_absolute | 50-55 | crore | FY27 | no | Samarth Jain: So you gave us the guidance of INR55 crores to INR60 crores in Pharma for FY '27. So is this including thi… |
| 2 | revenue_growth_pct | 50 | % | FY27 | no | Samarth Jain: So you gave us the guidance of INR55 crores to INR60 crores in Pharma for FY '27. So is this including thi… |
| 3 | capacity_addition | 2,500 | tons | FY27 | no | Yes. Currently, Pharma is hardly about 1,500 tons, and we have to still make new investments in that segment to take it … |
| 4 | capex_absolute | 80-85 | crore | FY27 | no | So these 3 areas, but we have a sharp lesser budget of capital investment in this current financial year, which was INR1… |
| 5 | capacity_addition | 67,000-68,000 | tons | end FY27 | no | Chirag: And that will lead to almost like 70,000 MTPA capacity by the end of FY '27. Is my assumption correct? J. Lakshm… |
| 6 | other_gross_margin_pct | 46-47 | % | coming quarters | no | Chirag: And sir, will it be fair to assume, though you have mentioned in your press release that all the cost increase w… |
| 7 | commissioning_event | null | null | before end FY27 | no | Sandeep Modi: Yes. Sir, there was a Pharma packaging we are trying to start some new this thing? J. Lakshmana Rao: Yes, … |
| 8 | revenue_growth_pct | 13-15 | % | FY27 | yes | So in terms of just volume, it might look like 10% to 15%, anywhere between 10% to 15% of growth is possible. But in ter… |
| 9 | revenue_absolute | 1,000 | crore | FY27 | yes | So in terms of just volume, it might look like 10% to 15%, anywhere between 10% to 15% of growth is possible. But in ter… |
| 10 | revenue_growth_pct | 20 | % | FY27 | no | If you combine the thick wall also, food is around 18%. But this 15.4%, I'm sure it will be looking at least 20% growth … |
| 11 | capacity_addition | 4 | machines | July 2026 | no | See, in ABG plant, that is mainly meant for Paints and Qpack, we are hardly reaching around 60% capacity utilization in … |
| 12 | other_capacity_utilization_pct | 40-50 | % | FY27 | no | So we are getting ready for the festive season that starts sometime in July. So I think next year, there will be a good … |
| 13 | other_ebitda_per_kg | 42.5-43 | INR/kg | FY27 | no | FY '27, as I expected, we are aiming at, at least 42 to 43, 42.5 could be a good estimate for the full year. And then ho… |
| 14 | other_capacity_utilization_pct | 70 | % | FY27 | no | And ABG plants, even today are hardly around 60% capacity utilization. And I hope next year, they will be reaching 70% p… |
| 15 | volume_growth_pct | 10-13 | % | FY27 | no | Akhil Parekh: Sir, and just reconfirm your growth guidance for '27, you suggested 10% to 15% volume growth and 13% to 15… |
| 16 | revenue_absolute | 35-40 | crore | FY27 | no | So going forward, that itself is indication that INR35 crores to INR40 crores of new addition in business can come from … |
| 17 | other_roce_pct | 13.5-14 | % | FY27 | no | Coming back to ROCE, yes, the ROCE has leaped by about 14% from 10.2% to 12.4% and probably it may hit around 13.5% to 1… |
| 18 | other_ebitda_absolute | 210 | crore | FY27 | no | Shanskar: Sir, most of my questions have been answered. Just wanted to understand on the growth perspective, while you h… |
| 19 | other_ebitda_growth_pct | 20 | % | FY27 | no | Shanskar: Sir, most of my questions have been answered. Just wanted to understand on the growth perspective, while you h… |
| 20 | pat_growth_pct | 20 | % | FY27 | yes | Shanskar: Sir, most of my questions have been answered. Just wanted to understand on the growth perspective, while you h… |

---

## Full Extracted Passages (verbatim)

> These are the raw passage texts returned by the model — for manual pass/fail review.

### arm0_gpt4o — `gpt-4o`

#### Asian Paints

**[1] commissioning_event** | `null`  | `H1 FY27` | scorable=no  
Speaker: Amit Syngle, MD & CEO  
Page: 11  

> Today, worldwide, there are very limited players who are making VAM-VAE, and for us, it is a signature project and we expect to commission first phase in the first half of this year.

**[2] price_increase_pct** | `10.5-11` % | `FY27` | scorable=no  
Speaker: Amit Syngle, MD & CEO  
Page: 18  

> When I spoke about pricing, despite very strong inflation, where we have already taken close to about 10.5-11% price increase, and we are talking of going ahead and taking some more price increases, which are going to happen.

#### Fineotex Chemical

**[1] capacity_addition** | `null`  | `FY27` | scorable=no  
Speaker: Ms. Aarti Jhunjhunwala, Executive Director  
Page: 3  

> In the line with increasing demand outlook and strong customer traction in the US oilfield chemicals market, we are now in process of doubling the manufacturing capacity in CrudeChem. This expansion positions helps us to cater to larger contracts, onboard new customers and accelerate growth in the high-margin specialty oilfield chemicals segment.

**[2] revenue_absolute** | `200` million | `FY28` | scorable=no  
Speaker: Mr. Sanjay Tibrewala, Chief Financial Officer  
Page: 6  

> Sanjay Tibrewala: Yes. Thank you so much for this question. This is something, which we have been answering very often. So yes, already, if you see the run rate at what we are in quarter four, if you annualize it, it's already touching almost $90 million to $100 million and the kind of traction, which has been seen with the customers, the kind of technology transfers we have done, the kind of efficiencies, I am very confident that the team will be able to deliver a $200 million business in the coming times.

**[3] capacity_addition** | `null`  | `FY28` | scorable=no  
Speaker: Mr. Sanjay Tibrewala, Chief Financial Officer  
Page: 7  

> Sanjay Tibrewala: So as such, already, we have been increasing the capacities from December onwards. This month also, we are seeing a great increase in the capacity, a lot of machines have been ordered, and we are just installing it maybe in a couple of weeks, things should also be increased to a great extent. I think easily, we should be looking at touching a business of $200 million with the new investment we are going to do in the machineries. At the same time, there has been a lot of product mix and a lot of traction in the customers demand, and the kind of sustainable solutions, which we have started providing in Oil & Gas is something, which is also picking up dramatically.

**[4] ebitda_margin_pct** | `18-20` % | `FY27` | scorable=yes  
Speaker: Mr. Sanjay Tibrewala, Chief Financial Officer  
Page: 9  

> Sanjay Tibrewala: So, all along, Fineotex has been proven for operational efficiencies in the last 15 years of being listed. Always, our EBITDA margins have been minimum in any of the quarters of, let's say, 60 quarters of being listed, Fineotex EBITDA have always been minimum 18% to 28% on the general level. So, this is something, which we are very much capable to bring more operational efficiencies and see wherever we can invest in the right technologies and the right inventories and other things. On a blended level, we would always look at getting to an easy EBITDA of around 18% to 20%, and that's what we are heading to. I think it's not too far from now, but what's more important right now is to drive the businesses and take the maximum businesses in control, and then keep working on the operational EBITDAs and operational efficiencies.

**[5] capex_absolute** | `7` million | `FY27` | scorable=no  
Speaker: Mr. Sanjay Tibrewala, Chief Financial Officer  
Page: 10  

> Sanjay Tibrewala: So there has been a lot of capex being done. In fact, after the acquisition also, the Fineotex has already done a capex of around $7 million. And, I mean, Fineotex has extended the funds to CCT for investments further of almost -- the line of -- this thing is almost $7 million. So, yes, this is going on.

#### Sandhar Technologies

**[1] revenue_growth_pct** | `15` % | `FY27` | scorable=yes  
Speaker: Jayant Davar – Executive Chairman and CEO  
Page: 4  

> I am happy to give a guidance of over a 15% growth in the overall revenue. This is without taking a price retrigger, which is likely to happen, especially with a lot of costs having gone up, a lot of states announcing new power costs, which has also been a challenge in the last few months.

**[2] revenue_absolute** | `40` crore | `FY27` | scorable=no  
Speaker: Jayant Davar – Executive Chairman and CEO  
Page: 4  

> We are expecting now to double this revenue in the current financial year. During Financial Year 2026, 41,000 battery chargers were sold and 5,500 motor control units were sold.

**[3] commissioning_event** | `null`  | `H1 FY27` | scorable=no  
Speaker: Jayant Davar – Executive Chairman and CEO  
Page: 5  

> We expect to commission Phase 1 by end of H1 FY27.

**[4] revenue_absolute** | `750` crore | `FY27` | scorable=no  
Speaker: Yashpal Jain – Chief Financial Officer and Company Secretary  
Page: 10  

> We expect to do so. 2.5% you can say INR 700 crores, INR 750 crores something. I mean, it is a range sir has given. 2.5x, which can be 2x to 2.5x basically, I would say. So, around INR 750 crores of revenue these projects can do. 468 they have already delivered.

#### Mold-Tek Packaging

**[1] revenue_absolute** | `50-55` crore | `FY27` | scorable=yes  
Speaker: J. Lakshmana Rao - Chairman and Managing Director  
Page: 3  

> J. Lakshmana Rao: No, INR55 crores is our target for the next financial year '26-'27. We hit almost INR34.4 crores for the current financial year. So we have taken a 50% growth to reach somewhere around close to between INR50 crores and INR55 crores for the Pharma. We are online with that, I hope.

**[2] capex_absolute** | `80-85` crore | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao - Chairman and Managing Director  
Page: 5  

> J. Lakshmana Rao: Yes, capacity is 63,000 tons and utilization is hardly 43,000. So we have a long way to go to make use of this capacity. And some more machines which were ordered last year are on the way, arriving in this year, because there will be always some replacement of old machinery and also expanding marginally especially units like Mysore and Satara where -- Mahad, especially. These are areas of growth. And Pharma will continue to add machinery to meet the increasing demand for our products. So these 3 areas, but we have a sharp lesser budget of capital investment in this current financial year, which was INR140 crores 2 years ago for 2 consecutive years and [120 years 0:11:33] in this financial year '25-'26. And we hope to control this capex to INR80 crores, INR85 crores in the next year, that is '26-'27 as we will be going only for brownfield expansions now onwards.

**[3] capacity_addition** | `67-70` tons | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao - Chairman and Managing Director  
Page: 5  

> J. Lakshmana Rao: Yes, I think we should be close to 68, 67 because capacity-wise in Pharma, the number of tons won't be too many, at maybe 1,000, 1,200 tons. And brownfield expansions are only envisaged at Mysore and Satara. Satara basically, that is Mahad plant supply. So these are the 2 areas. And the rest of the plants, we see -- and of course, North plant, Panipat, where we are adding thin wall capacities, 4 machines are coming in this July. So by end of this financial year, that is '26-'27, probably we will be somewhere around 67,000, 68,000, maybe close to 70,000 tons.

**[4] capex_absolute** | `80-85` crore | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao - Chairman and Managing Director  
Page: 6  

> J. Lakshmana Rao: Yes. We are planning it will be in the region of around INR80 crores to INR85 crores overall. It could be from -- mostly from internal accruals, a little bit here and there that if required.

**[5] commissioning_event** | `null`  | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao - Chairman and Managing Director  
Page: 8  

> J. Lakshmana Rao: Yes, '27. '27, before end of the financial year, I think we may start the new plant because of the delay in land allotment. Otherwise, it would have gone by third quarter of this year.

**[6] revenue_growth_pct** | `13-15` % | `FY27` | scorable=yes  
Speaker: J. Lakshmana Rao - Chairman and Managing Director  
Page: 10  

> J. Lakshmana Rao: See, I can see 2 ways of looking at in future because volume growth comes from mere kgs, then Pharma, even if it grows by 50%, the number of kgs it will add will be less. But the number of rupees or value-wise, it will be much higher because our average realization in Pharma is almost double that of other segments. So in terms of just volume, it might look like 10% to 15%, anywhere between 10% to 15% of growth is possible. But in terms of value, I'm sure we'll be clocking between 13% to 15% value growth, like what we did this year, 13.3%. We hope that we will be somewhere between 13% to 15% in the value growth in the next financial year. That is why I said in the year '26-'27, we may cross the INR1,000 crores mark sales.

**[7] ebitda_margin_pct** | `42-43` % | `FY27` | scorable=yes  
Speaker: J. Lakshmana Rao - Chairman and Managing Director  
Page: 13  

> J. Lakshmana Rao: FY '27, as I expected, we are aiming at, at least 42 to 43, 42.5 could be a good estimate for the full year. And then how it frames in Pharma in '28, probably we can aim at around 43 to 44 range. So definitely, we are -- the trend will continue now because 2 things. It's not just the growth in the different segments, but the consolidation of our operations in Hyderabad, where we reduced 5 plants to 2 plants. Now only Annaram and Sultanpur is 2 units, which are producing all the products which were earlier made in 5 plants. So thereby getting the better efficiencies, overhead reduction, and movement of goods has come down. All this is yielding to better productivity. All this consolidation happened only till January this year. That means until Jan, Feb. So the full benefit of this consolidation and improved efficiencies would be reflective in the next financial year. That itself should add a rupee or so to the already 40.7 what we have achieved this year compared to 37.6 in the previous year. So there's a jump of 8% -- 8.4% increase in the EBITDA margin, which is a substantial jump, which we lost during the last couple of years, we recovered. And going forward, with these efficiencies kicking in and more and more HCL labels also being made in-house and the new ways of automation, which we have taken up in various areas to reduce the manpower dependency is going to improve the efficiencies going forward. And ABG plants, even today are hardly around 60% capacity utilization. And I hope next year, they will be reaching 70% plus, which will be a very good accretive to the bottom line. So going forward with the only brownfield expansions, which will marginally may require capital, but increase in the capacity utilization will kick in. So I look at very positively for '26-'27 and to aim at least 42.5 to 43 range for '26-'27. '27-'28 may be a little difficult to predict now. Maybe we may touch even 45 given a good in Pharma. If it happens, we may aim at 44, 45 also for next '27-'28. But I can give a better picture going forward in the next couple of quarters.

### arm1_gpt55 — `gpt-5.5`

#### Asian Paints

**[1] commissioning_event** | `null`  | `H1 FY27` | scorable=no  
Speaker: Amit Syngle, MD & CEO  
Page: 11  

> The area of VAM-VAE, which is our backward integration project, is something which we are looking forward to strongly. Today, worldwide, there are very limited players  who are making VAM -VAE, and for us, it is a signature project and we expect to commission first phase in the first half of this year.

**[2] ebitda_margin_pct** | `18-20` % | `FY27` | scorable=yes  
Speaker: Amit Syngle, MD & CEO  
Page: 22  

> Amit Sachdeva: Just to understand clearly that in doing so, you would like to maintain your margin guidance, which has always been 18-20%, there is a high single-digit volume ambition as well for the year. I assume when you say high single-digit, you mean FY27. And also the pricing whatever will build up on top of it. Is this a way to interpret what you are saying?  
Amit Syngle: Absolutely right. We are maintaining our margin guidance, which is there. We are looking at the price increases that are happening and trying to see that we get into that area of 8-10% volume growth.

**[3] volume_growth_pct** | `8-10` % | `FY27` | scorable=no  
Speaker: Amit Syngle, MD & CEO  
Page: 22  

> Amit Sachdeva: Just to understand clearly that in doing so, you would like to maintain your margin guidance, which has always been 18-20%, there is a high single-digit volume ambition as well for the year. I assume when you say high single-digit, you mean FY27. And also the pricing whatever will build up on top of it. Is this a way to interpret what you are saying?  
Amit Syngle: Absolutely right. We are maintaining our margin guidance, which is there. We are looking at the price increases that are happening and trying to see that we get into that area of 8-10% volume growth.

**[4] volume_value_gap_pct** | `3-4` % | `next few quarters` | scorable=no  
Speaker: Amit Syngle, MD & CEO  
Page: 25  

> Pratik Gothi: Got it. And a related question is the volume value gap. The volume value gap of 3 -4%. Did you mention that?  
Amit Syngle: Yes, I did.  
Pratik Gothi: That will remain over the next few quarters as well, even while the price hikes are being followed through.  
Amit Syngle: Yes, because the price increases might not be at a regular interval. But, we think that this trajectory of 3-4% will remain as we go ahead.

#### Fineotex Chemical

**[1] ebitda_margin_pct** | `15` % | `going forward` | scorable=no  
Speaker: Sanjay Tibrewala – Chief Financial Officer – Fineotex Chemical Limited  
Page: 5  

> Amit Mehendale: Thank you, and congrats on great set of numbers. My first question is on our US acquisition of CCT. Are we expecting $200 million of revenue in FY  '28? And because I was looking at the PPT where it mentioned the specific number, and the timeline as well. And also, what type of EBITDA are we looking at in terms of EBITDA percentage as we scale up the business?
Sanjay Tibrewala: At the same time, the EBITDA margins have been improving considerably with the, kind of, the resources, which we have -- after our -- after we being the shareholders in CrudeChem, we could have a lot more resources on machinery, manpower, negotiations and suppliers’ negotiations. So, these factors have contributed to increase of EBITDA.  So going forward, I think comfortably, we should be at EBITDA of 15% more or less.

**[2] ebitda_margin_pct** | `18-20` % | `FY27` | scorable=yes  
Speaker: Sanjay Tibrewala – Chief Financial Officer – Fineotex Chemical Limited  
Page: 14  

> Vinay Nadkarni: Great. I think it's a great acquisition. Just one last question for you. When you said 18% to 20% of blended EBITDA going forward, would that be in F '27 or would you look at that as F '28?
Sanjay Tibrewala: We are trying our best to make it as soon as – as quickly as possible, but I think this can be reflecting even in this financial year. So, I won't be surprised rather on that.

#### Sandhar Technologies

**[1] revenue_growth_pct** | `15-16` % | `FY27` | scorable=yes  
Speaker: Jayant Davar – Executive Chairman (Executive Director) and Chief Executive Officer, Sandhar Technologies Limited  
Page: 5  

> We will, of course, have to wait and see, and therefore that is the reason why I am giving you a conservative estimate of 15% plus, 15% to 16% plus of revenue growth this year.

**[2] revenue_absolute** | `5500` crore | `FY27` | scorable=yes  
Speaker: Yashpal Jain – Chief Financial Officer and Company Secretary, Sandhar Technologies Limited  
Page: 8  

> And in the earlier calls, our Chairman has mentioned that we keep our CapEx limited to 5% to 7% of our revenues. So, taking our 15% growth on the current year's revenue, which is roughly INR 5,500 crores, you can expect somehow capital outlay of INR 275 crores to around INR 310 crores for the upcoming financial year, which will include a part of growth CapEx, part of maintenance CapEx, part of upgradation CapEx required to upgrade our some old facilities also.

**[3] capex_absolute** | `275-310` crore | `FY27` | scorable=no  
Speaker: Yashpal Jain – Chief Financial Officer and Company Secretary, Sandhar Technologies Limited  
Page: 8  

> And in the earlier calls, our Chairman has mentioned that we keep our CapEx limited to 5% to 7% of our revenues. So, taking our 15% growth on the current year's revenue, which is roughly INR 5,500 crores, you can expect somehow capital outlay of INR 275 crores to around INR 310 crores for the upcoming financial year, which will include a part of growth CapEx, part of maintenance CapEx, part of upgradation CapEx required to upgrade our some old facilities also.

**[4] other_ebitda_margin_expansion_pct** | `0.1-0.4` % | `FY27` | scorable=no  
Speaker: Yashpal Jain – Chief Financial Officer and Company Secretary, Sandhar Technologies Limited  
Page: 8  

> And like as we discussed and we discussed in earlier calls also, every year we want to grow and improve our EBITDA levels by at least half a percent, in a range of half a percent, which could be 0.20, 0.30 or something like that. So, this year also we are expecting to improve our EBITDA margins in a range of half a percent, which could be 0.1, 0.2, 0.3, 0.4, depending on the market dynamics as far as addressed in the previous question.

**[5] other_cwip_capitalization_absolute** | `115` crore | `Q2 FY27` | scorable=no  
Speaker: Yashpal Jain – Chief Financial Officer and Company Secretary, Sandhar Technologies Limited  
Page: 8  

> In terms of Sanaswadi also, the lead date is end of Quarter 2. So, mostly the INR 115 crore, this is something revolving type of capital work in progress. New investments are done, it keeps on floating. So, while this figure will be capitalized by the end of 2nd Quarter, new figures might come in.

**[6] revenue_absolute** | `700-750` crore | `FY27` | scorable=no  
Speaker: Yashpal Jain – Chief Financial Officer and Company Secretary, Sandhar Technologies Limited  
Page: 10  

> Ashutosh Tiwari: So, this INR 468 crore revenue that you did in this year can go to INR 800 crore plus in FY '27? Yashpal Jain: 2.5% you can say INR 700 crores, INR 750 crores something. I mean, it is a range sir has given. 2.5x, which can be 2x to 2.5x basically, I would say. So, around INR 750 crores of revenue these projects can do. 468 they have already delivered.

**[7] other_debt_repayment_absolute** | `103` crore | `FY27` | scorable=no  
Speaker: Yashpal Jain – Chief Financial Officer and Company Secretary, Sandhar Technologies Limited  
Page: 13  

> This year we have a repayment commitment of around close to INR 103 crores with various banks. So, term debt will start pairing as the repayment schedule comes in, but as working capital debt is aligned directly to the business, so I don't think that is a point of worry.

#### Mold-Tek Packaging

**[1] revenue_absolute** | `50-55` crore | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 3  

> Samarth Jain: So you gave us the guidance of INR55 crores to INR60 crores in Pharma for FY '27. So is this including this contract revenue or will it be incremental to this?
J. Lakshmana Rao: No, INR55 crores is our target for the next financial year '26-'27. We hit almost INR34.4 crores for the current financial year. So we have taken a 50% growth to reach somewhere around close to between INR50 crores and INR55 crores for the Pharma. We are online with that, I hope.

**[2] revenue_growth_pct** | `50` % | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 3  

> Samarth Jain: So you gave us the guidance of INR55 crores to INR60 crores in Pharma for FY '27. So is this including this contract revenue or will it be incremental to this?
J. Lakshmana Rao: No, INR55 crores is our target for the next financial year '26-'27. We hit almost INR34.4 crores for the current financial year. So we have taken a 50% growth to reach somewhere around close to between INR50 crores and INR55 crores for the Pharma. We are online with that, I hope.

**[3] capacity_addition** | `2500` tons | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 4  

> Richa: And sir, capacity-wise, how much additional capacity are we targeting for Grasim and in Pharma as well because we have some capacity capex planned in that segment?
J. Lakshmana Rao: Yes. Currently, Pharma is hardly about 1,500 tons, and we have to still make new investments in that segment to take it up to 2,500 tons in this year.

**[4] capex_absolute** | `80-85` crore | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 4  

> So these 3 areas, but we have a sharp lesser budget of capital investment in this current financial year, which was INR140 crores 2 years ago for 2 consecutive years and [120 years 0:11:33] in this financial year '25-'26. And we hope to control this capex to INR80 crores, INR85 crores in the next year, that is '26-'27 as we will be going only for brownfield expansions now onwards.

**[5] capacity_addition** | `67000-68000` tons | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 5  

> Chirag: And that will lead to almost like 70,000 MTPA capacity by the end of FY '27. Is my assumption correct?
J. Lakshmana Rao: Yes, I think we should be close to 68, 67 because capacity -wise in Pharma, the number of tons won't be too many, at maybe 1,000, 1,200 tons. And brownfield expansions are only envisaged at Mysore and Satara. Satara basically, that is Mahad plant supply. So these are the 2 areas.
 And the rest of the plants, we see -- and of course, North plant, Panipat, where we are adding thin wall capacities, 4 machines are coming in this July. So by end of this financial year, that is '26-'27, probably we will be somewhere around 67,000, 68,000, maybe close to 70,000 tons.

**[6] other_gross_margin_pct** | `46-47` % | `coming quarters` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 5  

> Chirag: And sir, will it be fair to assume, though you have mentioned in your press release that all the cost increase we are able to pass on. I just wanted to know the current scenario, like will it be fair to assume that we would be able to maintain the 46%, 47% gross margin levels in the coming quarters too?
J. Lakshmana Rao: Certainly, we have passed on the entire price rise to the clients across the segments. And they also appreciated that the reality -- ground realities and even some of them have reduced the period of raw material fluctuation. That means earlier, they used to be quarterly. Now they have come down to a monthly or even sometimes 15, fortnightly correction.
 So that way, even when the prices come down, we too will have to pass on the reduction to them. It's a fair game. But I'm very thankful to all our clients. Majority of them have accepted the price rise rapidly because the price movement in March was so rapid.
 From INR105 in the beginning, it went up to INR160, and now currently hovering around INR145, INR150. So we are, in this kind of a scenario, found our clients very much with us, and I think we can still continue to maintain our profit margins.

**[7] commissioning_event** | `null`  | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 8  

> Sandeep Modi: Yes. Sir, there was a Pharma packaging we are trying to start some new this thing?
J. Lakshmana Rao: Yes, the new plant is -- new land is mainly meant for Pharma alone.
Sandeep Modi: And what will be the...
J. Lakshmana Rao: So once the land is handed over, the construction activity will start immediately.
Sandeep Modi: So when will that complete this new factory start over?
J. Lakshmana Rao: I think it will go into commercial production only by beginning of next financial year, I mean, next calendar year. It may take at least 8-9 months to complete the construction once the land is handed over. For various reasons, there is a delay from the industrial estate to hand over the land. We have paid for it more than 7-8 months ago.
Sandeep Modi: So around Jan 2028, it will be operational fully?
J. Lakshmana Rao: Yes, '27. '27, before end of the financial year, I think we may start the new plant because of the delay in land allotment. Otherwise, it would have gone by third quarter of this year.

**[8] revenue_growth_pct** | `13-15` % | `FY27` | scorable=yes  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 9  

> Dipak Saha: And sir, FY '27 full year point of view, how should we understand the growth numbers? And if you can broadly give a breakup because Lubricant has been degrowing, Paint has started growing. You said both Asian Paints and other players are growing decently. So if you just can give some color on a full year basis, FY '27, what kind of a volume growth we should look for and the breakdown of that?
J. Lakshmana Rao: See, I can see 2 ways of looking at in future because volume growth comes from mere kgs, then Pharma, even if it grows by 50%, the number of kgs it will add will be less. But the number of rupees or value-wise, it will be much higher because our average realization in Pharma is almost double that of other segments.
 So in terms of just volume, it might look like 10% to 15%, anywhere between 10% to 15% of growth is possible. But in terms of value, I'm sure we'll be clocking between 13% to 15% value growth, like what we did this year, 13.3%. We hope that we will be somewhere between 13% to 15% in the value growth in the next financial year.
 That is why I said in the year '26-'27, we may cross the INR1,000 crores mark sales.

**[9] revenue_absolute** | `1000` crore | `FY27` | scorable=yes  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 9  

> Dipak Saha: And sir, FY '27 full year point of view, how should we understand the growth numbers? And if you can broadly give a breakup because Lubricant has been degrowing, Paint has started growing. You said both Asian Paints and other players are growing decently. So if you just can give some color on a full year basis, FY '27, what kind of a volume growth we should look for and the breakdown of that?
J. Lakshmana Rao: See, I can see 2 ways of looking at in future because volume growth comes from mere kgs, then Pharma, even if it grows by 50%, the number of kgs it will add will be less. But the number of rupees or value-wise, it will be much higher because our average realization in Pharma is almost double that of other segments.
 So in terms of just volume, it might look like 10% to 15%, anywhere between 10% to 15% of growth is possible. But in terms of value, I'm sure we'll be clocking between 13% to 15% value growth, like what we did this year, 13.3%. We hope that we will be somewhere between 13% to 15% in the value growth in the next financial year.
 That is why I said in the year '26-'27, we may cross the INR1,000 crores mark sales.

**[10] revenue_growth_pct** | `20` % | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 12  

> If you combine the thick wall also, food is around 18%. But this 15.4%, I'm sure it will be looking at least 20% growth in the food and FMCG, including the North numbers for the next financial year.

**[11] capacity_addition** | `4` machines | `July 2026` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 12  

> See, in ABG plant, that is mainly meant for Paints and Qpack, we are hardly reaching around 60% capacity utilization in Panipat. And in thin wall, which is hardly 4 -5 months old, we may be around 20%, 25% capacity utilization. So there's a long way to go. And we are, in fact, adding 4 more machines in July for thin wall, so which will expand the capacity there by another 100%.

**[12] other_ebitda_per_kg** | `42-43` INR/kg | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 12  

> Akhil Parekh: Many congratulations, sir, on a very good set of numbers. My first question on the EBITDA per kg, right? We have shown good improvement. What should that number look like, say, in FY '27 and '28?
J. Lakshmana Rao: FY '27, as I expected, we are aiming at, at least 42 to 43, 42.5 could be a good estimate for the full year.

**[13] other_capacity_utilization_pct** | `70` % | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 13  

> And ABG plants, even today are hardly around 60% capacity utilization. And I hope next year, they will be reaching 70% plus, which will be a very good accretive to the bottom line.

**[14] volume_growth_pct** | `10-13` % | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 13  

> Akhil Parekh: Sir, and just reconfirm your growth guidance for '27, you suggested 10% to 15% volume growth and 13% to 15% value growth. Did I hear correctly?
J. Lakshmana Rao: Yes. The volume growth is 10% to 13% because Pharma won't add volumes. It will hardly be in few tons. So even the rupee has become up by 50%. Volume-wise last year, it was hardly, how much, 853 tons.
 So last year, it was 853 tons. And so the next year, '26 -27, it will hardly touch 1,200 to 1,300 kgs. So -- sorry, tons, 1,200 tons to 1,300 tons, even if you achieve a 50% increment. So volume-wise increment might look 10% to 13%, but value -wise increment, we are aiming at 13% to 15%.

**[15] revenue_absolute** | `35-40` crore | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 15  

> Definitely, I'm very confident that more and more number of clients will be added in '26-27 than last year, basically, because our North plant has started operations from October, November. And slowly, there is a traction that is being created. As I said, in the month of March, we have made some sales worth around INR3 crores, INR3.5 crores for the -- both the Qpack and Food together, which was zero last year.
 So going forward, that itself is indication that INR35 crores to INR40 crores of new addition in business can come from North in Qpack and Food together. So that is still less than 50% capacity utilization, but it will be a handsome number new addition. So in my opinion, '26 -'27 we will have many more client additions in Food and FMCG from the North compared to overall year '25-'26.

**[16] other_roce_pct** | `13.5-14` % | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 16  

> Coming back to ROCE, yes, the ROCE has leaped by about 14% from 10.2% to 12.4% and probably it may hit around 13.5% to 14% in the next financial year.

**[17] other_ebitda_absolute** | `210` crore | `FY27` | scorable=no  
Speaker: J. Lakshmana Rao – Chairman and Managing Director – Mold-Tek Packaging Limited  
Page: 17  

> Shanskar: Sir, most of my questions have been answered. Just wanted to understand on the growth perspective, while you have answered on volume and value terms, I just wanted to get that you have guided going forward on maintaining around 20% growth rate in terms of profitability at EBITDA and PAT level. So are you maintaining that or is there any upside or downward revision?
J. Lakshmana Rao: I think we'll certainly be there. We are aiming at, at least INR210 crores EBITDA for next financial year, up from INR173, that's 20% price. I think we are definitely going to achieve that in view of not only the increasing business, but our internal improvisations and efficiency creation, what we are bringing through the consolidation of units. It might -- I mean, if thi ngs go well, I mean, nothing further damage happens through this war, we should be looking better than that expected EBITDA.

---

## Decision Summary

Evaluate each arm against the spec §9 thresholds:

- **Single-pass wins**: frontier arm clears ~≥70% recall AND ~≥70–80% precision across all companies, AND Mold-Tek does not truncate
- **Hybrid signal**: recall jumps well past baseline but precision is poor, OR misses are mostly label-failures not find-failures
- **Multi-stage validated**: no meaningful lift over baseline, OR Mold-Tek still truncates

**Fill this in after reviewing the numbers above:**

| Arm | Verdict | Notes |
|-----|---------|-------|
| arm0_gpt4o | (control — reproduce baseline) | |
| arm1_gpt55 | (to be filled in) | |

_See spec §8 for the manual semantic recall analysis (find-failure vs label-failure) on misses._
