"""Minimal, source-auditable FanGraphs readers used by Phase 1.

The readers intentionally use the same server-rendered JSON that backs the public
web pages. They do not require undocumented authentication or a commercial API.
Historical projection archives are not fetched because FanGraphs labels them as
members-only data.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable
from typing import Any

import requests

TRACKER_URL = "https://www.fangraphs.com/roster-resource/free-agent-tracker"
LEADERS_URL = "https://www.fangraphs.com/leaders/major-league"

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)


class SourceFormatError(RuntimeError):
    """Raised when a source page no longer matches the audited payload shape."""


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "contract-alpha-data-audit/0.1 "
                "(research; source URLs documented in repository)"
            )
        }
    )
    return session


def _get(session: requests.Session, url: str, *, params: dict[str, Any]) -> str:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = session.get(url, params=params, timeout=120)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Unable to fetch {url}: {last_error}")


def extract_next_data(html: str) -> dict[str, Any]:
    match = _NEXT_DATA_RE.search(html)
    if not match:
        raise SourceFormatError("Page does not contain a __NEXT_DATA__ payload")
    return json.loads(match.group(1))


def _query_data(payload: dict[str, Any]) -> Iterable[Any]:
    try:
        queries = payload["props"]["pageProps"]["dehydratedState"]["queries"]
    except KeyError as exc:
        raise SourceFormatError("Next.js query state was not found") from exc
    for query in queries:
        yield query.get("state", {}).get("data")


def extract_tracker_rows(html: str) -> list[dict[str, Any]]:
    for data in _query_data(extract_next_data(html)):
        if (
            isinstance(data, list)
            and (not data or isinstance(data[0], dict))
            and (not data or {"playerName", "ContractTotal"}.issubset(data[0]))
        ):
            return data
    raise SourceFormatError("Free-agent tracker rows were not found")


def extract_leader_rows(html: str) -> list[dict[str, Any]]:
    for data in _query_data(extract_next_data(html)):
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            rows = data["data"]
            if not rows or {"Season", "playerid"}.issubset(rows[0]):
                return rows
    raise SourceFormatError("Leaderboard rows were not found")


def fetch_tracker(session: requests.Session, season: int) -> list[dict[str, Any]]:
    html = _get(session, TRACKER_URL, params={"season": season, "pos": "all"})
    return extract_tracker_rows(html)


def fetch_player_seasons(
    session: requests.Session,
    *,
    player_ids: Iterable[str | int],
    stats: str,
    first_season: int,
    last_season: int,
) -> list[dict[str, Any]]:
    if stats not in {"bat", "pit"}:
        raise ValueError("stats must be 'bat' or 'pit'")
    ids = [str(player_id) for player_id in player_ids]
    if not ids:
        return []
    params = {
        "pos": "all",
        "stats": stats,
        "lg": "all",
        "qual": "0",
        "type": "8",
        "season": str(last_season),
        "season1": str(first_season),
        "ind": "1",
        "pageitems": "2000",
        "pagenum": "1",
        "players": ",".join(ids),
    }
    html = _get(session, LEADERS_URL, params=params)
    return extract_leader_rows(html)
