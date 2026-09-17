"""Read-only Phase 1 data-feasibility dashboard for Contract Alpha."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
AUDIT_DIR = ROOT / "data" / "processed" / "audit"


@st.cache_data
def load_json(name: str) -> dict:
    with (AUDIT_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(AUDIT_DIR / name)


def metric_card(label: str, value: str, help_text: str) -> None:
    st.metric(label, value, help=help_text)


def coverage_chart(frame: pd.DataFrame, selected_screen: str) -> None:
    selected = frame.loc[frame["guarantee_screen"] == selected_screen].iloc[0]
    chart = pd.DataFrame(
        {
            "Coverage": [
                selected["contract_year_row_percent"],
                selected["three_pre_rows_percent"],
                selected["any_post_row_percent"],
            ]
        },
        index=["Contract-year row", "All 3 pre-years", "Any post-signing row"],
    )
    st.bar_chart(chart, horizontal=True, color="#ffb347")


st.set_page_config(
    page_title="Contract Alpha — Data Feasibility",
    page_icon="⚾",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp { background-image: radial-gradient(circle at 82% 0%, #1d2a34 0, #0b1016 32rem); }
    [data-testid="stHeader"] { background: transparent; }
    .eyebrow { color: #ffb347; font-size: .78rem; font-weight: 750; letter-spacing: .14em; text-transform: uppercase; }
    .hero-title { font-size: clamp(2.5rem, 6vw, 5.4rem); font-weight: 760; letter-spacing: -.055em; line-height: .95; margin: .55rem 0 1rem; }
    .hero-copy { color: #b9c1c9; font-size: 1.12rem; line-height: 1.65; max-width: 52rem; }
    .phase-pill { display: inline-block; margin-top: 1.2rem; padding: .38rem .72rem; border: 1px solid #ffb34788; border-radius: 999px; color: #ffd195; background: #ffb34712; font-size: .8rem; font-weight: 700; }
    .callout { border-left: 3px solid #ffb347; padding: .8rem 1rem; background: #ffb3470b; color: #d8dde2; }
    [data-testid="stMetric"] { background: #141c25cc; border: 1px solid #263440; border-radius: 14px; padding: 1rem; }
    [data-testid="stMetricValue"] { color: #f4f1ea; }
    div[data-testid="stExpander"] { border-color: #2b3945; }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    summary = load_json("audit_summary.json")
    tracker = load_csv("tracker_coverage_by_season.csv")
    sensitivity = load_csv("eligibility_sensitivity.csv")
    age = load_csv("age_distribution_completed_classes.csv")
    roles = load_csv("role_split_complete_contracts.csv")
    guarantees = load_csv("contract_value_distribution_completed_classes.csv")
except (FileNotFoundError, json.JSONDecodeError, pd.errors.ParserError) as exc:
    st.error(f"The committed audit outputs could not be loaded: {exc}")
    st.stop()

source = summary["source_coverage"]
coverage = summary["coverage"]
distributions = summary["distributions"]

st.markdown('<div class="eyebrow">MLB free-agent research</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Contract Alpha</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-copy">Did teams pay for sustainable talent—or for the perfect contract year? '
    "This first release audits whether the data can answer that question before any model makes a claim.</div>",
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="phase-pill">PHASE 1 · DATA FEASIBILITY · NO ESTIMATOR YET</div>',
    unsafe_allow_html=True,
)

st.write("")
st.write("")
metric_columns = st.columns(4)
with metric_columns[0]:
    metric_card("Tracker rows", f"{source['tracker_rows']:,}", "2020–2026 tracker records")
with metric_columns[1]:
    metric_card(
        "Complete contracts",
        f"{source['completed_class_complete_contract_rows']:,}",
        "Positive years, guarantee, and AAV in completed 2020–2025 classes",
    )
with metric_columns[2]:
    metric_card(
        "Primary cohort",
        f"{source['completed_class_ge_5m_rows']:,}",
        "Completed-class contracts with a guarantee of at least $5 million",
    )
with metric_columns[3]:
    metric_card(
        "Historical projections",
        f"{coverage['historical_projection_complete_historical']['percent']:.0f}%",
        "Retained historical projection WAR in the current public tracker payload",
    )

st.divider()

overview, distributions_tab, methods = st.tabs(
    ["Coverage", "Cohort profile", "Method & limits"]
)

with overview:
    st.subheader("Can the study be built?")
    st.markdown(
        '<div class="callout"><strong>Scoped GO.</strong> The public-source design supports a '
        "2020–2025 baseline-based study. It does not yet support the preferred long-run, "
        "projection-rich specification.</div>",
        unsafe_allow_html=True,
    )
    st.write("")
    left, right = st.columns([1, 1.45], gap="large")
    with left:
        st.markdown("#### Eligibility sensitivity")
        selected_screen = st.selectbox(
            "Minimum nominal guarantee",
            sensitivity["guarantee_screen"].tolist(),
            index=2,
        )
        selected = sensitivity.loc[
            sensitivity["guarantee_screen"] == selected_screen
        ].iloc[0]
        st.metric("Contracts retained", f"{int(selected['contracts']):,}")
        st.caption(
            f"Duplicate player/offseason groups: "
            f"{int(selected['duplicate_player_season_groups'])}"
        )
    with right:
        st.markdown("#### Performance-row coverage")
        coverage_chart(sensitivity, selected_screen)
        st.caption("A missing MLB row is not automatically zero performance; Phase 2 must classify it.")

    st.markdown("#### Tracker records by signing class")
    tracker_chart = tracker.set_index("contract_start_year")[[
        "tracker_rows",
        "signed_rows",
        "complete_contract_rows",
        "guarantee_ge_5m",
    ]]
    tracker_chart.columns = ["Tracker", "Signed", "Complete terms", "Guarantee ≥$5M"]
    st.bar_chart(tracker_chart)
    with st.expander("View exact season counts"):
        st.dataframe(tracker, hide_index=True, width="stretch")

with distributions_tab:
    st.subheader("Who and what is in the completed-class universe?")
    stat_columns = st.columns(3)
    with stat_columns[0]:
        metric_card("Median age", f"{distributions['age']['median']:.0f}", "Range: 23–43")
    with stat_columns[1]:
        metric_card(
            "Median guarantee",
            f"${distributions['guaranteed_dollars']['median'] / 1_000_000:.2f}M",
            "Nominal headline guarantee",
        )
    with stat_columns[2]:
        metric_card(
            "90th percentile",
            f"${distributions['guaranteed_dollars']['p90'] / 1_000_000:.2f}M",
            "Nominal headline guarantee",
        )

    chart_columns = st.columns(3, gap="large")
    with chart_columns[0]:
        st.markdown("#### Role")
        st.bar_chart(roles.set_index("role")["complete_contracts"], color="#ffb347")
    with chart_columns[1]:
        st.markdown("#### Age band")
        st.bar_chart(age.set_index("age_band")["contracts"], color="#6fb7c6")
    with chart_columns[2]:
        st.markdown("#### Guarantee band")
        st.bar_chart(
            guarantees.set_index("guarantee_band")["contracts"], color="#95c778"
        )
    st.caption(
        "All distributions describe 1,078 complete positive-value contracts in the "
        "completed 2020–2025 signing classes."
    )

with methods:
    st.subheader("What this dashboard does—and does not—show")
    method_left, method_right = st.columns(2, gap="large")
    with method_left:
        st.markdown(
            """
            #### Supported now

            - Aggregate cohort counts and coverage
            - Role, age, and nominal-guarantee distributions
            - Eligibility-screen sensitivity
            - A reproducible, read-only view of committed audit outputs

            #### Planned Phase 2 controls

            - Pre-signing-only features and forward validation
            - Separate hitter and pitcher specifications
            - Season-length treatment for 2020
            - Explicit missing-appearance and contract-censoring rules
            - Dependence-aware uncertainty and screen sensitivity
            """
        )
    with method_right:
        st.markdown(
            """
            #### Not supported yet

            - A contract-year signal or fair-price estimate
            - Predicted overpayment or realized contract alpha
            - Causal claims about team decision-making
            - Exact cost accounting for deferrals, options, trades, or buyouts
            - Historical public projection coverage for the completed classes
            """
        )
        st.warning(
            "AAV is only a labeled cost fallback. No model-backed result should be "
            "published until the Phase 2 dataset, modeling, and temporal validation exist."
        )

    st.markdown("#### Provenance and public-data boundary")
    st.write(
        "This application reads only the aggregate CSV and JSON files committed with the "
        "repository. It makes no network requests, runs no scraper at startup, and exposes "
        "no player-level source data. Source sites retain their rights; row-level "
        "redistribution and model-backed deployment require a separate rights review."
    )
    st.markdown(
        "[Read the full feasibility report](https://github.com/zaynr13/contract-alpha/blob/main/docs/data-feasibility-report.md)"
        " · [Review the data notice](https://github.com/zaynr13/contract-alpha/blob/main/NOTICE.md)"
    )

st.divider()
st.caption(
    f"Audit generated {summary['generated_at_utc'][:10]} · "
    "Sources: FanGraphs Free Agent Tracker and Major League Leaderboards"
)
