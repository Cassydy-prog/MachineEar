"""Create exact, page-bound passages with local language and citation metadata."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from machineear.rag.extract_pdf_text import OUTPUT_ROOT as EXTRACTION_ROOT, file_hash
from machineear.rag.local_embeddings import LocalTokenizer, MODEL_DIR, MODEL_REVISION
from machineear.paths import ROOT, RESOURCE_ROOT

CHUNK_DIR = RESOURCE_ROOT / "results" / "rag" / "chunks"


def detect_language(text):
    from langdetect import DetectorFactory, detect_langs
    from langdetect.lang_detect_exception import LangDetectException

    if sum(ch.isalpha() for ch in text) < 20:
        return "und", 0.0
    DetectorFactory.seed = 42
    try:
        detected = detect_langs(text[:12000])
    except LangDetectException:
        return "und", 0.0
    best = detected[0]
    return (best.lang if best.prob >= 0.85 else "und"), float(best.prob)


def block_spans(page):
    spans, cursor = [], 0
    for block in page["blocks"]:
        start = page["text"].find(block["text"], cursor)
        if start < 0:
            raise ValueError(f"Block text does not match canonical page {page['page_id']}")
        end = start + len(block["text"])
        spans.append((start, end, block))
        cursor = end
    return spans


def is_heading(text):
    words = text.split()
    if not 1 <= len(words) <= 12 or len(text) > 120 or text.count("\n") > 1:
        return False
    letters = [ch for ch in text if ch.isalpha()]
    return (len(letters) >= 4 and (text.rstrip().endswith(":")
            or sum(ch.isupper() for ch in letters) / len(letters) > 0.85
            or bool(re.match(r"^\d+(?:\.\d+)+\s+[^\W\d_]", text))))


def section_ranges(page):
    spans = block_spans(page)
    starts = [(0, None)]
    last_region = None
    for start, _, block in spans:
        region = block.get("region_id")
        if is_heading(block["text"]) or (region and region != last_region):
            if starts[-1][0] == start:
                starts[-1] = (start, block["text"] if is_heading(block["text"]) else region)
            else:
                starts.append((start, block["text"] if is_heading(block["text"]) else region))
        last_region = region
    sections = []
    for index, (start, heading) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(page["text"])
        while start < end and page["text"][start].isspace():
            start += 1
        while end > start and page["text"][end - 1].isspace():
            end -= 1
        if end > start:
            sections.append((start, end, heading))
    index = 0
    while index < len(sections):
        start, end, heading = sections[index]
        while index + 1 < len(sections):
            included = [block for a, b, block in spans if a < end and b > start]
            if not included or not all(is_heading(block["text"]) for block in included):
                break
            index += 1
            end = sections[index][1]
        yield start, end, heading
        index += 1


def passage_windows(text, start, end, *, count_tokens, max_tokens=480, max_words=350, overlap_words=40):
    """Bound every passage without silent model truncation, including unspaced scripts."""
    if max_tokens < 8 or max_words < 1 or overlap_words < 0:
        raise ValueError("Invalid chunk limits")
    position = start
    while position < end:
        while position < end and text[position].isspace():
            position += 1
        if position >= end:
            break
        words = list(re.finditer(r"\S+", text[position:end]))
        upper = min(len(words), max_words)
        low, high, accepted = 1, upper, 0
        while low <= high:
            middle = (low + high) // 2
            candidate_end = position + words[middle - 1].end()
            if count_tokens(text[position:candidate_end]) <= max_tokens:
                accepted, low = middle, middle + 1
            else:
                high = middle - 1
        if accepted:
            stop = position + words[accepted - 1].end()
            yield position, stop
            if accepted == len(words):
                break
            overlap = min(overlap_words, accepted // 4)
            position += words[accepted - overlap].start()
        else:
            # A single long unspaced word can exceed the multilingual token budget.
            low, high, accepted_chars = 1, words[0].end(), 0
            while low <= high:
                middle = (low + high) // 2
                if count_tokens(text[position:position + middle]) <= max_tokens:
                    accepted_chars, low = middle, middle + 1
                else:
                    high = middle - 1
            if not accepted_chars:
                raise ValueError("A character cannot fit the configured token budget")
            yield position, position + accepted_chars
            position += accepted_chars


def chunk_page(page, *, count_tokens, max_tokens=480, max_words=350, overlap_words=40,
               language=None, language_score=0.0):
    if not page.get("usable_for_retrieval") or page.get("needs_review"):
        return []
    if page.get("extraction_method") == "ocr" and not page.get("ocr_human_proofread"):
        return []
    if hashlib.sha256(page["text"].encode("utf-8")).hexdigest() != page["text_sha256"]:
        raise ValueError("Canonical page text checksum mismatch")
    language, language_score = (detect_language(page["text"]) if language is None else (language, language_score))
    spans = block_spans(page)
    records = []
    for section_start, section_end, heading in section_ranges(page):
        for start, end in passage_windows(page["text"], section_start, section_end, count_tokens=count_tokens,
                                           max_tokens=max_tokens, max_words=max_words, overlap_words=overlap_words):
            text = page["text"][start:end]
            if sum(ch.isalpha() for ch in text) < 15:
                continue
            identity = f"{page['page_id']}:{page['text_sha256']}:{start}:{end}"
            blocks = [block for a, b, block in spans if a < end and b > start]
            keys = ("document_id", "page_id", "source_filename", "source_relative_path", "source_sha256",
                    "document_title", "machine_type_hint", "source_type_hint", "applicability", "applicability_verified",
                    "pdf_page_number", "page_index", "pdf_page_label", "citation", "extraction_method",
                    "ocr_human_proofread", "needs_review")
            record = {key: page.get(key) for key in keys}
            scope = "both" if page.get("source_type_hint") == "bearing_reference" else page.get("machine_type_hint", "unknown")
            record.update({"chunk_id": hashlib.sha256(identity.encode()).hexdigest(),
                           "page_text_sha256": page["text_sha256"], "char_start": start, "char_end": end,
                           "text": text, "section_heading": heading,
                           "block_indexes": [block["block_index"] for block in blocks],
                           "bboxes": [block["bbox"] for block in blocks], "machine_scope": scope,
                           "language": language, "language_detection_score": language_score,
                           "word_count": len(text.split()), "token_count": count_tokens(text)})
            records.append(record)
    return records


def build_chunks(pages_file=EXTRACTION_ROOT / "pages.jsonl", output_dir=CHUNK_DIR, *, model_dir=MODEL_DIR):
    pages_file, output_dir = Path(pages_file), Path(output_dir)
    before = file_hash(pages_file)
    tokenizer = LocalTokenizer(model_dir)
    pages = [json.loads(line) for line in pages_file.read_text(encoding="utf-8").splitlines()]
    chunks, skipped = [], []
    for index, page in enumerate(pages, start=1):
        if index == 1 or index % 100 == 0:
            print(f"Chunking PDF page record {index}/{len(pages)}", flush=True)
        result = chunk_page(page, count_tokens=tokenizer.count)
        if not result:
            skipped.append({"page_id": page["page_id"], "citation": page["citation"],
                            "reason": "unusable_or_unreviewed" if not page.get("usable_for_retrieval") or page.get("needs_review")
                            else "no_substantive_text"})
        chunks.extend(result)
    if not chunks or len({chunk["chunk_id"] for chunk in chunks}) != len(chunks):
        raise ValueError("Expected non-empty chunks with unique IDs")
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    manifest = {"pages_jsonl_sha256": before, "page_records": len(pages), "chunk_count": len(chunks),
                "indexed_page_count": len({c["page_id"] for c in chunks}), "skipped_pages": skipped,
                "max_passage_tokens": 480, "max_words": 350, "overlap_words_max": 40,
                "language_counts": dict(Counter(c["language"] for c in chunks)),
                "machine_scope_counts": dict(Counter(c["machine_scope"] for c in chunks)),
                "tokenizer_revision": MODEL_REVISION, "tokenizer_sha256": file_hash(Path(model_dir) / "tokenizer.json"),
                "chunks_jsonl_sha256": file_hash(output_dir / "chunks.jsonl"),
                "language_detection": "langdetect, seed 42; heuristic score, not calibrated probability",
                "unreviewed_ocr_included": False, "pages_unchanged": file_hash(pages_file) == before}
    if not manifest["pages_unchanged"]:
        raise RuntimeError("Extraction pages changed during chunking")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Created {len(chunks)} page-bound chunks; skipped {len(skipped)} pages. Output: {output_dir}")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=Path, default=EXTRACTION_ROOT / "pages.jsonl")
    parser.add_argument("--output-dir", type=Path, default=CHUNK_DIR)
    args = parser.parse_args(argv)
    build_chunks(args.pages, args.output_dir)


if __name__ == "__main__":
    main()
