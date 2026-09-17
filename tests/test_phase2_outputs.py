import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PHASE2 = ROOT / "data" / "processed" / "phase2"


class Phase2OutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((PHASE2 / "analysis_summary.json").read_text())
        cls.research = pd.read_csv(PHASE2 / "research_results.csv")
        cls.validation = pd.read_csv(PHASE2 / "model_validation.csv")
        cls.teams = pd.read_csv(PHASE2 / "team_results.csv")
        cls.leaderboards = json.loads((PHASE2 / "leaderboards.json").read_text())

    def test_headline_questions_have_effect_size_interval_and_sample(self):
        expected = {"A_price", "B_regression", "B_persistence", "C_alpha", "D_overpay"}
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

    def test_public_leaderboards_are_short_derived_tables(self):
        required = {"player_name", "guaranteed_dollars", "performance_spike", "contract_alpha"}
        for records in self.leaderboards.values():
            self.assertLessEqual(len(records), 10)
            if records:
                self.assertTrue(required.issubset(records[0]))


if __name__ == "__main__":
    unittest.main()
