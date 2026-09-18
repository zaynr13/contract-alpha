# Public research outputs

These precomputed files are the only data loaded by the hosted Streamlit app. They contain aggregate model results, validation summaries, team aggregates, and short transformed contract leaderboards—not the complete source-derived contract panel.

- `analysis_summary.json`: headline effects, cohort counts, validation summaries, and embedded sensitivity results.
- `research_results.csv`: primary, threshold, role, and 2021-exclusion regression results.
- `baseline_history_sensitivity.csv`: price, persistence, and alpha models requiring one, two, or three observed baseline seasons.
- `market_value_sensitivity.csv`: alpha models and leaderboard stability at 75%, 100%, and 125% of the base market $/WAR estimate.
- `market_price_per_war.csv`: base-case offseason market valuation series.
- `model_validation.csv`: expanding-window validation folds.
- `contract_size_validation.csv`: guarantee error by actual contract-size band.
- `team_results.csv`: team aggregates under all three market-value assumptions.
- `leaderboards.json`: short transformed contract result tables.

Run `PYTHONPATH=src python3 scripts/run_phase2.py` to rebuild them. The complete contract panel and timelines are written separately to the ignored `data/processed/private/` directory.
