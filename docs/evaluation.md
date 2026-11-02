# RAG Evaluation and Results

[Overview](../README.md) · [Evidence](evidence/README.md)

This document presents MachineEar’s measured RAG retrieval results, corpus statistics, source-verification checks, and evaluation limitations.

The ranking metrics below were calculated from the saved per-question outputs in `results/rag/evaluation/`. They evaluate **hybrid retrieval using Reciprocal Rank Fusion (RRF)**. RRF combines semantic and keyword rankings; it is not itself an evaluation metric.

## 1. Retrieval performance

The development set contains **17 questions**:

| Question category | Count | Evaluation purpose |
|---|---:|---|
| Technical questions | 15 | Find declared reference pages |
| Unrelated questions | 2 | Return no unsupported passages |
| **Total** | **17** | Retrieval and abstention checks |

The following results use the saved run with a **0.82 semantic cutoff**.

| Metric | Measured result | Meaning |
|---|---:|---|
| Reference Hit@1 | **33.33% — 5/15** | First result contains a declared reference page |
| Reference Hit@3 | **60.00% — 9/15** | First three results contain a declared reference page |
| Reference Hit@5 | **80.00% — 12/15** | First five results contain a declared reference page |
| Reference MRR@1 | **0.3333** | Mean reciprocal first-reference rank within one result |
| Reference MRR@3 | **0.4667** | Mean reciprocal first-reference rank within three results |
| Reference MRR@5 | **0.5133** | Mean reciprocal first-reference rank within five results |
| Correct abstention rate | **100.00% — 2/2** | Unrelated questions return no passages |
| False abstention rate | **0.00% — 0/15** | No technical question returns an empty result list |
| Combined development checks | **82.35% — 14/17** | Twelve reference hits at five plus two correct abstentions |

Ranking metrics use the **15 technical questions**. Abstention on unrelated questions uses a separate denominator of **two**.

These are development results, not an independent accuracy estimate. The cutoff was tuned using these same questions.

## 2. Results by machine family

| Machine family | Technical questions | Reference Hit@1 | Reference Hit@3 | Reference Hit@5 | Reference MRR@5 |
|---|---:|---:|---:|---:|---:|
| Fan | 7 | 28.57% — 2/7 | 57.14% — 4/7 | 71.43% — 5/7 | 0.4643 |
| Pump | 8 | 37.50% — 3/8 | 62.50% — 5/8 | 87.50% — 7/8 | 0.5563 |
| **Overall** | **15** | **33.33% — 5/15** | **60.00% — 9/15** | **80.00% — 12/15** | **0.5133** |

The pump subset achieved higher reference retrieval scores in this development set. The small sample does not establish that pump retrieval will consistently outperform fan retrieval.

## 3. Results by query language

| Query language | Technical questions | Reference Hit@1 | Reference Hit@3 | Reference Hit@5 | Reference MRR@5 |
|---|---:|---:|---:|---:|---:|
| English | 13 | 30.77% — 4/13 | 61.54% — 8/13 | 76.92% — 10/13 | 0.4962 |
| French | 2 | 50.00% — 1/2 | 50.00% — 1/2 | 100.00% — 2/2 | 0.6250 |
| **Overall** | **15** | **33.33% — 5/15** | **60.00% — 9/15** | **80.00% — 12/15** | **0.5133** |

French retrieval was checked with only two questions. Its observed 100% Hit@5 should therefore be interpreted as a small development check, not a broad multilingual performance claim. Other languages remain unevaluated.

## 4. Semantic cutoff experiment

Saved outputs are available for cutoffs **0.75** and **0.82**.

