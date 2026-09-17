# Contract Alpha methodology

## Research design

Contract Alpha studies MLB free-agent contracts as capital-allocation decisions:

```text
pre-signing performance → contract price → realized on-field return
```

The study is descriptive. It asks whether recent performance spikes were priced and whether those deals subsequently produced less on-field value. It does not identify a causal effect of a spike on a club's decision.

## Sources and study period

- Contract terms and player identifiers: FanGraphs RosterResource Free Agent Tracker.
- Regular-season performance: FanGraphs Major League Leaderboards.
- Signing classes: 2020–2025.
- Realized performance: through the completed 2025 regular season.

The live tracker does not retain usable historical projections for this window. Expected performance therefore uses a transparent historical baseline rather than a projection archive. Crowd estimates are not used.

## Cohorts

The research universe contains 844 free-agent contracts with a nominal guarantee of at least $1 million. The primary screen contains 465 contracts with at least a $5 million guarantee. A modelable primary observation must also have:

- an observed MLB contract-year row;
- at least one observed season in the prior-three-year window; and
- a hitter or pitcher role.

That produces 434 primary modelable contracts. Extensions, option modifications, unsigned players, and incomplete contract terms are excluded. The analysis repeats key models at $1 million and $25 million thresholds, without the 2021 class, and separately for hitters and pitchers.

## Performance signal

For a contract beginning in year `t`, the contract year is `t − 1`. The sustainable baseline is:

```text
Baseline WAR = weighted mean of observed WAR(t−2), WAR(t−3), and WAR(t−4)
Performance spike = contract-year WAR − baseline WAR
```

The nominal weights are 0.50, 0.30, and 0.20. If a pre-contract MLB row is unobserved, its weight is removed and the remaining weights are renormalized; it is not silently assigned 0.0 WAR. The data separately record unobserved baseline seasons and observed seasons with 0.0 WAR. The primary model requires at least one observed baseline season, and sensitivity models require at least two or all three.

The 2020 season is multiplied by 162/60 when used in signal construction. This makes its counting-stat contribution comparable with a normal season. The exclusion-of-2021 sensitivity removes contracts for which 2020 was the contract year.

The pipeline also decomposes the spike into:

- a rate component based on WAR per 600 PA for hitters or WAR per 180 IP for pitchers; and
- a playing-time component based on the change in PA or IP from the weighted baseline.

Percentiles are empirical within hitter/pitcher role and only among contracts eligible for the performance models. A 93rd-percentile spike means the player's improvement relative to baseline exceeded 93% of the relevant modelable free agents in that role.

## Pricing benchmark

The pricing model predicts AAV, guarantee, and years from information available before signing:

- baseline WAR;
- baseline rate WAR;
- baseline playing-time share;
- age and age²;
- hitter/pitcher role and an interaction with baseline WAR;
- signing-offseason index; and
- observed baseline-season count.

It intentionally excludes contract-year performance. The residual therefore asks how far the actual price sat above or below a sustainable-baseline benchmark. It is not a claim that the model captures every legitimate input available to a club.

Models are regularized ridge regressions on log-transformed targets. Validation is strictly forward: each offseason is predicted using only earlier offseasons. The first class is not scored. Prediction ranges are empirical 10th–90th percentile training-residual intervals, not formal individual confidence intervals.

The AAV and guarantee models beat a role-median baseline. The contract-length model did not, so its predictions are retained only for audit transparency and are not shown as decision-useful outputs.

## Market price per WAR

For each signing offseason, the market price of a win is the median winsorized ratio of AAV to sustainable baseline WAR among primary contracts with at least 0.75 baseline WAR. Ratios are capped at the offseason 10th and 90th percentiles before the median is calculated. This avoids imposing one fixed dollar value across the whole study window. Every value result is recalculated at 75%, 100%, and 125% of these rates, including contract alpha, team totals, category counts, and leaderboard stability.

## Realized on-field value

For each elapsed contract season:

```text
Production value = FanGraphs WAR × that season's estimated market $/WAR
Realized cost = AAV × elapsed-season factor
On-field contract alpha = production value − realized cost
Alpha ROI = contract alpha / realized cost
```

Only elapsed seasons through 2025 are included. A 2020 elapsed season uses 60/162 of AAV as an approximate cost. Negative WAR is retained and therefore destroys modeled value. Cost per WAR is undefined for zero or negative cumulative WAR rather than being displayed as an absurd ratio.

The cost measure is approximate. It does not allocate deferrals, retained salary after trades or releases, option buyouts, bonuses, or annual salary structure. Accordingly, the metric is **on-field contract alpha**, not team profit or total player economic value.

