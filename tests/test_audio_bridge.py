"""Verify delegation to the original audio script, without implementing a detector."""

import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from machineear.audio_bridge import MODEL_DIR, PREDICTOR, predict_audio


class AudioBridgeTests(unittest.TestCase):
    def response(self):
        return {"audio": "temporary.wav", "machine_type": "fan", "machine_id": "id_00",
                "model": "logmel_knn5_mean", "duration_seconds": 10.0, "n_windows": 9,
                "anomaly_score": 0.75, "threshold": 0.7, "anomaly_flag": True,
                "windows": [{"start_seconds": 0.0, "end_seconds": 2.0, "score": 0.75}]}

    def invoke(self, command, **kwargs):
        self.command = command
        self.upload = Path(command[command.index("--audio") + 1])
        self.upload_payload = self.upload.read_bytes()
        Path(command[command.index("--output") + 1]).write_text(json.dumps(self.response()), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    @patch("machineear.audio_bridge.subprocess.run")
    def test_uploaded_bytes_are_delegated_and_scores_are_preserved(self, run):
        run.side_effect = self.invoke
        result = predict_audio(b"uploaded WAV fixture")
        self.assertIn(str(PREDICTOR), self.command)
        self.assertEqual(self.upload_payload, b"uploaded WAV fixture")
        for key in ("anomaly_score", "threshold", "windows", "n_windows", "model"):
            self.assertEqual(result[key], self.response()[key])
        self.assertTrue(result["is_anomaly"])
        self.assertEqual(result["duration_sec"], 10.0)
        self.assertNotIn("audio", result)
        self.assertFalse(self.upload.exists())

    @patch("machineear.audio_bridge.subprocess.run")
    def test_inputs_cannot_select_another_machine_or_retrained_model(self, run):
        for args in ({"machine_id": "../id_00"}, {"model_dir": MODEL_DIR.parent}, {}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                predict_audio(b"", **args)
        run.assert_not_called()

    @patch("machineear.audio_bridge.subprocess.run")
    def test_upstream_errors_are_reported_without_inventing_a_prediction(self, run):
        run.return_value = SimpleNamespace(returncode=1, stderr="Invalid WAV", stdout="")
        with self.assertRaisesRegex(ValueError, "Invalid WAV"):
            predict_audio(b"invalid")

    @patch("machineear.audio_bridge.subprocess.run")
    def test_model_checksum_is_checked_before_calling_the_original_script(self, run):
        with patch("machineear.audio_bridge.hashlib.file_digest") as digest:
            digest.return_value.hexdigest.return_value = "changed"
            with self.assertRaisesRegex(ValueError, "checksum"):
                predict_audio(b"fixture")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
