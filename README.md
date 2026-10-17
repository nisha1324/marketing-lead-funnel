# Marketing Lead Funnel Analysis (DuckDB + SQL)

> **Status: in progress.** Parts 1 and 2 are done (conversion by month, channel and speed, the May drop, sales-team capacity, landing pages and the profile of won deals), and so is Part 3a: whether signed sellers actually start selling, by channel and lead type. Next: Part 3b (segments, landing pages and close speed after the deal). See [Roadmap](#roadmap).

**Business question:** a marketplace recruits sellers through a marketing and sales funnel: a business signs up on a landing page, a sales development rep (SDR) qualifies it, and a sales rep (SR) tries to close it. **Which marketing channels bring leads that actually sign, how fast do deals close, and why did conversion fall in May 2018?** The answers decide where marketing spends its budget and how sales should prioritise its follow-up.

## Findings so far
- **About 1 in 9 leads signs within 90 days.** 678 of the 5,998 leads from Jan–May 2018 (11.3%) became sellers within 90 days. Jan–Apr was steady at 11.3–12.6%, then May fell to **8.4%**.
- **Social and email bring volume, not sellers.** Together they are 23.3% of leads but only 9.9% of 90-day wins: social converts at 5.2% and email at 3.5%, against 12.3–12.9% for organic search, paid search and direct traffic.
- **A quarter of wins can't be credited to any channel.** Leads with origin `unknown` or missing are 14.4% of leads but 24.9% of wins, and they convert best (19.6%). Any cost-per-seller figure by channel built on this data leaves out a quarter of signed sellers.
- **Deals close fast or not at all.** 38.1% of wins sign within a week and 57.3% within two weeks; only 8.7% come after day 90.
- **May's drop was a conversion problem, not a lead-mix problem.** Of the 3.75-point fall, the channel mix explains −0.41 points and weaker conversion *within* channels −3.34 points (89%). Every large channel fell, e.g. paid search 13.4% → 9.0%.
- **Fewer reps is a weak explanation.** 15 reps closed a deal from the May cohort, the fewest of any cohort (16–20 in January–April), but wins per rep (8.7) were in line with February and March (8.3–8.4).
- **Wins lean on a few reps.** The top 5 of 21 reps won 51% of 2018 wins, and the top rep won 16%.
- **Three landing pages bring over half the sellers.** They took 29.6% of leads but 53.0% of 90-day wins, each converting at about 20%. Within organic search alone, the best page converts at 22.0% and the weakest at 4.7%.
- **The "unknown" channel is mostly one page.** 536 of the 813 unknown-origin leads, and 119 of their 157 wins, came in through page `b76ef374`, which gives marketing ops a concrete place to start fixing the tracking.
- **May's missing sellers were mostly mid-sized online sellers.** 90-day wins per 1,000 leads fell from 121.2 to 83.7; `online_medium` sellers account for 27.0 of that 37.5 drop (72%). Splitting the drop by landing page instead of channel gives the same answer: the page mix explains only −0.40 points.
- **Signing isn't selling: 43.1% of signed sellers made a sale within 90 days.** Of 643 sellers signed from December 2017 to May 2018, only 16.8% sold within 30 days, and 48.4% had no sale at all in the order data by 2018-08-21. The median first sale came 39 days after the deal.
- **Paid search overtakes organic search after the deal.** Both channels sign 12.3–12.4% of their leads, but 55.0% of paid-search sellers start selling within 90 days against 39.1% for organic search. That is about 68 vs 48 selling sellers per 1,000 leads.
- **Big online sellers start selling; offline businesses mostly don't.** 63.2% of `online_big` sellers made a sale within 90 days (active sellers' median: R$821), against 23.8% of `offline` and 35.6% of `industry` sellers.