| Metric | Cutoff 0.75 | Cutoff 0.82 | Observed change |
|---|---:|---:|---|
| Reference Hit@1 | 33.33% | 33.33% | Unchanged |
| Reference Hit@3 | 60.00% | 60.00% | Unchanged |
| Reference Hit@5 | 80.00% | 80.00% | Unchanged |
| Reference MRR@5 | 0.5133 | 0.5133 | Unchanged |
| Correct abstention | 0/2 — 0% | 2/2 — 100% | Both unrelated questions correctly rejected |
| False abstention | 0/15 — 0% | 0/15 — 0% | No additional empty technical results |
| Combined checks passed | 12/17 — 70.59% | 14/17 — 82.35% | Two additional checks passed |

Increasing the cutoff removed unsupported results for both unrelated questions while preserving the measured reference-hit rates and MRR.

Because these examples were used to select the cutoff, the improvement requires confirmation on a separately authored evaluation set. A similarity cutoff is not a confidence probability or a guarantee of relevant results.

## 5. Remaining retrieval misses

Three technical questions did not retrieve a declared reference page among their first five results.

| Case | Topic | Expected source | Physical PDF page |
|---|---|---|---:|
| `fan_noise` | Excessive fan noise or vibration | `Fan_Docs/463687CentFans_iom.pdf` | 15 |
| `fan_vibration_measurements` | Measurements needed to troubleshoot fan vibration | `Fan_Docs/Troubleshooting-Vibration-Problems-ES-202-1.pdf` | 1 |
| `pump_six_months` | Six-month pump alignment checks | `Pump_Docs/p2002569b-1.pdf` | 32 |

Reference pages were declared before inspecting these results and were not changed to improve the count.

The references are not exhaustive relevance judgments. Some returned pages may contain useful alternative guidance despite counting as reference misses.

## 6. Corpus and index

| Item | Count or configuration |
|---|---:|
| Original manuals | **12 PDFs** |
| Physical PDF pages | **835** |
| Native-text pages | 829 |
| OCR pages | 3 |
| Blank pages | 3 |
| Pages excluded from default retrieval | 7 |
| Eligible indexed pages | **828** |
| Indexed passages | **3,353** |
| Maximum passage length | **480 model tokens**, including the embedding prefix |
| Passage provenance | Exact substring of a single source page |

### Excluded pages

| Exclusion reason | Pages |
|---|---:|
| Unproofread OCR | 3 |
| Blank pages | 3 |
| Sparse text | 1 |
| **Total** | **7** |

Unproofread OCR and review-flagged pages remain excluded from default retrieval.

## 7. Citation and source verification

| Verification check | Result | What it establishes |
|---|---:|---|
| Returned passages match text re-extracted from original PDFs | **75/75 — 100%** | Exact passage provenance |
| Original PDF hashes match extraction records | **12/12 — 100%** | Source-file integrity |
| Indexed passages checked | **3,353** | Index passage verification |
| Indexed pages represented | **828** | Eligible page coverage |
| Maximum passage token budget | **480** | Declared model-input constraint |
| Unreviewed OCR admitted to default retrieval | **0 pages** | OCR exclusion policy preserved |

These checks establish source integrity and exact-text traceability. They do not establish that a passage answers the question or applies to a particular machine.

## 8. Retrieval configuration

| Component | Implementation |
|---|---|
| Semantic encoder | Quantized `Xenova/multilingual-e5-small` |
| Embedding execution | Local Node.js ONNX Runtime worker |
| Embedding dimensions | 384 |
| Semantic search | Cosine similarity over stored vectors |
| Keyword search | SQLite FTS5 with BM25 |
| Ranking fusion | Reciprocal Rank Fusion |
| Default semantic cutoff | 0.82 |
| Comparison candidate lists | 50 candidates per ranking |
| Result deduplication | Unique source document and physical PDF page |
| Filtering | Machine family and language |
| Citation validation | Source hashes, page metadata, exact text and offsets |

Processing and query embedding run locally. External embedding or LLM services are not required for the retrieval measurements reported here.

## 9. Metric definitions

