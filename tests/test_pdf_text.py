"""Page provenance, recursive ingestion and real local OCR regression checks."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from machineear.rag.extract_pdf_text import (
    SCANNED_GUIDE, TESSDATA_ROOT, extract_corpus, extract_document,
    file_hash, normalize_text, ocr_pdf_page, ocr_reason, text_quality,
)
from machineear.paths import ROOT
from machineear.runtime import prepare_native_runtime

HAS_PDF = importlib.util.find_spec("pymupdf") is not None
HAS_OCR = (TESSDATA_ROOT / "eng.traineddata").is_file()


class TextHandlingTests(unittest.TestCase):
    def test_normalization_preserves_units_accents_and_line_breaks(self):
        self.assertEqual(normalize_text("  Cafe\u0301 25 °C\r\n5 µm\x00\n\n\nEnd  "), "Café 25 °C\n5 µm\n\nEnd")

    def test_ocr_detection_distinguishes_blank_native_image_and_corrupt_pages(self):
        self.assertIsNone(ocr_reason("", filename="blank.pdf", image_count=0))
        self.assertIsNone(ocr_reason("Readable maintenance instructions " * 10, filename="native.pdf", image_count=1))
        self.assertEqual(ocr_reason("", filename="scan.pdf", image_count=1), "visual_content_without_text")
        self.assertEqual(ocr_reason("\ufffd" * 50, filename="bad.pdf", image_count=0), "unusable_native_encoding")
        self.assertEqual(ocr_reason("Readable text", filename=SCANNED_GUIDE, image_count=1), "scanned_maintenance_guide")
        self.assertGreater(text_quality("\x01\ufffd")['invalid_character_ratio'], 0.5)

    def test_import_does_not_extract_download_or_load_native_libraries(self):
        script = """
import sys
from unittest.mock import patch
with patch('pathlib.Path.mkdir', side_effect=AssertionError('mkdir during import')), patch('urllib.request.urlopen', side_effect=AssertionError('network during import')):
    import machineear.rag.extract_pdf_text