## Data
[Marketing Funnel by Olist](https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist): real, anonymised data on 8,000 marketing-qualified leads (MQLs) who asked to sell on the Olist marketplace between June 2017 and June 2018, randomly sampled by Olist from all its MQLs, plus the 842 of them that signed. Kaggle needs a login, so `scripts/download_data.py` fetches the two CSVs (~0.9 MB) from public GitHub mirrors ([`mara/mara-olist-ecommerce-data`](https://github.com/mara/mara-olist-ecommerce-data), with [`patterns-app/public_data`](https://github.com/patterns-app/public_data) as a fallback). Both mirrors serve byte-identical files whose total size matches the Kaggle listing exactly. The script pins their SHA-256 hashes and stops if a file changes. The raw CSVs aren't committed.

**Licence:** the dataset is © Olist and published under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (see the [Kaggle page](https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist)). This repo uses it for non-commercial analysis and publishes only derived aggregates.

| Table | Rows | What it holds |
|---|---:|---|
| `mqls` | 8,000 | lead id, first contact date (2017-06-14 to 2018-05-31), landing page, origin (channel) |
| `closed_deals` | 842 | won date (2017-12-05 to 2018-11-14), seller id, SDR, SR, business segment, lead type, self-declared profile |
| `orders` (Part 3) | 99,441 | order id, status, purchase time (2016-09-04 to 2018-10-17) |
| `order_items` (Part 3) | 112,650 | order id, seller id, item price |

**Part 3: what signed sellers sold.** The won deals join to Olist's [Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) by `seller_id` (© Olist, also CC BY-NC-SA 4.0). The download script takes only the orders and order items (~33 MB), from Olist's own GitHub repo ([`olist/work-at-olist-data`](https://github.com/olist/work-at-olist-data)) with the mara mirror as fallback. The two copies have the same rows but aren't byte-identical: the mara copy quotes every field, and 67 order lines have a different `freight_value`. The analysis doesn't use freight, so each source has its own pinned hash. 380 of the 842 signed sellers appear in the orders, and none has an order dated before it signed.

**Selling window.** The order data has 176–372 orders a day in the four weeks to 2018-08-21; from 2018-08-22 it falls almost every day (187, 144, 99 … 14 orders on 2018-08-29), so the snapshot was taken while recent orders were still coming in. Orders from 2018-08-22 on are ignored. Each seller is followed for 90 days after signing, so Part 3 uses the **643 sellers signed from 2017-12-05 to 2018-05-23**. A *sale* is an order that wasn't cancelled or unavailable; *sales value* is the item price without freight.

**Analysis window: leads first contacted in Jan–May 2018 (5,998 leads).** The deal records start on 2017-12-05, so a 2017 lead that signed before then simply isn't in the data. The June–October 2017 cohorts show no win within 90 days at all, which is a recording gap, not a sales result. Every 2018 cohort is observed for at least 167 days, so a 90-day conversion window is complete for all of them.

## Approach
1. **Download** (`scripts/download_data.py`): two sources per file, SHA-256 checked.
2. **Load** (`pipeline/build_db.py`): typed DuckDB tables plus a `leads` view (cohort month, days to close, a 90-day win flag, the analysis-window flag). Part 3 adds the `orders` and `order_items` tables and a `signed_sellers` view (one row per won deal: first sale, orders and sales value in the 90 days after signing). Data-quality checks run on load and the build stops if one fails: unique lead ids, unique sellers, no deal without a lead, no wins before deal tracking started, unique order lines, no order line without an order, and no signed seller with an order before it signed. Reported, not dropped: 1 deal dated 2 days before its first contact, 60 leads with no origin, and only 45 of 842 deals with a declared monthly revenue above 0 (so revenue can't be analysed from this field).
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

### 5. Sales capacity: May had slightly fewer reps, and wins lean on a few people
![Sales reps with a win, and rep concentration](results/charts/05_sales_capacity.png)

| Lead cohort | Leads | Wins | Reps with a win (SDR / SR) | Wins per SR | Median days to close |
|---|---:|---:|---:|---:|---:|
| 2018-01 | 1,141 | 152 | 12 / 16 | 9.5 | 17.5 |
| 2018-02 | 1,028 | 149 | 17 / 18 | 8.3 | 16.0 |
| 2018-03 | 1,174 | 167 | 17 / 20 | 8.4 | 12.0 |
| 2018-04 | 1,352 | 183 | 13 / 16 | 11.4 | 9.0 |
| 2018-05 | 1,303 | 130 | 15 / 15 | 8.7 | 10.0 |

- **May had the fewest reps, but only by a little.** 15 reps closed a May-cohort deal, against 16–20 in January–April. Wins per rep (8.7) matched February and March (8.3 and 8.4), and April (11.4) was the outlier. A headcount dip of one to five people doesn't explain a fall of 3.75 points on its own.
- **Deals that did sign closed no slower.** The median days to close for May's wins is 10, against 16–18 for January and February.
- **Wins are concentrated.** 21 reps won at least one deal in the window. The top rep won 128 of 781 (16.4%), the top 5 won 50.6%, and the top 10 won 81.0%. Losing one of the top reps would be a material capacity hit.

**What this can't show.** Reps are recorded only on won deals, so a rep with no win from a cohort is invisible, and the counts are a lower bound. Leads per rep aren't in the data, so workload can't be measured directly; "wins per rep" is a proxy, not a win rate. Queries: [`05_sales_capacity.sql`](sql/05_sales_capacity.sql), [`06_rep_concentration.sql`](sql/06_rep_concentration.sql).

### 6. Landing pages: three pages bring half the sellers, and pages differ within a channel
The 5,998 leads arrived through 407 landing pages. 18 pages have 50+ leads; the other 389 pages share 31.6% of leads and convert at 8.2%.

| Page | Leads | % of wins | Conversion | 95% interval | Main channel (share of the page's leads) |
|---|---:|---:|---:|---|---|
| b76ef374 | 751 | 22.4 | 20.2% | 17.5–23.3 | unknown (71.4%) |
| 22c29808 | 726 | 22.0 | 20.5% | 17.7–23.6 | organic_search (56.9%) |
| 58326e62 | 495 | 3.2 | **4.4%** | 3.0–6.6 | social (93.7%), live from March |
| ce1a65ab | 346 | 6.9 | 13.6% | 10.4–17.6 | organic_search (59.8%) |
| 88740e65 | 306 | 3.1 | 6.9% | 4.5–10.3 | social (93.1%), January–March only |
| 40dec9f3 | 297 | 8.6 | 19.5% | 15.4–24.4 | paid_search (73.1%) |
| f017be4d | 224 | 2.4 | 7.1% | 4.4–11.3 | organic_search (63.8%) |
| e492ee5e | 214 | 1.2 | 3.7% | 1.9–7.2 | organic_search (39.7%) |

Pages are ids only (the data is anonymised), so we can't see what is on them. The top three pages (`b76ef374`, `22c29808`, `40dec9f3`) took 29.6% of leads and **53.0% of 90-day wins**.

Many pages serve mostly one channel, so a page's rate partly reflects its channel. Comparing pages **inside the same channel** removes that:

![Landing pages within the same channel](results/charts/06_pages_within_channel.png)

- **Organic search: 22.0% on one page, 4.7–7.0% on two others.** Page `22c29808` converts 22.0% of its 413 organic-search leads (18.3–26.3); `f017be4d` converts 7.0% (3.8–12.4) and `e492ee5e` 4.7% (1.8–11.5). The intervals don't overlap, so the gap isn't noise. The channel as a whole converts at 12.3%.
- **Paid search: `40dec9f3` converts 19.4%** of its 217 paid leads (14.6–25.1), against 12.4% for the channel.
- **Social: the page changed in March.** Page `88740e65` ran January–March at 7.0% of its social leads; `58326e62` took over from March at 4.1%. The intervals overlap (4.6–10.6 vs 2.6–6.3), so this sample can't show that the new page is worse, but it is the first thing to check for social.
- **Unknown origin is concentrated on one page.** `b76ef374` holds 536 of the 813 unknown-origin leads (65.9%) and 119 of their 157 wins, converting at 22.2%. Whatever route feeds this page is missing its tracking tag.

A page id can stand for a campaign or a target audience rather than a design, so these gaps are a reason to A/B test the weaker pages against the strong ones, not proof that the page layout causes them. Queries: [`07_landing_pages.sql`](sql/07_landing_pages.sql), [`08_pages_within_channel.sql`](sql/08_pages_within_channel.sql).

### 7. May's drop by page and by type of seller
**By page, the answer doesn't change.** Repeating Part 1's shift-share split with landing pages as the groups gives a page-mix effect of −0.40 points and a within-page effect of −3.35 points (channels: −0.41 / −3.34). The social page switch moved May's leads onto a weaker page (−0.74 points), partly offset by the old social page dropping out (+0.34) and smaller shifts elsewhere. About half the within-page fall (−1.66 points) is in the long tail of small pages, which fell from 9.4% to 4.5%; the two biggest pages also fell (`22c29808` 21.6% → 16.8%, `b76ef374` 20.8% → 17.8%). Query: [`09_may_drop_by_page.sql`](sql/09_may_drop_by_page.sql).

**By lead type, the drop is concentrated.** The sales rep records a lead type only when a deal is won, so a conversion rate per type can't be computed. Instead, each type's 90-day wins are scaled to all leads in the period; these add up to the overall rate.

![May's drop by lead type](results/charts/07_may_drop_by_lead_type.png)

| Lead type | 90-day wins (Jan–May) | Wins per 1,000 leads, Jan–Apr | May | Change | Share of the drop |
|---|---:|---:|---:|---:|---:|
| online_medium | 274 | 51.5 | 24.6 | **−27.0** | **71.9%** |
| online_big | 100 | 17.9 | 12.3 | −5.6 | 14.9% |
| online_small | 57 | 10.4 | 6.1 | −4.3 | 11.4% |
| offline | 85 | 14.7 | 12.3 | −2.4 | 6.4% |
| industry | 102 | 17.5 | 15.3 | −2.1 | 5.6% |
| online_beginner | 42 | 6.4 | 9.2 | +2.8 | −7.5% |
| online_top | 13 | 1.9 | 3.1 | +1.2 | −3.1% |
| **All** | **678** | **121.2** | **83.7** | **−37.5** | **100%** |

(5 wins with no lead type are left out of the rows but included in the total.) Mid-sized online sellers are the biggest group of wins (40.4%), and in May they signed at under half the earlier rate (32 wins against an average of 60.5 a month in January–April). The other groups changed by a few wins each. So May's problem was mostly with one kind of prospect, the established mid-sized online seller. Query: [`10_may_drop_by_lead_type.sql`](sql/10_may_drop_by_lead_type.sql).

### 8. What the funnel signs: business segments of won deals
Of the 781 sellers signed from the 2018 cohorts, the top 6 of 33 segments make up 56.2%: home décor (12.3%), health & beauty (11.4%), car accessories (9.0%), construction tools / house & garden (7.9%), household utilities (7.9%) and audio/video electronics (7.7%). 28.6% of all signed sellers are manufacturers and the rest resellers, but this varies a lot by segment: 55.2% in home décor against 14.3% in car accessories, 8.3% in audio/video and none of 31 in computers. 54.5% of these wins closed within 14 days; audio/video closed slower (43.3% within 14 days, 60 wins). Segment counts are small, so these are a profile for Part 3 rather than findings to act on alone. Query: [`11_won_segments.sql`](sql/11_won_segments.sql).

### 9. After the deal: fewer than half of signed sellers start selling
![Time to first sale](results/charts/08_time_to_first_sale.png)

Of the 643 sellers signed from December 2017 to May 2018:

| Milestone after the deal | Sellers | % of signed sellers |
|---|---:|---:|
| first sale within 7 days | 13 | 2.0 |
| within 14 days | 41 | 6.4 |
| within 30 days | 108 | 16.8 |
| within 60 days | 204 | 31.7 |
| within 90 days | 277 | **43.1** |
| first sale after day 90 (before 2018-08-22) | 55 | 8.6 |
| no sale in the order data | 311 | **48.4** |

- **Getting to the first sale is slow.** Among sellers who sold within 90 days, the median first sale came 39 days after the deal. Deals close fast (Part 1: most within two weeks), but revenue starts about five weeks later.
- **Nearly half never show a sale.** 311 sellers (48.4%) had no order by 2018-08-21, even though each had at least 90 days. Some may sell in orders missing from the public data (see Limitations), so treat 43.1% as a lower bound, but a gap this large is worth checking against Olist's internal seller data.
- **By month signed**, 38.9–51.0% sold within 90 days (May: 51.0% of 100). The 90-day sales value of the 277 active sellers was R$328,038, with a median of R$324 per active seller. One seller made 23.1% of it, and 56.4% of February's, so sales-value totals swing with single accounts; the activation rate is the steadier measure.

Queries: [`12_seller_activation.sql`](sql/12_seller_activation.sql), [`13_time_to_first_sale.sql`](sql/13_time_to_first_sale.sql).

### 10. Which channels and kinds of seller start selling
![Activation by channel and lead type](results/charts/09_activation_by_group.png)

| Channel | Signed sellers | Sold ≤ 90 days | 95% interval | Lead → deal (Part 1) | Selling sellers per 1,000 leads | Share of 90-day sales value |
|---|---:|---:|---|---:|---:|---:|
| organic_search | 202 | 39.1% | 32.6–46.0 | 12.3% | 48.0 | 27.3% |
| unknown | 147 | 40.1% | 32.6–48.2 | 19.3% | **77.5** | 38.1% |
| paid_search | 140 | **55.0%** | 46.7–63.0 | 12.4% | **68.4** | 22.6% |
| social | 54 | 42.6% | 30.3–55.8 | 5.2% | 22.3 | 3.9% |
| direct_traffic | 49 | 44.9% | 31.9–58.7 | 12.9% | 57.9 | 2.7% |
| smaller channels (pooled) | 51 | 33.3% | 22.0–47.0 | 6.8% | 22.7 | 5.3% |

"Selling sellers per 1,000 leads" multiplies the channel's lead-to-deal rate (Part 1, 2018 cohorts) by its activation rate. The two rates come from overlapping but not identical groups, so it's an estimate.

- **Paid search beats organic search once selling is counted.** The two channels sign leads at the same rate, but paid-search sellers start selling more often (55.0% vs 39.1%; the intervals only just don't overlap: organic up to 46.0%, paid from 46.7%). Per 1,000 leads that's about 68 selling sellers vs 48.
- **Social's problem is the lead step, not the sellers.** Social sellers who sign start selling at about the average rate (42.6%, interval 30.3–55.8), so social stays near the bottom (~22 per 1,000 leads) mainly because few of its leads sign.
- **Unknown-origin leads stay the most valuable** (~78 selling sellers per 1,000 leads) and carry 38.1% of the 90-day sales value, though one seller makes 60.5% of that channel's total. This makes the tracking fix (recommendation 7) more urgent.

| Lead type | Signed sellers | Sold ≤ 90 days | 95% interval | Active sellers' median sales | Share of 90-day sales value |
|---|---:|---:|---|---:|---:|
| online_medium | 263 | 46.4% | 40.5–52.4 | R$260 | 26.9% |
| online_big | 95 | **63.2%** | 53.1–72.2 | **R$821** | **46.9%** |
| industry | 90 | 35.6% | 26.4–45.9 | R$189 | 4.9% |
| offline | 80 | **23.8%** | 15.8–34.1 | R$190 | 2.2% |
| online_small | 62 | 38.7% | 27.6–51.2 | R$295 | 6.3% |
| online_beginner | 37 | 32.4% | 19.6–48.5 | R$409 | 3.2% |
| other types (pooled) | 16 | 50.0% | 28.0–72.0 | R$323 | 9.6% |

- **`online_big` sellers are 14.8% of signed sellers but 46.9% of the 90-day sales value.** They are the most likely to start selling (63.2%), and an active one sells a median of R$821 in 90 days, about 3× an `online_medium` seller. One of them makes 49.2% of the group's total, but the activation rate and median barely depend on it.
- **Offline and industry sellers sign but rarely start selling.** Only 23.8% of `offline` and 35.6% of `industry` sellers made a sale within 90 days; their intervals sit below `online_big`'s. One plausible reason is that businesses without an online shop need more help to list products, an onboarding cost the deal doesn't show; that is a hypothesis to check with the onboarding team.
- **May's missing sellers were average sellers.** `online_medium`, the type behind most of May's drop (section 7), starts selling at 46.4%, close to the 43.1% average.

Queries: [`14_activation_by_channel.sql`](sql/14_activation_by_channel.sql), [`15_activation_by_lead_type.sql`](sql/15_activation_by_lead_type.sql).

## So what for the business (so far)
1. **Rebalance social and email towards search.** They supply nearly a quarter of leads but a tenth of sellers. Either cut spend, or add a qualification step (form questions, a self-serve check) so SDRs don't spend time on leads that rarely sign. *Owner: marketing lead.*
2. **Fix lead-source tracking before judging channel ROI.** A quarter of signed sellers have no channel, so every channel's cost per seller is wrong today. *Owner: marketing ops.*
3. **Front-load sales follow-up.** Most wins happen in the first 14 days; a lead untouched in that window is losing its best odds. *Owner: SDR team lead.*
4. **Treat May as a sales-side alert, but look at process before headcount.** Lead quality per channel didn't explain the fall, and the rep count dipped only slightly (15, against 16–20), so check follow-up speed and lead handling first. Lead contact dates would settle it. *Owner: sales manager.*
5. **Reduce reliance on the top reps.** The top 5 of 21 reps won half of 2018's wins. Pair them with other reps on large leads, and track win volume by rep so that a departure is visible early. *Owner: sales manager.*
6. **A/B test the weak landing pages against the strong ones.** Within organic search, page `22c29808` converts about 3–5× better than `f017be4d` and `e492ee5e`. Route part of the weak pages' traffic to the strong page (or copy its form and pitch) and compare. Check the March social page switch (`88740e65` → `58326e62`) the same way. *Owner: marketing / web team.*
7. **Start the tracking fix with page `b76ef374`.** It carries two thirds of the unknown-origin leads and three quarters of their wins, so finding out what links to it should recover most of the missing attribution. *Owner: marketing ops.*
8. **Review how mid-sized online sellers were handled in May.** They account for 72% of May's fall in wins per lead. Look at what changed for them (pitch, pricing or terms, which reps they went to) before treating May as a general slowdown. *Owner: sales manager.*

9. **Measure the funnel to the first sale, not to the signature.** Only 43.1% of signed sellers sold within 90 days, and the median first sale came 39 days after the deal. Add "first sale within 30/90 days" to the sales and marketing scorecards, and have onboarding contact every seller with no sale by day 30 (most of them: 83.2%), starting with the lead types least likely to sell (recommendation 11). *Owner: head of sales / seller onboarding.*
10. **Value paid search on selling sellers.** It signs leads at the same rate as organic search but brings ~68 vs ~48 selling sellers per 1,000 leads. Judge its budget on that, not on signatures. *Owner: marketing lead.*
11. **Give offline and industry sellers an onboarding track, or qualify them harder.** Only 23.8% and 35.6% of them start selling within 90 days, against 63.2% of big online sellers. Either help them list (catalogue upload, photos) or weigh lead type when prioritising follow-up. *Owner: sales manager / seller onboarding.*

These are first-pass recommendations. The final set will be ranked once Part 3 is done.

## How to run
```bash
python -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -r requirements.txt
python scripts/download_data.py        # ~34 MB (funnel + orders), hash-checked
python -m pipeline.build_db            # DuckDB + data-quality checks
python -m report.build                 # results/REPORT.md, CSVs, charts
pytest                                 # offline tests on a fixture database
```

## Roadmap
- [x] Part 1: conversion by month and channel, time to close, May drop decomposition
- [x] Part 2a: sales-team capacity (reps with a win per cohort, wins per rep, rep concentration)
- [x] Part 2b: landing pages (within-channel comparison with 95% intervals, May split by page) and the profile of won deals (lead type, business segment)
- [x] Part 3a: after the deal: won sellers joined to the [Olist e-commerce orders](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) by `seller_id`; 90-day activation, time to first sale, and activation by channel and lead type
- [ ] Part 3b: activation by business segment and landing page, and whether fast-closing deals become better sellers
- [ ] Final TL;DR, ranked recommendations with owners, limitations

## Limitations (so far)
- **One channel per lead.** Olist notes a lead may have come from several sources; the data records one origin.
- **Reps are visible only through their wins.** Win rates by rep can't be measured, and the rep counts are a lower bound (see Part 2).
- **Lead type and segment only for wins.** They are recorded when a deal is won, so Part 2b describes the sellers who signed and scales wins to all leads; it can't give a conversion rate per type or segment.
- **Pages are anonymous ids.** The data says which page a lead used, not what was on it, so page gaps can't be pinned on design.
- **Won deals only.** There is no record of lost deals or SDR contact dates, so the funnel has two measurable steps (lead → signed), not every stage.
- **A sample.** The 8,000 leads are Olist's random sample of its MQLs, so counts are a fraction of the real volume; rates are what matter.
- **2017 excluded** from rates because the deal records start in December 2017 (see Data).
- **The public order data may not be complete.** It holds ~99k orders and isn't documented as a complete record of every order on the marketplace, so "no sale" means no sale in this data. Activation rates are a lower bound, and the comparison between groups is more reliable than the level.
- **Sales value is concentrated.** One seller makes 23.1% of the 90-day sales value, so totals and shares by group move with single accounts. Part 3 leans on activation rates and medians for that reason.
- **A fixed 90-day window.** Sellers signed after 2018-05-23 can't be followed for 90 days before the order data thins out, so Part 3 covers sellers signed December 2017 to May 2018 (including 31 from 2017 leads).
