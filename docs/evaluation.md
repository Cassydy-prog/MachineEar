# MachineEar: Audio Anomaly Detection and RAG

MachineEar combines audio anomaly detection with retrieval from maintenance manuals. It helps technicians identify unusual machine sounds and find relevant documentation with source-page citations.

## 1. Audio Anomaly Detection

The audio pipeline uses Ballystone’s trained **`logmel_knn5_mean`** model to analyze fan and pump recordings.

| Input | Output |
|---|---|
| WAV recording, machine family, and machine ID | Anomaly score, saved threshold, anomaly flag, and window results |

### Saved audio results

| Machine | Precision | Recall | F1 | False-alarm rate |
|---|---:|---:|---:|---:|
| Fan | 0.881 | 0.389 | 0.540 | 0.047 |
| Pump | 0.757 | 0.608 | 0.675 | 0.059 |

These results come from Ballystone/the audio team’s saved evaluation in `results/final_test/summary.csv`. The RAG contribution preserves the original models and thresholds.

An anomaly indicates an unusual sound; it does not identify a mechanical fault.

## 2. RAG: Maintenance Document Retrieval

The retrieval pipeline searches fan and pump manuals and returns relevant passages with document names and physical PDF page numbers.

| Component | Implementation |
|---|---|
| PDF extraction | PyMuPDF and local OCR |
| Semantic embeddings | Multilingual E5-small |
| Keyword search | SQLite FTS5 with BM25 |
| Hybrid ranking | Reciprocal Rank Fusion — RRF |
| Source verification | PDF checksums and exact passage matching |

RRF combines keyword and semantic rankings to produce the final search results. Retrieval and query embeddings run locally.

### Document collection

| Resource | Count |
|---|---:|
| Maintenance manuals | 12 |
| Physical PDF pages | 835 |
| Indexed pages | 828 |
| Indexed passages | 3,353 |

### Measured retrieval results

Results were calculated from the saved hybrid retrieval outputs using **15 technical questions** and **two unrelated questions**.

| Metric | Result |
|---|---:|
| Reference Hit@1 | 33.33% |
| Reference Hit@3 | 60.00% |
| Reference Hit@5 | 80.00% |
| Reference MRR@5 | 0.5133 |
| Correct abstention | 2/2 |
| Returned passages matching original PDF text | 75/75 |

**Hit@k** measures whether a declared reference page appears in the first k results. **MRR** measures how early the first reference appears.

These are development results from questions also used to tune the retrieval cutoff.

### Results by machine family

| Machine | Technical questions | Reference Hit@5 | Reference MRR@5 |
|---|---:|---:|---:|
| Fan | 7 | 71.43% | 0.4643 |
| Pump | 8 | 87.50% | 0.5563 |
| **Overall** | **15** | **80.00%** | **0.5133** |

## 3. Connected Workflow

| Step | Action |
|---|---|
| 1 | Provide a WAV recording and select the machine family and ID |
| 2 | Run the original audio predictor |
| 3 | Build a maintenance query using the result and optional technician notes |
| 4 | Retrieve relevant manual passages |
| 5 | Return the audio result and cited documentation |

The anomaly flag guides the inspection query without assigning a specific fault.

## 4. Installation

Install Python, Node.js, and npm, then run from the repository root:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/rag.txt -r requirements-web.txt
```

On Windows PowerShell, activate the environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Prepare the local embedding model:

```sh
python -m machineear.rag.local_embeddings --prepare
```

The manuals and prepared document index are already included in the repository.

## 5. Usage

### Search maintenance manuals

```sh
python -m machineear.rag.retrieve_documents search \
  --machine-type fan \
  --language en \
  --query "What NLGI grease grade is specified for fan bearings?"
```

### Analyze a recording

```sh
python -m machineear.analyze_recording \
  --wav recording.wav \
  --machine-type fan \
  --machine-id id_00 \
  --notes "Which bearing lubrication checks are documented?" \
  --output results/analysis/recording.json
```

| Option | Supported values |
|---|---|
| Machine family | `fan`, `pump` |
| Machine ID | `id_00`, `id_02`, `id_04`, `id_06` |
| Retrieval language | `en`, `fr`, `auto`, `all` |

### Start the web application

```sh
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## 6. Tests

```sh
python -B -m unittest discover -s tests -v
```

| Latest cloud test outcome | Count |
|---|---:|
| Passed | 48 |
| Unsuccessful interface tests | 2 |
| Skipped because required assets were unavailable | 5 |
| **Total** | **55** |

## 7. Repository Structure

```text
machineear/
    rag/                   Document extraction, retrieval, and evaluation
    audio_bridge.py        Connection to the original audio predictor
    analyze_recording.py   Combined audio and retrieval pipeline

scripts/                   Original audio processing and prediction
backend/                   FastAPI application
frontend/                  Web interface
data/manuals/              Original maintenance PDFs
results/logmel_knn/         Frozen audio models
results/final_test/         Saved audio evaluation
results/rag/               Document index and retrieval results
tests/                     Software and integration checks
docs/                      Setup, architecture, and evaluation
```

## 8. Documentation

| Document | Contents |
|---|---|
| [Setup](docs/setup.md) | Installation and commands |
| [Architecture](docs/architecture.md) | Pipeline design |
| [Evaluation](docs/evaluation.md) | Audio and retrieval results |
| [Code reference](docs/code/README.md) | Modules and APIs |

The audio anomaly detector is Ballystone/the audio team’s contribution. The RAG component adds local document retrieval, source verification, and its connection to the existing audio predictions.
