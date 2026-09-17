# Contract Alpha

**Did teams pay for sustainable talent—or for the perfect contract year?**

Contract Alpha treats an MLB free-agent contract as a capital-allocation decision:

> **performance → price → return**

The research question is whether an unusually strong pre-free-agency season predicts a larger contract, more subsequent regression, and lower realized **on-field** contract alpha.

## Current status

**Phase 1 data audit complete — scoped GO. No application or estimator has been built.**

The verified public-source design supports a useful 2020–2025 study, not yet the preferred 10–20 offseason study. The audited primary screen contains 471 contracts with guarantees of at least $5 million. Historical public projection coverage is the principal blocker to the projection-based specification.

Read the full [data feasibility report](docs/data-feasibility-report.md).

## Question

The eventual research program will test:

1. Does a contract-year performance spike predict a price premium?
2. Does that spike predict subsequent performance regression?
3. Does it predict lower realized on-field contract alpha?
4. Does model-estimated overpayment predict lower realized alpha?

No causal claim is assumed. A null or subgroup-specific result is valid.

## Data

The Phase 1 audit uses:

- FanGraphs RosterResource Free Agent Tracker pages for contract records, ages, positions, teams, prior-season WAR, and partially populated crowd/projection fields.
- FanGraphs major-league leaderboards for player-season WAR, playing time, and rate statistics, joined with FanGraphs player IDs.

Only aggregate audit outputs are committed. Source-level payloads and a redistributable master dataset are intentionally excluded pending data-rights review. Baseball-Reference is documented as a potential manual validation source, not scraped into the product.

## Contract-Year Trap

The planned signal is not raw contract-year WAR alone. It will compare contract-year performance with a pre-signing baseline, distinguish playing-time change from rate-performance change, and model hitters and pitchers separately.

Historical public projection data are absent from the verified 2020–2025 tracker payloads, so the initial expected-performance specification must be a transparent pre-signing historical baseline. A projection-based robustness check remains conditional on licensed or otherwise authorized historical archives.

## Contract Alpha

The eventual primary outcome is:

```text
On-Field Contract Alpha = modeled value of realized WAR − realized contract cost
```

It is not total financial profit. WAR does not capture sponsorships, attendance, merchandise, international exposure, postseason context, or every strategic reason a club signs a player.

## Methodology

Phase 1 defines a complete contract record as a signed tracker row with positive years, guarantee, and AAV. The recommended primary research screen is a nominal guarantee of at least $5 million, with all-positive, $1 million, and $25 million screens retained as sensitivity analyses.

The $5 million screen was chosen only after examining the distribution. It retains 471 contracts across six completed signing classes, removes all duplicate player/offseason groups present in the positive-value universe, and focuses the test on material capital commitments. It is not treated as a natural law, and later work must test sensitivity to the screen and to baseball-market inflation.

## Validation

The audit parser has fixture-based tests that fail loudly when the expected source payload changes. The modeling phase must use rolling or forward temporal validation; random train/test splitting will not be accepted as the sole validation design.

## App

Not built. The project brief requires data feasibility to be established before product work.

## Findings

No substantive baseball-market finding is claimed in Phase 1. The only result is feasibility:

- 1,078 complete positive-value contract rows in completed 2020–2025 classes.
- 471 contracts in the provisional $5 million primary screen.
- 94.1% of that primary cohort has an observed contract-year player-season row.
- 87.5% has observed rows in all three pre-contract seasons.
- 98.9% has at least one observed post-signing MLB season row.
- 0% of the completed-class cohort has a retained historical projection in the current public tracker payload.

## Limitations

- The live tracker covers only 2020–2026, short of the 10–20 offseason target.
- Historical projection archives are members-only or otherwise not available as a reproducible public bulk source.
- Exact annual cash flows, deferrals, options, buyouts, and traded salary responsibility are not complete in the tracker; AAV is only a labeled fallback.
- Missing player-season rows can represent no MLB appearance rather than unavailable data. They require explicit zero/absence rules in Phase 2.
- WAR is an estimate of on-field value, not team revenue.
- A public deployment requires data licensing and redistribution review.

## Reproduction

Python 3.9+ is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
PYTHONPATH=src python3 scripts/run_data_audit.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The audit writes aggregate CSV tables and a machine-readable summary to `data/processed/audit/`. It does not retain source HTML.

## Repository map

```text
contract-alpha/
├── data/
│   ├── external/
│   ├── processed/audit/
│   └── raw/
├── docs/
│   └── data-feasibility-report.md
├── scripts/
│   └── run_data_audit.py
├── src/contract_alpha/
│   ├── audit.py
│   └── ingestion/fangraphs.py
└── tests/
```
