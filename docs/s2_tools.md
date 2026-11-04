# S2: Tool use and structured outputs

MachineEar exposes three agent-facing wrappers around existing functionality.
They do not implement a replacement detector, train models or generate reports
with an LLM. The existing web interface is not rewired by this lab package.

| Tool | Access | Input | Output |
|---|---|---|---|
| `analyze_audio` | read | Registered recording ID, fan/pump family, trained machine ID | Frozen anomaly score, threshold, flag and windows |
| `search_manuals` | read | Question, family, language, top-k (1–5) | Verified passages with PDF page citations, or no supported passages |
| `save_report_revision` | write | Registered report ID, reviewed text, single-use approval ID | Saved revision ID, reviewer, timestamp and status |

## Files and schemas

- `machineear/agent_tools/models.py`: three input and three main output models,
  plus nested audio-window and passage models. Pydantic v2 forbids extra fields,
  rejects type coercion and nonfinite numbers, and validates status consistency.
- `schemas.py`: exports the JSON Schema of each input and output. Read/write
  metadata is separate from the provider's function-call schema.
- `executor.py`: validates before dispatch and validates outputs. Unknown tools,
  invalid inputs, missing assets and backend failures raise explicit exceptions.
- `schemas/machineear_tools.json`: the three generated tool definitions with
  descriptions, parameters, output contracts and access classifications.
- `notebooks/MachineEar_S2_Tools.ipynb`: runnable contract examples and opt-in live
  retrieval/audio calls. Its synthetic examples are labelled and do not claim
  model performance or real maintenance approval.

Regenerate the schema file from the repository root:

```sh
python -m machineear.agent_tools.schemas
```

To supply tool definitions to a provider, use:

```python
from machineear.agent_tools.schemas import tool_schemas
provider_tools = [entry['tool'] for entry in tool_schemas()]
```

The wrapper validates results using Pydantic regardless of provider support for
strict structured generation. This validates structure and local invariants,
not the factual truth of generated prose. A future model loop must return
validation errors to the model and enforce its own execution budgets. This S2
package supplies a dispatcher, not an autonomous loop or a working Groq test.

## Approval boundary

Only the three named tools are available through `execute()`. Host application
code registers uploads and report records using `register_recording()` and
`register_report()`. Model arguments contain IDs, never arbitrary filesystem
paths or output directories. The audio bridge can use temporary files internally;
read/write classification describes persistent application side effects.

A trusted local human-review UI must display the report text and obtain a
reviewer's explicit approval and applicability confirmation before calling
`approve_report()`. This method is not a model tool. Approval binds a snapshot
of the registered record and the validated text to the report ID. Passage text and reviewed report text retain their original whitespace. Approval IDs
are session-local and single-use; changed text, another report, fabricated IDs,
extra `approved` fields and replayed IDs are rejected. The original
`review.save_review()` appends a new history file and preserves old revisions.

The gate assumes trusted host code. It is not identity authentication, does not
verify reviewer credentials or validate mechanical advice, and is not yet wired
into the existing web UI. A server deployment must authenticate reviewers and
isolate sessions. Never expose registration or approval methods through an LLM
or unrestricted code-execution tool.

## Run in VS Code on Windows

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/agent.txt
.\.venv\Scripts\python.exe -m machineear.agent_tools.schemas
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Open `notebooks/MachineEar_S2_Tools.ipynb` and select that `.venv` kernel.
Run the cells in order. Schema inspection, validation, and the temporary-history
save demo need no API key or downloaded embedding weights. The audio/retrieval
fixtures test contract plumbing only; the save demo calls the real history code
inside a temporary directory and uses explicitly simulated approval.

For real retrieval, first prepare the local model and Node runtime:

```powershell
.\.venv\Scripts\python.exe -m machineear.rag.local_embeddings --prepare
```

Then enable the notebook's live retrieval switch. For real audio, set the WAV
path to an original **normal-training** recording and its correct family/ID,
then enable the separate audio switch. No recordings or individual analyses
are published. Never use held-out test audio for these optional checks.
Missing prerequisites must be reported as unavailable; do not label a skipped
live call as a successful demonstration.

## Verification and submission

Run `python -B -m unittest discover -s tests -v`. S2 tests cover known outputs,
invalid arguments, unverified evidence, backend failures, approval binding,
replay rejection, append-only saves and import side effects. Frozen audio files
and existing notebooks are unchanged. A fresh clone without local recordings,
OCR data or embedding runtime skips the existing optional integration checks.

Commit message: `S2: add three MachineEar tool schemas and Pydantic validation`.
A schema or synthetic fixture alone does not prove the tools work on real
recordings or manuals. Retain local live demonstration evidence for submission;
strip private outputs and keys before committing notebooks.
