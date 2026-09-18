"""Phase 2–6 analytical pipeline for MLB Contract-Year Trap.

The module keeps source ingestion separate from model construction. Public outputs are
aggregate research results and short derived leaderboards; the contract-level research
panel is written to an ignored local directory pending redistribution permission.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from contract_alpha.audit import (
    LAST_COMPLETED_SEASON,
    TRACKER_FIRST_SEASON,
    classify_role,
    fetch_performance_for_contracts,
    prepare_contracts,
)
from contract_alpha.ingestion.fangraphs import fetch_tracker, make_session


PRIMARY_THRESHOLD_DOLLARS = 5_000_000
RESEARCH_MINIMUM_DOLLARS = 1_000_000
SHORTENED_SEASON = 2020
SHORTENED_GAMES = 60
FULL_SEASON_GAMES = 162
BASELINE_WEIGHTS = (0.50, 0.30, 0.20)
MARKET_VALUE_SCENARIOS = {"low": 0.75, "base": 1.00, "high": 1.25}
CONTRACT_SIZE_BINS = (1_000_000, 5_000_000, 25_000_000, 100_000_000, math.inf)
CONTRACT_SIZE_LABELS = ("$1M–<$5M", "$5M–<$25M", "$25M–<$100M", "$100M+")
MODEL_FEATURES = (
    "baseline_war",
    "baseline_rate_war",
    "baseline_playing_time_share",
    "age",
    "age_squared",
    "is_pitcher",
    "baseline_war_pitcher",
    "start_year_index",
    "baseline_observed_seasons",
)


@dataclass(frozen=True)
class SeasonLine:
    observed: bool
    war: float
    pa: float
    ip: float
    wrc_plus: float
    fip_minus: float


def season_length_factor(season: int) -> float:
    """Return a 162-game-equivalent multiplier for the shortened 2020 season."""

    return FULL_SEASON_GAMES / SHORTENED_GAMES if season == SHORTENED_SEASON else 1.0


def salary_elapsed_factor(season: int) -> float:
    """Approximate the fraction of a normal salary season paid in 2020."""

    return SHORTENED_GAMES / FULL_SEASON_GAMES if season == SHORTENED_SEASON else 1.0


def _finite(value: Any, default: float = math.nan) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric if math.isfinite(numeric) else default


def aggregate_player_seasons(performance: pd.DataFrame) -> pd.DataFrame:
    """Collapse batting/pitching sides into one player-season observation."""

    if performance.empty:
        return pd.DataFrame(
            columns=["player_id", "season", "war", "pa", "ip", "wrc_plus", "fip_minus"]
        )
    frame = performance.copy()
    frame["playerid"] = frame["playerid"].astype("string")
    frame["Season"] = pd.to_numeric(frame["Season"], errors="coerce").astype("Int64")
    for column in ["WAR", "PA", "IP", "wRC+", "FIP-"]:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")

    def weighted_rate(group: pd.DataFrame, value: str, weight: str) -> float:
        valid = group[value].notna() & group[weight].fillna(0).gt(0)
        if not valid.any():
            return math.nan
        return float(np.average(group.loc[valid, value], weights=group.loc[valid, weight]))

    rows: list[dict[str, Any]] = []
    for (player_id, season), group in frame.groupby(["playerid", "Season"], dropna=True):
        rows.append(
            {
                "player_id": str(player_id),
                "season": int(season),
                "war": float(group["WAR"].sum(min_count=1)),
                "pa": float(group["PA"].sum(min_count=1)) if group["PA"].notna().any() else 0.0,
                "ip": float(group["IP"].sum(min_count=1)) if group["IP"].notna().any() else 0.0,
                "wrc_plus": weighted_rate(group, "wRC+", "PA"),
                "fip_minus": weighted_rate(group, "FIP-", "IP"),
            }
        )
    return pd.DataFrame(rows)


def _season_lookup(performance: pd.DataFrame) -> dict[tuple[str, int], SeasonLine]:
    return {
        (str(row.player_id), int(row.season)): SeasonLine(
            observed=True,
            war=_finite(row.war, 0.0),
            pa=_finite(row.pa, 0.0),
            ip=_finite(row.ip, 0.0),
            wrc_plus=_finite(row.wrc_plus),
            fip_minus=_finite(row.fip_minus),
        )
        for row in performance.itertuples()
    }


def _empty_line() -> SeasonLine:
    return SeasonLine(False, 0.0, 0.0, 0.0, math.nan, math.nan)


def _playing_time(line: SeasonLine, role: str) -> tuple[float, float]:
    if role == "pitcher":
        return line.ip, 180.0
    if role == "hitter":
        return line.pa, 600.0
    return line.pa + 3.333333 * line.ip, 600.0


def _normalized_line(line: SeasonLine, season: int) -> SeasonLine:
    factor = season_length_factor(season)
    return SeasonLine(
        observed=line.observed,
        war=line.war * factor,
        pa=line.pa * factor,
        ip=line.ip * factor,
        wrc_plus=line.wrc_plus,
        fip_minus=line.fip_minus,
    )


def _weighted_observed(
    values: list[float],
    observed: list[bool],
    weights: tuple[float, ...] = BASELINE_WEIGHTS,
) -> float:
    """Weight observed seasons only, renormalizing rather than imputing missing rows as zero."""

    included = [
        (value, weight)
        for value, is_observed, weight in zip(values, observed, weights)
        if is_observed and math.isfinite(value)
    ]
    if not included:
        return math.nan
    weight_total = sum(weight for _, weight in included)
    return float(sum(value * weight for value, weight in included) / weight_total)


def build_contract_panel(
    contracts: pd.DataFrame,
    performance: pd.DataFrame,
    *,
    minimum_guarantee: float = RESEARCH_MINIMUM_DOLLARS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create the contract-level research panel and its player-season timeline."""

    source = contracts.copy()
    if "role" not in source:
        source["role"] = source["position"].map(classify_role)
    eligible = source[
        source["has_complete_contract"]
        & source["season"].between(TRACKER_FIRST_SEASON, LAST_COMPLETED_SEASON)
        & source["ContractTotal"].ge(minimum_guarantee)
        & source["ContractType"].eq("Free Agent")
        & source["option_type"].ne("MODIFICATION")
    ].copy()
    aggregated = aggregate_player_seasons(performance)
    lookup = _season_lookup(aggregated)
    panel_rows: list[dict[str, Any]] = []
    timeline_rows: list[dict[str, Any]] = []

    for contract in eligible.itertuples():
        player_id = str(contract.playerId)
        start_year = int(contract.season)
        role = str(contract.role)
        contract_year = start_year - 1
        raw_contract_line = lookup.get((player_id, contract_year), _empty_line())
        contract_line = _normalized_line(raw_contract_line, contract_year)
        contract_playing_time, standard_playing_time = _playing_time(contract_line, role)

        baseline_lines: list[SeasonLine] = []
        baseline_wars: list[float] = []
        baseline_playing_times: list[float] = []
        rate_values: list[tuple[float, float]] = []
        for lag in (1, 2, 3):
            season = contract_year - lag
            line = _normalized_line(lookup.get((player_id, season), _empty_line()), season)
            baseline_lines.append(line)
            playing_time, _ = _playing_time(line, role)
            baseline_wars.append(line.war)
            baseline_playing_times.append(playing_time)
            if playing_time > 0:
                rate_values.append((line.war / playing_time * standard_playing_time, BASELINE_WEIGHTS[lag - 1]))

        baseline_observed = [line.observed for line in baseline_lines]
        baseline_war = _weighted_observed(baseline_wars, baseline_observed)
        baseline_playing_time = _weighted_observed(
            baseline_playing_times, baseline_observed
        )
        if rate_values:
            weight_total = sum(weight for _, weight in rate_values)
            baseline_rate_war = sum(value * weight for value, weight in rate_values) / weight_total
        else:
            baseline_rate_war = math.nan
        expected_at_contract_playing_time = (
            baseline_rate_war * contract_playing_time / standard_playing_time
            if math.isfinite(baseline_rate_war)
            else math.nan
        )
        rate_spike = (
            contract_line.war - expected_at_contract_playing_time
            if math.isfinite(expected_at_contract_playing_time)
            else math.nan
        )
        playing_time_component = (
            baseline_rate_war
            * (contract_playing_time - baseline_playing_time)
            / standard_playing_time
            if math.isfinite(baseline_rate_war)
            else math.nan
        )

        contract_years = int(round(float(contract.contract_years)))
        elapsed_seasons = list(
            range(start_year, min(start_year + contract_years, LAST_COMPLETED_SEASON + 1))
        )
        realized_war = 0.0
        normalized_realized_war = 0.0
        equivalent_salary_years = 0.0
        post_observed = 0
        post_values: dict[str, float] = {}
        for number, season in enumerate(elapsed_seasons, start=1):
            line = lookup.get((player_id, season), _empty_line())
            realized_war += line.war
            normalized_realized_war += line.war * season_length_factor(season)
            equivalent_salary_years += salary_elapsed_factor(season)
            post_observed += int(line.observed)
            post_values[f"post_war_y{number}"] = line.war

        future_war_per_season = (
            normalized_realized_war / len(elapsed_seasons) if elapsed_seasons else math.nan
        )
        realized_cost = float(contract.aav) * equivalent_salary_years

        row = {
            "contract_id": int(contract.ContractId),
            "player_id": player_id,
            "player_name": str(contract.playerName),
            "role": role,
            "position": str(contract.position),
            "age": float(contract.age),
            "start_year": start_year,
            "contract_year": contract_year,
            "prior_team": str(contract.team_prev),
            "signing_team": str(contract.team_new),
            "contract_years": contract_years,
            "guaranteed_dollars": float(contract.ContractTotal),
            "aav": float(contract.aav),
            "is_primary": bool(float(contract.ContractTotal) >= PRIMARY_THRESHOLD_DOLLARS),
            "contract_year_observed": raw_contract_line.observed,
            "baseline_observed_seasons": sum(baseline_observed),
            "baseline_unobserved_seasons": 3 - sum(baseline_observed),
            "baseline_observed_zero_war_seasons": sum(
                line.observed and abs(line.war) < 1e-12 for line in baseline_lines
            ),
            "contract_year_war": contract_line.war,
            "contract_year_playing_time": contract_playing_time,
            "baseline_war": baseline_war,
            "baseline_rate_war": baseline_rate_war,
            "baseline_playing_time": baseline_playing_time,
            "baseline_playing_time_share": baseline_playing_time / standard_playing_time,
            "performance_spike": contract_line.war - baseline_war,
            "rate_spike": rate_spike,
            "playing_time_component": playing_time_component,
            "contract_year_wrc_plus": contract_line.wrc_plus,
            "contract_year_fip_minus": contract_line.fip_minus,
            "elapsed_contract_seasons": len(elapsed_seasons),
            "post_seasons_observed": post_observed,
            "post_seasons_without_mlb_row": len(elapsed_seasons) - post_observed,
            "realized_war": realized_war,
            "normalized_realized_war": normalized_realized_war,
            "future_war_per_season": future_war_per_season,
            "regression_from_contract_year": future_war_per_season - contract_line.war,
            "equivalent_salary_years": equivalent_salary_years,
            "realized_cost": realized_cost,
            **post_values,
        }
        panel_rows.append(row)

        for season in range(contract_year - 3, LAST_COMPLETED_SEASON + 1):
            line = lookup.get((player_id, season), _empty_line())
            timeline_rows.append(
                {
                    "contract_id": int(contract.ContractId),
                    "player_id": player_id,
                    "player_name": str(contract.playerName),
                    "season": season,
                    "war": line.war,
                    "observed": line.observed,
                    "period": (
                        "baseline"
                        if season < contract_year
                        else "contract_year"
                        if season == contract_year
                        else "under_contract"
                        if season < start_year + contract_years
                        else "post_contract"
                    ),
                }
            )

    panel = pd.DataFrame(panel_rows)
    if panel.empty:
        return panel, pd.DataFrame(timeline_rows)
    panel["spike_percentile"] = math.nan
    percentile_eligible = (
        panel["contract_year_observed"]
        & panel["baseline_observed_seasons"].ge(1)
        & panel["role"].isin(["hitter", "pitcher"])
    )
    panel.loc[percentile_eligible, "spike_percentile"] = (
        panel.loc[percentile_eligible]
        .groupby("role")["performance_spike"]
        .rank(pct=True)
        * 100
    )
    return panel, pd.DataFrame(timeline_rows)


