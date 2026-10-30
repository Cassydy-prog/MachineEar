"""Extract page-indexed local PDF text, with local OCR for scanned pages."""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import html
import io
from importlib.metadata import version
import json
from os.path import relpath
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote
from urllib.request import Request, urlopen

from machineear.paths import ROOT, RESOURCE_ROOT
from machineear.runtime import prepare_native_runtime

PDF_ROOT = RESOURCE_ROOT / "data" / "manuals"
OUTPUT_ROOT = RESOURCE_ROOT / "results" / "rag" / "extraction"
TESSDATA_ROOT = RESOURCE_ROOT / ".venv" / "tessdata"
OCR_DATA_TAG = "4.1.0"
OCR_LANGUAGES = ("eng", "fra", "deu")
SCANNED_GUIDE = "Troubleshooting-Maintenance-Guides-1.pdf"
GUIDE_PROFILE_SHA256 = "4511275e79be307c80a98217c3ade204f19272b35cb4a1252bc0f0a8ee381ca4"
# Visually checked page regions in physical PDF points for this exact source.
# Photos are excluded from OCR; the searchable derivative retains the full original page image.
GUIDE_REGIONS = {
    0: [("company_header", (15, 3, 603, 54)), ("title", (175, 68, 580, 145)),
        ("vibration_noise", (30, 162, 300, 490)), ("overheated_bearings", (30, 510, 300, 725)),
        ("underperformance", (323, 162, 600, 331)), ("overheated_motor", (323, 600, 604, 695)),
        ("footer", (15, 747, 604, 789))],
    1: [("company_header", (15, 3, 603, 54)), ("title", (175, 68, 580, 145)),
        ("wheel", (30, 161, 306, 482)), ("safety_note", (25, 602, 308, 701)),
        ("connections", (324, 162, 604, 435)), ("lubrication", (324, 444, 605, 701)),
        ("footer", (15, 733, 604, 789))],
}


def file_hash(path):
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def normalize_text(text):
    """Keep Unicode, line breaks and units; remove only invalid control bytes."""
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cc" or ch in "\n\t")
    return re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text).strip()


def text_quality(text):
    visible = [ch for ch in text if not ch.isspace()]
    invalid = sum(ch == "\ufffd" or unicodedata.category(ch) in ("Cc", "Co") for ch in visible)
    return {"character_count": len(text.strip()),
            "word_count": len(re.findall(r"[^\W\d_]{2,}", text, re.UNICODE)),
            "invalid_character_count": invalid,
            "invalid_character_ratio": invalid / max(1, len(visible))}


def ocr_reason(native_text, *, filename, image_count, drawing_count=0):
    quality = text_quality(native_text)
    if filename == SCANNED_GUIDE:
        return "scanned_maintenance_guide"
    if quality["invalid_character_ratio"] > 0.02:
        return "unusable_native_encoding"
    if not native_text.strip() and (image_count or drawing_count):
        return "visual_content_without_text"
    if quality["character_count"] < 50 and image_count:
        return "sparse_native_text_with_image"
    if quality["character_count"] < 30 and drawing_count > 100:
        return "possible_vector_text"
    return None


def language_hint(filename):
    lowered = filename.lower()
    if "french" in lowered:
        return "fra+eng"
    if "_de_en" in lowered:
        return "eng+deu"
    return "eng"


def source_hints(relative):
    parts = {part.lower() for part in relative.parts[:-1]}
    family = "fan" if "fan_docs" in parts else "pump" if "pump_docs" in parts else "unknown"
    name = relative.name.lower()
    kind = ("bearing_reference" if name.startswith("wl_") else
            "engineering_sourcebook" if name == "pump.pdf" else
            "troubleshooting_guide" if "troubleshooting" in name else
            "installation_operation_maintenance_manual")
    return {"machine_type_hint": family, "source_type_hint": kind,
            "applicability": "generic_guidance_equipment_match_unverified",
            "applicability_verified": False}


