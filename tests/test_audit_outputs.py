import json
import unittest
from pathlib import Path

import pandas as pd


AUDIT_DIR = Path(__file__).resolve().parents[1] / "data" / "processed" / "audit"


class AuditOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (AUDIT_DIR / "audit_summary.json").open(encoding="utf-8") as handle:
            cls.summary = json.load(handle)

    def test_completed_contract_distributions_reconcile(self):
        expected = self.summary["source_coverage"][
            "completed_class_complete_contract_rows"
        ]
        for filename, count_column in [
            ("age_distribution_completed_classes.csv", "contracts"),
            ("contract_value_distribution_completed_classes.csv", "contracts"),
            ("role_split_complete_contracts.csv", "complete_contracts"),
        ]:
            with self.subTest(filename=filename):
                frame = pd.read_csv(AUDIT_DIR / filename)
                self.assertEqual(int(frame[count_column].sum()), expected)

    def test_primary_screen_reconciles_to_summary(self):
        frame = pd.read_csv(AUDIT_DIR / "eligibility_sensitivity.csv")
        primary = frame.loc[frame["guarantee_screen"] == ">=$5M"].iloc[0]
        expected = self.summary["source_coverage"]["completed_class_ge_5m_rows"]
        self.assertEqual(int(primary["contracts"]), expected)
        self.assertEqual(float(primary["contract_year_row_percent"]), 94.1)
        self.assertEqual(float(primary["three_pre_rows_percent"]), 87.5)
        self.assertEqual(float(primary["any_post_row_percent"]), 98.9)


if __name__ == "__main__":
    unittest.main()
