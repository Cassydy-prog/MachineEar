# Setup and portable assets

[Overview](../README.md) - [Code reference](code/README.md)

## Install

Run from the cloned repository root. Create and activate a virtual environment:

```sh
python -m venv .venv
python -m pip install -r requirements/rag.txt
```

Use the environment's Python after activation (`.venv/Scripts/python.exe` on
Windows or `.venv/bin/python` on Linux/macOS). On the prepared Python 3.15 Windows
machine, set `$env:PYYAML_FORCE_LIBYAML = '0'` before installing to use the
pure-Python PyYAML build. Local work uses Python 3.15.2, Node 24.19.0, librosa
0.11.0 and scikit-learn 1.9.1. Hosted Python 3.11/Linux CI is configured but has
not been verified yet. The original `requirements-audio.txt` is unchanged and
pins librosa 1.0.0; this is not reproduction of the original audio test environment.

Install Node.js/npm separately and ensure they are on PATH. Prepare the pinned
local multilingual query encoder and Node ONNX runtime:

```sh
python -m machineear.rag.local_embeddings --prepare
```

This downloads about 118 MB of weights plus tokenizer/runtime dependencies into
`.venv/`. Existing document vectors/index are reused. It does not send PDFs or
queries to an external service. `requirements/rag.txt` includes `base.txt`, which
also supplies the dependencies needed by Ballystone's original predictor.
The Node runtime is pinned by `requirements/embedding-runtime.lock.json`.

## What a clone includes

| Path | Contents |
| --- | --- |
| `data/manuals/Fan_Docs/`, `data/manuals/Pump_Docs/` | 12 original PDFs, 835 physical pages |
| `data/features/machineear_features_all_snr.csv` | Original 29,265-row, 52-feature CSV; reference data, not a RAG input |
| `results/baseline/data_splits.csv` | Ballystone's fixed split; no duplicate copy added |
| `results/rag/extraction/` | Text by page/document, page JSONL, provenance, OCR derivatives and browse index |
| `results/rag/chunks/` | 3,353 exact page-bound passages and manifest |
| `results/rag/index/` | Existing embeddings, SQLite BM25 index, passages and checksums |
| `results/rag/evaluation/` | Saved development queries, results and HTML report |
| `results/logmel_knn/`, `results/final_test/` | Inherited audio models and saved results, unchanged |

Recordings are intentionally absent. Supply a new recording only when using
connected audio analysis. Source hashes are in `docs/evidence/input_hashes.json`;
publication/portability checks are in `docs/evidence/repository_assets.json`.

Leave `MACHINEEAR_RESOURCE_ROOT` unset for the cloned resources. The optional
variable can reuse assets on the original workstation; it never redirects the
frozen models or original scripts. To use the original prepared environment in
the supplied nested checkout, run `../../.venv/Scripts/python.exe` and set
`$env:MACHINEEAR_RESOURCE_ROOT = (Resolve-Path '../..').Path`. That option is not
needed on another laptop.

## Search and inspect

```sh
python -m machineear.rag.retrieve_documents search --machine-type fan --language en --query "What NLGI grease grade is specified for fan bearings?"
python -m machineear.rag.retrieve_documents search --machine-type pump --language en --query "How does vapor pressure cause pump cavitation?"
```

Use `fr` for French, `auto` for heuristic language detection or `all` for
cross-language search. Specify a language for short ambiguous questions.
Open `results/rag/extraction/index.html` to browse documents and physical-page
text; `results/rag/evaluation/report.html` shows saved retrieval checks.

## Connect Ballystone's audio result

```sh
python -m machineear.analyze_recording --wav recording.wav --machine-type fan --machine-id id_00 --notes "Which inspection checks are documented?" --output results/analysis/example.json
```

The bridge runs the original `scripts/predict_audio.py`, then adapts its saved
JSON to the RAG API. It does not fit, extract features or calculate scores itself.
New recordings and output analysis JSON remain local. Missing/invalid retrieval
assets produce `audio_only` with the original audio result preserved.

## Rebuild documents only when needed

Existing extraction/chunks/index are already included. An intentional rebuild
requires local OCR data; downloads and processing are explicit:

```sh
python -m machineear.rag.extract_pdf_text --prepare-ocr-data
python -m machineear.rag.extract_pdf_text
python -m machineear.rag.chunk_documents
python -m machineear.rag.retrieve_documents build
python -m machineear.rag.evaluate_retrieval
```

Review OCR before admitting flagged pages. Rebuild affected stages after source
or tokenizer changes; checksum checks reject stale assets. Preserve original
PDFs. No audio training, feature extraction or final-test scoring is required.

## Verify

```sh
python -B -m unittest discover -s tests -v
```

Checks cover RAG, citation provenance and the connector boundary. Real OCR/search
checks require their local dependencies; connected tests additionally require
normal training WAVs, so they skip on a clone without recordings. A skip does
not claim that integration ran. Git preserves checksum-linked asset bytes using
`.gitattributes`; environments, secrets and embedding weights remain excluded.
