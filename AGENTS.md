# MachineEar RAG contribution instructions

This branch builds on Ballystone's `audio-bally-stone-20261027-223928`, commit
`3eae3ae5da664e4e37ab9397288a049da6ea728e`.

## Scope and ownership

- This contribution is RAG and its connection to existing audio predictions.
  Do not add alternate anomaly detectors, training pipelines, feature extraction
  implementations or detector comparisons. Those belong to Ballystone's work.
- Keep original `scripts/`, notebooks, `requirements-audio.txt`, all trained
  bundles, fixed split and saved audio results byte-for-byte unchanged.
- `machineear/audio_bridge.py` calls the original `scripts/predict_audio.py` in a
  child process, adapting paths/JSON only. Do not reimplement numerical scoring.
- No audio retraining, threshold changes or held-out test inference. Use normal
  training WAVs only for optional connected checks; do not publish recordings.
- Preserve contributor attribution. Do not fabricate authors or rewrite history.

## RAG and interpretation

- Keep RAG under `machineear/rag/` and the connected API in `analyze_recording.py`.
- Preserve original PDF checksums, physical page citations and exact passages.
  Unproofread OCR and review-flagged pages remain excluded from default search.
- An anomaly is not a diagnosed fault. Technician observations and manual
  applicability remain unverified; human review is required.
- LLM reports and the technician review/history interface remain pending.
- Processing, embeddings and queries stay local. External embedding/LLM services
  need explicit authorization; Git publication is not authorization for them.

## Assets and portability

- The user explicitly authorized Git publication of `data/manuals/`, the original
  `data/features/machineear_features_all_snr.csv` and prepared `results/rag/`.
  This supersedes the earlier exclusion of these assets.
- Exclude audio recordings, environments, downloaded embedding weights, secrets,
  new audio models and individual recording analyses. Preserve source originals.
- Keep manifests/links portable and checksum-linked assets byte-stable across
  Git checkouts. Never change feature CSV contents or split assignments.
- `MACHINEEAR_RESOURCE_ROOT` optionally supplies external assets; leave it unset
  to use the cloned corpus. It must never redirect Ballystone's frozen models.

## Workflow

- State intended changes first. Avoid broad rewrites or large installations
  without authorization. Imports must not extract, train, download or initialize
  heavy native dependencies.
- Update the consolidated `docs/code/README.md` when modules/tests change.
- Run `python -B -m unittest discover -s tests -v`; report missing prerequisites
  as skips. Verify unchanged upstream files and the staged diff.
- Commit/push only when requested. The user requested publishing the RAG branch
  and its specified assets; preserve that authorized scope.
