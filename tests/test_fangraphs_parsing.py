import json
import unittest

from contract_alpha.audit import classify_role, prepare_contracts
from contract_alpha.ingestion.fangraphs import (
    SourceFormatError,
    extract_leader_rows,
    extract_tracker_rows,
)


def next_page_queries(*data_items):
    payload = {
        "props": {
            "pageProps": {
                "dehydratedState": {
                    "queries": [
                        {"state": {"data": data_item}} for data_item in data_items
                    ]
                }
            }
        }
    }
    return (
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script>"
    )


def next_page(data):
    return next_page_queries(data)


class ParsingTests(unittest.TestCase):
    def test_extract_tracker_rows(self):
        rows = [{"playerName": "Example", "ContractTotal": 10_000_000}]
        self.assertEqual(extract_tracker_rows(next_page(rows)), rows)

    def test_tracker_ignores_unrelated_empty_query(self):
        rows = [{"playerName": "Example", "ContractTotal": 10_000_000}]
        self.assertEqual(extract_tracker_rows(next_page_queries([], rows)), rows)

    def test_empty_tracker_candidate_fails_loudly(self):
        with self.assertRaises(SourceFormatError):
            extract_tracker_rows(next_page([]))

    def test_extract_leader_rows(self):
        rows = [{"playerid": 123, "Season": 2024, "WAR": 2.0}]
        self.assertEqual(
            extract_leader_rows(next_page({"data": rows, "totalCount": 1})), rows
        )

    def test_format_drift_fails_loudly(self):
        with self.assertRaises(SourceFormatError):
            extract_tracker_rows(next_page([{"unexpected": True}]))

    def test_role_classification(self):
        cases = [
            ("SP", "pitcher"),
            ("SP/RP", "pitcher"),
            ("SS/2B", "hitter"),
            ("DH/SP", "two-way"),
        ]
        for position, expected in cases:
            with self.subTest(position=position):
                self.assertEqual(classify_role(position), expected)

    def test_contract_completeness_requires_positive_actual_terms(self):
        import pandas as pd

        frame = pd.DataFrame(
            [
                {
                    "playerId": "1",
                    "position": "SS",
                    "team_new": "NYY",
                    "contract_years": 2,
                    "ContractTotal": 12_000_000,
                    "aav": 6_000_000,
                },
                {
                    "playerId": "2",
                    "position": "RP",
                    "team_new": "BOS",
                    "contract_years": 1,
                    "ContractTotal": 0,
                    "aav": 0,
                },
            ]
        )
        for column in ["age", "war_prev", "war_proj", "med_years", "med_aav"]:
            frame[column] = None
        audited = prepare_contracts(frame)
        self.assertEqual(audited["has_complete_contract"].tolist(), [True, False])
        self.assertEqual(audited["meets_5m_screen"].tolist(), [True, False])


if __name__ == "__main__":
    unittest.main()
