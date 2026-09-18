"""Findings-led MLB Contract-Year Trap research application."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "data" / "processed" / "public"
PRIVATE_DIR = Path(
    os.environ.get("CONTRACT_ALPHA_PRIVATE_DIR", ROOT / "data" / "processed" / "private")
)


@st.cache_data
def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def money(value: float | None, decimals: int = 1) -> str:
    if value is None or not math.isfinite(float(value)):
        return "—"
    value = float(value)
    sign = "−" if value < 0 else ""
    return f"{sign}${abs(value) / 1_000_000:,.{decimals}f}M"


def interval(row: dict, *, percent: bool = False, money_units: bool = False) -> str:
    low, high = row["ci_low"], row["ci_high"]
    if percent:
        transform = lambda value: 100 * (math.exp(value) - 1)
        return f"95% CI {transform(low):+.1f}% to {transform(high):+.1f}% · n={row['n']:,}"
    if money_units:
        return f"95% CI {low:+.2f} to {high:+.2f} $M/year · n={row['n']:,}"
    return f"95% CI {low:+.2f} to {high:+.2f} WAR/year · n={row['n']:,}"


def leaderboard_frame(records: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    return pd.DataFrame(
        {
            "Player": frame["player_name"],
            "Deal": frame["start_year"].astype(str) + " " + frame["signing_team"],
            "Guarantee": frame["guaranteed_dollars"].map(money),
            "Spike WAR": frame["performance_spike"].map(lambda value: f"{value:+.1f}"),
            "Future WAR/yr": frame["future_war_per_season"].map(lambda value: f"{value:.1f}"),
            "Baseline-price residual": frame["guarantee_baseline_residual"].map(money),
            "Model range": frame["guarantee_benchmark_reliability"],
            "Realized WAR": frame["realized_war"].map(lambda value: f"{value:.1f}"),
            "Alpha": frame["contract_alpha"].map(money),
            "ROI": frame["alpha_roi_percent"].map(lambda value: f"{value:+.0f}%"),
        }
    )


def team_frame(frame: pd.DataFrame, scenario: str) -> pd.DataFrame:
    suffix = scenario.lower()
    return pd.DataFrame(
        {
            "Team": frame["signing_team"],
            "Contracts": frame["contracts"],
            "Priced deals": frame["price_prediction_contracts"],
            "Guarantees": frame["total_guarantee"].map(money),
            "Baseline-price residual": frame["total_guarantee_baseline_residual"].map(money),
            "Elapsed cost": frame["realized_cost"].map(money),
            "Production value": frame[f"realized_production_value_{suffix}"].map(money),
            "Realized alpha": frame[f"contract_alpha_{suffix}"].map(money),
            "Alpha ROI": frame[f"alpha_roi_percent_{suffix}"].map(lambda value: f"{value:+.0f}%"),
        }
    )


st.set_page_config(page_title="MLB Contract-Year Trap — MLB contract returns", page_icon="⚾", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: radial-gradient(circle at 85% -10%, #203040 0, #0b1118 31rem); }
    [data-testid="stHeader"] { background: transparent; }
    .eyebrow { color: #ffb34d; font-size: .76rem; font-weight: 800; letter-spacing: .15em; text-transform: uppercase; }
    .hero { font-size: clamp(2.7rem, 6vw, 5.5rem); font-weight: 790; letter-spacing: -.055em; line-height: .94; margin: .5rem 0 1rem; }
    .dek { color: #bec8d1; font-size: 1.16rem; line-height: 1.6; max-width: 59rem; }
    .scope { display: inline-block; margin-top: 1rem; padding: .38rem .72rem; border: 1px solid #ffb34d80; border-radius: 999px; color: #ffd59e; background: #ffb34d10; font-size: .78rem; font-weight: 750; }
    .finding { min-width: 0; min-height: 8.7rem; padding: 1rem 1.05rem; border: 1px solid #293846; border-radius: 14px; background: #121b24cc; box-sizing: border-box; overflow-wrap: anywhere; }
    .finding-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; width: 100%; max-width: 100%; box-sizing: border-box; }
    .finding-kicker { color: #8ea1b2; font-size: .74rem; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
    .finding-value { color: #f5f1e8; font-size: 1.65rem; font-weight: 760; margin: .3rem 0; }
    .finding-copy { color: #b9c4cd; font-size: .86rem; line-height: 1.45; }
    .callout { border-left: 3px solid #ffb34d; padding: .85rem 1rem; background: #ffb34d0b; color: #dce2e7; }
    [data-testid="stMetric"] { background: #121b24cc; border: 1px solid #293846; border-radius: 14px; padding: .9rem; }
    div[data-testid="stExpander"] { border-color: #293846; }
    @media (max-width: 650px) { .finding-grid { grid-template-columns: 1fr; } .finding { min-height: auto; } }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    summary = load_json(PUBLIC_DIR / "analysis_summary.json")
    leaderboards = load_json(PUBLIC_DIR / "leaderboards.json")
    research = load_csv(PUBLIC_DIR / "research_results.csv")
    validation = load_csv(PUBLIC_DIR / "model_validation.csv")
    market = load_csv(PUBLIC_DIR / "market_price_per_war.csv")
    teams = load_csv(PUBLIC_DIR / "team_results.csv")
    market_sensitivity = load_csv(PUBLIC_DIR / "market_value_sensitivity.csv")
    baseline_sensitivity = load_csv(PUBLIC_DIR / "baseline_history_sensitivity.csv")
    size_validation = load_csv(PUBLIC_DIR / "contract_size_validation.csv")
except (FileNotFoundError, json.JSONDecodeError, pd.errors.ParserError) as exc:
    st.error(f"The committed research outputs could not be loaded: {exc}")
    st.stop()

answers = summary["answers"]
price = answers["A_price"]
persistence = answers["B_persistence"]
alpha = answers["C_alpha"]
residual = answers["D_residual"]
price_percent = 100 * (math.exp(price["estimate"]) - 1)
persistence_percent = 100 * persistence["estimate"]
faded_percent = 100 - persistence_percent

st.markdown('<div class="eyebrow">MLB free-agent pricing and returns</div>', unsafe_allow_html=True)
st.markdown('<div class="hero">MLB Contract-Year Trap</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="dek">Do teams pay for sustainable talent—or the perfect contract year? '
    "This study follows 2020–2025 free agents from pre-signing performance through the value "
    "they delivered after signing.</div>",
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="scope">2020–2025 STUDY · {summary["cohort"]["primary_modelable_contracts"]:,} MODELABLE DEALS · REALIZED THROUGH 2025</div>',
    unsafe_allow_html=True,
)

st.write("")
finding_cards = [
    (
        "1 · Price",
        f"{price_percent:+.0f}% guarantee",
        f"per +1 WAR contract-year spike, conditional on baseline, age, role and offseason. {interval(price, percent=True)}",
    ),
    (
        "2 · Persistence",
        f"{persistence_percent:.0f}% persisted",
        f"of each +1 WAR spike per future season. The corresponding fade is {faded_percent:.0f}%. "
        f"95% CI {100 * persistence['ci_low']:.1f}% to {100 * persistence['ci_high']:.1f}% · n={persistence['n']:,}",
    ),
    (
        "3 · Realized alpha",
        f"{money(alpha['estimate'] * 1_000_000, 2)}/year",
        f"for each +1 WAR spike. The primary estimate is negative, but sensitive to the 2021 screen. {interval(alpha, money_units=True)}",
    ),
    (
        "4 · Baseline-price residual",
        f"{residual['estimate']:+.2f} $M/year",
        f"per $10M above the sustainable-baseline benchmark. Directionally negative, but inconclusive overall. {interval(residual, money_units=True)}",
    ),
]
cards_html = "".join(
    f'<div class="finding"><div class="finding-kicker">{kicker}</div>'
    f'<div class="finding-value">{value}</div><div class="finding-copy">{copy}</div></div>'
    for kicker, value, copy in finding_cards
)
st.markdown(f'<div class="finding-grid">{cards_html}</div>', unsafe_allow_html=True)

st.caption(
    "Associations are descriptive, not causal. Confidence intervals use player-clustered standard errors; all models include offseason fixed effects."
)
st.markdown("### How to read these results")
st.markdown(
    """
    - **Sustainable baseline:** a 50/30/20 weighted history of observed pre-contract MLB seasons; missing rows are not silently assigned zero WAR.
    - **Contract-year spike:** contract-year WAR minus that sustainable baseline.
    - **Realized on-field alpha:** realized WAR valued at the base-case offseason market $/WAR, minus approximate elapsed AAV cost.
    - **Baseline-price residual:** actual guarantee minus a pre-signing historical benchmark. It is a model residual—not proof that a club irrationally overpaid.
    """
)
st.divider()

has_private_explorer = (
    (PRIVATE_DIR / "contract_research_panel.csv").exists()
    and (PRIVATE_DIR / "contract_timelines.csv").exists()
)
contracts_tab_label = "Contract explorer" if has_private_explorer else "Selected contracts"
findings_tab, traps_tab, explorer_tab, validation_tab, method_tab = st.tabs(
    ["What we found", "Contract-Year Trap", contracts_tab_label, "Model checks", "Method & limits"]
)

with findings_tab:
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.subheader("The market paid for the spike—and most of it faded")
        st.write(
            f"A one-WAR contract-year spike was associated with a **{price_percent:.1f}% larger "
            f"guarantee**, holding the player's prior baseline, age, role and signing offseason "
            f"constant. After signing, **{persistence_percent:.0f}% of the incremental spike "
            f"persisted**. The corresponding **{faded_percent:.0f}% faded** is simply one minus "
            "that persistence estimate—not a separate model."
        )
        st.write(
            f"The same one-WAR spike was associated with **{money(abs(alpha['estimate']) * 1_000_000, 2)} "
            "less on-field alpha per elapsed contract year**. That result is statistically clear in "
            "the primary sample and especially strong for pitchers, but it becomes uncertain when "
            "the post-shortened-season 2021 class is excluded."
        )
        st.markdown(
            '<div class="callout"><strong>Bottom line:</strong> contract-year surges carried some real signal, '
            "but teams paid as if much more of the surge would last. The strongest return penalty appears in pitcher deals.</div>",
            unsafe_allow_html=True,
        )
    with right:
        st.subheader("Estimated market price of a WAR")
        market_chart = market.assign(
            market_m=market["market_dollars_per_war"] / 1_000_000,
            season=market["season"].astype(str),
        ).set_index("season")[["market_m"]]
        st.line_chart(market_chart, color="#ffb34d")
        st.caption("Median winsorized AAV divided by sustainable pre-signing WAR; $M per WAR.")

    st.subheader("Does the result survive reasonable alternatives?")
    sensitivity = research[
        research["question"].isin(["A_price", "B_persistence", "C_alpha", "D_residual"])
    ].copy()
    labels = {
        "A_price": "Spike → log guarantee",
        "B_persistence": "Spike → future WAR/year",
        "C_alpha": "Spike → alpha/year ($M)",
        "D_residual": "Baseline-price residual → alpha/year ($M)",
    }
    sensitivity["Question"] = sensitivity["question"].map(labels)
    sensitivity["Screen"] = sensitivity["specification"].replace(
        {
            "primary": "Primary ≥$5M",
            "minimum_1m": "Deals ≥$1M",
            "large_25m": "Deals ≥$25M",
            "exclude_2021": "Exclude 2021",
            "hitters": "Hitters",
            "pitchers": "Pitchers",
        }
    )
    sensitivity["Estimate (95% CI)"] = sensitivity.apply(
        lambda row: f"{row['estimate']:+.3f} [{row['ci_low']:+.3f}, {row['ci_high']:+.3f}]", axis=1
    )
    st.dataframe(
        sensitivity[["Question", "Screen", "Estimate (95% CI)", "n"]].rename(columns={"n": "N"}),
        hide_index=True,
        width="stretch",
    )

    robustness_left, robustness_right = st.columns(2, gap="large")
    with robustness_left:
        st.markdown("#### Baseline-history sensitivity")
        baseline_table = baseline_sensitivity.copy()
        baseline_table["Result"] = baseline_table.apply(
            lambda row: f"{row['estimate']:+.3f} [{row['ci_low']:+.3f}, {row['ci_high']:+.3f}]",
            axis=1,
        )
        baseline_table["Question"] = baseline_table["question"].map(
            {
                "A_price": "Price",
                "B_persistence": "Persistence",
                "C_alpha": "Alpha/year",
            }
        )
        st.dataframe(
            baseline_table[["Question", "minimum_observed_baseline_seasons", "Result", "n"]].rename(
                columns={"minimum_observed_baseline_seasons": "Min. seasons", "n": "N"}
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Price and persistence barely move. The alpha estimate remains negative with all three "
            "baseline seasons, but its 95% interval crosses zero."
        )
    with robustness_right:
        st.markdown("#### Market-value sensitivity")
        market_table = market_sensitivity.copy()
        market_table["Assumption"] = market_table["scenario"].map(
            {"low": "75% of base", "base": "Base case", "high": "125% of base"}
        )
        market_table["Spike → alpha/year"] = market_table.apply(
            lambda row: f"{row['estimate']:+.3f} [{row['ci_low']:+.3f}, {row['ci_high']:+.3f}]",
            axis=1,
        )
        market_table["Trap top-10 overlap"] = market_table[
            "trap_top10_overlap_with_base"
        ].map(lambda value: f"{int(value)}/10")
        st.dataframe(
            market_table[["Assumption", "Spike → alpha/year", "contract_year_traps", "Trap top-10 overlap"]].rename(
                columns={"contract_year_traps": "Trap contracts"}
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "The coefficient stays negative in all three cases, but becomes statistically uncertain "
            "when each WAR is valued 25% above the base estimate."
        )

with traps_tab:
    st.subheader("Contract-Year Trap leaderboard")
    st.write(
        "These deals combined a top-quintile pre-signing spike with negative realized on-field "
        "alpha. Ranking uses realized value through 2025, so newer and still-active contracts are censored."
    )
    board_choice = st.radio(
        "Leaderboard",
        [
            "Contract-year traps",
            "Largest value destruction",
            "Best realized alpha",
            "Biggest spikes",
            "Largest baseline-price residual",
        ],
        horizontal=True,
    )
    board_key = {
        "Contract-year traps": "contract_year_traps",
        "Largest value destruction": "value_destruction",
        "Best realized alpha": "positive_alpha",
        "Biggest spikes": "contract_year_spikes",
        "Largest baseline-price residual": "largest_baseline_price_residuals",
    }[board_choice]
    st.dataframe(leaderboard_frame(leaderboards[board_key]), hide_index=True, width="stretch")
    st.caption(
        "Alpha = realized FanGraphs WAR × estimated signing-offseason $/WAR − AAV-based elapsed cost. "
        "A negative WAR season reduces production value; it is not floored at zero."
    )
    if board_choice == "Largest baseline-price residual":
        st.warning(
            "Large residuals—especially for superstar contracts—often fall outside the model's "
            "reliable range. They are benchmark misses, not definitive evidence of overpayment."
        )
    st.subheader("Team capital allocation")
    st.write(
        "Team totals aggregate primary-screen free-agent deals and their realized-to-date on-field "
        "alpha. They are not a front-office ranking: spending level, roster context, and censoring differ."
    )
    team_sort = st.radio(
        "Team ranking",
        ["Highest alpha", "Lowest alpha", "Largest baseline-price residual"],
        horizontal=True,
    )
    team_scenario = st.selectbox(
        "WAR valuation assumption",
        ["Base", "Low", "High"],
        help="Low and high value every WAR at 75% and 125% of the base estimate.",
    )
    scenario_suffix = team_scenario.lower()
    team_sort_rules = {
        "Highest alpha": (f"contract_alpha_{scenario_suffix}", False),
        "Lowest alpha": (f"contract_alpha_{scenario_suffix}", True),
        "Largest baseline-price residual": ("total_guarantee_baseline_residual", False),
    }
    sort_column, ascending = team_sort_rules[team_sort]
    ranked_teams = teams.sort_values(sort_column, ascending=ascending)
    st.dataframe(
        team_frame(ranked_teams, team_scenario), hide_index=True, width="stretch"
    )
    st.caption(
        "The baseline-price residual is actual guarantee minus the pre-signing sustainable-baseline "
        "benchmark. It is available only for contracts with an earlier-offseason training set."
    )

with explorer_tab:
    panel_path = PRIVATE_DIR / "contract_research_panel.csv"
    timeline_path = PRIVATE_DIR / "contract_timelines.csv"
    if has_private_explorer:
        panel = load_csv(panel_path)
        timelines = load_csv(timeline_path)
        primary_panel = panel[panel["is_primary"].astype(bool)].copy()
        primary_panel["choice"] = primary_panel.apply(
            lambda row: f"{row['player_name']} — {row['start_year']} {row['signing_team']} — {money(row['guaranteed_dollars'])}",
            axis=1,
        )
        st.subheader("Player and contract explorer")
        selected_label = st.selectbox("Contract", primary_panel.sort_values(["player_name", "start_year"])["choice"])
        selected = primary_panel.loc[primary_panel["choice"].eq(selected_label)].iloc[0]
        metrics = st.columns(5)
        metrics[0].metric("Actual guarantee", money(selected["guaranteed_dollars"]))
        metrics[1].metric("Baseline WAR", f"{selected['baseline_war']:.1f}")
        metrics[2].metric("Contract-year spike", f"{selected['performance_spike']:+.1f} WAR")
        metrics[3].metric("Realized WAR", f"{selected['realized_war']:.1f}")
        metrics[4].metric("Realized alpha", money(selected["contract_alpha"]))

        chart_side, detail_side = st.columns([1.35, 1], gap="large")
        with chart_side:
            st.markdown("#### Performance timeline")
            timeline = timelines[
                timelines["contract_id"].eq(selected["contract_id"]) & timelines["observed"].astype(bool)
            ][["season", "war"]].set_index("season")
            st.line_chart(timeline, color="#ffb34d")
            st.caption(
                f"Contract year: {int(selected['contract_year'])}. A season without an MLB leaderboard row is "
                "omitted from the line and contributes zero realized MLB WAR after a successful source query; "
                "it remains distinct from an observed 0.0-WAR season."
            )
        with detail_side:
            st.markdown("#### Deal economics")
            expected = money(selected["predicted_guarantee"])
            if math.isfinite(float(selected["predicted_guarantee"])):
                expected_range = f"{money(selected['predicted_guarantee_low'])}–{money(selected['predicted_guarantee_high'])}"
            else:
                expected_range = "Not scored: no prior offseason training set"
            details = pd.DataFrame(
                {
                    "Measure": [
                        "Sustainable-baseline guarantee benchmark",
                        "Empirical 80% interval",
                        "Baseline-price residual",
                        "Benchmark reliability",
                        "Elapsed cost",
                        "Realized production value",
                        "Alpha ROI",
                        "Classification",
                    ],
                    "Value": [
                        expected,
                        expected_range,
                        money(selected["guarantee_baseline_residual"]),
                        selected["guarantee_benchmark_reliability"],
                        money(selected["realized_cost"]),
                        money(selected["realized_production_value"]),
                        f"{selected['alpha_roi_percent']:+.1f}%",
                        selected["classification"],
                    ],
                }
            )
            st.dataframe(details, hide_index=True, width="stretch")
            st.caption(
                "This is a broad historical benchmark—not a fair-value appraisal or proof of "
                "irrational pricing. Star contracts can fall outside its already-wide interval."
            )
        st.markdown("#### Elapsed contract cash flow")
        cashflow = timelines[
            timelines["contract_id"].eq(selected["contract_id"])
            & timelines["period"].eq("under_contract")
        ].copy()
        cashflow_table = pd.DataFrame(
            {
                "Season": cashflow["season"].astype(int),
                "WAR": cashflow["war"].map(lambda value: f"{value:.1f}"),
                "Estimated cost": cashflow["salary_cost"].map(money),
                "Production value": cashflow["production_value"].map(money),
                "Season alpha": cashflow["season_alpha"].map(money),
            }
        )
        st.dataframe(cashflow_table, hide_index=True, width="stretch")
    else:
        st.subheader("Selected contracts")
        st.info(
            "This hosted view is a curated set of transformed contract results, not a searchable "
            "full-dataset explorer. The complete player, team, and offseason explorer is local-only "
            "while source-data redistribution permission remains unresolved."
        )
        st.dataframe(leaderboard_frame(leaderboards["contract_year_traps"]), hide_index=True, width="stretch")

with validation_tab:
    st.subheader("Forward validation, not a random split")
    st.write(
        "Each offseason is predicted only from earlier offseasons. The first class has no estimate; "
        "later classes never train on future contracts or post-signing performance."
    )
    validation_columns = st.columns(3)
    validation_labels = {
        "aav": "AAV benchmark",
        "guaranteed_dollars": "Guarantee benchmark",
        "contract_years": "Contract length",
    }
    for column, target in zip(validation_columns, ["aav", "guaranteed_dollars", "contract_years"]):
        result = summary["validation"][target]
        currency = target != "contract_years"
        value = money(result["weighted_mae"], 2) if currency else f"{result['weighted_mae']:.2f} years"
        baseline = money(result["weighted_naive_mae"], 2) if currency else f"{result['weighted_naive_mae']:.2f} years"
        with column:
            st.metric(validation_labels[target], value, delta=f"Naive MAE {baseline}", delta_color="off")
            if result["beats_naive"]:
                st.success("Beat the role-median baseline")
            else:
                st.error("Did not beat baseline — do not use")

    fold_table = validation.copy()
    fold_table["Model MAE"] = fold_table.apply(
        lambda row: money(row["mae"], 2) if row["target"] != "contract_years" else f"{row['mae']:.2f}", axis=1
    )
    fold_table["Naive MAE"] = fold_table.apply(
        lambda row: money(row["naive_mae"], 2) if row["target"] != "contract_years" else f"{row['naive_mae']:.2f}", axis=1
    )
    with st.expander("See every forward-validation fold"):
        st.dataframe(
            fold_table[["test_year", "training_last_year", "target", "n_train", "n_test", "Model MAE", "Naive MAE"]],
            hide_index=True,
            width="stretch",
        )
    st.markdown("#### Guarantee error by actual contract size")
    size_table = size_validation.copy()
    size_table["MAE"] = size_table["mae"].map(lambda value: money(value, 2))
    size_table["Median error"] = size_table["median_absolute_error"].map(
        lambda value: money(value, 2)
    )
    size_table["Median % error"] = size_table[
        "median_absolute_percentage_error"
    ].map(lambda value: f"{value:.1f}%")
    size_table["Interval coverage"] = size_table[
        "empirical_interval_coverage_percent"
    ].map(lambda value: f"{value:.1f}%")
    st.dataframe(
        size_table[
            [
                "contract_size_band",
                "n",
                "MAE",
                "Median error",
                "Median % error",
                "mean_absolute_log_error",
                "Interval coverage",
            ]
        ].rename(
            columns={
                "contract_size_band": "Actual guarantee",
                "n": "N",
                "mean_absolute_log_error": "Mean abs. log error",
            }
        ),
        hide_index=True,
        width="stretch",
    )
    st.warning(
        "The guarantee model improves on a simple baseline at the population level, but individual "
        "performance is poor for \\$100M+ contracts: their MAE exceeds \\$150M and fewer than 40% fall "
        "inside the empirical interval. Extreme superstar residuals are not reliable appraisals. "
        "Contract-length predictions failed the baseline and are excluded from decision-useful outputs."
    )

with method_tab:
    st.subheader("Definitions that drive the result")
    method_left, method_right = st.columns(2, gap="large")
    with method_left:
        st.markdown(
            """
            #### Contract-year spike

            Contract-year WAR minus a **50% / 30% / 20% weighted** average of the prior three
            seasons. Weights are renormalized over observed MLB rows; an unobserved row is not
            silently converted to zero. The pipeline also separates rate and playing-time components.

            #### Realized contract alpha

            Realized WAR × the relevant season's empirical market price of WAR, minus elapsed
            AAV-based cost. The displayed estimate is the base case; results are repeated at 75%
            and 125% of that $/WAR value. Active contracts are measured only through 2025.

            #### Primary cohort

            True free-agent deals beginning in 2020–2025 with at least a $5 million guarantee,
            an observed contract year and at least one observed baseline season.
            """
        )
    with method_right:
        st.markdown(
            """
            #### 2020 treatment

            The shortened season is scaled to a 162-game equivalent for signal construction.
            When 2020 is an elapsed contract season, cost is prorated to 60/162 of AAV.

            #### Inference

            Linear models include baseline WAR, age, age², role and offseason fixed effects.
            Standard errors are clustered by player. Results are associations, not causal effects.

            #### Pricing benchmark

            Ridge models use sustainable, pre-signing-only features and expanding-window validation.
            No post-signing variable is available to the model at prediction time. The result is a
            baseline-price residual, not a fair-value appraisal; \\$100M+ contracts are outside the
            model's reliable range unusually often.

            #### Persistence

            The primary estimate is the share of spike WAR associated with future WAR per season.
            The percentage that faded is one minus that estimate, not an independent result.
            """
        )
    st.markdown("#### Important limits")
    for limitation in summary["limitations"]:
        st.markdown(f"- {limitation}")
    st.write(
        "The app does not run ingestion at startup. Committed output files are reproducible with the "
        "analysis pipeline; full row-level outputs remain local-only pending redistribution permission."
    )
    st.markdown(
        "[Read the full methodology](https://github.com/zaynr13/contract-alpha/blob/main/docs/methodology.md)"
        " · [Review the data notice](https://github.com/zaynr13/contract-alpha/blob/main/NOTICE.md)"
    )

st.divider()
st.caption(
    f"Research outputs generated {summary['generated_at_utc'][:10]} · Source: FanGraphs Free Agent Tracker and Major League Leaderboards"
)
