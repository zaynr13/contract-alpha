import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class AppTests(unittest.TestCase):
    def test_dashboard_starts_and_renders_core_metrics(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=20)

        self.assertFalse(app.exception)
        labels = [metric.label for metric in app.metric]
        self.assertIn("Tracker rows", labels)
        self.assertIn("Primary cohort", labels)
        self.assertIn("Historical projections", labels)
        self.assertEqual(app.selectbox[0].value, ">=$5M")


if __name__ == "__main__":
    unittest.main()