## Statistical tests

All primary regressions include age, age², baseline WAR, hitter/pitcher role, and offseason fixed effects. Alpha models also control for contract length. Standard errors are clustered by player because the same player can sign more than one contract.

The four principal questions are:

1. Does spike WAR predict log guaranteed dollars?
2. Does spike WAR predict the change from contract-year WAR to future WAR per season?
3. Does spike WAR predict realized alpha per elapsed contract year?
4. Does the sustainable-baseline guarantee residual predict realized alpha per elapsed year?

The second question also reports a persistence model with future WAR per season as the outcome. Its coefficient is the primary result: how much of one incremental spike WAR persisted after signing. The regression-from-contract-year coefficient equals persistence minus one, so “69% faded” is a transformation of the 31% persistence estimate, not an independent finding.

## Main results

Primary estimates use 434 contracts unless the forward price residual is required, in which case 376 contracts are available.

| Question | Effect estimate | 95% confidence interval | Interpretation |
|---|---:|---:|---|
| Spike → guarantee | +0.381 log points | +0.339 to +0.423 | About 46.4% larger guarantee per +1 spike WAR |
| Spike → persistence | +0.309 WAR/year | +0.189 to +0.429 | About 31% of an incremental spike WAR persisted |
| Spike → regression | −0.691 WAR/year | −0.811 to −0.571 | Corresponding transformation: about 69% faded |
| Spike → alpha | −$0.901M/year | −$1.732M to −$0.070M | Lower realized on-field return in the base valuation |
| $10M baseline-price residual → alpha | −$0.417M/year | −$0.959M to +$0.126M | Directionally negative but statistically uncertain overall |

The price and persistence estimates are stable when the analysis requires one, two, or three observed baseline seasons. The alpha estimate is −$0.881M/year with two seasons and −$0.805M/year with three, but the three-season interval crosses zero. At 75%/100%/125% of estimated $/WAR, the alpha estimate is −$1.278M/−$0.901M/−$0.525M per year; the high-scenario interval crosses zero. The alpha result is also uncertain after excluding the 2021 class. Role splits show a clear negative baseline-residual association for pitchers but not hitters. These qualifications are part of the result, not footnotes to it.

## Pricing validation by contract size

Forward guarantee errors rise sharply with deal size. For $100M+ contracts, only 27 forward-scored observations are available; median absolute error is $122.2M, median absolute percentage error is 78.5%, and the empirical prediction interval covers 37.0%. The corresponding figures are materially better for the $5M–<$25M band (262 observations; $5.1M median absolute error; 53.1% median absolute percentage error; 84.0% coverage). Extreme residuals should therefore be read as evidence that the simple benchmark misses important information—not as definitive proof that a club overpaid.

## Leaderboard definitions

- **Contract-year trap:** top-quintile role-specific spike and negative realized alpha.
- **Sustainable breakout:** top-quintile spike and non-negative realized alpha.
- **Positive alpha:** positive realized alpha outside the breakout label.

These are transparent descriptive categories. They do not prove that a club was irrational or that the contract-year spike caused the outcome.

Signing-team totals sum primary-cohort guarantees, elapsed costs, production values, and realized alpha. They are provided as capital-allocation context, not as a front-office-quality estimate: teams spend at different levels, inherit different competitive constraints, and have differently censored contract portfolios.

## Limitations

- Six signing classes are a short historical window.
- Historical public projections are unavailable for the verified cohort.
- AAV is an imperfect proxy for annual team cost.
- Active contracts are right-censored and should be read as realized-to-date only.
- WAR and $/WAR are models of regular-season on-field value, not literal revenue.
- Postseason performance, star commercial value, strategic roster value, and insurance are not included.
- Injury risk is part of realized contract risk but is not separately identified.
- Defense and pitcher WAR contain measurement uncertainty.
- The pricing benchmark is useful at the population level but imprecise for individual stars.
- No result should be interpreted causally.

## Reproduction and public-data boundary

Run `PYTHONPATH=src python3 scripts/run_phase2.py` to rebuild the research outputs. The script writes aggregate results and short transformed leaderboards to `data/processed/public/`. The full contract panel and timelines are written to the git-ignored `data/processed/private/` directory.

FanGraphs retains rights in its data and currently restricts unauthorized reproduction and publication. The repository therefore does not commit the complete row-level source-derived panel. Anyone refreshing, redistributing, or commercializing the data should review the current source terms and obtain any required permission.
