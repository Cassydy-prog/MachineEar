"""Page-bound chunks, filter isolation, exact citations and local retrieval."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from machineear.rag.chunk_documents import chunk_page, passage_windows, detect_language
from machineear.rag.extract_pdf_text import OUTPUT_ROOT
from machineear.rag.local_embeddings import MODEL_DIR, RUNTIME_DIR, LocalEmbedder
from machineear.paths import ROOT
from machineear.rag.retrieve_documents import INDEX_DIR, LocalRetriever, eligible_chunk, reciprocal_rank_fusion, verify_passage


def fixture_page():
    texts = ["BEARING MAINTENANCE", "WARNING", "Inspect the bearings and check lubrication before operating the fan. " * 35]
    text = "\n\n".join(texts)
    return {"document_id": "document", "page_id": "document:p0001", "source_filename": "manual.pdf",
            "source_relative_path": "Fan_Docs/manual.pdf", "source_sha256": "sourcehash", "document_title": "Manual",
            "machine_type_hint": "fan", "source_type_hint": "installation_operation_maintenance_manual",
            "applicability": "generic_guidance_equipment_match_unverified", "applicability_verified": False,
            "pdf_page_number": 1, "page_index": 0, "pdf_page_label": None, "citation": "[Fan_Docs/manual.pdf, PDF p. 1]",
            "extraction_method": "native", "ocr_human_proofread": None, "needs_review": False,
            "usable_for_retrieval": True, "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "blocks": [{"block_index": i, "text": value, "bbox": [20, 30 + i * 30, 500, 50 + i * 30]}
                       for i, value in enumerate(texts)]}


class ChunkAndCitationTests(unittest.TestCase):
    def chunks(self, page=None):
        return chunk_page(page or fixture_page(), count_tokens=lambda text: len(text.split()) + 2,
                          max_tokens=40, overlap_words=4, language="en")

    def test_chunks_fit_budget_and_are_exact_single_page_substrings(self):
        page = fixture_page()
        chunks = self.chunks(page)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(chunk["token_count"], 40)
            self.assertEqual(chunk["text"], page["text"][chunk["char_start"]:chunk["char_end"]])
            self.assertEqual(chunk["pdf_page_number"], 1)
            self.assertTrue(verify_passage(chunk, page))
        second = copy.deepcopy(page)
        second.update(page_id="document:p0002", pdf_page_number=2, page_index=1,
                      citation="[Fan_Docs/manual.pdf, PDF p. 2]")
        self.assertFalse({c["chunk_id"] for c in chunks} & {c["chunk_id"] for c in self.chunks(second)})

    def test_unspaced_text_is_split_without_loss_or_truncation(self):
        text = "漢字" * 100
        ranges = list(passage_windows(text, 0, len(text), count_tokens=lambda value: len(value) + 2,
                                      max_tokens=30, max_words=100, overlap_words=0))
        self.assertEqual("".join(text[a:b] for a, b in ranges), text)
        self.assertTrue(all(b - a + 2 <= 30 for a, b in ranges))

    def test_adjacent_headings_stay_with_instructions(self):
        first = self.chunks()[0]
        self.assertIn("BEARING MAINTENANCE", first["text"])
        self.assertIn("WARNING", first["text"])
        self.assertIn("Inspect the bearings", first["text"])

    def test_blank_and_unreviewed_ocr_pages_are_excluded(self):
        page = fixture_page()
        page["needs_review"] = True
        self.assertEqual(self.chunks(page), [])
        page["needs_review"] = False
        page["extraction_method"] = "ocr"
        page["ocr_human_proofread"] = False
        self.assertEqual(self.chunks(page), [])
        page["usable_for_retrieval"] = False
        self.assertEqual(self.chunks(page), [])

    def test_tampered_page_text_is_rejected(self):
        page = fixture_page()
        page["text"] += "changed"
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.chunks(page)

    def test_citation_metadata_and_passage_tampering_are_rejected(self):
        page = fixture_page()
        original = self.chunks(page)[0]
        for key, replacement in (("pdf_page_number", 99), ("text", "invented passage"), ("char_end", 99999)):
            changed = copy.deepcopy(original)
            changed[key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_passage(changed, page)

    def test_machine_and_language_filters_allow_only_matching_or_generic_sources(self):
        base = {"machine_scope": "fan", "language": "fr", "needs_review": False}
        self.assertTrue(eligible_chunk(base, "fan", "fr"))
        self.assertFalse(eligible_chunk(base, "pump", "fr"))
        self.assertFalse(eligible_chunk(base, "fan", "en"))
        self.assertTrue(eligible_chunk(dict(base, machine_scope="both", language="und"), "pump", "en"))
        self.assertFalse(eligible_chunk(dict(base, needs_review=True), "fan", "fr"))

    def test_rank_fusion_rewards_agreement_between_independent_rankings(self):
        scores = reciprocal_rank_fusion([1, 2], [2, 3])
        self.assertGreater(scores[2], scores[1])
        self.assertGreater(scores[2], scores[3])

    def test_language_detection_handles_english_french_and_short_unknowns(self):
        self.assertEqual(detect_language("How should the bearings of an industrial fan be lubricated?")[0], "en")
        self.assertEqual(detect_language("Comment faut-il lubrifier les roulements du ventilateur industriel ?")[0], "fr")
        self.assertEqual(detect_language("42")[0], "und")

    def test_import_has_no_download_embedding_or_native_ml_side_effects(self):
        script = """
