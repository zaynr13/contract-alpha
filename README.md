# Contract Alpha

**Did teams pay for sustainable talent—or for the perfect contract year?**

Contract Alpha treats an MLB free-agent contract as a capital-allocation decision:

> **performance → price → return**

It tests whether a player who surged immediately before free agency received a larger contract, regressed after signing, and delivered less on-field value than the team paid for.

## Current status

**The scoped 2020–2025 study is complete.** The repository contains the contract/performance panel builder, contract-year signal, temporally validated pricing benchmarks, realized-alpha valuation, formal research tests, sensitivity analyses, tests, documentation, and a findings-led Streamlit product.

The public app reads precomputed transformed outputs; it does not scrape or train at startup. The full contract-level panel remains local and git-ignored pending source-data redistribution permission.

- [Live app](https://mlbcontract.streamlit.app/)
- [Methodology and results](docs/methodology.md)
- [Phase 1 feasibility report](docs/data-feasibility-report.md)

## Question

The study answers four linked questions:

1. Does a contract-year performance spike predict a larger guarantee?
2. Does that spike predict subsequent performance regression?
3. Does it predict lower realized on-field contract alpha?
4. Does a larger baseline-price residual predict lower realized alpha?

The analysis is descriptive. It does not assume or claim that contract-year performance causes a club to overpay.

## Why it matters

An MLB club committing $50 million, $150 million, or $300 million is making a large investment under uncertainty. Recent performance may contain genuine information, noise, changed playing time, or all three. Contract Alpha connects the player signal to the price paid and the return subsequently realized rather than stopping at salary prediction.

## Data

- FanGraphs RosterResource Free Agent Tracker for contracts, player IDs, roles, ages, and teams.
- FanGraphs Major League Leaderboards for player-season WAR, PA/IP, wRC+, and FIP-.
- 2020–2025 free-agent signing classes; outcomes realized through 2025.
- 844 research contracts with at least a $1 million guarantee.
- 465 contracts in the primary $5 million screen; 434 are modelable.

True free-agent deals are retained. Extensions, option modifications, unsigned records, incomplete contract terms, and sub-$1 million contracts are excluded. Public historical projections were not available for the verified window, so expected ability uses a transparent pre-signing historical baseline.

## Contract-Year Trap

The signal is not raw contract-year WAR. It compares the contract year with a 50% / 30% / 20% weighted average of the prior three seasons:

```text
Performance spike = contract-year WAR − sustainable baseline WAR
```

The pipeline also separates rate-performance from playing-time change, normalizes 2020 counting statistics to a 162-game equivalent, and computes empirical spike percentiles only within the eligible hitter/pitcher model cohort. Missing pre-contract rows are not assigned zero WAR: baseline weights are renormalized over observed rows, and unobserved seasons remain distinct from observed 0.0-WAR seasons.

A **Contract-Year Trap** is a transparent descriptive label: top-quintile spike plus negative realized alpha. Every label is accompanied by the underlying WAR, contract, cost, and value numbers.

## Contract Alpha

```text
On-field contract alpha = modeled value of realized WAR − elapsed contract cost
```

Realized production uses season-specific market dollars per WAR. Cost uses AAV across elapsed seasons, with 2020 prorated to 60/162. Active contracts are measured only through completed 2025 play. Negative WAR is retained as value destruction.

This is **on-field** alpha—not team profit. It excludes commercial revenue, postseason context, insurance, and strategic roster value.

## Methodology

Pricing benchmarks are ridge regressions using only sustainable, pre-signing information: baseline production, rate production, playing-time share, age, role, and offseason. Contract-year performance is deliberately excluded so the residual represents price relative to a sustainable baseline.

Research regressions include baseline WAR, age, age², role, and offseason fixed effects; alpha models also control for contract length. Standard errors are clustered by player. Results are repeated across guarantee screens, excluding the 2021 class, separately for hitters and pitchers, with one/two/three observed baseline seasons, and at 75%/100%/125% of the estimated market price per WAR.

The complete specification is in [docs/methodology.md](docs/methodology.md).

## Validation

Each offseason is predicted only from earlier offseasons. There is no random era-mixing and no future-performance leakage.

| Target | Forward MAE | Role-median MAE | Result |
|---|---:|---:|---|
| AAV | $4.05M | $5.24M | Beats baseline |
| Guarantee | $14.96M | $17.21M | Beats baseline |
| Contract years | 0.73 years | 0.65 years | **Fails baseline** |

Because contract length fails the simple baseline, the app does not present its predictions as decision-useful. Guarantee intervals are wide and are described as historical benchmarks—not precise player appraisals.

## App

The Streamlit app leads with the actual baseball-market findings, then provides:

- effect sizes, confidence intervals, and sensitivity tables;
- a Contract-Year Trap leaderboard;
- positive-alpha, value-destruction, and spike leaderboards;
- signing-team capital-allocation totals;
- a local full player/contract explorer with career timeline and deal economics;
- an elapsed-season cost, production-value, and alpha table for each local contract;
- expanding-window model validation; and
- complete method and limitation notes.

The hosted version exposes only transformed research outputs and curated short leaderboards under **Selected contracts**. It does not provide a searchable player database. Running the pipeline locally creates the rights-restricted panel and enables the complete **Contract explorer**.

```bash
python3 -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Findings

In the 434-contract primary modelable cohort:

- One additional contract-year spike WAR is associated with a **46.4% larger guarantee** (95% interval after transforming the log coefficient: about 40.4% to 52.7%).
- **31% persisted:** one additional spike WAR is associated with 0.309 WAR per future season (95% CI: 0.189 to 0.429). The corresponding transformation is that about 69% faded relative to the contract year; this is not a second independent estimate.
- One additional spike WAR is associated with **−$0.901 million of realized alpha per elapsed contract year** (95% CI: −$1.732M to −$0.070M) in the base valuation.
- Each $10 million baseline-price residual is associated with **−$0.417 million of alpha per year**, but the interval crosses zero (95% CI: −$0.959M to +$0.126M).

The price and persistence estimates remain similar when two or three observed baseline seasons are required. The alpha association is negative in all three baseline-history specifications, but its interval crosses zero with three full seasons. It is also uncertain after excluding the 2021 class and under the high (+25%) $/WAR scenario. The baseline-price residual is a model diagnostic—not a fair-value estimate or proof of overpayment. The defensible conclusion is narrow: the market strongly priced recent spikes, most of the incremental spike did not persist, and the base valuation associates larger spikes with weaker realized on-field returns.

## Limitations

- Six signing classes are a short sample.
- Historical public projections are unavailable for the verified period.
- AAV omits salary structure, deferrals, options, trades, retained salary, and buyouts.
- Active contracts are right-censored and evaluated only to date.
- WAR and $/WAR are modeled on-field value, not literal revenue.
- Postseason production and star commercial value are excluded.
- The pricing model improves population-level error but remains imprecise for individual stars.
- Guarantee validation is especially weak for $100M+ deals (27 observations; $122.2M median absolute error; 37.0% empirical interval coverage).
- The results are associations, not causal estimates of front-office bias.
- Source rights limit public redistribution of the full row-level panel.

## Reproduction

Python 3.9+ is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
PYTHONPATH=src python3 scripts/run_data_audit.py
PYTHONPATH=src python3 scripts/run_phase2.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

`run_phase2.py` writes public aggregate and transformed outputs to `data/processed/public/` and the full local research panel to the ignored `data/processed/private/` directory.

## Repository map

```text
contract-alpha/
├── data/processed/
│   ├── public/                 # committed aggregates and transformed leaderboards
│   └── private/                # local row-level panel; git-ignored
├── docs/
│   ├── data-feasibility-report.md
│   └── methodology.md
├── scripts/
│   ├── run_data_audit.py
│   └── run_phase2.py
├── src/contract_alpha/
│   ├── analysis.py
│   ├── audit.py
│   └── ingestion/fangraphs.py
├── tests/
├── streamlit_app.py
└── requirements.txt
```