| Metric | Definition | Evaluation unit |
|---|---|---|
| Reference Hit@k | Fraction of technical questions with at least one declared reference in the first k results | Question |
| Reference MRR@k | Mean of `1 / first relevant rank` within k; zero when no reference is found | Question |
| Correct abstention rate | Unrelated questions returning no passages divided by all unrelated questions | Unrelated question |
| False abstention rate | Technical questions returning no passages divided by all technical questions | Technical question |
| Citation text match rate | Returned passages matching original PDF text divided by checked passages | Passage |
| Source hash match rate | Matching original PDF hashes divided by checked PDFs | Source PDF |

Ranking metrics count unique `(source_relative_path, pdf_page_number)` pairs. Multiple passages from the same physical page count once.

A nonempty but incorrect result list is a reference miss, not an abstention.

### Metrics requiring additional evidence

| Metric | Required evidence |
|---|---|
| Precision@k | Complete relevance judgments for retrieved pages |
| Recall@k | Complete identification of relevant pages in the eligible corpus |
| nDCG@k | Complete relevance judgments with graded usefulness |
| Median/p95 latency | Recorded query timings under a documented runtime configuration |
| Generated-answer faithfulness | Generated answers checked against their supporting evidence |
| Generated-answer correctness | Reviewed reference answers or expert judgments |

These values are not inferred from Hit@k or software-test success. Incomplete reference labels support reference Hit/MRR, but not exhaustive relevance claims.

## 10. Software test results

The cloud environment’s latest complete suite ran **55 test methods** after Streamlit and OCR assets were installed.

| Outcome | Test count | Details |
|---|---:|---|
| Passed | **48** | Includes both previously skipped OCR integration tests |
| Unsuccessful | **2** | Streamlit tests do not match the current interface |
| Skipped | **4** | Local embedding assets unavailable because model downloads are blocked |
| Skipped | **1** | Original normal-training fan/pump WAVs unavailable |
| **Total** | **55** | Software verification, separate from retrieval quality |

### Unsuccessful interface checks

| Test expectation | Observed issue |
|---|---|
| Import `display_result` from `streamlit_app.py` | Function is absent |
| Select the `Historique` sidebar option | Current interface uses a different menu option |

The first test contains three failing status subtests; the second raises an error. This produces the runner summary `failures=3, errors=1` across two unsuccessful test methods.

### Remaining skipped checks

| Category | Count | Missing prerequisite |
|---|---:|---|
| Embedding integration | 1 | Approved local embedding model assets |
| Retrieval integration | 3 | Local query encoder and runtime assets |
| Connected audio-to-retrieval integration | 1 | Original normal-training WAVs |
| **Total** | **5** | |

Run the software suite from the repository root:

```sh
python -B -m unittest discover -s tests -v
```

No held-out audio inference was performed. Passing software tests does not establish retrieval accuracy or maintenance effectiveness.

## 11. Run a new method comparison

The benchmark supports semantic, semantic-gated BM25, and hybrid RRF rankings.

| Method | Ranking | Important condition |
|---|---|---|
| Semantic | Embedding similarity | Uses the shared semantic cutoff |
| BM25 | Keyword ranking | Still uses the shared semantic gate and query embeddings |
| Hybrid | Reciprocal Rank Fusion | Default application ranking |

The BM25 comparison is **semantic-gated BM25**, not a standalone lexical baseline. The measured results earlier in this document describe the saved hybrid output, not a completed comparison between all three methods.

After preparing the local embedding assets:

```sh
python -m machineear.rag.benchmark_retrieval
```

For a separately authored question set:

```sh
python -m machineear.rag.benchmark_retrieval \
  --cases my_cases.json \
  --output-dir results/rag/benchmark-held-out
```

| Output file | Contents |
|---|---|
| `metrics.json` | Per-query results, summaries, and reproducibility metadata |
| `scoreboard.csv` | One summary row per retrieval method |

The default benchmark reuses the existing 17 development questions. Naming an output directory `benchmark-held-out` does not make the question set independent.

