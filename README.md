# Marketing Lead Funnel Analysis (DuckDB + SQL)

> **Status: in progress.** Part 1 (lead-to-seller conversion by month, channel and speed) is done. Next: sales-team and lead-profile drivers, then what signed sellers actually sold. See [Roadmap](#roadmap).

**Business question:** a marketplace recruits sellers through a marketing and sales funnel: a business signs up on a landing page, a sales development rep (SDR) qualifies it, and a sales rep (SR) tries to close it. **Which marketing channels bring leads that actually sign, how fast do deals close, and why did conversion fall in May 2018?** The answers decide where marketing spends its budget and how sales should prioritise its follow-up.

## Findings so far
- **About 1 in 9 leads signs within 90 days.** 678 of the 5,998 leads from Jan–May 2018 (11.3%) became sellers within 90 days. Jan–Apr was steady at 11.3–12.6%, then May fell to **8.4%**.
- **Social and email bring volume, not sellers.** Together they are 23.3% of leads but only 9.9% of 90-day wins: social converts at 5.2% and email at 3.5%, against 12.3–12.9% for organic search, paid search and direct traffic.
- **A quarter of wins can't be credited to any channel.** Leads with origin `unknown` or missing are 14.4% of leads but 24.9% of wins, and they convert best (19.6%). Any cost-per-seller figure by channel built on this data leaves out a quarter of signed sellers.
- **Deals close fast or not at all.** 38.1% of wins sign within a week and 57.3% within two weeks; only 8.7% come after day 90.
- **May's drop was a conversion problem, not a lead-mix problem.** Of the 3.75-point fall, the channel mix explains −0.41 points and weaker conversion *within* channels −3.34 points (89%). Every large channel fell, e.g. paid search 13.4% → 9.0%.

## Data
[Marketing Funnel by Olist](https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist): real, anonymised data on 8,000 marketing-qualified leads (MQLs) who asked to sell on the Olist marketplace between June 2017 and June 2018, randomly sampled by Olist from all its MQLs, plus the 842 of them that signed. Kaggle needs a login, so `scripts/download_data.py` fetches the two CSVs (~0.9 MB) from public GitHub mirrors ([`mara/mara-olist-ecommerce-data`](https://github.com/mara/mara-olist-ecommerce-data), with [`patterns-app/public_data`](https://github.com/patterns-app/public_data) as a fallback). Both mirrors serve byte-identical files whose total size matches the Kaggle listing exactly. The script pins their SHA-256 hashes and stops if a file changes. The raw CSVs aren't committed.

**Licence:** the dataset is © Olist and published under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (see the [Kaggle page](https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist)). This repo uses it for non-commercial analysis and publishes only derived aggregates.

| Table | Rows | What it holds |
|---|---:|---|
| `mqls` | 8,000 | lead id, first contact date (2017-06-14 to 2018-05-31), landing page, origin (channel) |
| `closed_deals` | 842 | won date (2017-12-05 to 2018-11-14), seller id, SDR, SR, business segment, lead type, self-declared profile |

**Analysis window: leads first contacted in Jan–May 2018 (5,998 leads).** The deal records start on 2017-12-05, so a 2017 lead that signed before then simply isn't in the data. The June–October 2017 cohorts show no win within 90 days at all, which is a recording gap, not a sales result. Every 2018 cohort is observed for at least 167 days, so a 90-day conversion window is complete for all of them.

## Approach
1. **Download** (`scripts/download_data.py`): two mirrors, SHA-256 checked.
2. **Load** (`pipeline/build_db.py`): typed DuckDB tables plus a `leads` view (cohort month, days to close, a 90-day win flag, the analysis-window flag). Data-quality checks run on load and the build stops if one fails: unique lead ids, unique sellers, no deal without a lead, no wins before deal tracking started. Reported, not dropped: 1 deal dated 2 days before its first contact, 60 leads with no origin, and only 45 of 842 deals with a declared monthly revenue above 0 (so revenue can't be analysed from this field).
3. **Query** ([`sql/`](sql/)): each file answers one business question and is commented.
4. **Report** (`report/build.py`): runs every query and writes [`results/REPORT.md`](results/REPORT.md), CSVs and charts.

## Findings

### 1. About 1 in 9 leads signs within 90 days, and May 2018 dropped
![Conversion by month of first contact](results/charts/01_cohort_conversion.png)

| First contact | Leads | Signed ≤ 90 days | % | Signed by Nov 2018 | % |
|---|---:|---:|---:|---:|---:|
| 2018-01 | 1,141 | 129 | 11.3 | 152 | 13.3 |
| 2018-02 | 1,028 | 128 | 12.5 | 149 | 14.5 |
| 2018-03 | 1,174 | 141 | 12.0 | 167 | 14.2 |
| 2018-04 | 1,352 | 171 | 12.6 | 183 | 13.5 |
| 2018-05 | 1,303 | 109 | **8.4** | 130 | 10.0 |
| **Jan–May** | **5,998** | **678** | **11.3** | **781** | **13.0** |

Lead volume ran at 1,000–1,350 a month while conversion held at 11–13% until May. Query: [`01_cohort_conversion.sql`](sql/01_cohort_conversion.sql).

### 2. Social and email fill the top of the funnel but rarely sign
![Conversion by channel](results/charts/02_channel_conversion.png)

| Channel | Leads | % of leads | Wins ≤ 90 d | % of wins | Conversion | 95% interval |
|---|---:|---:|---:|---:|---:|---|
| organic_search | 1,736 | 28.9 | 213 | 31.4 | 12.3% | 10.8–13.9 |
| paid_search | 1,182 | 19.7 | 147 | 21.7 | 12.4% | 10.7–14.4 |
| social | 1,051 | 17.5 | 55 | 8.1 | **5.2%** | 4.0–6.7 |
| unknown | 813 | 13.6 | 157 | 23.2 | **19.3%** | 16.7–22.2 |
| direct_traffic | 380 | 6.3 | 49 | 7.2 | 12.9% | 9.9–16.6 |
| email | 347 | 5.8 | 12 | 1.8 | **3.5%** | 2.0–5.9 |
| referral | 211 | 3.5 | 21 | 3.1 | 10.0% | 6.6–14.7 |
| other, display, other_publicities, (missing) | 278 | 4.6 | 24 | 3.5 | 8.6% | small groups, see [`REPORT.md`](results/REPORT.md) |

- **Social and email** are 1,398 leads (23.3%) but 67 wins (9.9%). Their intervals don't overlap with the search channels', so the gap isn't noise. Each of their leads still costs SDR time to qualify.
- **Paid and organic search convert the same** (12.4% vs 12.3%), so paid search buys extra volume at the same quality rather than better leads.
- **Unattributed leads convert best.** `unknown` (813) and missing origin (48) together are 861 leads (14.4%) with 169 wins (24.9%), a 19.6% rate. The data can't say where they came from. One plausible reading is that they include routes that aren't tagged, such as partner or sales-sourced contacts, but that is a hypothesis to check with the marketing team, not a finding.

Query: [`02_channel_conversion.sql`](sql/02_channel_conversion.sql) (Wilson 95% intervals, computed in SQL).

### 3. Deals close in the first two weeks or drift
![Time to close](results/charts/03_time_to_close.png)

Of the 743 wins that closed within 167 days (the follow-up every 2018 cohort gets), **38.1% signed within 7 days, 57.3% within 14, 74.3% within 30 and 91.3% within 90**. Among 90-day wins, the median time to close is 8–10 days for search and direct leads but 18 days for social. Query: [`03_time_to_close.sql`](sql/03_time_to_close.sql).

### 4. May's drop: weaker conversion within channels, not a worse mix
![May drop bridge](results/charts/04_may_drop_bridge.png)

A shift-share split of the change from Jan–Apr (12.1%) to May (8.4%):

| Effect | Points | What it means |
|---|---:|---|
| Channel mix | −0.41 | May had more social and email leads (social 16.7% → 20.6% of leads) |
| Within-channel conversion | **−3.34** | the same channels converted worse |

| Channel | Jan–Apr conversion | May conversion |
|---|---:|---:|
| organic_search | 12.9% | 9.6% |
| paid_search | 13.4% | 9.0% |
| social | 6.0% | 3.0% |
| unknown | 19.9% | 16.9% |
| direct_traffic | 14.2% | 7.7% |

Because nearly every channel fell together, the cause is more likely on the sales side (capacity, follow-up, or a change in process) than in marketing targeting. Part 2 checks SDR and SR workload to test this. Query: [`04_may_drop_mix_vs_rate.sql`](sql/04_may_drop_mix_vs_rate.sql).

## So what for the business (so far)
1. **Rebalance social and email towards search.** They supply nearly a quarter of leads but a tenth of sellers. Either cut spend, or add a qualification step (form questions, a self-serve check) so SDRs don't spend time on leads that rarely sign. *Owner: marketing lead.*
2. **Fix lead-source tracking before judging channel ROI.** A quarter of signed sellers have no channel, so every channel's cost per seller is wrong today. *Owner: marketing ops.*
3. **Front-load sales follow-up.** Most wins happen in the first 14 days; a lead untouched in that window is losing its best odds. *Owner: SDR team lead.*
4. **Treat May as a sales-side alert.** Lead quality per channel didn't explain the fall, so look at sales capacity and process first (Part 2). *Owner: sales manager.*

These are first-pass recommendations. The final set will be ranked once Parts 2–3 are done.

## How to run
```bash
python -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -r requirements.txt
python scripts/download_data.py        # ~0.9 MB, hash-checked
python -m pipeline.build_db            # DuckDB + data-quality checks
python -m report.build                 # results/REPORT.md, CSVs, charts
pytest                                 # offline tests on a fixture database
```

## Roadmap
- [x] Part 1: conversion by month and channel, time to close, May drop decomposition
- [ ] Part 2: sales-team and lead-profile drivers (SDR/SR workload and win rates, landing pages, business segment and lead type of won deals)
- [ ] Part 3: after the deal: join won sellers to the [Olist e-commerce orders](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) by `seller_id` to see which channels bring sellers who actually sell
- [ ] Final TL;DR, ranked recommendations with owners, limitations

## Limitations (so far)
- **One channel per lead.** Olist notes a lead may have come from several sources; the data records one origin.
- **Won deals only.** There is no record of lost deals or SDR contact dates, so the funnel has two measurable steps (lead → signed), not every stage.
- **A sample.** The 8,000 leads are Olist's random sample of its MQLs, so counts are a fraction of the real volume; rates are what matter.
- **2017 excluded** from rates because the deal records start in December 2017 (see Data).
