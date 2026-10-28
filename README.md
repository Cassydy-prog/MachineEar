# MachineEar: connecting machine sounds to maintenance manuals

MachineEar brings together two parts of our project: detecting unusual machine
sounds and finding useful information in maintenance manuals. The idea is to
give a technician both the audio result and relevant source passages to review,
with a clear reference to the document and page each passage came from.

This branch builds on **Ballystone's audio anomaly-detection work**. His acoustic
extraction, training, final model (`logmel_knn5_mean`) and saved evaluation remain
unchanged. Our contribution here is the document-retrieval side and its connection
to that existing predictor. We have not retrained his models or changed their
thresholds.

## What we built during the RAG phase

The retrieval part of RAG, or retrieval-augmented generation, is implemented.
It can find and return source passages; the LLM step that turns those passages
into a drafted report is still to come.

### 1. Extracting the manuals while keeping their sources

We processed **12 fan and pump PDFs containing 835 physical pages**. We used
**PyMuPDF** to extract native text and local **MuPDF/Tesseract OCR** where a page
contained scanned text. The scanned maintenance guide needed a column-aware OCR
profile to preserve its reading order.

Each page keeps its original PDF filename, physical page number, any printed
page label, text blocks and coordinates. SHA-256 checksums record which source
PDF and page text were used. Original PDFs are preserved, and OCR copies are
saved separately. You can browse the extraction in
[the document index](results/rag/extraction/index.html).

OCR still needs human proofreading. Unreviewed OCR, blank pages and other pages
flagged for review are excluded from default retrieval. The current index uses
**828 eligible pages**.

### 2. Splitting pages into passages

We created **3,353 chunks**, each copied exactly from a single page. Every chunk
keeps its source page, character offsets and citation, so a returned passage can
be checked against the extracted text.

Chunks are limited to 480 model tokens, including the embedding prefix, and
350 words, with up to 40 words of overlap. This gives search some surrounding
context while staying within the model's input limit. Python handles the
chunking, **Hugging Face tokenizers** counts tokens, and **langdetect** provides
language hints. Those hints are heuristic, so an explicit language is useful
for short questions.

### 3. Building local semantic and keyword search

We use the quantized **Xenova/multilingual-e5-small** embedding model to represent
passages and questions as 384-dimensional vectors. This supports multilingual
semantic search, including our English and French examples. The model runs
locally through a **Node.js ONNX Runtime** worker, using the `query:` and
`passage:` prefixes expected by E5.

The vectors are stored in a **NumPy** file and searched using cosine similarity.
Alongside them, **SQLite FTS5 with BM25** provides keyword search for terms such
as grease grades, bearing names and maintenance instructions. Python combines
the two rankings using **reciprocal rank fusion**. This is our hybrid search;
it does not require a separate vector-database service.

### 4. Filtering results and verifying citations

Search considers the selected machine family and language. Before a passage is
returned, the pipeline checks its exact text and offsets, citation metadata and
the original PDF checksum. It also checks the index and tokenizer fingerprints
to reject stale or mismatched assets.

Results include the source document, physical PDF page and passage text. If
there are no supported passages, the response says so. A similarity score is
not a confidence probability, and a generic manual is not automatically
applicable to a particular manufacturer or machine model.

### 5. Connecting retrieval to Ballystone's audio result

`audio_bridge.py` calls Ballystone's original `scripts/predict_audio.py` and
adapts its JSON output for `analyze_recording()`. It passes through his scores,
thresholds and window results; it does not implement another detector.

The connected pipeline uses the machine family, the anomaly flag and optional
technician notes to form a maintenance query. The flag changes the general
inspection intent, but it does not infer a specific fault. Raw scores and dataset
IDs are not used as manual-search terms.

### Tools used

| Part | Tools |
| --- | --- |
| PDF text and page layout | PyMuPDF |
| Scanned-page OCR | MuPDF's integrated Tesseract; Pillow for image handling |
| Chunking and language hints | Python, Hugging Face tokenizers, langdetect |
| Semantic embeddings | Quantized Xenova/multilingual-e5-small |
| Local embedding inference | Node.js and onnxruntime-node |
| Vector storage and similarity | NumPy and cosine similarity |
| Keyword search | SQLite FTS5 and BM25 |
| Combining search results | Reciprocal rank fusion in Python |
| Source verification | SHA-256, page metadata and exact-text/offset checks |
| Software checks | Python unittest |