def model_feature_frame(panel: pd.DataFrame) -> pd.DataFrame:
    """Return the pre-signing-only sustainable-baseline feature matrix."""

    age = pd.to_numeric(panel["age"], errors="coerce")
    pitcher = panel["role"].eq("pitcher").astype(float)
    frame = pd.DataFrame(index=panel.index)
    frame["baseline_war"] = pd.to_numeric(panel["baseline_war"], errors="coerce")
    frame["baseline_rate_war"] = pd.to_numeric(panel["baseline_rate_war"], errors="coerce").fillna(0)
    frame["baseline_playing_time_share"] = pd.to_numeric(
        panel["baseline_playing_time_share"], errors="coerce"
    ).fillna(0)
    frame["age"] = age
    frame["age_squared"] = age.pow(2)
    frame["is_pitcher"] = pitcher
    frame["baseline_war_pitcher"] = frame["baseline_war"] * pitcher
    frame["start_year_index"] = pd.to_numeric(panel["start_year"], errors="coerce") - TRACKER_FIRST_SEASON
    frame["baseline_observed_seasons"] = pd.to_numeric(
        panel["baseline_observed_seasons"], errors="coerce"
    )
    return frame[list(MODEL_FEATURES)]


def add_forward_price_predictions(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add strictly forward, sustainable-baseline price estimates."""

    result = panel.copy()
    targets = {
        "aav": "predicted_aav",
        "guaranteed_dollars": "predicted_guarantee",
        "contract_years": "predicted_years",
    }
    for prediction in targets.values():
        result[prediction] = math.nan
        result[f"{prediction}_low"] = math.nan
        result[f"{prediction}_high"] = math.nan
    result["prediction_train_last_year"] = pd.Series(pd.NA, index=result.index, dtype="Int64")

    features = model_feature_frame(result)
    eligible = (
        result["contract_year_observed"]
        & result["baseline_observed_seasons"].ge(1)
        & result["role"].isin(["hitter", "pitcher"])
        & features.notna().all(axis=1)
    )
    validations: list[dict[str, Any]] = []
    for test_year in sorted(result.loc[eligible, "start_year"].unique()):
        train_mask = eligible & result["start_year"].lt(test_year)
        test_mask = eligible & result["start_year"].eq(test_year)
        if train_mask.sum() < 50 or test_mask.sum() == 0:
            continue
        result.loc[test_mask, "prediction_train_last_year"] = int(test_year) - 1
        train_features = features.loc[train_mask]
        test_features = features.loc[test_mask]

        for target, prediction in targets.items():
            scale = 1_000_000.0 if target in {"aav", "guaranteed_dollars"} else 1.0
            train_actual = result.loc[train_mask, target].astype(float) / scale
            test_actual = result.loc[test_mask, target].astype(float) / scale
            train_target = np.log1p(train_actual)
            model = make_pipeline(StandardScaler(), Ridge(alpha=5.0))
            model.fit(train_features, train_target)
            predicted = np.expm1(model.predict(test_features))
            fitted_train = np.expm1(model.predict(train_features))
            log_residual = train_target.to_numpy() - np.log1p(np.maximum(fitted_train, 0))
            low_resid, high_resid = np.quantile(log_residual, [0.10, 0.90])
            low = np.expm1(np.log1p(np.maximum(predicted, 0)) + low_resid)
            high = np.expm1(np.log1p(np.maximum(predicted, 0)) + high_resid)
            if target == "contract_years":
                predicted = np.clip(predicted, 1, 15)
                low = np.clip(low, 1, 15)
                high = np.clip(high, 1, 15)
            elif target == "guaranteed_dollars":
                # The research cohort itself is screened at $1 million. Ridge
                # extrapolation can otherwise produce a slightly negative
                # estimate for a fringe observation, which is not a meaningful
                # contract price.
                predicted = np.maximum(predicted, 1.0)
                low = np.maximum(low, 1.0)
                high = np.maximum(high, predicted)
            else:
                predicted = np.maximum(predicted, 0.5)
                low = np.maximum(low, 0.5)
                high = np.maximum(high, predicted)
            result.loc[test_mask, prediction] = predicted * scale
            result.loc[test_mask, f"{prediction}_low"] = low * scale
            result.loc[test_mask, f"{prediction}_high"] = high * scale

            naive = result.loc[train_mask].groupby("role")[target].median()
            naive_prediction = result.loc[test_mask, "role"].map(naive).astype(float) / scale
            error = test_actual.to_numpy() - predicted
            naive_error = test_actual.to_numpy() - naive_prediction.to_numpy()
            validations.append(
                {
                    "test_year": int(test_year),
                    "training_last_year": int(test_year) - 1,
                    "target": target,
                    "n_train": int(train_mask.sum()),
                    "n_test": int(test_mask.sum()),
                    "mae": float(np.mean(np.abs(error)) * scale),
                    "median_absolute_error": float(np.median(np.abs(error)) * scale),
                    "rmse": float(np.sqrt(np.mean(error**2)) * scale),
                    "naive_mae": float(np.mean(np.abs(naive_error)) * scale),
                }
            )

    result["aav_baseline_residual"] = result["aav"] - result["predicted_aav"]
    result["guarantee_baseline_residual"] = (
        result["guaranteed_dollars"] - result["predicted_guarantee"]
    )
    result["guarantee_baseline_residual_percent"] = np.where(
        result["predicted_guarantee"].gt(0),
        100 * result["guarantee_baseline_residual"] / result["predicted_guarantee"],
        math.nan,
    )
    result["guarantee_actual_to_benchmark_ratio"] = np.where(
        result["predicted_guarantee"].gt(0),
        result["guaranteed_dollars"] / result["predicted_guarantee"],
        math.nan,
    )
    result["guarantee_outside_empirical_range"] = (
        result["predicted_guarantee"].notna()
        & (
            result["guaranteed_dollars"].lt(result["predicted_guarantee_low"])
            | result["guaranteed_dollars"].gt(result["predicted_guarantee_high"])
        )
    )
    result["guarantee_benchmark_reliability"] = "not scored"
    scored = result["predicted_guarantee"].notna()
    far_outside = scored & (
        result["guarantee_outside_empirical_range"]
        | result["guarantee_actual_to_benchmark_ratio"].gt(3)
        | result["guarantee_actual_to_benchmark_ratio"].lt(1 / 3)
    )
    result.loc[scored & ~far_outside, "guarantee_benchmark_reliability"] = (
        "within modeled range"
    )
    result.loc[far_outside, "guarantee_benchmark_reliability"] = (
        "outside reliable modeled range"
    )
    return result, pd.DataFrame(validations)


def make_contract_size_validation(panel: pd.DataFrame) -> pd.DataFrame:
    """Summarize forward guarantee error by actual contract-size band."""

    scored = panel[panel["predicted_guarantee"].notna()].copy()
    scored["contract_size_band"] = pd.cut(
        scored["guaranteed_dollars"],
        bins=CONTRACT_SIZE_BINS,
        labels=CONTRACT_SIZE_LABELS,
        right=False,
    )
    scored["absolute_error"] = (
        scored["guaranteed_dollars"] - scored["predicted_guarantee"]
    ).abs()
    scored["absolute_percentage_error"] = (
        100 * scored["absolute_error"] / scored["guaranteed_dollars"]
    )
    scored["absolute_log_error"] = (
        np.log1p(scored["guaranteed_dollars"])
        - np.log1p(scored["predicted_guarantee"])
    ).abs()
    rows: list[dict[str, Any]] = []
    for band in CONTRACT_SIZE_LABELS:
        group = scored[scored["contract_size_band"].astype("string").eq(band)]
        if group.empty:
            continue
        rows.append(
            {
                "contract_size_band": band,
                "n": int(len(group)),
                "mae": float(group["absolute_error"].mean()),
                "median_absolute_error": float(group["absolute_error"].median()),
                "median_absolute_percentage_error": float(
                    group["absolute_percentage_error"].median()
                ),
                "mean_absolute_log_error": float(group["absolute_log_error"].mean()),
                "empirical_interval_coverage_percent": float(
                    100 * (~group["guarantee_outside_empirical_range"]).mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def estimate_market_price_per_war(panel: pd.DataFrame) -> pd.DataFrame:
    """Estimate a robust offseason-specific AAV price per sustainable WAR."""

    rows: list[dict[str, Any]] = []
    primary = panel[
        panel["is_primary"]
        & panel["baseline_war"].ge(0.75)
        & panel["role"].isin(["hitter", "pitcher"])
    ]
    for season, group in primary.groupby("start_year", sort=True):
        ratios = group["aav"] / group["baseline_war"]
        low, high = ratios.quantile([0.10, 0.90])
        trimmed = ratios.clip(lower=low, upper=high)
        rows.append(
            {
                "season": int(season),
                "contracts": int(len(group)),
                "market_dollars_per_war": float(trimmed.median()),
                "p25": float(trimmed.quantile(0.25)),
                "p75": float(trimmed.quantile(0.75)),
                "method": "median winsorized AAV / sustainable baseline WAR",
            }
        )
    return pd.DataFrame(rows)


def add_contract_alpha(panel: pd.DataFrame, market_rates: pd.DataFrame) -> pd.DataFrame:
    """Value realized production under low, base, and high market-$-per-WAR cases."""

    result = panel.copy()
    rates = market_rates.set_index("season")["market_dollars_per_war"].to_dict()
    production_values: list[float] = []
    for row in result.itertuples():
        total = 0.0
        for number, season in enumerate(
            range(row.start_year, row.start_year + row.elapsed_contract_seasons), start=1
        ):
            total += float(getattr(row, f"post_war_y{number}", 0.0)) * float(rates[season])
        production_values.append(total)
    base_production = pd.Series(production_values, index=result.index)
    for scenario, multiplier in MARKET_VALUE_SCENARIOS.items():
        production_column = f"realized_production_value_{scenario}"
        alpha_column = f"contract_alpha_{scenario}"
        roi_column = f"alpha_roi_percent_{scenario}"
        per_year_column = f"alpha_per_equivalent_year_{scenario}"
        result[production_column] = base_production * multiplier
        result[alpha_column] = result[production_column] - result["realized_cost"]
        result[roi_column] = np.where(
            result["realized_cost"].gt(0),
            100 * result[alpha_column] / result["realized_cost"],
            math.nan,
        )
        result[per_year_column] = np.where(
            result["equivalent_salary_years"].gt(0),
            result[alpha_column] / result["equivalent_salary_years"],
            math.nan,
        )
    result["realized_production_value"] = result["realized_production_value_base"]
    result["contract_alpha"] = result["contract_alpha_base"]
    result["alpha_roi_percent"] = result["alpha_roi_percent_base"]
    result["alpha_per_equivalent_year"] = result["alpha_per_equivalent_year_base"]
    result["cost_per_war"] = np.where(
        result["realized_war"].gt(0), result["realized_cost"] / result["realized_war"], math.nan
    )
    result["classification"] = "Measured contract"
    high_spike = result["spike_percentile"].ge(80)
    result.loc[high_spike & result["contract_alpha"].lt(0), "classification"] = "Contract-year trap"
    result.loc[high_spike & result["contract_alpha"].ge(0), "classification"] = "Sustainable breakout"
    result.loc[result["contract_alpha"].gt(0), "classification"] = result.loc[
        result["contract_alpha"].gt(0), "classification"
    ].replace("Measured contract", "Positive alpha")
    return result


def add_timeline_values(
    timeline: pd.DataFrame,
    panel: pd.DataFrame,
    market_rates: pd.DataFrame,
) -> pd.DataFrame:
    """Add elapsed-season cost, production value, and alpha to contract timelines."""

    contract_terms = panel[["contract_id", "aav"]]
    result = timeline.merge(contract_terms, on="contract_id", how="left", validate="many_to_one")
    rates = market_rates.set_index("season")["market_dollars_per_war"]
    result["market_dollars_per_war"] = result["season"].map(rates)
    elapsed = result["period"].eq("under_contract")
    result["salary_cost"] = np.where(
        elapsed,
        result["aav"] * result["season"].map(salary_elapsed_factor),
        math.nan,
    )
    result["production_value"] = np.where(
        elapsed,
        result["war"] * result["market_dollars_per_war"],
        math.nan,
    )
    result["season_alpha"] = result["production_value"] - result["salary_cost"]
    return result.drop(columns=["aav"])


def make_team_results(panel: pd.DataFrame) -> pd.DataFrame:
    """Aggregate realized primary-cohort capital allocation by signing team."""

    primary = panel[panel["is_primary"]].copy()
    primary["has_price_prediction"] = primary["predicted_guarantee"].notna().astype(int)
    aggregations: dict[str, tuple[str, str]] = {
        "contracts": ("contract_id", "size"),
        "total_guarantee": ("guaranteed_dollars", "sum"),
        "realized_cost": ("realized_cost", "sum"),
        "price_prediction_contracts": ("has_price_prediction", "sum"),
        "total_guarantee_baseline_residual": ("guarantee_baseline_residual", "sum"),
    }
    for scenario in MARKET_VALUE_SCENARIOS:
        aggregations[f"realized_production_value_{scenario}"] = (
            f"realized_production_value_{scenario}",
            "sum",
        )
        aggregations[f"contract_alpha_{scenario}"] = (
            f"contract_alpha_{scenario}",
            "sum",
        )
    grouped = primary.groupby("signing_team", as_index=False).agg(**aggregations)
    for scenario in MARKET_VALUE_SCENARIOS:
        grouped[f"alpha_roi_percent_{scenario}"] = np.where(
            grouped["realized_cost"].gt(0),
            100 * grouped[f"contract_alpha_{scenario}"] / grouped["realized_cost"],
            math.nan,
        )
        grouped[f"alpha_per_contract_{scenario}"] = (
            grouped[f"contract_alpha_{scenario}"] / grouped["contracts"]
        )
    grouped["realized_production_value"] = grouped["realized_production_value_base"]
    grouped["contract_alpha"] = grouped["contract_alpha_base"]
    grouped["alpha_roi_percent"] = grouped["alpha_roi_percent_base"]
    grouped["alpha_per_contract"] = grouped["alpha_per_contract_base"]
    grouped = grouped.sort_values("contract_alpha", ascending=False)
    return grouped


def _cluster_ols(
    frame: pd.DataFrame,
    *,
    outcome: str,
    focal: str,
    controls: list[str],
    cluster: str = "player_id",
) -> dict[str, Any]:
    columns = [outcome, focal, cluster, *controls, "start_year"]
    model = frame[columns].replace([np.inf, -np.inf], np.nan).dropna().copy()
    year_dummies = pd.get_dummies(model["start_year"].astype(int), prefix="year", drop_first=True, dtype=float)
    x = pd.concat([model[[focal, *controls]].astype(float), year_dummies], axis=1)
    x.insert(0, "intercept", 1.0)
    y = model[outcome].astype(float).to_numpy()
    matrix = x.to_numpy(dtype=float)
    inverse = np.linalg.pinv(matrix.T @ matrix)
    beta = inverse @ matrix.T @ y
    residual = y - matrix @ beta
    meat = np.zeros((matrix.shape[1], matrix.shape[1]))
    clusters = model[cluster].astype(str).to_numpy()
    unique_clusters = np.unique(clusters)
    for group in unique_clusters:
        group_matrix = matrix[clusters == group]
        group_residual = residual[clusters == group]
        score = group_matrix.T @ group_residual
        meat += np.outer(score, score)
    n, k = matrix.shape
    groups = len(unique_clusters)
    correction = (groups / (groups - 1)) * ((n - 1) / (n - k)) if groups > 1 and n > k else 1.0
    covariance = correction * inverse @ meat @ inverse
    focal_index = list(x.columns).index(focal)
    estimate = float(beta[focal_index])
    standard_error = float(math.sqrt(max(covariance[focal_index, focal_index], 0)))
    statistic = estimate / standard_error if standard_error > 0 else math.nan
    p_value = math.erfc(abs(statistic) / math.sqrt(2)) if math.isfinite(statistic) else math.nan
    total_sum = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1 - float(np.sum(residual**2)) / total_sum if total_sum > 0 else math.nan
    return {
        "n": int(n),
        "clusters": int(groups),
        "estimate": estimate,
        "standard_error": standard_error,
        "ci_low": estimate - 1.96 * standard_error,
        "ci_high": estimate + 1.96 * standard_error,
        "p_value": p_value,
        "r_squared": r_squared,
    }


def run_research_models(panel: pd.DataFrame) -> pd.DataFrame:
    """Run the four preregistered descriptive association tests and sensitivities."""

    rows: list[dict[str, Any]] = []
    base_controls = ["baseline_war", "age", "age_squared", "is_pitcher"]
    prepared = panel.copy()
    prepared["age_squared"] = prepared["age"].pow(2)
    prepared["is_pitcher"] = prepared["role"].eq("pitcher").astype(float)
    prepared["log_aav"] = np.log(prepared["aav"])
    prepared["log_guarantee"] = np.log(prepared["guaranteed_dollars"])
    prepared["alpha_per_year_m"] = prepared["alpha_per_equivalent_year"] / 1_000_000
    prepared["guarantee_baseline_residual_per_10m"] = (
        prepared["guarantee_baseline_residual"] / 10_000_000
    )

    questions = [
        ("A_price", "log_guarantee", "performance_spike", base_controls),
        (
            "B_regression",
            "regression_from_contract_year",
            "performance_spike",
            base_controls + ["elapsed_contract_seasons"],
        ),
        (
            "B_persistence",
            "future_war_per_season",
            "performance_spike",
            base_controls + ["elapsed_contract_seasons"],
        ),
        ("C_alpha", "alpha_per_year_m", "performance_spike", base_controls + ["contract_years"]),
        (
            "D_residual",
            "alpha_per_year_m",
            "guarantee_baseline_residual_per_10m",
            base_controls + ["contract_years"],
        ),
    ]
    specifications = [
        ("primary", 5_000_000, False, "all"),
        ("minimum_1m", 1_000_000, False, "all"),
        ("large_25m", 25_000_000, False, "all"),
        ("exclude_2021", 5_000_000, True, "all"),
        ("hitters", 5_000_000, False, "hitter"),
        ("pitchers", 5_000_000, False, "pitcher"),
    ]
    for specification, threshold, exclude_2021, role in specifications:
        cohort = prepared[
            prepared["guaranteed_dollars"].ge(threshold)
            & prepared["contract_year_observed"]
            & prepared["baseline_observed_seasons"].ge(1)
            & prepared["role"].isin(["hitter", "pitcher"])
        ]
        if exclude_2021:
            cohort = cohort[cohort["start_year"].ne(2021)]
        if role != "all":
            cohort = cohort[cohort["role"].eq(role)]
        for question, outcome, focal, controls in questions:
            if question == "D_residual":
                question_cohort = cohort[cohort["predicted_guarantee"].notna()]
            else:
                question_cohort = cohort
            result = _cluster_ols(
                question_cohort,
                outcome=outcome,
                focal=focal,
                controls=controls,
            )
            rows.append(
                {
                    "question": question,
                    "specification": specification,
                    "role": role,
                    "guarantee_threshold": threshold,
                    "outcome": outcome,
                    "focal_variable": focal,
                    **result,
                }
            )
    return pd.DataFrame(rows)


def run_baseline_history_sensitivity(panel: pd.DataFrame) -> pd.DataFrame:
    """Repeat principal models with one, two, and three observed baseline seasons."""

    prepared = panel.copy()
    prepared["age_squared"] = prepared["age"].pow(2)
    prepared["is_pitcher"] = prepared["role"].eq("pitcher").astype(float)
    prepared["log_guarantee"] = np.log(prepared["guaranteed_dollars"])
    prepared["alpha_per_year_m"] = prepared["alpha_per_equivalent_year"] / 1_000_000
    base_controls = ["baseline_war", "age", "age_squared", "is_pitcher"]
    questions = [
        ("A_price", "log_guarantee", base_controls),
        (
            "B_persistence",
            "future_war_per_season",
            base_controls + ["elapsed_contract_seasons"],
        ),
        ("C_alpha", "alpha_per_year_m", base_controls + ["contract_years"]),
    ]
    rows: list[dict[str, Any]] = []
    for minimum_seasons in (1, 2, 3):
        cohort = prepared[
            prepared["is_primary"]
            & prepared["contract_year_observed"]
            & prepared["baseline_observed_seasons"].ge(minimum_seasons)
            & prepared["role"].isin(["hitter", "pitcher"])
        ]
        for question, outcome, controls in questions:
            rows.append(
                {
                    "question": question,
                    "minimum_observed_baseline_seasons": minimum_seasons,
                    "outcome": outcome,
                    "focal_variable": "performance_spike",
                    **_cluster_ols(
                        cohort,
                        outcome=outcome,
                        focal="performance_spike",
                        controls=controls,
                    ),
                }
            )
    return pd.DataFrame(rows)


def run_market_value_sensitivity(panel: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """Test alpha results and leaderboard stability across ±25% market-WAR values."""

    prepared = panel.copy()
    prepared["age_squared"] = prepared["age"].pow(2)
    prepared["is_pitcher"] = prepared["role"].eq("pitcher").astype(float)
    cohort = prepared[
        prepared["is_primary"]
        & prepared["contract_year_observed"]
        & prepared["baseline_observed_seasons"].ge(1)
        & prepared["role"].isin(["hitter", "pitcher"])
    ].copy()
    mature = cohort[cohort["equivalent_salary_years"].ge(1)].copy()
    base_controls = ["baseline_war", "age", "age_squared", "is_pitcher", "contract_years"]

    def leaderboard_sets(frame: pd.DataFrame, alpha_column: str) -> dict[str, set[int]]:
        high_spike = frame["spike_percentile"].ge(80)
        traps = frame[high_spike & frame[alpha_column].lt(0)].nsmallest(limit, alpha_column)
        return {
            "traps": set(traps["contract_id"].astype(int)),
            "value_destruction": set(
                frame.nsmallest(limit, alpha_column)["contract_id"].astype(int)
            ),
            "positive_alpha": set(
                frame.nlargest(limit, alpha_column)["contract_id"].astype(int)
            ),
        }

    base_sets = leaderboard_sets(mature, "contract_alpha_base")
    rows: list[dict[str, Any]] = []
    for scenario, multiplier in MARKET_VALUE_SCENARIOS.items():
        alpha_column = f"contract_alpha_{scenario}"
        outcome = f"alpha_per_year_m_{scenario}"
        cohort[outcome] = cohort[f"alpha_per_equivalent_year_{scenario}"] / 1_000_000
        result = _cluster_ols(
            cohort,
            outcome=outcome,
            focal="performance_spike",
            controls=base_controls,
        )
        scenario_sets = leaderboard_sets(mature, alpha_column)
        rows.append(
            {
                "scenario": scenario,
                "market_value_multiplier": multiplier,
                "negative_alpha_contracts": int(mature[alpha_column].lt(0).sum()),
                "contract_year_traps": int(
                    (mature["spike_percentile"].ge(80) & mature[alpha_column].lt(0)).sum()
                ),
                "trap_top10_overlap_with_base": len(
                    scenario_sets["traps"] & base_sets["traps"]
                ),
                "value_destruction_top10_overlap_with_base": len(
                    scenario_sets["value_destruction"] & base_sets["value_destruction"]
                ),
                "positive_alpha_top10_overlap_with_base": len(
                    scenario_sets["positive_alpha"] & base_sets["positive_alpha"]
                ),
                **result,
            }
        )
    return pd.DataFrame(rows)


def _evidence_label(row: pd.Series, expected_direction: int) -> str:
    estimate = float(row["estimate"])
    low = float(row["ci_low"])
    high = float(row["ci_high"])
    if expected_direction > 0 and low > 0:
        return "clear positive association"
    if expected_direction < 0 and high < 0:
        return "clear negative association"
    if estimate * expected_direction > 0:
        return "directional, but statistically uncertain"
    return "no evidence in the hypothesized direction"


def make_leaderboards(panel: pd.DataFrame, limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    """Return short, transformed result tables suitable for public presentation."""

    primary = panel[
        panel["is_primary"]
        & panel["contract_year_observed"]
        & panel["baseline_observed_seasons"].ge(1)
    ].copy()
    columns = [
        "player_name",
        "signing_team",
        "start_year",
        "role",
        "contract_years",
        "guaranteed_dollars",
        "contract_year_war",
        "baseline_war",
        "performance_spike",
        "spike_percentile",
        "future_war_per_season",
        "predicted_guarantee",
        "predicted_guarantee_low",
        "predicted_guarantee_high",
        "guarantee_baseline_residual",
        "guarantee_benchmark_reliability",
        "realized_war",
        "realized_production_value",
        "realized_cost",
        "contract_alpha",
        "contract_alpha_low",
        "contract_alpha_high",
        "alpha_roi_percent",
        "classification",
    ]

    def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
        clean = frame.reindex(columns=columns).replace([np.inf, -np.inf], np.nan)
        return json.loads(clean.round(3).to_json(orient="records"))

    mature = primary[primary["equivalent_salary_years"].ge(1)]
    priced = primary[primary["predicted_guarantee"].notna()]
    traps = mature[mature["spike_percentile"].ge(80) & mature["contract_alpha"].lt(0)]
    return {
        "positive_alpha": records(mature.nlargest(limit, "contract_alpha")),
        "value_destruction": records(mature.nsmallest(limit, "contract_alpha")),
        "contract_year_spikes": records(primary.nlargest(limit, "performance_spike")),
        "largest_baseline_price_residuals": records(
            priced.nlargest(limit, "guarantee_baseline_residual")
        ),
        "contract_year_traps": records(traps.nsmallest(limit, "contract_alpha")),
    }


def make_analysis_summary(
    panel: pd.DataFrame,
    research: pd.DataFrame,
    validation: pd.DataFrame,
    market_rates: pd.DataFrame,
    baseline_sensitivity: pd.DataFrame,
    market_sensitivity: pd.DataFrame,
    size_validation: pd.DataFrame,
) -> dict[str, Any]:
    primary = panel[panel["is_primary"]]
    modelable = primary[
        primary["contract_year_observed"]
        & primary["baseline_observed_seasons"].ge(1)
        & primary["role"].isin(["hitter", "pitcher"])
    ]
    main = research[research["specification"].eq("primary")].set_index("question")
    answers: dict[str, Any] = {}
    expected = {
        "A_price": 1,
        "B_regression": -1,
        "B_persistence": 1,
        "C_alpha": -1,
        "D_residual": -1,
    }
    for question, direction in expected.items():
        row = main.loc[question]
        answers[question] = {
            "estimate": float(row["estimate"]),
            "ci_low": float(row["ci_low"]),
            "ci_high": float(row["ci_high"]),
            "p_value": float(row["p_value"]),
            "n": int(row["n"]),
            "evidence": _evidence_label(row, direction),
        }
    model_validation = {}
    for target, group in validation.groupby("target"):
        weight = group["n_test"] / group["n_test"].sum()
        model_validation[target] = {
            "test_contracts": int(group["n_test"].sum()),
            "weighted_mae": float((group["mae"] * weight).sum()),
            "weighted_naive_mae": float((group["naive_mae"] * weight).sum()),
            "beats_naive": bool((group["mae"] * weight).sum() < (group["naive_mae"] * weight).sum()),
        }
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "2020-2025 free-agent contracts; realized through 2025",
        "cohort": {
            "research_contracts_ge_1m": int(len(panel)),
            "primary_contracts_ge_5m": int(len(primary)),
            "primary_modelable_contracts": int(len(modelable)),
            "forward_priced_primary_contracts": int(primary["predicted_guarantee"].notna().sum()),
            "primary_with_two_baseline_seasons": int(
                modelable["baseline_observed_seasons"].ge(2).sum()
            ),
            "primary_with_three_baseline_seasons": int(
                modelable["baseline_observed_seasons"].eq(3).sum()
            ),
        },
        "answers": answers,
        "validation": model_validation,
        "market_price_per_war": json.loads(market_rates.round(2).to_json(orient="records")),
        "market_value_sensitivity": json.loads(
            market_sensitivity.round(4).to_json(orient="records")
        ),
        "baseline_history_sensitivity": json.loads(
            baseline_sensitivity.round(4).to_json(orient="records")
        ),
        "contract_size_validation": json.loads(
            size_validation.round(4).to_json(orient="records")
        ),
        "method": {
            "spike": "162-game-equivalent contract-year WAR minus a 50/30/20 prior-three-season baseline renormalized over observed MLB rows",
            "price_model": "ridge regression using sustainable pre-contract baseline features; strictly forward offseason testing",
            "inference": "OLS with offseason fixed effects and player-clustered standard errors",
            "alpha": "realized WAR times offseason-specific market $/WAR minus AAV-based elapsed cost",
            "shortened_2020": "WAR and playing time scaled to 162 games for signal models; 2020 cost prorated 60/162 for realized alpha",
            "market_value_sensitivity": "realized alpha repeated at 75%, 100%, and 125% of the empirical offseason market $/WAR estimate",
        },
        "interpretation": {
            "price_estimate": "The guarantee coefficient is a conditional association, not a causal return to one additional WAR.",
            "persistence_estimate": "The persistence coefficient is the primary finding: the share of one additional spike WAR associated with future WAR per season. The percentage that faded is one minus this estimate, not a separate model.",
            "price_prediction": "The predicted guarantee is a sustainable-baseline benchmark with a wide empirical interval, not a fair-value appraisal or proof that a club overpaid.",
            "years_prediction": "Contract-length predictions are reported for validation transparency but should not be used because they did not beat the role-median baseline.",
        },
        "limitations": [
            "AAV approximates annual cost and omits deferrals, options, trades, releases, and retained salary.",
            "Market $/WAR is estimated from recent free-agent AAV divided by sustainable baseline WAR.",
            "The six-offseason window is short; results are descriptive, not causal.",
            "Historical public projections are unavailable, so expected performance uses a transparent historical baseline.",
            "Unobserved baseline rows are not imputed as zero; observed baseline weights are renormalized, and results are repeated for one, two, and three observed seasons.",
            "WAR measures on-field contribution, not commercial or total financial value.",
        ],
    }


def fetch_phase2_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    session = make_session()
    tracker_rows: list[dict[str, Any]] = []
    for season in range(TRACKER_FIRST_SEASON, LAST_COMPLETED_SEASON + 1):
        rows = fetch_tracker(session, season)
        for row in rows:
            row["season"] = season
        tracker_rows.extend(rows)
    contracts = prepare_contracts(pd.DataFrame(tracker_rows))
    performance = fetch_performance_for_contracts(
        contracts[contracts["has_complete_contract"]],
        first_season=TRACKER_FIRST_SEASON - 4,
        last_season=LAST_COMPLETED_SEASON,
    )
    return contracts, performance


def run_phase2(public_output_dir: Path, private_output_dir: Path) -> dict[str, Any]:
    contracts, performance = fetch_phase2_inputs()
    panel, timeline = build_contract_panel(contracts, performance)
    panel, validation = add_forward_price_predictions(panel)
    size_validation = make_contract_size_validation(panel)
    market_rates = estimate_market_price_per_war(panel)
    panel = add_contract_alpha(panel, market_rates)
    timeline = add_timeline_values(timeline, panel, market_rates)
    research = run_research_models(panel)
    baseline_sensitivity = run_baseline_history_sensitivity(panel)
    market_sensitivity = run_market_value_sensitivity(panel)
    leaderboards = make_leaderboards(panel)
    team_results = make_team_results(panel)
    summary = make_analysis_summary(
        panel,
        research,
        validation,
        market_rates,
        baseline_sensitivity,
        market_sensitivity,
        size_validation,
    )

    public_output_dir.mkdir(parents=True, exist_ok=True)
    private_output_dir.mkdir(parents=True, exist_ok=True)
    research.to_csv(public_output_dir / "research_results.csv", index=False)
    validation.to_csv(public_output_dir / "model_validation.csv", index=False)
    size_validation.to_csv(public_output_dir / "contract_size_validation.csv", index=False)
    market_rates.to_csv(public_output_dir / "market_price_per_war.csv", index=False)
    market_sensitivity.to_csv(public_output_dir / "market_value_sensitivity.csv", index=False)
    baseline_sensitivity.to_csv(
        public_output_dir / "baseline_history_sensitivity.csv", index=False
    )
    team_results.to_csv(public_output_dir / "team_results.csv", index=False)
    (public_output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (public_output_dir / "leaderboards.json").write_text(
        json.dumps(leaderboards, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    panel.to_csv(private_output_dir / "contract_research_panel.csv", index=False)
    timeline.to_csv(private_output_dir / "contract_timelines.csv", index=False)
    return summary
