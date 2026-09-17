# Contract Alpha — Data Feasibility Report

Audit date: **2026-09-17**

Decision: **GO — scoped to a 2020–2025, baseline-based study**

## Executive decision

Enough real, linkable data exists to proceed to Phase 2 for a bounded study of recent MLB free-agent contracts. The verified source set supports a material-contract cohort of **471 contracts across six completed signing classes** with strong pre/post player-season coverage.

This is not an unconditional green light for the full proposed design:

- The live contract tracker exposes 2020–2026, not the preferred 10–20+ offseasons.
- Its current public payload retains **no historical projection WAR for the completed 2020–2025 classes**.
- Exact annual salary cash flows, options, deferrals, and retained salary are not available consistently in the audited core source.

Therefore Phase 2 may build the contract/performance master table using pre-signing historical baselines and clearly labeled AAV cost approximations. It may not claim a projection-based fair-price model, present-value cash-flow precision, or a 10–20 year historical result until those inputs are licensed or otherwise sourced reproducibly.

## Reproducible audit universe

The script queried the public FanGraphs tracker for every supported class and joined FanGraphs player IDs to the public leaderboards for 2016–2025. The 2026 season is in progress, so 2026 signings are included in source-coverage counts but excluded from realized-outcome coverage.

| Measure | Count |
|---|---:|
| Tracker rows, 2020–2026 | 2,017 |
| Rows with a signing team | 1,672 |
| Signed rows with positive years, guarantee, and AAV | 1,281 |
| Complete positive-value rows, completed classes 2020–2025 | 1,078 |
| Provisional primary screen, guarantee ≥ $5M, 2020–2025 | 471 |

“Rows” means contract records, not unique players. The positive-value 2020–2025 universe contains 24 player/offseason groups with more than one contract, generally because a player signed again after being released. No duplicate player/offseason group remains at the $1 million, $5 million, or $25 million screens. Each contract ID remains the observation unit.

## Coverage by signing class

| Start year | Tracker rows | Signed | Complete terms | Guarantee ≥ $5M | Prior-year WAR present | Historical projection present | Crowd estimate present |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 269 | 173 | 156 | 64 | 251 | 0 | 73 |
| 2021 | 333 | 289 | 213 | 65 | 277 | 0 | 85 |
| 2022 | 265 | 217 | 164 | 85 | 250 | 0 | 0 |
| 2023 | 274 | 243 | 170 | 96 | 251 | 0 | 78 |
| 2024 | 301 | 253 | 183 | 77 | 271 | 0 | 75 |
| 2025 | 280 | 245 | 192 | 84 | 262 | 0 | 95 |
| 2026 | 295 | 252 | 203 | 75 | 268 | 249 | 95 |

Prior-year WAR and projection/crowd counts above use all tracker rows in that class. The row-level inferential universe applies the complete-terms and eligibility rules below.

## Pre- and post-contract performance coverage

Among the **1,078** complete positive-value contracts in completed classes:

| Coverage test | Count | Percent |
|---|---:|---:|
| Observed contract-year player-season row | 1,011 | 93.8% |
| Observed rows in all three pre-contract seasons | 924 | 85.7% |
| At least one observed post-signing row | 1,051 | 97.5% |
| Observed row in every elapsed contract season | 1,017 | 94.3% |
| Historical projected WAR retained in tracker | 0 | 0.0% |
| Crowd years and AAV both present | 366 | 34.0% |

Among the **471** contracts in the provisional $5 million primary screen:

| Coverage test | Count | Percent |
|---|---:|---:|
| Observed contract-year player-season row | 443 | 94.1% |
| Observed rows in all three pre-contract seasons | 412 | 87.5% |
| At least one observed post-signing row | 466 | 98.9% |
| Observed row in every elapsed contract season | 434 | 92.1% |

A missing leaderboard row is not automatically missing data. It can mean the player made no MLB appearance that season, which is potentially an economically important outcome. Phase 2 must verify the roster/availability state before converting a missing row to zero WAR and zero PA/IP.

## Hitter/pitcher split

The completed-class, complete-contract universe contains:

| Role | Contracts | Share |
|---|---:|---:|
| Pitchers | 603 | 55.9% |
| Hitters | 474 | 44.0% |
| Two-way | 1 | 0.1% |

