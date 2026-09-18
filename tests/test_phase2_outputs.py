import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data" / "processed" / "public"


class PublicOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((PUBLIC / "analysis_summary.json").read_text())
        cls.research = pd.read_csv(PUBLIC / "research_results.csv")
        cls.validation = pd.read_csv(PUBLIC / "model_validation.csv")
        cls.teams = pd.read_csv(PUBLIC / "team_results.csv")
        cls.baseline = pd.read_csv(PUBLIC / "baseline_history_sensitivity.csv")
        cls.market = pd.read_csv(PUBLIC / "market_value_sensitivity.csv")
        cls.size = pd.read_csv(PUBLIC / "contract_size_validation.csv")
        cls.leaderboards = json.loads((PUBLIC / "leaderboards.json").read_text())

    def test_headline_questions_have_effect_size_interval_and_sample(self):
        expected = {"A_price", "B_regression", "B_persistence", "C_alpha", "D_residual"}
        self.assertEqual(set(self.summary["answers"]), expected)
        for result in self.summary["answers"].values():
            self.assertLessEqual(result["ci_low"], result["estimate"])
            self.assertGreaterEqual(result["ci_high"], result["estimate"])
            self.assertGreater(result["n"], 0)

    def test_forward_folds_never_train_on_test_or_future_years(self):
        self.assertTrue(
            (self.validation["training_last_year"] < self.validation["test_year"]).all()
        )
        self.assertNotIn(2020, self.validation["test_year"].tolist())

    def test_team_contract_counts_reconcile_to_primary_cohort(self):
        self.assertFalse(self.teams["signing_team"].duplicated().any())
        self.assertEqual(
            int(self.teams["contracts"].sum()),
            self.summary["cohort"]["primary_contracts_ge_5m"],
        )
        for scenario in ("low", "base", "high"):
            self.assertIn(f"contract_alpha_{scenario}", self.teams)
            self.assertIn(f"alpha_roi_percent_{scenario}", self.teams)

    def test_market_value_sensitivity_reconciles_to_headline(self):
        self.assertEqual(set(self.market["scenario"]), {"low", "base", "high"})
        base = self.market.loc[self.market["scenario"].eq("base")].iloc[0]
        self.assertAlmostEqual(base["estimate"], self.summary["answers"]["C_alpha"]["estimate"])
        self.assertTrue((self.market["estimate"] < 0).all())
        self.assertTrue((self.market["trap_top10_overlap_with_base"] >= 8).all())

    def test_baseline_history_sensitivity_has_all_required_screens(self):
        self.assertEqual(
            set(self.baseline["minimum_observed_baseline_seasons"]), {1, 2, 3}
        )
        self.assertEqual(
            set(self.baseline["question"]), {"A_price", "B_persistence", "C_alpha"}
        )
        one_season = self.baseline[
            self.baseline["minimum_observed_baseline_seasons"].eq(1)
        ].set_index("question")
        for question in ("A_price", "B_persistence", "C_alpha"):
            self.assertAlmostEqual(
                one_season.loc[question, "estimate"],
                self.summary["answers"][question]["estimate"],
            )

    def test_contract_size_validation_reports_required_error_metrics(self):
        self.assertEqual(
            set(self.size["contract_size_band"]),
            {"$1M–<$5M", "$5M–<$25M", "$25M–<$100M", "$100M+"},
        )
        for column in (
            "mae",
            "median_absolute_error",
            "median_absolute_percentage_error",
            "mean_absolute_log_error",
        ):
            self.assertTrue(self.size[column].notna().all())

    def test_public_leaderboards_are_short_derived_tables(self):
        required = {"player_name", "guaranteed_dollars", "performance_spike", "contract_alpha"}
        for records in self.leaderboards.values():
            self.assertLessEqual(len(records), 10)
            if records:
                self.assertTrue(required.issubset(records[0]))
        self.assertIn("largest_baseline_price_residuals", self.leaderboards)
        self.assertNotIn("pricing_premiums", self.leaderboards)


if __name__ == "__main__":
    unittest.main()
