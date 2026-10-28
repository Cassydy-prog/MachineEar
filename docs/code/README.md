# RAG code and API reference

[Overview](../../README.md) - [Setup](../setup.md)

## Project boundary

Ballystone's original `scripts/`, notebooks, audio models, splits and saved
results are inherited unchanged. They are not new RAG work. This branch adds
the modules below; it adds no training, feature extraction or anomaly-detection
comparison implementation.

| Source | Purpose |
| --- | --- |
| [`analyze_recording.py`](../../machineear/analyze_recording.py) | Join the existing audio result, technician context and cited retrieval |
| [`audio_bridge.py`](../../machineear/audio_bridge.py) | Run original `scripts/predict_audio.py`; adapt paths/JSON without recomputing scores |
| [`paths.py`](../../machineear/paths.py) | Portable resource roots, frozen-model location and legacy recording-key resolution |
| [`runtime.py`](../../machineear/runtime.py) | Discover native Windows DLL directories on demand |
| [`rag/extract_pdf_text.py`](../../machineear/rag/extract_pdf_text.py) | Native extraction/local OCR, stable pages, source hashes and relative-path manifests |
| [`rag/chunk_documents.py`](../../machineear/rag/chunk_documents.py) | Exact single-page chunks with token limits and language metadata |
| [`rag/local_embeddings.py`](../../machineear/rag/local_embeddings.py) | Explicit model/runtime preparation, tokenization and local embeddings |
| [`rag/embedding_worker.cjs`](../../machineear/rag/embedding_worker.cjs) | Required persistent local CPU ONNX worker |
| [`rag/retrieve_documents.py`](../../machineear/rag/retrieve_documents.py) | Cosine/BM25 index building, filtered hybrid search and citation verification |
| [`rag/evaluate_retrieval.py`](../../machineear/rag/evaluate_retrieval.py) | Declared development queries and original-PDF passage verification |

Package `__init__.py` files are import-safe markers. Imports do not extract,
train, download or start native ML workers. Original audio scripts have
top-level execution and are called in a separate process, never imported into
the running application. Audio bridge requests have a 120-second timeout.

## Connected API

```python
from machineear.analyze_recording import analyze_recording

result = analyze_recording(
    "recording.wav", machine_type="fan", machine_id="id_00",
    technician_notes="Which bearing lubrication checks are documented?",
    language="en", top_k=5,
)
```

The first argument accepts a path or uploaded WAV bytes. Select `fan`/`pump` and
the actual dataset ID (`id_00`, `id_02`, `id_04`, `id_06`). Technician notes are
limited to 1,000 characters and equipment context to 400; oversized text is
rejected. `top_k` is 1-20. Language defaults to `en`; `fr`, `auto`, `all` and
language codes are accepted. English/French query templates are implemented.

Results separate `audio`, `technician_context`, `query_plan`, `retrieval`,
`interpretation` and `timings`. Original audio score/threshold/window values
come directly from Ballystone's JSON. The connector adds field aliases and
review context only. Technician observations and manual applicability are
unverified. No specific fault is inferred from an anomaly flag.

| Outcome | Status | CLI exit |
| --- | --- | ---: |
| Completed with passages or no supported passages | `analysis_complete`; retrieval `passages_for_review` or `no_supported_passages` | 0 |
| Invalid audio/model/settings or output error | API raises; CLI reports error | 1 |
| Retrieval fails after audio prediction succeeds | `audio_only`, original audio retained, explicit error, no passages | 2 |

The Python API saves no history; CLI `--output` explicitly writes local JSON.
`retriever=` accepts a prepared `LocalRetriever` owned/closed by the caller;
otherwise the function constructs and closes its own instance. No LLM report
or technician approval UI is generated.

## Retrieval API and commands

Use `LocalRetriever` as a context manager or close it explicitly. Its `search`
accepts query, machine family, language and top-k. It returns only verified
eligible passages or `no_supported_passages`. Similarity is not confidence.
Use `python -m machineear.rag.<module>` for the documented CLI stages; index
commands are `build` and `search`. See [setup](../setup.md) for full commands.

## Tests

| Source | Coverage |
| --- | --- |
| [`test_analysis.py`](../../tests/test_analysis.py) | Query/evidence boundaries, failure handling and optional fan/pump connection |
| [`test_audio_bridge.py`](../../tests/test_audio_bridge.py) | Delegation, unchanged returned values, temporary uploads and upstream failures |
| [`test_pdf_text.py`](../../tests/test_pdf_text.py) | Exact pages/source hashes, relative manifests, recursive extraction and local OCR |
| [`test_retrieval.py`](../../tests/test_retrieval.py) | Chunk boundaries, filtering/ranking, citation tampering and local embeddings/search |

Run `python -B -m unittest discover -s tests -v`. Real connected tests need
normal training WAVs; these are intentionally not published. OCR/embedding
integration requires local prepared assets. Missing prerequisites are skips.
