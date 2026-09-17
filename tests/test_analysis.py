import unittest

import numpy as np
import pandas as pd

from contract_alpha.analysis import (
    MODEL_FEATURES,
    add_contract_alpha,
    add_forward_price_predictions,
    aggregate_player_seasons,
    build_contract_panel,
    salary_elapsed_factor,
    season_length_factor,
)


class AnalysisTests(unittest.TestCase):
    def test_2020_has_explicit_signal_and_cost_treatment(self):
        self.assertAlmostEqual(season_length_factor(2020), 162 / 60)
        self.assertAlmostEqual(salary_elapsed_factor(2020), 60 / 162)
        self.assertEqual(season_length_factor(2021), 1)
        self.assertEqual(salary_elapsed_factor(2021), 1)

    def test_two_way_player_season_sums_war_and_weights_rates(self):
        performance = pd.DataFrame(
            [
                {"playerid": "1", "Season": 2024, "WAR": 2.0, "PA": 400, "IP": 0, "wRC+": 120, "FIP-": np.nan},
                {"playerid": "1", "Season": 2024, "WAR": 1.5, "PA": 0, "IP": 80, "wRC+": np.nan, "FIP-": 85},
            ]
        )
        result = aggregate_player_seasons(performance).iloc[0]
        self.assertEqual(result["war"], 3.5)
        self.assertEqual(result["pa"], 400)
        self.assertEqual(result["ip"], 80)
        self.assertEqual(result["wrc_plus"], 120)
        self.assertEqual(result["fip_minus"], 85)

    def test_panel_normalizes_2020_contract_year_and_uses_weighted_baseline(self):
        contracts = pd.DataFrame(
            [
                {
                    "ContractId": 10,
                    "playerId": "1",
                    "playerName": "Example Hitter",
                    "position": "OF",
                    "role": "hitter",
                    "age": 29,
                    "season": 2021,
                    "team_prev": "OLD",
                    "team_new": "NEW",
                    "contract_years": 2,
                    "ContractTotal": 20_000_000,
                    "aav": 10_000_000,
                    "ContractType": "Free Agent",
                    "option_type": "",
                    "has_complete_contract": True,
                }
            ]
        )
        performance = pd.DataFrame(
            [
                {"playerid": "1", "Season": 2017, "WAR": 1.0, "PA": 600, "IP": 0, "wRC+": 100, "FIP-": np.nan},
                {"playerid": "1", "Season": 2018, "WAR": 2.0, "PA": 600, "IP": 0, "wRC+": 105, "FIP-": np.nan},
                {"playerid": "1", "Season": 2019, "WAR": 3.0, "PA": 600, "IP": 0, "wRC+": 110, "FIP-": np.nan},
                {"playerid": "1", "Season": 2020, "WAR": 2.0, "PA": 200, "IP": 0, "wRC+": 130, "FIP-": np.nan},
                {"playerid": "1", "Season": 2021, "WAR": 2.0, "PA": 500, "IP": 0, "wRC+": 110, "FIP-": np.nan},
                {"playerid": "1", "Season": 2022, "WAR": 1.0, "PA": 300, "IP": 0, "wRC+": 100, "FIP-": np.nan},
            ]
        )
        panel, timeline = build_contract_panel(contracts, performance)
        row = panel.iloc[0]
        self.assertAlmostEqual(row["contract_year_war"], 5.4)
        self.assertAlmostEqual(row["baseline_war"], 2.3)
        self.assertAlmostEqual(row["performance_spike"], 3.1)
        self.assertEqual(row["realized_war"], 3.0)
        self.assertEqual(row["realized_cost"], 20_000_000)
        self.assertEqual(len(timeline), 9)

    def test_alpha_keeps_negative_war_in_production_value(self):
        panel = pd.DataFrame(
            [{
                "start_year": 2025,
                "elapsed_contract_seasons": 1,
                "post_war_y1": -1.0,
                "realized_war": -1.0,
                "realized_cost": 10_000_000.0,
                "equivalent_salary_years": 1.0,
                "spike_percentile": 90.0,
            }]
        )
        rates = pd.DataFrame([{"season": 2025, "market_dollars_per_war": 6_000_000.0}])
        result = add_contract_alpha(panel, rates).iloc[0]
        self.assertEqual(result["realized_production_value"], -6_000_000)
        self.assertEqual(result["contract_alpha"], -16_000_000)
        self.assertEqual(result["classification"], "Contract-year trap")

    def test_price_features_are_pre_signing_only_and_validation_is_forward(self):
        forbidden = ("contract_year", "future", "post_", "realized")
        self.assertFalse(any(token in feature for feature in MODEL_FEATURES for token in forbidden))
        rows = []
        for index in range(80):
            start_year = 2020 if index < 60 else 2021
            role = "pitcher" if index % 2 else "hitter"
            baseline = 0.5 + (index % 15) / 4
            rows.append(
                {
                    "player_id": str(index),
                    "start_year": start_year,
                    "age": 25 + index % 10,
                    "role": role,
                    "baseline_war": baseline,
                    "baseline_rate_war": baseline + 0.2,
                    "baseline_playing_time_share": 0.5 + (index % 5) / 10,
                    "baseline_observed_seasons": 3,
                    "contract_year_observed": True,
                    "aav": 1_000_000 + baseline * 4_000_000,
                    "guaranteed_dollars": 2_000_000 + baseline * 12_000_000,
                    "contract_years": 1 + index % 5,
                }
            )
        predicted, validation = add_forward_price_predictions(pd.DataFrame(rows))
        self.assertTrue(predicted.loc[predicted["start_year"].eq(2020), "predicted_guarantee"].isna().all())
        test_rows = predicted[predicted["start_year"].eq(2021)]
        self.assertTrue(test_rows["predicted_guarantee"].notna().all())
        self.assertTrue((test_rows["prediction_train_last_year"] < test_rows["start_year"]).all())
        self.assertTrue((validation["training_last_year"] < validation["test_year"]).all())
        self.assertGreaterEqual(test_rows["predicted_guarantee"].min(), 1_000_000)


if __name__ == "__main__":
    unittest.main()
