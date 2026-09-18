"""Phase 1 feasibility audit for MLB Contract-Year Trap."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from contract_alpha.ingestion.fangraphs import (
    LEADERS_URL,
    TRACKER_URL,
    fetch_player_seasons,
    fetch_tracker,
    make_session,
)

TRACKER_FIRST_SEASON = 2020
TRACKER_LAST_SEASON = 2026
LAST_COMPLETED_SEASON = 2025
PRIMARY_THRESHOLD_DOLLARS = 5_000_000


def classify_role(position: object) -> str:
    text = str(position or "").upper()
    tokens = {token.strip() for token in text.replace("-", "/").split("/")}
    pitcher_tokens = {"P", "SP", "RP"}
    has_pitcher = bool(tokens & pitcher_tokens)
    has_hitter = bool(tokens - pitcher_tokens - {"", "NONE", "NAN"})
    if has_pitcher and has_hitter:
        return "two-way"
    return "pitcher" if has_pitcher else "hitter"


def prepare_contracts(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    numeric = [
        "age",
        "war_prev",
        "war_proj",
        "med_years",
        "med_aav",
        "contract_years",
        "ContractTotal",
        "aav",
    ]
    for column in numeric:
        df[column] = pd.to_numeric(df.get(column), errors="coerce")
    df["playerId"] = df["playerId"].astype("string")
    df["role"] = df["position"].map(classify_role)
    df["is_signed"] = df["team_new"].notna()
    df["has_complete_contract"] = (
        df["is_signed"]
        & df["contract_years"].gt(0)
        & df["ContractTotal"].gt(0)
        & df["aav"].gt(0)
    )
    df["meets_5m_screen"] = (
        df["has_complete_contract"]
        & df["ContractTotal"].ge(PRIMARY_THRESHOLD_DOLLARS)
    )
    return df


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def fetch_performance_for_contracts(
    contracts: pd.DataFrame,
    *,
    first_season: int,
    last_season: int,
    chunk_size: int = 75,
) -> pd.DataFrame:
    session = make_session()
    rows: list[dict[str, Any]] = []
    plans: list[tuple[str, list[str]]] = []
    for role, stats in (("hitter", "bat"), ("pitcher", "pit")):
        player_ids = sorted(
            set(
                contracts.loc[contracts["role"].eq(role), "playerId"]
                .dropna()
                .astype(str)
            )
        )
        plans.append((stats, player_ids))
    # A future two-way record must be queried on both leaderboards.
    two_way = sorted(
        set(
            contracts.loc[contracts["role"].eq("two-way"), "playerId"]
            .dropna()
            .astype(str)
        )
    )
    plans.extend((("bat", two_way), ("pit", two_way)))

    for stats, player_ids in plans:
        for chunk in _chunks(player_ids, chunk_size):
            fetched = fetch_player_seasons(
                session,
                player_ids=chunk,
                stats=stats,
                first_season=first_season,
                last_season=last_season,
            )
            for row in fetched:
                row["stat_side"] = stats
            rows.extend(fetched)

    if not rows:
        return pd.DataFrame(
            columns=["playerid", "Season", "stat_side", "WAR", "PA", "IP"]
        )
    keep = [
        "playerid",
        "PlayerName",
        "Season",
        "stat_side",
        "WAR",
        "G",
        "PA",
        "wRC+",
        "IP",
        "FIP",
        "ERA-",
        "FIP-",
        "K/9",
        "BB/9",
    ]
    frame = pd.DataFrame(rows).reindex(columns=keep)
    frame["playerid"] = frame["playerid"].astype("string")
    frame["Season"] = pd.to_numeric(frame["Season"], errors="coerce").astype("Int64")
    for column in set(keep) - {"playerid", "PlayerName", "stat_side", "Season"}:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.drop_duplicates(["playerid", "Season", "stat_side"])


def add_performance_coverage(
    contracts: pd.DataFrame, performance: pd.DataFrame
) -> pd.DataFrame:
    df = contracts.copy()
    observed = {
        (str(row.playerid), int(row.Season), str(row.stat_side))
        for row in performance[["playerid", "Season", "stat_side"]].itertuples()
        if pd.notna(row.playerid) and pd.notna(row.Season)
    }

    def sides(role: str) -> tuple[str, ...]:
        if role == "pitcher":
            return ("pit",)
        if role == "two-way":
            return ("bat", "pit")
        return ("bat",)

    def present(player_id: str, season: int, role: str) -> bool:
        return any((str(player_id), int(season), side) in observed for side in sides(role))

    coverage: list[dict[str, Any]] = []
    for row in df.itertuples():
        start = int(row.season)
        player_id = str(row.playerId)
        pre_flags = [present(player_id, year, row.role) for year in range(start - 3, start)]
        if row.has_complete_contract and start <= LAST_COMPLETED_SEASON:
            elapsed = max(
                0,
                min(int(row.contract_years), LAST_COMPLETED_SEASON - start + 1),
            )
        else:
            elapsed = 0
        post_flags = [
            present(player_id, year, row.role)
            for year in range(start, start + elapsed)
        ]
        coverage.append(
            {
                "pre_seasons_observed": sum(pre_flags),
                "has_contract_year_row": pre_flags[-1],
                "has_three_pre_rows": all(pre_flags),
                "elapsed_contract_seasons": elapsed,
                "post_seasons_observed": sum(post_flags),
                "has_any_post_row": bool(post_flags) and any(post_flags),
                "has_all_elapsed_rows": bool(post_flags) and all(post_flags),
            }
        )
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(coverage)], axis=1)


def _count_and_percent(series: pd.Series) -> dict[str, float | int]:
    count = int(series.sum())
    total = int(series.size)
    return {
        "count": count,
        "denominator": total,
        "percent": round(100 * count / total, 1) if total else math.nan,
    }


def build_outputs(contracts: pd.DataFrame) -> dict[str, pd.DataFrame]:
    signed = contracts[contracts["is_signed"]]
    complete = contracts[contracts["has_complete_contract"]]
    historical = complete[complete["season"].le(LAST_COMPLETED_SEASON)]
    primary = historical[historical["meets_5m_screen"]]

    season_rows: list[dict[str, Any]] = []
    for season, group in contracts.groupby("season", sort=True):
        season_rows.append(
            {
                "contract_start_year": int(season),
                "tracker_rows": len(group),
                "signed_rows": int(group["is_signed"].sum()),
                "complete_contract_rows": int(group["has_complete_contract"].sum()),
                "guarantee_ge_5m": int(group["meets_5m_screen"].sum()),
                "contract_year_war_present": int(group["war_prev"].notna().sum()),
                "projection_war_present": int(group["war_proj"].notna().sum()),
                "crowd_estimate_present": int(
                    (group["med_years"].notna() & group["med_aav"].notna()).sum()
                ),
            }
        )
    by_season = pd.DataFrame(season_rows)

    missing_fields = {
        "player_id": signed["playerId"].isna(),
        "player_name": signed["playerName"].isna(),
        "position": signed["position"].isna(),
        "age": signed["age"].isna(),
        "prior_team": signed["team_prev"].isna(),
        "signing_team": signed["team_new"].isna(),
        "contract_years": signed["contract_years"].isna()
        | signed["contract_years"].le(0),
        "guaranteed_dollars": signed["ContractTotal"].isna()
        | signed["ContractTotal"].le(0),
        "aav": signed["aav"].isna() | signed["aav"].le(0),
        "contract_year_war": signed["war_prev"].isna(),
        "projection_war": signed["war_proj"].isna(),
        "crowd_years": signed["med_years"].isna(),
        "crowd_aav": signed["med_aav"].isna(),
    }
    missingness = pd.DataFrame(
        [
            {
                "variable": variable,
                "missing_count": int(mask.sum()),
                "signed_rows": len(signed),
                "missing_percent": round(100 * mask.mean(), 1),
            }
            for variable, mask in missing_fields.items()
        ]
    )

    role_split = (
        historical.groupby("role", dropna=False)
        .size()
        .rename("complete_contracts")
        .reset_index()
    )
    role_split["percent"] = (
        100 * role_split["complete_contracts"] / role_split["complete_contracts"].sum()
    ).round(1)

    age_bands = pd.cut(
        historical["age"],
        bins=[0, 26, 29, 32, float("inf")],
        labels=["<=26", "27-29", "30-32", "33+"],
    )
    age_distribution = (
        age_bands.value_counts(sort=False).rename("contracts").reset_index()
    )
    age_distribution.columns = ["age_band", "contracts"]
    age_distribution["percent"] = (
        100 * age_distribution["contracts"] / age_distribution["contracts"].sum()
    ).round(1)

    value_bins = [-0.01, 1e6, 5e6, 25e6, 75e6, 150e6, float("inf")]
    value_labels = [
        "<$1M",
        "$1M-<$5M",
        "$5M-<$25M",
        "$25M-<$75M",
        "$75M-<$150M",
        "$150M+",
    ]
    values = pd.cut(
        historical["ContractTotal"],
        bins=value_bins,
        labels=value_labels,
        right=False,
    )
    value_distribution = (
        values.value_counts(sort=False).rename("contracts").reset_index()
    )
    value_distribution.columns = ["guarantee_band", "contracts"]
    value_distribution["percent"] = (
        100 * value_distribution["contracts"] / value_distribution["contracts"].sum()
    ).round(1)

    perf_rows: list[dict[str, Any]] = []
    for season, group in historical.groupby("season", sort=True):
        perf_rows.append(
            {
                "contract_start_year": int(season),
                "complete_contracts": len(group),
                "has_contract_year_row": int(group["has_contract_year_row"].sum()),
                "has_three_pre_rows": int(group["has_three_pre_rows"].sum()),
                "has_any_post_row": int(group["has_any_post_row"].sum()),
                "has_all_elapsed_rows": int(group["has_all_elapsed_rows"].sum()),
            }
        )
    performance_coverage = pd.DataFrame(perf_rows)

    sensitivity_rows: list[dict[str, Any]] = []
    for label, threshold in (
        (">$0", 0),
        (">=$1M", 1_000_000),
        (">=$5M", 5_000_000),
        (">=$25M", 25_000_000),
    ):
        cohort = historical[historical["ContractTotal"].ge(threshold)]
        player_season_sizes = cohort.groupby(["season", "playerId"]).size()
        sensitivity_rows.append(
            {
                "guarantee_screen": label,
                "contracts": len(cohort),
                "duplicate_player_season_groups": int((player_season_sizes > 1).sum()),
                "contract_year_row_percent": round(
                    100 * cohort["has_contract_year_row"].mean(), 1
                ),
                "three_pre_rows_percent": round(
                    100 * cohort["has_three_pre_rows"].mean(), 1
                ),
                "any_post_row_percent": round(
                    100 * cohort["has_any_post_row"].mean(), 1
                ),
            }
        )
    eligibility_sensitivity = pd.DataFrame(sensitivity_rows)

    return {
        "tracker_coverage_by_season": by_season,
        "missingness_signed_rows": missingness,
        "role_split_complete_contracts": role_split,
        "age_distribution_completed_classes": age_distribution,
        "contract_value_distribution_completed_classes": value_distribution,
        "performance_coverage_by_season": performance_coverage,
        "eligibility_sensitivity": eligibility_sensitivity,
        "_historical": historical,
        "_primary": primary,
    }


def make_summary(contracts: pd.DataFrame, outputs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    historical = outputs["_historical"]
    primary = outputs["_primary"]
    current = contracts[contracts["season"].eq(TRACKER_LAST_SEASON)]
    signed = contracts[contracts["is_signed"]]
    complete = contracts[contracts["has_complete_contract"]]
    numeric_guarantees = historical["ContractTotal"].dropna()
    numeric_ages = historical["age"].dropna()
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_coverage": {
            "tracker_first_season": TRACKER_FIRST_SEASON,
            "tracker_last_season": TRACKER_LAST_SEASON,
            "completed_outcome_last_season": LAST_COMPLETED_SEASON,
            "tracker_rows": len(contracts),
            "signed_rows": len(signed),
            "complete_contract_rows": len(complete),
            "completed_class_complete_contract_rows": len(historical),
            "completed_class_ge_5m_rows": len(primary),
        },
        "coverage": {
            "contract_year_row_complete_historical": _count_and_percent(
                historical["has_contract_year_row"]
            ),
            "three_pre_rows_complete_historical": _count_and_percent(
                historical["has_three_pre_rows"]
            ),
            "any_post_row_complete_historical": _count_and_percent(
                historical["has_any_post_row"]
            ),
            "all_elapsed_rows_complete_historical": _count_and_percent(
                historical["has_all_elapsed_rows"]
            ),
            "historical_projection_complete_historical": _count_and_percent(
                historical["war_proj"].notna()
            ),
            "current_2026_projection_all_tracker_rows": _count_and_percent(
                current["war_proj"].notna()
            ),
            "crowd_estimate_complete_historical": _count_and_percent(
                historical["med_years"].notna() & historical["med_aav"].notna()
            ),
            "contract_year_row_ge_5m_historical": _count_and_percent(
                primary["has_contract_year_row"]
            ),
            "three_pre_rows_ge_5m_historical": _count_and_percent(
                primary["has_three_pre_rows"]
            ),
            "any_post_row_ge_5m_historical": _count_and_percent(
                primary["has_any_post_row"]
            ),
            "all_elapsed_rows_ge_5m_historical": _count_and_percent(
                primary["has_all_elapsed_rows"]
            ),
        },
        "distributions": {
            "age": {
                "count": int(numeric_ages.size),
                "min": float(numeric_ages.min()),
                "median": float(numeric_ages.median()),
                "max": float(numeric_ages.max()),
            },
            "guaranteed_dollars": {
                "count": int(numeric_guarantees.size),
                "min": float(numeric_guarantees.min()),
                "p25": float(numeric_guarantees.quantile(0.25)),
                "median": float(numeric_guarantees.median()),
                "p75": float(numeric_guarantees.quantile(0.75)),
                "p90": float(numeric_guarantees.quantile(0.90)),
                "max": float(numeric_guarantees.max()),
            },
        },
        "sources": {
            "free_agent_tracker": TRACKER_URL,
            "player_leaderboards": LEADERS_URL,
        },
    }
    canonical = json.dumps(payload, sort_keys=True).encode("utf-8")
    payload["summary_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def run_audit(output_dir: Path) -> dict[str, Any]:
    session = make_session()
    tracker_rows: list[dict[str, Any]] = []
    for season in range(TRACKER_FIRST_SEASON, TRACKER_LAST_SEASON + 1):
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
    contracts = add_performance_coverage(contracts, performance)
    outputs = build_outputs(contracts)
    summary = make_summary(contracts, outputs)

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in outputs.items():
        if not name.startswith("_"):
            frame.to_csv(output_dir / f"{name}.csv", index=False)
    (output_dir / "audit_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary
