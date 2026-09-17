import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class AppTests(unittest.TestCase):
    def test_research_app_starts_and_renders_findings_product(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=20)

        self.assertFalse(app.exception)
        tab_labels = [tab.label for tab in app.tabs]
        self.assertIn("What we found", tab_labels)
        self.assertIn("Contract-Year Trap", tab_labels)
        self.assertIn("Model checks", tab_labels)
        labels = [metric.label for metric in app.metric]
        self.assertIn("Guarantee benchmark", labels)
        self.assertIn("Contract length", labels)
        self.assertEqual(app.radio[0].value, "Contract-year traps")

    def test_hosted_app_works_without_private_row_level_data(self):
        with tempfile.TemporaryDirectory() as empty_private:
            with patch.dict(os.environ, {"CONTRACT_ALPHA_PRIVATE_DIR": empty_private}):
                app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=20)

        self.assertFalse(app.exception)
        self.assertFalse(app.selectbox)
        messages = [item.value for item in app.info]
        self.assertTrue(any("full row-level explorer" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