import sys
from unittest.mock import patch
with patch('urllib.request.urlopen',side_effect=AssertionError('network')),patch('subprocess.Popen',side_effect=AssertionError('worker')):
    import machineear.rag.chunk_documents,machineear.rag.local_embeddings,machineear.rag.retrieve_documents
assert not {'numpy','tokenizers','langdetect'}.intersection(sys.modules)
"""
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless((MODEL_DIR / "model_manifest.json").is_file() and (RUNTIME_DIR / "node_modules").is_dir(),
                     "Prepare the approved local embedding model/runtime for embedding integration")
class EmbeddingIntegrationTests(unittest.TestCase):
    def test_local_embeddings_are_normalized_and_match_relevant_bilingual_text(self):
        import numpy as np

        with LocalEmbedder() as encoder:
            query = encoder.encode(["How should fan bearings be lubricated?"], kind="query")[0]
            passages = encoder.encode(["Lubrifiez les roulements du ventilateur conformément aux instructions du fabricant.",
                                       "A chocolate cake contains flour, sugar and eggs."])
            self.assertGreater(float(passages[0] @ query), float(passages[1] @ query))
            np.testing.assert_allclose(np.linalg.norm(passages, axis=1), 1, atol=1e-5)


@unittest.skipUnless((INDEX_DIR / "manifest.json").is_file()
                     and (MODEL_DIR / "model_manifest.json").is_file()
                     and (RUNTIME_DIR / "node_modules").is_dir(),
                     "Prepare the local query encoder/runtime to use the bundled retrieval index")
class RetrievalIntegrationTests(unittest.TestCase):
    def test_fan_and_french_results_have_valid_exact_citations_and_family_filters(self):
        with LocalRetriever() as retriever:
            for query, machine, language in (("How should fan bearings be lubricated?", "fan", "en"),
                                              ("Comment éviter de mélanger les graisses des roulements du ventilateur ?", "fan", "fr"),
                                              ("How should a pump be primed before starting?", "pump", "en")):
                with self.subTest(machine=machine, language=language):
                    response = retriever.search(query, machine, language=language)
                    self.assertTrue(response["results"])
                    for result in response["results"]:
                        self.assertTrue(result["citation_verified"])
                        self.assertTrue(eligible_chunk(result, machine, language))
                        self.assertTrue(verify_passage(result, retriever.pages[result["page_id"]]))

    def test_unrelated_development_questions_return_no_supported_passages(self):
        with LocalRetriever() as retriever:
            for query, machine in (("How do I bake a chocolate cake with buttercream frosting?", "fan"),
                                   ("What is the capital city of France?", "pump")):
                with self.subTest(query=query):
                    response = retriever.search(query, machine, language="en")
                    self.assertEqual(response["status"], "no_supported_passages")
                    self.assertEqual(response["results"], [])

    def test_overlong_queries_raise_instead_of_silently_truncating(self):
        with LocalRetriever() as retriever:
            with self.assertRaisesRegex(ValueError, "No silent truncation"):
                retriever.search("fan bearing lubrication " * 600, "fan", language="en")


if __name__ == "__main__":
    unittest.main()