assert 'pymupdf' not in sys.modules
"""
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(HAS_PDF, "Install requirements-rag.txt for PDF extraction tests")
class PdfExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare_native_runtime()
        import pymupdf

        cls.pdf = pymupdf

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs, self.outputs = self.root / "input", self.root / "output"
        self.inputs.mkdir()

    def native_pdf(self, relative="Fan_Docs/native.pdf"):
        path = self.inputs / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.pdf.open() as doc:
            doc.new_page().insert_text((72, 72), "First page: inspect fan bearings before maintenance.")
            doc.new_page().insert_text((72, 72), "Second page: check lubrication and alignment.")
            doc.new_page()  # A blank physical page must still receive a record.
            doc.set_page_labels([{"startpage": 0, "prefix": "A-", "style": "D", "firstpagenum": 1}])
            doc.save(path)
        return path

    def test_page_numbers_labels_blank_pages_blocks_and_source_hash_are_preserved(self):
        path = self.native_pdf()
        before = file_hash(path)
        records, summary = extract_document(path, input_dir=self.inputs, output_dir=self.outputs)
        self.assertEqual([r["pdf_page_number"] for r in records], [1, 2, 3])
        self.assertEqual([r["page_index"] for r in records], [0, 1, 2])
        self.assertEqual([r["pdf_page_label"] for r in records], ["A-1", "A-2", "A-3"])
        self.assertIn("bearings", records[0]["text"])
        self.assertNotIn("lubrication", records[0]["text"])
        self.assertIn("lubrication", records[1]["text"])
        self.assertTrue(records[0]["blocks"])
        self.assertEqual(records[2]["text"], "")
        self.assertFalse(records[2]["usable_for_retrieval"])
        self.assertEqual(records[2]["status"], "blank")
        self.assertEqual(file_hash(path), before)
        self.assertEqual(summary["source_sha256"], before)
        self.assertEqual(records[0]["citation"], "[Fan_Docs/native.pdf, PDF p. 1]")
        self.assertEqual(len({r["page_id"] for r in records}), 3)
        self.assertIsNone(summary["searchable_pdf"])

    def test_recursive_ingestion_avoids_duplicate_filename_collisions(self):
        first = self.native_pdf("Fan_Docs/manual.pdf")
        second = self.inputs / "Pump_Docs" / "manual.pdf"
        second.parent.mkdir()
        second.write_bytes(first.read_bytes())  # Even identical PDFs keep distinct source identities.
        run = extract_corpus(self.inputs, self.outputs)
        self.assertTrue(run["passed"])
        self.assertEqual(run["document_count"], 2)
        self.assertEqual(run["page_count"], 6)
        self.assertEqual(run["directory_paths_relative_to"], "manifest_directory")
        self.assertEqual((self.outputs / run["input_directory"]).resolve(), self.inputs.resolve())
        self.assertEqual(run["output_directory"], ".")
        records = [json.loads(line) for line in (self.outputs / "pages.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual({r["source_relative_path"] for r in records}, {"Fan_Docs/manual.pdf", "Pump_Docs/manual.pdf"})
        self.assertEqual({r["machine_type_hint"] for r in records}, {"fan", "pump"})
        self.assertEqual(len({r["page_id"] for r in records}), 6)
        self.assertTrue(all((self.outputs / r["text_file"]).is_file() for r in records))

    def test_output_cannot_be_written_into_original_pdf_folder(self):
        with self.assertRaisesRegex(ValueError, "outside the original PDF directory"):
            extract_corpus(self.inputs, self.inputs / "generated")

    def test_unreadable_document_is_reported_without_silently_passing(self):
        self.native_pdf()
        (self.inputs / "broken.pdf").write_bytes(b"not a PDF")
        run = extract_corpus(self.inputs, self.outputs)
        self.assertFalse(run["passed"])
        self.assertEqual(len(run["document_failures"]), 1)
        self.assertTrue(run["original_pdfs_unchanged"])

    @unittest.skipUnless(HAS_OCR, "Run python -m machineear.rag.extract_pdf_text --prepare-ocr-data for OCR integration")
    def test_image_only_pdf_is_ocred_and_searchable_copy_keeps_page_count(self):
        path = self.inputs / SCANNED_GUIDE
        with self.pdf.open() as source, self.pdf.open() as scanned:
            for title in ("BEARING INSPECTION", "LUBRICATION CHECK"):
                page = source.new_page(width=600, height=800)
                page.insert_text((55, 80), title, fontsize=22)
                page.insert_textbox((55, 130, 540, 500),
                                    "Inspect the equipment before starting maintenance. Check bearings, lubrication, "
                                    "alignment and fasteners. Follow the manual and record all inspection findings.", fontsize=18)
                pix = page.get_pixmap(dpi=150, alpha=False)
                image_page = scanned.new_page(width=600, height=800)
                image_page.insert_image(image_page.rect, stream=pix.tobytes("png"))
            scanned.save(path)
        before = file_hash(path)
        with self.pdf.open(path) as doc:
            self.assertEqual(doc[0].get_text().strip(), "")
        records, summary = extract_document(path, input_dir=self.inputs, output_dir=self.outputs, dpi=200)
        self.assertEqual([r["extraction_method"] for r in records], ["ocr", "ocr"])
        self.assertTrue(all(r["usable_for_retrieval"] for r in records))
        self.assertIn("bearing", records[0]["text"].lower())
        self.assertIn("lubrication", records[1]["text"].lower())
        self.assertEqual(file_hash(path), before)
        with self.pdf.open(self.outputs / summary["searchable_pdf"]) as searchable:
            self.assertEqual(len(searchable), 2)
            self.assertIn("bearing", searchable[0].get_text().lower())
        self.assertEqual([r["pdf_page_number"] for r in records], [1, 2])

    def test_missing_ocr_data_is_an_explicit_page_error(self):
        path = self.native_pdf(SCANNED_GUIDE)
        records, summary = extract_document(path, input_dir=self.inputs, output_dir=self.outputs,
                                            tessdata_dir=self.root / "missing_tessdata")
        self.assertTrue(summary["errors"])
        self.assertTrue(all(r["status"] == "ocr_error" for r in records))
        self.assertTrue(all(not r["usable_for_retrieval"] for r in records))

    @unittest.skipUnless(HAS_OCR, "Prepare local OCR data for region OCR integration")
    def test_region_ocr_keeps_column_order_and_original_page_appearance(self):
        with self.pdf.open() as doc:
            page = doc.new_page(width=612, height=792)
            page.draw_rect(self.pdf.Rect(0, 0, 612, 792), fill=(0.95, 0.9, 0.85))
            page.insert_text((50, 100), "LEFT BEARINGS", fontsize=20)
            page.insert_text((50, 135), "Inspect lubrication first.", fontsize=14)
            page.insert_text((330, 100), "RIGHT CONNECTIONS", fontsize=18)
            page.insert_text((330, 135), "Check alignment next.", fontsize=14)
            before = page.get_pixmap(dpi=144, alpha=False).samples
            result = ocr_pdf_page(page, pymupdf=self.pdf, language="eng", tessdata_dir=TESSDATA_ROOT,
                                  dpi=144, regions=[("left", (40, 75, 300, 160)), ("right", (320, 75, 605, 160))])
            with self.pdf.open("pdf", result) as recognized:
                text = recognized[0].get_text().lower()
                self.assertIn("bearings", text)
                self.assertIn("connections", text)
                self.assertLess(text.index("bearings"), text.index("connections"))
                self.assertEqual(recognized[0].get_pixmap(dpi=144, alpha=False).samples, before)


if __name__ == "__main__":
    unittest.main()
