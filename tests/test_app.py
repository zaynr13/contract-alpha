import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class AppTests(unittest.TestCase):
    def test_research_app_starts_and_renders_findings_product(self):
        with tempfile.TemporaryDirectory() as empty_private:
            with patch.dict(os.environ, {"CONTRACT_ALPHA_PRIVATE_DIR": empty_private}):
                app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=20)

        self.assertFalse(app.exception)
        tab_labels = [tab.label for tab in app.tabs]
        self.assertIn("What we found", tab_labels)
        self.assertIn("Contract-Year Trap", tab_labels)
        self.assertIn("Selected contracts", tab_labels)
        self.assertIn("Model checks", tab_labels)
        labels = [metric.label for metric in app.metric]
        self.assertIn("Guarantee benchmark", labels)
        self.assertIn("Contract length", labels)
        self.assertEqual(app.radio[0].value, "Contract-year traps")

    def test_headline_cards_are_responsive_and_use_public_summary(self):
        source = (ROOT / "streamlit_app.py").read_text()
        self.assertIn(".finding-grid", source)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", source)
        self.assertIn("overflow-wrap: anywhere", source)
        self.assertIn("@media (max-width: 650px)", source)

        app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=20)
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("MLB Contract-Year Trap", rendered)
        self.assertIn("Do teams pay for sustainable talent—or the perfect contract year?", rendered)
        self.assertIn("4 · Baseline-price residual", rendered)
        self.assertIn("31% persisted", rendered)
        self.assertIn("How to read these results", rendered)

    def test_hosted_app_works_without_private_row_level_data(self):
        with tempfile.TemporaryDirectory() as empty_private:
            with patch.dict(os.environ, {"CONTRACT_ALPHA_PRIVATE_DIR": empty_private}):
                app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=20)

        self.assertFalse(app.exception)
        tab_labels = [tab.label for tab in app.tabs]
        self.assertIn("Selected contracts", tab_labels)
        self.assertNotIn("Contract explorer", tab_labels)
        selectbox_labels = [item.label for item in app.selectbox]
        self.assertNotIn("Contract", selectbox_labels)
        messages = [item.value for item in app.info]
        self.assertTrue(any("not a searchable" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
