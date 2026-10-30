"""Streamlit rendering checks with synthetic results; no recordings or models."""

import importlib.util
from pathlib import Path
import unittest


def result_view(record):
    from streamlit_app import display_result
    display_result(record)


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Install requirements/ui.txt for interface tests")
class InterfaceTests(unittest.TestCase):
    def test_missing_upload_is_actionable_and_history_opens(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py")).run()
        self.assertFalse(app.exception)
        app.button[0].click().run()
        self.assertIn("WAV", app.error[0].value)
        app.sidebar.radio[0].set_value("Historique").run()
        self.assertFalse(app.exception)

    def test_all_retrieval_outcomes_render_with_audio_preserved(self):
        from streamlit.testing.v1 import AppTest
        for status in ("unavailable", "no_supported_passages", "passages_for_review"):
            with self.subTest(status=status):
                passages = [{"citation": "manual.pdf, page 2", "text": "Exact passage.",
                             "source_relative_path": "Fan_Docs/manual.pdf", "pdf_page_number": 2}] if status == "passages_for_review" else []
                record = {"analysis": {"audio": {"is_anomaly": False, "anomaly_score": 2.1,
                    "threshold": 3.5, "duration_sec": 10, "machine_type": "fan", "machine_id": "id_00"},
                    "retrieval": {"status": status, "results": passages}, "query_plan": {"query": "Inspection"}}}
                app = AppTest.from_function(result_view, args=(record,)).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.metric[0].value, "2.100")
                self.assertIn("garanti", app.info[0].value)
                if passages:
                    self.assertEqual(app.text[0].value, "Exact passage.")