## Set it up on another laptop

Clone this branch and run commands from the repository root. Install Node.js
and npm separately, then create and activate a Python environment. In Windows
PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements/rag.txt
python -m machineear.rag.local_embeddings --prepare
```

On Linux/macOS, replace the activation command with `source .venv/bin/activate`.
See [setup](docs/setup.md) for the Windows/Python 3.15 installation note and
other environment details.

The preparation command downloads the pinned local embedding model, tokenizer
and ONNX runtime. The manuals, extracted pages, chunks and prepared index are
already in the repository, so you do not need to extract or embed them again.
PDF processing and search run locally; document contents and queries are not
sent to an external embedding or LLM service. Leave `MACHINEEAR_RESOURCE_ROOT`
unset to use the cloned assets.

You can try document search without providing any recording:

```sh
python -m machineear.rag.retrieve_documents search --machine-type fan --language en --query "What NLGI grease grade is specified for fan bearings?"
```

## Try the full pipeline with one WAV file

**You can analyze a single WAV file without downloading the original recording
dataset.** After setup, place your file in the repository folder or provide its
full path. Use a recording of at least two seconds and choose the correct
machine family and trained machine ID.

```sh
python -m machineear.analyze_recording --wav "my_recording.wav" --machine-type fan --machine-id id_00 --notes "Which bearing lubrication checks are documented?" --output results/analysis/my_recording.json
```

Replace `my_recording.wav` with your filename. For a pump, use `--machine-type
pump`. Supported IDs are `id_00`, `id_02`, `id_04` and `id_06`; select the bundle
that corresponds to the machine being recorded. The program does not identify
the equipment automatically. Notes are optional; the example is a question,
not an observation of a bearing fault. Use `--language fr` for French retrieval.

The command prints the structured result and saves it to
`results/analysis/my_recording.json`. It contains:

- Ballystone's anomaly score, saved threshold, anomaly flag and window results.
- The technician context and the query used for retrieval.
- Relevant manual passages with their document and physical-page citations.
- Retrieval status and timing information.

An anomaly means the sound is unusual according to the selected model; it does
not confirm a mechanical fault. If retrieval is unavailable, the result keeps
the audio prediction and reports `audio_only` with an error. The JSON is an
analysis result, not an LLM-generated maintenance report.

## Repository layout

```text
machineear/
    rag/                   PDF extraction, chunks, embeddings, search and evaluation
    analyze_recording.py   Connect audio predictions to cited retrieval
    audio_bridge.py        Call Ballystone's original predictor
    paths.py, runtime.py   Resource paths and native runtime setup
scripts/                   Ballystone's original audio scripts
data/manuals/              Original fan and pump PDFs
data/features/             Original combined feature CSV
results/rag/               Extracted text, chunks, vectors, SQLite index and checks
results/logmel_knn/         Existing frozen audio models
results/final_test/         The audio team's saved evaluation
tests/                     RAG, connector and citation tests
docs/                      Setup, methods, evaluation and code reference
```

The feature CSV is included as reference data; RAG does not use its acoustic
values or labels as document evidence. The fixed split remains at
`results/baseline/data_splits.csv`. Recordings, virtual environments, downloaded
embedding weights, secrets and individual recording analyses are excluded from Git.

## Checks and current limits

Our saved retrieval development checks found the declared reference page in the
top five results for **12 of 15 technical questions**. Two unrelated questions
returned no passages at the revised cutoff, giving **14 of 17 development checks**
overall. All 75 returned passages matched text re-extracted from the original
PDFs. The cutoff was tuned on these examples, so these are development findings,
not an independent retrieval-accuracy estimate.

The prepared local environment passed **39 software tests**. Without recordings
or downloaded OCR/embedding assets, 32 passed and seven integration checks
skipped. Run the suite with:

```sh
python -B -m unittest discover -s tests -v
```

The next steps are source-cited LLM report drafting and a technician interface
for editing, approval and saved history. Both remain pending. The audio team's
final-test results are recorded separately in [evaluation](docs/evaluation.md);
this RAG work did not retrain the model, change thresholds or rerun that test.

- [Setup and commands](docs/setup.md)
- [Architecture](docs/architecture.md)
- [Evaluation and limitations](docs/evaluation.md)
- [Code and API reference](docs/code/README.md)
