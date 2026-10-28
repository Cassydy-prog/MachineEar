# MachineEar: RAG integration

This branch adds local maintenance-document retrieval to **Ballystone's existing
audio anomaly-detection project**. Ballystone owns the acoustic extraction,
training, model selection and final-test evaluation. His original `scripts/`,
models, split assignments, notebooks and saved results are preserved unchanged.

The contribution here is PDF extraction/OCR, page-bound chunking, local
multilingual embeddings, hybrid retrieval, citation verification and the
`analyze_recording()` connection. `audio_bridge.py` calls Ballystone's original
`scripts/predict_audio.py` and adapts its JSON; it contains no acoustic features,
detector training, scoring implementation or threshold calibration.

## Layout

```text
machineear/
    rag/                   PDF extraction, chunks, embeddings, search and evaluation
    analyze_recording.py   Connect the original audio result to cited retrieval
    audio_bridge.py        Thin adapter calling Ballystone's original predictor
    paths.py, runtime.py   Portable resource paths and native runtime setup
scripts/                   Ballystone's original audio scripts, unchanged
data/manuals/              12 source manuals
data/features/             Original combined feature CSV
results/rag/               Extracted text, chunks, vectors, SQLite index and checks
results/logmel_knn/         Ballystone's inherited frozen audio bundles
results/final_test/         Ballystone's inherited saved evaluation
tests/                     RAG, connector and citation tests
docs/                      Setup, methods, evaluation and code reference
```

Recordings, environments, embedding-model weights, secrets and individual audio
analyses are excluded. Manuals, feature CSV and prepared RAG assets are included
at the user's request so a clone can recover the document pipeline. The CSV is
preserved reference data; RAG does not use its acoustic values or labels as
document evidence. The fixed split already exists at `results/baseline/data_splits.csv`.

## Start on another laptop

Create/activate a Python environment, install Node.js/npm separately, then run:

```sh
python -m pip install -r requirements/rag.txt
python -m machineear.rag.local_embeddings --prepare
python -m machineear.rag.retrieve_documents search --machine-type fan --language en --query "What NLGI grease grade is specified for fan bearings?"
```

Preparation downloads the pinned local query encoder and ONNX runtime; source
PDFs, extracted text and the index are already in Git. It does not rebuild the
index or upload document contents. Leave `MACHINEEAR_RESOURCE_ROOT` unset to use
the checkout's assets. See [setup](docs/setup.md) for platform details.

To connect a new recording to the manuals:

```sh
python -m machineear.analyze_recording --wav recording.wav --machine-type fan --machine-id id_00 --notes "Which inspection checks are documented?"
```

Supply the actual family/ID. The anomaly result indicates unusual sound, not a
confirmed mechanical fault. Manuals remain generic guidance until equipment
applicability is checked by a technician.

## Status

Local retrieval and the audio connector are implemented. Source-cited LLM report
drafting and the technician editing/approval/history interface remain pending.
No audio retraining, threshold change or final-test inference is part of this
contribution. The team's saved final audio metrics remain attributed to its
original work; [evaluation](docs/evaluation.md) keeps them separate from RAG checks.

- [Setup and commands](docs/setup.md)
- [Architecture](docs/architecture.md)
- [Evaluation and limitations](docs/evaluation.md)
- [Code and API reference](docs/code/README.md)

```sh
python -B -m unittest discover -s tests -v
```