def prepare_ocr_data(tessdata_dir=TESSDATA_ROOT):
    """Download only official, pinned language data; never upload documents."""
    tessdata_dir = Path(tessdata_dir)
    tessdata_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for language in OCR_LANGUAGES:
        destination = tessdata_dir / f"{language}.traineddata"
        url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{OCR_DATA_TAG}/{language}.traineddata"
        if not destination.is_file():
            print(f"Downloading local OCR language data: {language}", flush=True)
            request = Request(url, headers={"User-Agent": "MachineEar-local-PDF-ingestion"})
            temporary = destination.with_suffix(".traineddata.part")
            with urlopen(request, timeout=60) as response, temporary.open("wb") as handle:
                while block := response.read(1024 * 1024):
                    handle.write(block)
            if temporary.stat().st_size < 100_000:
                raise RuntimeError(f"Unexpectedly small OCR model download: {language}")
            temporary.replace(destination)
        records.append({"language": language, "filename": destination.name,
                        "sha256": file_hash(destination), "source_url": url,
                        "bytes": destination.stat().st_size})
    (tessdata_dir / "download_manifest.json").write_text(json.dumps({
        "repository": "tesseract-ocr/tessdata_fast", "tag": OCR_DATA_TAG, "files": records,
    }, indent=2), encoding="utf-8")
    best = tessdata_dir / "best" / "eng.traineddata"
    best.parent.mkdir(exist_ok=True)
    best_url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/{OCR_DATA_TAG}/eng.traineddata"
    if not best.is_file():
        print("Downloading higher-accuracy English OCR data for the scanned guide", flush=True)
        with urlopen(Request(best_url, headers={"User-Agent": "MachineEar-local-PDF-ingestion"}), timeout=60) as response:
            temporary = best.with_suffix(".traineddata.part")
            with temporary.open("wb") as handle:
                while block := response.read(1024 * 1024):
                    handle.write(block)
            if temporary.stat().st_size < 100_000:
                raise RuntimeError("Unexpectedly small high-accuracy English OCR model")
            temporary.replace(best)
    best_record = {"language": "eng", "filename": "best/eng.traineddata", "source_url": best_url,
                   "sha256": file_hash(best), "bytes": best.stat().st_size}
    (best.parent / "download_manifest.json").write_text(json.dumps(best_record, indent=2), encoding="utf-8")
    records.append(best_record)
    return records


def extract_blocks(page, pymupdf, *, sort=True):
    """Retain spatial blocks so later chunking need not assume a single column."""
    blocks = []
    for item in page.get_text("blocks", sort=sort, flags=pymupdf.TEXTFLAGS_TEXT):
        if len(item) > 6 and item[6] != 0:
            continue
        text = normalize_text(item[4])
        if text:
            blocks.append({"block_index": len(blocks), "bbox": [float(v) for v in item[:4]], "text": text})
    return blocks


def ocr_pdf_page(page, *, pymupdf, language, tessdata_dir, dpi, regions=None):
    """Return a one-page searchable PDF; reuse its OCR for every text export."""
    for code in language.split("+"):
        if not (Path(tessdata_dir) / f"{code}.traineddata").is_file():
            raise FileNotFoundError(
                f"Missing local OCR data for {code}. Run python -m machineear.rag.extract_pdf_text --prepare-ocr-data"
            )
    if regions:
        from PIL import Image, ImageOps

        with pymupdf.open() as result:
            target = result.new_page(width=page.rect.width, height=page.rect.height)
            for name, bounds in regions:
                rect = pymupdf.Rect(bounds)
                pixmap = page.get_pixmap(clip=rect, dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples).convert("L")
                image = image.point(lambda value: 0 if value < 150 else 255)
                if image.histogram()[0] > image.width * image.height * 0.5:
                    image = ImageOps.invert(image)
                buffer = io.BytesIO()
                image.convert("RGB").save(buffer, format="PNG")
                cleaned = pymupdf.Pixmap(buffer.getvalue())
                cleaned.set_dpi(dpi, dpi)
                recognized_bytes = cleaned.pdfocr_tobytes(compress=True, language=language, tessdata=str(tessdata_dir))
                with pymupdf.open("pdf", recognized_bytes) as region_pdf:
                    target.show_pdf_page(rect, region_pdf, 0)
            # Cover the temporary binarized regions with the complete original image.
            # Their hidden OCR text remains searchable underneath, while all photos,
            # colours, logos and visual content remain visible in the derivative.
            original = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
            target.insert_image(target.rect, pixmap=original)
            return result.tobytes(garbage=4, deflate=True)
    pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    return pixmap.pdfocr_tobytes(compress=True, language=language, tessdata=str(tessdata_dir))