The two-way record requires combined batting and pitching treatment; it must not be forced into an ordinary hitter-only or pitcher-only model.

## Age distribution

Age is present for all 1,078 completed-class complete contracts. The range is **23–43**, with median **32**.

| Age band | Contracts | Share |
|---|---:|---:|
| ≤26 | 13 | 1.2% |
| 27–29 | 160 | 14.8% |
| 30–32 | 408 | 37.8% |
| 33+ | 497 | 46.1% |

The concentration at older ages makes continuous age adjustment and nonlinear age effects essential. The ≤26 group is too small to support a standalone band estimate without pooling or regularization.

## Contract-value distribution

For the 1,078 complete contracts in completed classes, nominal guarantees have:

- minimum: **$19,892**
- 25th percentile: **$1.21M**
- median: **$3.25M**
- 75th percentile: **$12.0M**
- 90th percentile: **$34.15M**
- maximum: **$765M**

| Nominal guarantee | Contracts | Share |
|---|---:|---:|
| <$1M | 175 | 16.2% |
| $1M–<$5M | 432 | 40.1% |
| $5M–<$25M | 326 | 30.2% |
| $25M–<$75M | 92 | 8.5% |
| $75M–<$150M | 29 | 2.7% |
| $150M+ | 24 | 2.2% |

The long right tail argues for log-dollar targets, robust errors, median error, and contract-size sensitivity analyses. Nominal guarantees must not be compared across eras without a baseball-labor-market adjustment.

## Missingness in signed tracker rows

Across 1,672 rows with a signing team:

| Variable | Missing | Percent |
|---|---:|---:|
| Player ID | 0 | 0.0% |
| Player name | 0 | 0.0% |
| Position | 2 | 0.1% |
| Age | 0 | 0.0% |
| Prior team | 0 | 0.0% |
| Signing team | 0 | 0.0% |
| Contract years | 7 | 0.4% |
| Positive guarantee | 389 | 23.3% |
| Positive AAV | 391 | 23.4% |
| Contract-year WAR | 132 | 7.9% |
| Projection WAR | 1,439 | 86.1% |
| Crowd years | 1,206 | 72.1% |
| Crowd AAV | 1,206 | 72.1% |

The projection missingness is structural by class: 2020–2025 are empty in the current public tracker payload, while 249 of 295 current 2026 tracker rows (84.4%) contain projected WAR.

## Eligibility rules after inspecting the distribution

### Contract universe

A record is complete when it:

1. appears on the FanGraphs Free Agent Tracker;
2. has a signing team;
3. has positive actual years, guarantee, and AAV; and
4. has a stable FanGraphs player ID.

The primary hypothesis cohort additionally requires:

5. contract start year 2020–2025;
6. nominal guarantee of at least $5 million;
7. an observed contract-year row; and
8. sufficient pre-contract history for the chosen baseline specification.

The $5 million screen is provisional but defensible: it follows inspection of the highly concentrated low-value tail, focuses the analysis on material capital commitments, retains 471 contracts, and eliminates same-player/same-offseason repeat-contract groups in this snapshot. Every major result must be rerun on all positive guarantees, ≥$1M, and ≥$25M cohorts. A later cross-era extension must inflation-adjust the screen.

International entrants without prior MLB performance cannot answer the MLB contract-year-spike question and should be excluded from that regression, although they may remain in descriptive pricing tables.

## Source register

### Accepted core sources

