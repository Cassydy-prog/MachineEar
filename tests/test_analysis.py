"""Audio-to-retrieval orchestration, evidence boundaries and failure handling."""

import json
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from machineear.analyze_recording import analyze_recording, build_retrieval_query
from machineear.paths import ROOT, RESOURCE_ROOT, LOGMEL_MODEL_DIR as MODEL_DIR
from machineear.rag.retrieve_documents import INDEX_DIR, LocalRetriever, verify_passage


def prediction(machine="fan", anomaly=True):
    return {"machine_type": machine, "machine_id": "id_00", "is_anomaly": anomaly,
            "anomaly_score": 0.712345 if anomaly else 0.4, "threshold": 0.6, "prediction": int(anomaly),
            "duration_sec": 10.0, "message": "Measured result; no fault confirmed."}


def search_response(machine="fan", empty=False):
    passage = {"citation_verified": True, "machine_scope": machine, "needs_review": False,
               "text": "Follow the equipment manual for inspection checks.",
               "source_relative_path": "Fan_Docs/fixture.pdf", "pdf_page_number": 2,
               "citation": "[Fan_Docs/fixture.pdf, PDF p. 2]"}
    return {"machine_type": machine, "status": "no_supported_passages" if empty else "passages_for_review",
            "results": [] if empty else [passage]}