def extract_document(path, *, input_dir, output_dir, tessdata_dir=TESSDATA_ROOT, dpi=300, save_searchable=True):
    prepare_native_runtime()
    import pymupdf

    path, input_dir, output_dir = Path(path), Path(input_dir), Path(output_dir)
    relative = path.relative_to(input_dir)
    digest = file_hash(path)
    document_id = hashlib.sha256((relative.as_posix() + "\0" + digest).encode("utf-8")).hexdigest()
    destination = output_dir / "documents" / relative.with_suffix("")
    destination.mkdir(parents=True, exist_ok=True)
    page_dir = destination / "pages"
    page_dir.mkdir(exist_ok=True)
    pages, combined, errors = [], [], []
    searchable_path = None
    hints = source_hints(relative)
    with pymupdf.open(path) as document, pymupdf.open() as searchable:
        if document.needs_pass:
            raise ValueError(f"Encrypted PDF needs a password: {relative}")
        title = document.metadata.get("title") or relative.stem
        searchable_started = False
        for index, page in enumerate(document):
            number = index + 1
            if len(document) <= 5 or number == 1 or number % 25 == 0:
                print(f"  PDF page {number}/{len(document)}: {relative}", flush=True)
            native_blocks = extract_blocks(page, pymupdf)
            native_text = "\n\n".join(block["text"] for block in native_blocks)
            # Inspect pre-cleaning text too, so invalid controls cannot hide bad encoding.
            native_raw = page.get_text("text", sort=True)
            image_count = len(page.get_images())
            drawing_count = len(page.get_drawings()) if len(native_raw.strip()) < 30 and image_count == 0 else 0
            reason = ocr_reason(native_raw, filename=path.name, image_count=image_count, drawing_count=drawing_count)
            method = "native" if native_text else "none"
            text, blocks = native_text, native_blocks
            coordinate_rect = [float(v) for v in page.rect]
            warnings, page_error = [], None
            used_ocr = False
            language = language_hint(path.name)
            regions = GUIDE_REGIONS.get(index) if digest == GUIDE_PROFILE_SHA256 else None
            effective_tessdata = Path(tessdata_dir) / "best" if regions else Path(tessdata_dir)
            if reason:
                print(f"    PDF page {number}: local OCR ({language}, {dpi} dpi): {reason}", flush=True)
                native_file = destination / "native_before_ocr" / f"page_{number:04d}.txt"
                native_file.parent.mkdir(exist_ok=True)
                native_file.write_text(native_raw, encoding="utf-8")
                if save_searchable and not searchable_started:
                    if index:
                        searchable.insert_pdf(document, from_page=0, to_page=index - 1)
                    searchable_started = True
                try:
                    pdf_bytes = ocr_pdf_page(page, pymupdf=pymupdf, language=language,
                                             tessdata_dir=effective_tessdata, dpi=dpi, regions=regions)
                    with pymupdf.open("pdf", pdf_bytes) as recognized:
                        ocr_blocks = extract_blocks(recognized[0], pymupdf, sort=not bool(regions))
                        if regions:
                            for block in ocr_blocks:
                                center = pymupdf.Rect(block["bbox"]).tl + (pymupdf.Rect(block["bbox"]).br - pymupdf.Rect(block["bbox"]).tl) * 0.5
                                block["region_id"] = next((name for name, bounds in regions
                                                           if pymupdf.Rect(bounds).contains(center)), "unassigned")
                        ocr_text = "\n\n".join(block["text"] for block in ocr_blocks)
                        if path.name == SCANNED_GUIDE and text_quality(ocr_text)["word_count"] < 10:
                            raise RuntimeError("Maintenance guide OCR produced too little readable text")
                        if not ocr_text and native_text:
                            warnings.append("OCR returned no text; retained the native text")
                            if save_searchable:
                                searchable.insert_pdf(document, from_page=index, to_page=index)
                        else:
                            text, blocks, method, used_ocr = ocr_text, ocr_blocks, "ocr", True
                            coordinate_rect = [float(v) for v in recognized[0].rect]
                            if save_searchable:
                                searchable.insert_pdf(recognized)
                except Exception as exc:
                    page_error = str(exc)
                    errors.append({"pdf_page_number": number, "error": page_error})
                    warnings.append("OCR failed; review this page before retrieval")
                    if save_searchable:
                        searchable.insert_pdf(document, from_page=index, to_page=index)
            elif save_searchable and searchable_started:
                searchable.insert_pdf(document, from_page=index, to_page=index)
            quality = text_quality(text)
            if used_ocr:
                warnings.append("Automatic OCR: verify numbers, symbols and section associations against the source")
            if not text:
                warnings.append("No text extracted; blank page or unrecognized visual content")
            elif quality["word_count"] == 0 or quality["character_count"] < 20:
                warnings.append("Sparse text; inspect page before including it in retrieval")
            if quality["invalid_character_ratio"] > 0.02:
                warnings.append("Text contains a high proportion of invalid or unmapped characters")
            usable = bool(text and quality["word_count"] > 0 and not page_error
                          and quality["invalid_character_ratio"] <= 0.02)
            status = "ocr_error" if page_error else "blank" if not text else "review" if warnings else "ok"
            text_file = page_dir / f"page_{number:04d}.txt"
            text_file.write_text(text, encoding="utf-8")
            record = {
                "document_id": document_id, "page_id": f"{document_id}:p{number:04d}",
                "source_filename": path.name, "source_relative_path": relative.as_posix(),
                "source_sha256": digest, "document_title": title, **hints,
                "pdf_page_number": number, "page_index": index, "pdf_page_label": page.get_label() or None,
                "citation": f"[{relative.as_posix()}, PDF p. {number}]",
                "extraction_method": method, "ocr_attempted": bool(reason), "ocr_reason": reason,
                "ocr_language": language if used_ocr else None, "ocr_dpi": dpi if used_ocr else None,
                "ocr_layout_profile": "airpro_guide_4511275e_v1" if regions and used_ocr else None,
                "ocr_regions": [{"region_id": name, "bbox": list(bounds)} for name, bounds in regions] if regions and used_ocr else [],
                "ocr_human_proofread": False if used_ocr else None,
                "ocr_language_model_sha256": {code: file_hash(effective_tessdata / f"{code}.traineddata")
                                               for code in language.split("+")} if used_ocr else {},
                "ocr_preprocessing": {"grayscale_threshold": 150, "automatic_polarity": True,
                                      "original_page_image_preserved_in_derivative": True} if regions and used_ocr else None,
                "native_character_count": len(native_raw.strip()), "native_quality": text_quality(native_raw),
                "text": text, "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "blocks": blocks, "block_coordinate_system": "pymupdf_text_coordinates",
                "extracted_page_rect": coordinate_rect, "source_page_rect": [float(v) for v in page.rect],
                "source_rotation": page.rotation, "text_file": text_file.relative_to(output_dir).as_posix(),
                "status": status, "usable_for_retrieval": usable, "needs_review": bool(warnings),
                "warnings": warnings, "error": page_error, **quality,
            }
            pages.append(record)
            label = f"; declared page label {record['pdf_page_label']}" if record["pdf_page_label"] else ""
            combined.append(f"=== PDF page {number} of {len(document)}{label} | {method} ===\n\n{text}")
        if save_searchable and any(p["extraction_method"] == "ocr" for p in pages):
            if len(searchable) != len(document):
                raise RuntimeError("Searchable derivative must retain every original PDF page")
            searchable.set_metadata({"title": title, "subject": f"Local OCR derivative of {relative.as_posix()}",
                                     "producer": f"MachineEar / PyMuPDF {pymupdf.__version__}"})
            labels = document.get_page_labels()
            if labels:
                searchable.set_page_labels(labels)
            searchable_file = destination / f"{path.stem}.searchable.pdf"
            searchable.save(searchable_file, garbage=4, deflate=True)
            searchable_path = searchable_file.relative_to(output_dir).as_posix()
        (destination / "document.txt").write_text("\n\n\f\n\n".join(combined), encoding="utf-8")
        summary = {"document_id": document_id, "source_filename": path.name,
                   "source_relative_path": relative.as_posix(), "source_sha256": digest,
                   "document_title": title, **hints, "page_count": len(document),
                   "method_counts": dict(Counter(p["extraction_method"] for p in pages)),
                   "ocr_attempted_pages": sum(p["ocr_attempted"] for p in pages),
                   "blank_pages": sum(p["status"] == "blank" for p in pages),
                   "review_pages": [p["pdf_page_number"] for p in pages if p["needs_review"]],
                   "character_count": sum(p["character_count"] for p in pages),
                   "document_text_file": (destination / "document.txt").relative_to(output_dir).as_posix(),
                   "searchable_pdf": searchable_path, "errors": errors}
    if file_hash(path) != digest:
        raise RuntimeError(f"Original PDF changed during extraction: {relative}")
    (destination / "document.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return pages, summary


def write_index(documents, output_dir, input_dir, manifest):
    from os.path import relpath

    rows = []
    for document in documents:
        relative = document["source_relative_path"]
        original = quote(Path(relpath(input_dir / relative, output_dir)).as_posix(), safe="/.")
        text_file = quote(document["document_text_file"], safe="/.")
        searchable = document["searchable_pdf"]
        copy_link = f'<a href="{quote(searchable, safe="/.")}">Searchable copy</a>' if searchable else "—"
        methods = document["method_counts"]
        rows.append(f'<tr><td><a href="{original}">{html.escape(relative)}</a></td>'
                    f'<td>{document["page_count"]}</td><td>{methods.get("native", 0)}</td>'
                    f'<td>{methods.get("ocr", 0)}</td><td>{document["blank_pages"]}</td>'
                    f'<td>{html.escape(str(document["review_pages"]))}</td>'
                    f'<td><a href="{text_file}">Page-marked text</a></td><td>{copy_link}</td></tr>')
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MachineEar PDF extraction</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;color:#203348;margin:30px}}main{{max-width:1400px;margin:auto}}
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:10px;border-bottom:1px solid #dce3eb;text-align:left}}
thead{{background:#edf3f8}}.note{{background:#fff4db;padding:16px}}a{{color:#145b97}}</style></head><body><main>
<h1>PDF text extraction and local OCR</h1><p>{manifest['document_count']} documents · {manifest['page_count']} PDF pages ·
{manifest['ocr_page_count']} OCR pages · {manifest['blank_page_count']} pages without text</p>
<p class="note">Citations use physical PDF pages, starting at 1. Declared PDF page labels are recorded separately.
OCR, diagrams, reading order and tables require review before authoritative maintenance instructions are generated.
All equipment applicability remains unverified. Original PDFs were preserved; searchable copies are derivatives.</p>
<table><thead><tr><th>Original PDF</th><th>Pages</th><th>Native text</th><th>OCR</th><th>No text</th><th>Review pages</th>
<th>Text export</th><th>OCR derivative</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Structured outputs</h2><ul><li><a href="pages.jsonl">One JSON object per PDF page</a></li>
<li><a href="page_inventory.csv">Page inventory and extraction status</a></li><li><a href="manifest.json">Provenance and document checksums</a></li></ul>
<p>Text files retain page boundaries. JSON records also include block text and coordinates for later layout-aware chunking.
No chunking, embedding, retrieval or LLM generation was performed in this stage.</p></main></body></html>'''
    (output_dir / "index.html").write_text(page, encoding="utf-8")


def extract_corpus(input_dir=PDF_ROOT, output_dir=OUTPUT_ROOT, *, tessdata_dir=TESSDATA_ROOT, dpi=300, save_searchable=True):
    input_dir, output_dir, tessdata_dir = Path(input_dir).resolve(), Path(output_dir).resolve(), Path(tessdata_dir).resolve()
    if output_dir == input_dir or input_dir in output_dir.parents:
        raise ValueError("Extraction output must be outside the original PDF directory")
    if not 72 <= dpi <= 600:
        raise ValueError("OCR DPI must be between 72 and 600")
    files = sorted(p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")
    if not files:
        raise FileNotFoundError(f"No PDFs found under {input_dir}")
    input_hashes = {p.relative_to(input_dir).as_posix(): file_hash(p) for p in files}
    output_dir.mkdir(parents=True, exist_ok=True)
    records, documents, failures = [], [], []
    for path in files:
        print(f"Extracting {path.relative_to(input_dir)}", flush=True)
        try:
            pages, document = extract_document(path, input_dir=input_dir, output_dir=output_dir,
                                               tessdata_dir=tessdata_dir, dpi=dpi, save_searchable=save_searchable)
            records.extend(pages)
            documents.append(document)
        except Exception as exc:
            failures.append({"source_relative_path": path.relative_to(input_dir).as_posix(), "error": str(exc)})
            print(f"  ERROR: {exc}", flush=True)
    with (output_dir / "pages.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    fields = ["source_relative_path", "pdf_page_number", "pdf_page_label", "page_id", "extraction_method",
              "status", "character_count", "word_count", "native_character_count", "ocr_language",
              "usable_for_retrieval", "needs_review", "text_file"]
    with (output_dir / "page_inventory.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    prepare_native_runtime()
    import pymupdf

    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "input_directory": Path(relpath(input_dir, output_dir)).as_posix(),
                "output_directory": ".", "directory_paths_relative_to": "manifest_directory",
                "input_document_count": len(files), "document_count": len(documents), "page_count": len(records),
                "input_pdf_sha256": input_hashes,
                "ocr_page_count": sum(p["extraction_method"] == "ocr" for p in records),
                "blank_page_count": sum(p["status"] == "blank" for p in records),
                "review_page_count": sum(p["needs_review"] for p in records), "ocr_dpi": dpi,
                "pymupdf_version": version("PyMuPDF"), "mupdf_version": pymupdf.VersionFitz,
                "documents": documents, "document_failures": failures,
                "passed": not failures and not any(d["errors"] for d in documents),
                "page_numbering": "physical_pdf_page_1_based; declared PDF page labels stored separately",
                "ocr_engine": "MuPDF integrated Tesseract; runs locally",
                "ocr_language_data": [{"filename": p.relative_to(tessdata_dir).as_posix(), "sha256": file_hash(p)}
                                      for p in sorted(tessdata_dir.rglob("*.traineddata"))],
                "original_pdfs_unchanged": all(file_hash(input_dir / relative) == digest for relative, digest in input_hashes.items()),
                "document_contents_sent_to_external_services": False}
    if not manifest["original_pdfs_unchanged"]:
        raise RuntimeError("An original PDF changed during extraction")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_index(documents, output_dir, input_dir, manifest)
    print(f"Extracted {len(records)} pages from {len(documents)} PDFs; OCR: {manifest['ocr_page_count']}; "
          f"review pages: {manifest['review_page_count']}; errors: {len(failures) + sum(len(d['errors']) for d in documents)}")
    print(f"Index: {output_dir / 'index.html'}")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=PDF_ROOT)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--tessdata-dir", type=Path, default=TESSDATA_ROOT)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--prepare-ocr-data", action="store_true", help="Download pinned local language data, then exit")
    parser.add_argument("--no-searchable-pdf", action="store_true")
    args = parser.parse_args(argv)
    if args.prepare_ocr_data:
        prepare_ocr_data(args.tessdata_dir)
        return 0
    manifest = extract_corpus(args.input_dir, args.output_dir, tessdata_dir=args.tessdata_dir,
                              dpi=args.dpi, save_searchable=not args.no_searchable_pdf)
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