### Timing protocol

| Operation | Treatment |
|---|---|
| One warmup query | Excluded |
| Query encoding | Included |
| Citation verification | Included |
| Model/index construction | Excluded |
| Method ordering | Rotated to reduce systematic cache advantages |
| p95 calculation | Nearest-rank percentile |

Latency measurements from a small question set provide only approximate runtime estimates.

## 12. Custom relevance judgments

Use a nonempty JSON list:

```json
[
  {
    "case_id": "fan-example",
    "query": "What NLGI grease grade is specified for fan bearings?",
    "machine_type": "fan",
    "language": "en",
    "answerable": true,
    "judgments_complete": false,
    "relevance": [
      {
        "source_relative_path": "Fan_Docs/463687CentFans_iom.pdf",
        "pdf_page_number": 11,
        "grade": 1
      }
    ]
  },
  {
    "case_id": "unsupported-example",
    "query": "What is the refund policy for airline tickets?",
    "machine_type": "fan",
    "language": "en",
    "answerable": false,
    "judgments_complete": false,
    "relevance": []
  }
]
```

| Relevance grade | Meaning |
|---|---|
| 0 | Irrelevant |
| 1 | Partly useful |
| 2 | Directly useful |

Set `judgments_complete: true` only after exhaustively reviewing relevance in the eligible corpus for that question. Do not relabel misses merely to improve the score.

## 13. Limitations and next evaluation steps

| Area | Current limitation | Next step |
|---|---|---|
| Generalization | Small development set reused for cutoff tuning | Evaluate a separately held-out question set |
| Relevance coverage | Declared references are incomplete | Review all relevant pages for each evaluation question |
| Ranking errors | Three reference misses | Inspect why generic pages outrank the expected instructions |
| Multilingual evaluation | Only English and French examples | Add reviewed questions for each intended language |
| OCR | Three pages remain unproofread | Review text against original page images |
| Equipment applicability | Generic manuals may not match actual equipment | Verify manufacturer/model applicability |
| Generated answers | Faithfulness and correctness unmeasured | Evaluate claims against cited evidence |
| Technician workflow | Usability and approval time unmeasured | Conduct a supervised workflow study |
| Interface tests | Two tests expect an earlier interface | Align tests and application behavior |
| Connected integration | Original training recordings absent | Supply the required normal-training WAVs |

An anomaly is not a diagnosed fault. Retrieved guidance requires human review before it informs maintenance decisions.

## 14. Existing audio evaluation — separate from RAG

The following values are **Ballystone/the audio team’s** saved `logmel_knn5_mean` results from `results/final_test/summary.csv`.

| Machine | Precision | Recall | F1 | False-alarm rate |
|---|---:|---:|---:|---:|
| Fan | 0.881 | 0.389 | 0.540 | 0.047 |
| Pump | 0.757 | 0.608 | 0.675 | 0.059 |

Saved counts, model hashes, and split identity were checked. This RAG contribution did not retrain the models, change frozen thresholds, introduce another anomaly detector, or rerun final-test inference.

These audio metrics do not measure retrieval performance.

## 15. Evidence and implementation

| Location | Contents |
|---|---|
| `results/rag/evaluation/results.json` | Saved per-question hybrid results at cutoff 0.82 |
| `results/rag/evaluation/initial_cutoff_075_results.json` | Saved results before the cutoff change |
| `results/rag/evaluation/summary.json` | Original development summary |
| `results/rag/evaluation/report.html` | Browsable retrieval evaluation |
| `results/rag/evaluation/findings.md` | Original findings and reference misses |
| `docs/evidence/` | Supporting evidence and compact outcomes |
| `machineear/rag/retrieval_metrics.py` | Ranking, abstention, and latency metric implementation |
| `machineear/rag/benchmark_retrieval.py` | Method comparison and JSON/CSV export |
| `results/final_test/summary.csv` | Audio team’s saved evaluation results |
