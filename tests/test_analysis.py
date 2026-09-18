import unittest

import numpy as np
import pandas as pd

from contract_alpha.analysis import (
    MODEL_FEATURES,
    add_contract_alpha,
    add_forward_price_predictions,
    aggregate_player_seasons,
    build_contract_panel,
    make_contract_size_validation,
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
        self.assertEqual(result["contract_alpha_low"], -14_500_000)
        self.assertEqual(result["contract_alpha_high"], -17_500_000)
        self.assertEqual(result["classification"], "Contract-year trap")

    def test_unobserved_baseline_seasons_are_not_silently_zero(self):
        contracts = pd.DataFrame(
            [{
                "ContractId": 11,
                "playerId": "2",
                "playerName": "Sparse History",
                "position": "OF",
                "role": "hitter",
                "age": 28,
                "season": 2025,
                "team_prev": "OLD",
                "team_new": "NEW",
                "contract_years": 1,
                "ContractTotal": 6_000_000,
                "aav": 6_000_000,
                "ContractType": "Free Agent",
                "option_type": "",
                "has_complete_contract": True,
            }]
        )
        performance = pd.DataFrame(
            [
                {"playerid": "2", "Season": 2021, "WAR": 3.0, "PA": 600, "IP": 0, "wRC+": 110, "FIP-": np.nan},
                {"playerid": "2", "Season": 2024, "WAR": 4.0, "PA": 600, "IP": 0, "wRC+": 120, "FIP-": np.nan},
                {"playerid": "2", "Season": 2025, "WAR": 1.0, "PA": 300, "IP": 0, "wRC+": 100, "FIP-": np.nan},
            ]
        )
        panel, _ = build_contract_panel(contracts, performance)
        row = panel.iloc[0]
        self.assertEqual(row["baseline_observed_seasons"], 1)
        self.assertEqual(row["baseline_unobserved_seasons"], 2)
        self.assertAlmostEqual(row["baseline_war"], 3.0)
        self.assertAlmostEqual(row["performance_spike"], 1.0)

    def test_spike_percentile_excludes_unobserved_contract_year(self):
        contracts = pd.DataFrame(
            [
                {
                    "ContractId": contract_id,
                    "playerId": str(contract_id),
                    "playerName": f"Player {contract_id}",
                    "position": "OF",
                    "role": "hitter",
                    "age": 28,
                    "season": 2025,
                    "team_prev": "OLD",
                    "team_new": "NEW",
                    "contract_years": 1,
                    "ContractTotal": 6_000_000,
                    "aav": 6_000_000,
                    "ContractType": "Free Agent",
                    "option_type": "",
                    "has_complete_contract": True,
                }
                for contract_id in (21, 22)
            ]
        )
        performance = pd.DataFrame(
            [
                {"playerid": str(player_id), "Season": season, "WAR": war, "PA": 600, "IP": 0, "wRC+": 100, "FIP-": np.nan}
                for player_id, season, war in [
                    (21, 2023, 1.0),
                    (21, 2024, 3.0),
                    (22, 2023, 2.0),
                ]
            ]
        )
        panel, _ = build_contract_panel(contracts, performance)
        observed = panel.loc[panel["contract_id"].eq(21)].iloc[0]
        unobserved = panel.loc[panel["contract_id"].eq(22)].iloc[0]
        self.assertEqual(observed["spike_percentile"], 100.0)
        self.assertTrue(np.isnan(unobserved["spike_percentile"]))

    def test_contract_size_validation_reports_all_bands(self):
        panel = pd.DataFrame(
            {
                "guaranteed_dollars": [2e6, 10e6, 50e6, 150e6],
                "predicted_guarantee": [1.5e6, 8e6, 40e6, 80e6],
                "predicted_guarantee_low": [1e6, 5e6, 20e6, 50e6],
                "predicted_guarantee_high": [3e6, 15e6, 70e6, 120e6],
                "guarantee_outside_empirical_range": [False, False, False, True],
            }
        )
        result = make_contract_size_validation(panel)
        self.assertEqual(len(result), 4)
        self.assertEqual(result["n"].sum(), 4)
        self.assertEqual(
            result.loc[result["contract_size_band"].eq("$100M+"), "empirical_interval_coverage_percent"].iloc[0],
            0.0,
        )

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
