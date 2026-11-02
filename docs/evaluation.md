# Evaluation and limitations

[Overview](../README.md) - [Evidence](evidence/README.md)

## RAG development checks

The corpus has 12 PDFs and 835 physical pages: 829 native-text pages, three OCR
pages and three blanks. Default chunking excludes seven pages: three unproofread
OCR pages, three blanks and one sparse page. The index has 3,353 passages from
828 pages; each is an exact source-page substring within 480 tokens.

Fifteen technical questions have declared reference pages; two unrelated
questions check abstention. Twelve technical references appear in the first
five results. Both unrelated questions return nothing at the revised 0.82
cutoff: 14/17 development checks pass. The cutoff was raised from 0.75 using
these same examples, so this is not independent validation or an accuracy claim.

All 75 returned passages match text re-extracted from original pages, and the
12 source hashes match extraction. This verifies provenance, not relevance or
equipment applicability. English/French have development examples; other
languages remain unevaluated. Remaining reference misses concern fan noise,
fan vibration measurements and pump six-month alignment checks. Expected pages
were not changed to improve the count. See the full saved report under
`results/rag/evaluation/` and compact outcomes under `docs/evidence/`.

## Ballystone's existing audio evaluation

| Machine | Precision | Recall | F1 | False-alarm rate |
| --- | ---: | ---: | ---: | ---: |
| Fan | 0.881 | 0.389 | 0.540 | 0.047 |
| Pump | 0.757 | 0.608 | 0.675 | 0.059 |

These are the team's saved `logmel_knn5_mean` results in
`results/final_test/summary.csv`, produced by its original evaluation workflow.
They are attributed to Ballystone/the audio team, not this RAG contribution.
Saved counts, model hashes and split identity were checked; audio test inference
was not rerun and the original test environment was not independently reproduced.
The bridge uses the original predictor with its frozen mean threshold. No
alternate detector, acoustic-feature implementation or comparison experiment
is added by this branch.

## Software and portability checks

The current RAG/connector checks and publication inventory are recorded in
`docs/evidence/repository_assets.json`. Earlier broad audio-development test
counts are not presented as the RAG branch's current suite. The connector tests
verify delegation and unchanged score/threshold fields; optional normal-training
WAV checks exercise fan/pump audio-to-retrieval integration. No held-out test
recordings are required for these checks.

Checks without recordings or local embedding/OCR assets report unavailable
integration prerequisites as skips. Hosted Python 3.11/Linux CI is configured;
it has not yet been verified. The prepared Windows environment differs from
the original audio requirements, so integration success does not reproduce the
original final-test environment.

## Remaining evaluation

LLM reports and the technician interface are not implemented. Report factuality,
unsupported assertions, usability and time to an approved report are therefore
unmeasured. Do not treat retrieved guidance, software tests or saved audio metrics
as completed end-to-end maintenance validation.

## Retrieval metric scoreboard

Run from the repository root after preparing the local embedding runtime:

```sh
python -m machineear.rag.benchmark_retrieval
python -m machineear.rag.benchmark_retrieval --cases my_cases.json --output-dir results/rag/benchmark-held-out
```

The command writes `metrics.json` (per-query results and reproducibility metadata)
and `scoreboard.csv` (one row per retrieval method). It does not overwrite the
original development reports. The default is the same 17 development questions,
not a new held-out benchmark. No new measured performance is claimed by this code.

The three methods are semantic ranking, BM25 ranking, and hybrid RRF ranking.
All use the same family/language filters, 50-candidate lists, page deduplication,
original-PDF checks and production semantic cutoff (default 0.82). **The BM25
comparison is semantic-gated BM25, not pure lexical retrieval.** It still uses
query embeddings. RRF is a fusion algorithm, not an evaluation metric. Existing
application calls retain hybrid retrieval by default.

Metrics use unique `(source_relative_path, pdf_page_number)` physical pages:

- Hit@1/3/5: fraction of answerable questions with a labelled reference in top k.
- MRR@1/3/5: mean reciprocal first relevant rank within k, with misses set to zero.
- Precision@k: relevant pages / k; unfilled slots count as nonrelevant.
- Recall@k: retrieved relevant pages / all labelled relevant pages.
- nDCG@k: graded gain `2**grade - 1`, logarithmic discount, normalized by ideal order.
- Correct abstention: empty retrieval / unsupported questions.
- False abstention: empty retrieval / answerable questions (a wrong nonempty list
  is a reference miss, not an abstention).
- Median and nearest-rank p95 latency in ms: one excluded warmup, rotated method
  order, encoding and citation verification included; model/index construction
  excluded. Small development sets give only rough latency estimates.

Existing reference pages are incomplete judgments. Therefore the default reports
**reference** Hit/MRR and leaves precision, recall and nDCG null (blank in CSV).
A valid alternative page can still count as a reference miss. Full relevance
metrics require complete labels for every answerable case in the evaluated set;
summary metrics remain null when complete and incomplete judgments are mixed.
No unsupported question contributes to the relevance metric averages.

Custom cases are a nonempty JSON list with this schema (add unsupported cases
with `answerable: false` and `relevance: []`):

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
      {"source_relative_path": "Fan_Docs/463687CentFans_iom.pdf", "pdf_page_number": 11, "grade": 1}
    ]
  }
]
```

Grades: 0 irrelevant, 1 partly useful, 2 directly useful. Set
`judgments_complete: true` only after exhaustively judging relevant pages in the
eligible corpus for that question; do not relabel a reference miss merely to
improve the score. Author a separate held-out set before further cutoff tuning.
Generation faithfulness/correctness remain outside this retrieval-only benchmark.
