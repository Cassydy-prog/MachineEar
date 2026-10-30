"""Build and query a local dense/BM25 index with verifiable PDF citations."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3

from machineear.rag.chunk_documents import CHUNK_DIR, detect_language
from machineear.rag.extract_pdf_text import PDF_ROOT, OUTPUT_ROOT as EXTRACTION_ROOT, file_hash
from machineear.rag.local_embeddings import LocalEmbedder, MODEL_DIR, MODEL_REPO, MODEL_REVISION
from machineear.paths import ROOT, RESOURCE_ROOT

INDEX_DIR = RESOURCE_ROOT / "results" / "rag" / "index"
STOP_WORDS = set("a an the is are was were be been how what why when where which should do does can could i we my our your it its of to in on for and or with from about this that les le la des du de un une est sont comment pourquoi quand que pour dans et ou au aux ces ce il elle je nous vous mon ma mes".split())


def query_terms(query):
    return [word.lower() for word in re.findall(r"[^\W_]+(?:[-_][^\W_]+)*", query, re.UNICODE)
            if word.lower() not in STOP_WORDS and len(word) > 1][:32]


def eligible_chunk(chunk, machine_type, language=None):
    return (not chunk.get("needs_review") and chunk.get("machine_scope") in (machine_type, "both")
            and (language is None or chunk.get("language") in (language, "und")))


def verify_passage(chunk, page):
    keys = ("page_id", "document_id", "source_relative_path", "source_sha256", "pdf_page_number", "pdf_page_label", "citation")
    if any(chunk.get(key) != page.get(key) for key in keys):
        raise ValueError("Passage citation metadata disagrees with its source page")
    start, end = chunk["char_start"], chunk["char_end"]
    digest = hashlib.sha256(page["text"].encode("utf-8")).hexdigest()
    if digest != chunk["page_text_sha256"] or not 0 <= start < end <= len(page["text"]):
        raise ValueError("Passage offsets or page checksum are invalid")
    if page["text"][start:end] != chunk["text"]:
        raise ValueError("Passage text is not an exact source-page substring")
    if page.get("needs_review") or not page.get("usable_for_retrieval"):
        raise ValueError("Source page is not cleared for default retrieval")
    return True


def reciprocal_rank_fusion(dense_ids, keyword_ids, constant=60):
    scores = {}
    for ranking in (dense_ids, keyword_ids):
        for rank, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + 1 / (constant + rank)
    return scores


def build_index(chunks_file=CHUNK_DIR / "chunks.jsonl", output_dir=INDEX_DIR, *, batch_size=8):
    import numpy as np

    if batch_size < 1 or batch_size > 32:
        raise ValueError("Embedding batch size must be between 1 and 32")
    chunks_file, output_dir = Path(chunks_file), Path(output_dir)
    chunks = [json.loads(line) for line in chunks_file.read_text(encoding="utf-8").splitlines()]
    if not chunks or any(chunk.get("needs_review") for chunk in chunks):
        raise ValueError("Expected non-empty, reviewed/indexable chunks")
    before = file_hash(chunks_file)
    output_dir.mkdir(parents=True, exist_ok=True)
    embeddings = np.zeros((len(chunks), 384), dtype=np.float32)
    with LocalEmbedder() as encoder:
        order = sorted(range(len(chunks)), key=lambda i: chunks[i]["token_count"])
        for offset in range(0, len(order), batch_size):
            indices = order[offset:offset + batch_size]
            embeddings[indices] = encoder.encode([chunks[i]["text"] for i in indices])
            if offset == 0 or offset // batch_size % 10 == 0 or offset + batch_size >= len(order):
                print(f"Embedded {min(offset + batch_size, len(order))}/{len(order)} passages", flush=True)
        runtime_info = encoder.runtime_info
    np.save(output_dir / "embeddings.npy", embeddings, allow_pickle=False)
    temporary_db = output_dir / "chunks.sqlite3.building"
    temporary_db.unlink(missing_ok=True)
    with sqlite3.connect(temporary_db) as connection:
        connection.execute("CREATE TABLE chunks(id INTEGER PRIMARY KEY, chunk_id TEXT UNIQUE, scope TEXT, language TEXT, metadata TEXT)")
        connection.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tokenize='unicode61 remove_diacritics 2')")
        for index, chunk in enumerate(chunks, start=1):
            connection.execute("INSERT INTO chunks VALUES(?,?,?,?,?)", (index, chunk["chunk_id"], chunk["machine_scope"], chunk["language"], json.dumps(chunk, ensure_ascii=False)))
            connection.execute("INSERT INTO chunks_fts(rowid,text) VALUES(?,?)", (index, chunk["text"]))
        connection.commit()
    connection.close()
    temporary_db.replace(output_dir / "chunks.sqlite3")
    shutil.copyfile(chunks_file, output_dir / "chunks.jsonl")
    chunk_manifest = json.loads((chunks_file.parent / "manifest.json").read_text(encoding="utf-8"))
    manifest = {"chunk_count": len(chunks), "embedding_dimension": 384, "model_repo": MODEL_REPO,
                "model_revision": MODEL_REVISION, "runtime": runtime_info,
                "pages_jsonl_sha256": chunk_manifest["pages_jsonl_sha256"],
                "chunks_jsonl_sha256": before, "embedding_sha256": file_hash(output_dir / "embeddings.npy"),
                "sqlite_sha256": file_hash(output_dir / "chunks.sqlite3"),
                "tokenizer_sha256": chunk_manifest["tokenizer_sha256"],
                "keyword_search": "SQLite FTS5 BM25, Unicode and diacritic normalization",
                "fusion": "equal-weight reciprocal rank fusion, constant 60",
                "unreviewed_ocr_included": False, "remote_inference": False,
                "source_applicability": "generic guidance; equipment match unverified"}
    if file_hash(chunks_file) != before:
        raise RuntimeError("Chunk input changed while building the index")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Local hybrid index ready: {len(chunks)} passages in {output_dir}")
    return manifest


class LocalRetriever:
    def __init__(self, index_dir=INDEX_DIR, *, pages_file=EXTRACTION_ROOT / "pages.jsonl", source_root=PDF_ROOT):
        import numpy as np

        self.index_dir, self.source_root = Path(index_dir), Path(source_root)
        self.encoder = None
        self.manifest = json.loads((self.index_dir / "manifest.json").read_text(encoding="utf-8"))
        expected = self.manifest
        for name, key in (("embeddings.npy", "embedding_sha256"), ("chunks.sqlite3", "sqlite_sha256"), ("chunks.jsonl", "chunks_jsonl_sha256")):
            if file_hash(self.index_dir / name) != expected[key]:
                raise ValueError(f"Index artifact checksum mismatch: {name}")
        if file_hash(pages_file) != expected["pages_jsonl_sha256"]:
            raise ValueError("Extraction changed; rebuild chunks and the retrieval index")
        if expected["model_revision"] != MODEL_REVISION:
            raise ValueError("Index embedding model revision does not match the query encoder")
        if file_hash(MODEL_DIR / "tokenizer.json") != expected["tokenizer_sha256"]:
            raise ValueError("Index tokenizer does not match the query tokenizer; rebuild the index")
        self.chunks = [json.loads(line) for line in (self.index_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
        self.pages = {page["page_id"]: page for page in (json.loads(line) for line in Path(pages_file).read_text(encoding="utf-8").splitlines())}
        self.vectors = np.load(self.index_dir / "embeddings.npy", allow_pickle=False)
        if self.vectors.shape != (len(self.chunks), 384) or not np.isfinite(self.vectors).all():
            raise ValueError("Index vector shape or values are invalid")
        self.connection = sqlite3.connect((self.index_dir / "chunks.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)

    def search(self, query, machine_type, *, language="auto", top_k=5, min_similarity=0.82):
        import numpy as np

        if not query.strip() or machine_type not in ("fan", "pump") or not 1 <= top_k <= 20:
            raise ValueError("Provide a question, fan/pump family, and top_k between 1 and 20")
        if not -1 <= min_similarity <= 1:
            raise ValueError("Minimum similarity must be between -1 and 1")
        detected, confidence = detect_language(query)
        selected_language = (None if detected == "und" else detected) if language == "auto" else None if language == "all" else language
        if selected_language and not re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2})?", selected_language):
            raise ValueError("Use auto, all, or a language code such as en/fr")
        eligible = np.asarray([i for i, chunk in enumerate(self.chunks) if eligible_chunk(chunk, machine_type, selected_language)], dtype=int)
        response = {"query": query, "machine_type": machine_type, "language_filter": selected_language,
                    "detected_query_language": detected, "language_detection_score": confidence,
                    "minimum_semantic_similarity": min_similarity,
                    "status": "no_supported_passages", "results": [],
                    "applicability_note": "Generic technical guidance; applicability to the selected equipment is unverified."}
        if not len(eligible):
            return response
        if self.encoder is None:
            self.encoder = LocalEmbedder()
        query_vector = self.encoder.encode([query], kind="query")[0]
        similarities = self.vectors @ query_vector
        dense_ids = [int(i) for i in eligible[np.argsort(-similarities[eligible], kind="stable")[:50]]]
        terms = query_terms(query)
        keyword_ids = []
        if terms:
            expression = " OR ".join('"' + word.replace('"', '""') + '"' for word in terms)
            sql = "SELECT c.id FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid WHERE chunks_fts MATCH ? AND c.scope IN (?,?)"
            values = [expression, machine_type, "both"]
            if selected_language:
                sql += " AND c.language IN (?,?)"
                values += [selected_language, "und"]
            sql += " ORDER BY bm25(chunks_fts),c.id LIMIT 50"
            keyword_ids = [int(row[0]) - 1 for row in self.connection.execute(sql, values)]
        fused = reciprocal_rank_fusion(dense_ids, keyword_ids)
        seen_pages = set()
        for index in sorted(fused, key=lambda i: (-fused[i], -float(similarities[i]), i)):
            chunk = self.chunks[index]
            if chunk["page_id"] in seen_pages or similarities[index] < min_similarity:
                continue
            verify_passage(chunk, self.pages[chunk["page_id"]])
            source = self.source_root / chunk["source_relative_path"]
            if not source.is_file() or file_hash(source) != chunk["source_sha256"]:
                raise ValueError(f"Original PDF changed or is missing: {chunk['source_relative_path']}; re-extract and rebuild")
            seen_pages.add(chunk["page_id"])
            result = {**chunk, "rank": len(response["results"]) + 1,
                      "semantic_similarity": float(similarities[index]), "fusion_score": fused[index],
                      "keyword_rank": keyword_ids.index(index) + 1 if index in keyword_ids else None,
                      "semantic_rank": dense_ids.index(index) + 1 if index in dense_ids else None,
                      "citation_verified": True}
            response["results"].append(result)
            if len(response["results"]) == top_k:
                break
        if response["results"]:
            response["status"] = "passages_for_review"
        return response

    def close(self):
        if self.encoder:
            self.encoder.close()
            self.encoder = None
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--chunks", type=Path, default=CHUNK_DIR / "chunks.jsonl")
    build.add_argument("--index-dir", type=Path, default=INDEX_DIR)
    search = sub.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--machine-type", choices=("fan", "pump"), required=True)
    search.add_argument("--language", default="auto")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--index-dir", type=Path, default=INDEX_DIR)
    args = parser.parse_args(argv)
    if args.command == "build":
        build_index(args.chunks, args.index_dir)
    else:
        with LocalRetriever(args.index_dir) as retriever:
            print(json.dumps(retriever.search(args.query, args.machine_type, language=args.language,
                                              top_k=args.top_k), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
