import tempfile
import unittest
from pathlib import Path

from machineear.review import load_history, new_record, save_review


class ReviewTests(unittest.TestCase):
    def test_revisions_preserve_analysis_and_do_not_store_wav(self):
        result = {"audio": {"anomaly_score": 2.5, "threshold": 3.1}}
        record = new_record(result, b"audio", "upload.wav")
        with tempfile.TemporaryDirectory() as directory:
            first = save_review(record, "Inspection proposée", "Bally", directory=directory)
            second = save_review(record, "Inspection relue", "Bally", True, True, directory=directory)
            history, errors = load_history(directory)
            self.assertFalse(errors)
            self.assertEqual(len(history), 2)
            self.assertEqual(first["analysis"], result)
            self.assertEqual(second["analysis"], result)
            self.assertTrue(history[0]["review"]["approved"])
            self.assertEqual({p.suffix for p in Path(directory).iterdir()}, {".json"})

    def test_approval_requires_review_and_corrupt_history_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                save_review({}, "Report", "Bally", True, False, directory=directory)
            with self.assertRaises(ValueError):
                save_review({}, "Report", "", directory=directory)
            Path(directory, "broken.json").write_text("{", encoding="utf-8")
            records, errors = load_history(directory)
            self.assertFalse(records)
            self.assertEqual(len(errors), 1)