class AnalysisContractTests(unittest.TestCase):
    def test_flag_changes_general_intent_without_inventing_faults_or_using_raw_scores(self):
        for family in ("fan", "pump"):
            unusual = build_retrieval_query(family, True)
            routine = build_retrieval_query(family, False)
            self.assertEqual(unusual["intent"], "unusual_sound_inspection")
            self.assertEqual(routine["intent"], "routine_inspection")
            self.assertNotEqual(unusual["query"], routine["query"])
            for plan in (unusual, routine):
                self.assertIn(family, plan["query"])
                self.assertFalse(plan["specific_fault_inferred"])
                for invented in ("bearing", "belt", "cavitation", "id_00", "0.712345"):
                    self.assertNotIn(invented, plan["query"])

    def test_auto_language_uses_french_notes_before_adding_query_instructions(self):
        notes = "Comment faut-il lubrifier les roulements du ventilateur industriel ?"
        plan = build_retrieval_query("fan", True, technician_notes=notes, language="auto")
        self.assertEqual(plan["language"], "fr")
        self.assertIn("Équipement", plan["query"])
        self.assertIn(notes, plan["query"])

    @patch("machineear.analyze_recording.predict_audio")
    def test_selected_model_context_and_verified_passages_are_kept_separate(self, predict):
        predict.return_value = prediction("pump")
        service = Mock()
        service.search.return_value = search_response("pump")
        notes = "Technician suspects a bearing problem; inspect lubrication guidance."
        result = analyze_recording(b"uploaded bytes", "pump", "id_00", technician_notes=notes,
                                   equipment_context="Manufacturer/model not supplied", retriever=service, top_k=3)
        predict.assert_called_once_with(b"uploaded bytes", "pump", "id_00", model_dir=MODEL_DIR)
        args, kwargs = service.search.call_args
        self.assertEqual(args[1], "pump")
        self.assertIn(notes, args[0])
        self.assertNotIn("id_00", args[0])
        self.assertNotIn("0.712345", args[0])
        self.assertEqual(kwargs, {"language": "en", "top_k": 3})
        self.assertEqual(result["audio"], predict.return_value)
        self.assertEqual(result["retrieval"]["results"], service.search.return_value["results"])
        self.assertFalse(result["technician_context"]["verified"])
        self.assertFalse(result["interpretation"]["specific_fault_diagnosed"])
        self.assertFalse(result["interpretation"]["equipment_applicability_verified"])
        self.assertEqual(result["status"], "analysis_complete")
        service.close.assert_not_called()
        json.dumps(result, allow_nan=False)

    @patch("machineear.analyze_recording.predict_audio", return_value=prediction(anomaly=False))
    def test_below_threshold_audio_still_retrieves_and_empty_results_stay_empty(self, predict):
        service = Mock()
        service.search.return_value = search_response(empty=True)
        result = analyze_recording(b"wav", retriever=service)
        service.search.assert_called_once()
        self.assertEqual(result["query_plan"]["intent"], "routine_inspection")
        self.assertEqual(result["retrieval"]["status"], "no_supported_passages")
        self.assertEqual(result["retrieval"]["results"], [])
        self.assertEqual(result["status"], "analysis_complete")

    @patch("machineear.analyze_recording.predict_audio", return_value=prediction())
    def test_missing_index_preserves_audio_with_an_explicit_unavailable_result(self, predict):
        with patch("machineear.analyze_recording.LocalRetriever", side_effect=FileNotFoundError("Index missing")):
            result = analyze_recording(b"wav")
        self.assertEqual(result["audio"], predict.return_value)
        self.assertEqual(result["status"], "audio_only")
        self.assertEqual(result["retrieval"]["status"], "unavailable")
        self.assertEqual(result["retrieval"]["results"], [])
        self.assertEqual(result["retrieval"]["error"]["type"], "FileNotFoundError")

    @patch("machineear.analyze_recording.predict_audio", return_value=prediction())
    def test_wrong_family_unverified_citations_and_tampered_sources_fail_closed(self, predict):
        cases = [search_response("pump"), search_response()]
        cases[1]["results"][0]["citation_verified"] = False
        for response in cases:
            service = Mock()
            service.search.return_value = response
            with self.subTest(response=response):
                result = analyze_recording(b"wav", retriever=service)
                self.assertEqual(result["status"], "audio_only")
                self.assertEqual(result["retrieval"]["results"], [])
        service = Mock()
        service.search.side_effect = ValueError("Original PDF changed or checksum mismatch")
        self.assertEqual(analyze_recording(b"wav", retriever=service)["retrieval"]["results"], [])

    @patch("machineear.analyze_recording.predict_audio", side_effect=ValueError("Invalid WAV"))
    def test_prediction_failure_does_not_run_retrieval_or_fabricate_audio(self, predict):
        with patch("machineear.analyze_recording.LocalRetriever") as factory:
            with self.assertRaisesRegex(ValueError, "Invalid WAV"):
                analyze_recording(b"bad wav")
            factory.assert_not_called()

    @patch("machineear.analyze_recording.predict_audio")
    def test_invalid_settings_fail_before_audio_is_processed_without_truncation(self, predict):
        for kwargs in ({"top_k": 0}, {"technician_notes": "x" * 1001},
                       {"equipment_context": "x" * 401}, {"machine_id": "../id_00"},
                       {"language": "ENGLISH"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                analyze_recording(b"wav", **kwargs)
        predict.assert_not_called()

    @patch("machineear.analyze_recording.predict_audio", return_value=prediction())
    def test_owned_retriever_is_closed_even_when_search_raises(self, predict):
        with patch("machineear.analyze_recording.LocalRetriever") as factory:
            factory.return_value.__enter__.return_value.search.side_effect = RuntimeError("Worker unavailable")
            self.assertEqual(analyze_recording(b"wav")["status"], "audio_only")
            factory.return_value.__exit__.assert_called_once()

    def test_import_never_downloads_runs_a_worker_or_loads_native_ml_libraries(self):
        script = """
import sys
from unittest.mock import patch
with patch('urllib.request.urlopen',side_effect=AssertionError('network')),patch('subprocess.Popen',side_effect=AssertionError('worker')):
    import machineear.analyze_recording
assert not {'numpy','librosa','pandas','sklearn','tokenizers','langdetect'}.intersection(sys.modules)
"""
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


TRAINING_AUDIO = {family: RESOURCE_ROOT / f"data/audio/{family.title()}/{prefix}0/id_00/normal/00000001.wav"
                  for family, prefix in (("fan", "FAN"), ("pump", "Pump"))}
HAS_LOCAL_PIPELINE = (all(path.is_file() for path in TRAINING_AUDIO.values())
                      and (INDEX_DIR / "manifest.json").is_file()
                      and all((MODEL_DIR / f"{family}_id_00.joblib").is_file() for family in ("fan", "pump")))


@unittest.skipUnless(HAS_LOCAL_PIPELINE, "Provide original CSV/WAVs, fan/pump models and the local index for connected integration")
class ConnectedIntegrationTests(unittest.TestCase):
    def test_training_wav_path_and_upload_bytes_connect_both_families_to_verified_pages(self):
        with LocalRetriever() as service:
            for family in ("fan", "pump"):
                path = TRAINING_AUDIO[family]
                audio = path if family == "fan" else path.read_bytes()
                with self.subTest(machine=family):
                    result = analyze_recording(audio, family, "id_00", retriever=service,
                                               technician_notes="Which bearing lubrication checks are documented?")
                    self.assertEqual(result["status"], "analysis_complete")
                    self.assertEqual(result["audio"]["machine_type"], family)
                    self.assertEqual(result["audio"]["model"], "logmel_knn5_mean")
                    self.assertTrue(result["retrieval"]["results"])
                    for passage in result["retrieval"]["results"]:
                        self.assertIn(passage["machine_scope"], (family, "both"))
                        self.assertTrue(verify_passage(passage, service.pages[passage["page_id"]]))


if __name__ == "__main__":
    unittest.main()