1. **[FanGraphs RosterResource Free Agent Tracker](https://www.fangraphs.com/roster-resource/free-agent-tracker?season=2025&pos=all)**

   Verified live seasons: 2020–2026. Relevant fields: FanGraphs player ID, age, position, prior/signing teams, prior-year WAR, crowd estimates where populated, years, guarantee, and AAV. The public page is reproducible, but its Excel download is members-only. Historical projection cells are not retained for 2020–2025.

2. **[FanGraphs Major League Leaderboards](https://www.fangraphs.com/leaders/major-league)**

   Verified player-ID joins for 2016–2025. Relevant fields include WAR, PA, wRC+, IP, FIP, ERA-, FIP-, and strikeout/walk measures. FanGraphs documents leaderboard export behavior in its [leaderboard guide](https://library.fangraphs.com/how-to-use-fangraphs-leaderboards/).

### Conditional or validation-only sources

3. **[FanGraphs Projections](https://www.fangraphs.com/projections?stats=bat&team=0&type=steamer)**

   The page lists historical ZiPS (2010–2025) and Steamer (2012–2025) archives as members-exclusive. These could create an excellent projection specification if a membership/license permits reproducible project use, but they are not a public fallback.

4. **[Steamer pre-season projection archive](https://steamerprojections.com/index.php/projections/pre-season-projections)**

   The public index lists preseason files back to at least 2017, but download/login behavior was not verifiably anonymous and stable. Do not treat it as the core fallback without written access and redistribution terms.

5. **[Baseball-Reference free-agent pages](https://www.baseball-reference.com/leagues/majors/2024-free-agents.shtml)**

   Useful for human validation of signings and post-signing performance. The page defines signings as those within six months of free agency, but does not supply a complete bulk contract-value history. Automated access returned HTTP 403 during the audit. Sports Reference's [data-use policy](https://www.sports-reference.com/data_use.html) requires care and permission for database/app uses, so it is not an automated core source.

6. **[Baseball-Reference salary information](https://www.baseball-reference.com/about/salary.shtml)**

   Documents historical salary provenance and complex cases such as released players paid by a former team. Useful conceptually and for manual QA, not accepted for bulk ingestion without permission.

7. **[Spotrac MLB contracts](https://www.spotrac.com/mlb/contracts)**

   Provides contract values and salary breakdowns, but is a commercial source. Use only for manual validation or under a license; the project must not depend on unlicensed scraping.

8. **[The Baseball Cube contracts](https://www.thebaseballcube.com/content/contracts/)**

   Broad public history and CSV references are promising, but a displayed zero can mean either a minimum salary or unavailable value. It is not precise enough to replace the core contract source without validation.

## Can the market-value methodology be constructed?

**Yes, with constraints.** The verified contract records and pre-signing performance support an offseason-aware pricing model using only information known at signing. For the initial six-class study:

- estimate expected performance from lagged MLB history, age, playing time, rate stats, and role;
- model AAV, guarantee, and years separately;
- use offseason fixed effects or partial pooling rather than fitting an unstable standalone $/WAR slope to every small annual cohort;
- validate strictly forward in time; and
- compare against simple age + expected-WAR and expected-WAR × market-price baselines.

Historical public projections cannot be the primary feature. A projection specification is a conditional robustness check.

## Can realized contract alpha be constructed?

**Provisionally.** Realized WAR and elapsed seasons are highly observable. Cost is less precise:

- the tracker provides headline guarantee and AAV;
- exact annual cash flow is incomplete;
- options, buyouts, opt-outs, traded salary, and deferrals require structured contract terms;
- Ohtani-style deferrals make headline AAV economically misleading.

The first alpha version may use **AAV × elapsed seasons**, labeled as an approximation, with special-contract flags. A production finance mode needs licensed annual cash flows and present-value rules before publication.

## Phase 2 acceptance criteria

Proceed only if the master-table build can demonstrate all of the following:

- one auditable contract ID per observation;
- deterministic player-ID joins;
- explicit treatment of no-appearance seasons;
- hitter/pitcher and two-way handling;
- no post-signing fields in expected-performance or price models;
- an options/deferrals/manual-review flag;
- source snapshots or hashes permitted by source terms;
- contract counts that reconcile to this audit or explain every change; and
- documented permission/licensing before any row-level public redistribution or deployed app.

## Bottom line

The project clears the data gate for a serious **recent-era, baseline-based** study. It does not yet clear the gate for the full historical and projection-rich version. The honest next step is Phase 2 on the 2020–2025 cohort while pursuing authorized historical projections and annual cash-flow data in parallel—not frontend development.

## Phase 1 dashboard boundary

After this audit cleared the scoped data gate, the repository added a read-only aggregate feasibility dashboard. The dashboard visualizes only the committed tables described in this report. It does not fetch source data at startup, expose player-level records, implement an estimator, or make a baseball-market claim. This interface is a transparent view of the audit—not a substitute for Phase 2 construction and validation.
