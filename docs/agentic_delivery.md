# MachineEar agentic extension — S3–S6

## Scope and source of truth

Use `schemas/machineear_tools.json`, generated from `machineear/agent_tools/schemas.py`.
The older root `tool_schemas.json` is the original classroom proposal, not the
executor's contract. The executable tools are `analyze_audio`, `search_manuals`
and `save_report_revision`. Do not call the proposed ticket tool: no ticket
backend exists. Report revision uses the existing human-review history instead.
No scripts, detector bundles, thresholds, source PDFs or prepared retrieval assets
are changed. This extension does not replace the web application's current chat.

## Install — Git Bash, existing repository virtual environment

```bash
source .venv/Scripts/activate
python -m pip install -r requirements/agentic.txt
python -B -m unittest discover -s tests -v
```

Keep existing audio/RAG dependencies installed (`requirements/agent.txt`).
MCP is intentionally restricted to SDK major version 1, matching these imports.

## S3: real MCP transport

```bash
python -m agentic.mcp_client
```

This launches `server.py` over stdio, initializes MCP and lists the sole exposed
tool, `search_manuals`. It does not initialize embeddings or download weights.

After the existing local embedding runtime and prepared corpus are available:

```bash
python -m agentic.mcp_client --query "fan bearing lubrication" --machine-type fan
```

This calls the real validated executor and existing local retriever. Missing
assets are errors, not a successful result. It requires no Groq key. For setup,
follow `docs/s2_tools.md`. The server exposes no write, approval or upload endpoint.
Use `notebooks/MachineEar_S3_MCP.ipynb` in a local kernel at repository root.
A remote Colab kernel cannot access a stdio process on your Windows computer.

## S4: control strategy and memory (five lines)

1. One ReAct agent chooses between validated tools through a LangGraph loop.
2. Tool results and errors return as observations; physical maintenance is never executed.
3. Request history lives only in RAM for that request and is discarded afterwards.
4. A reviewed report persists only after trusted host approval; existing revisions are preserved.
5. Limits: eight model rounds, eight tool calls, 10,000 reported tokens and 120 seconds before starting another action.

The time limit is cooperative: an in-flight predictor can run until its existing
120-second subprocess timeout; an in-flight provider call has a 45-second timeout.
Token usage can exceed the budget in the last model response because input and
output usage is reported afterwards. Further tool execution is blocked. This is
not a prepaid hard token cap or a process-wide wall-clock kill switch.

## S5: opt-in live LangGraph agent

The request, schemas and returned passages/results are sent to Groq only when
`--allow-groq` is selected. No live external call was made during package checks.
Enter the key without printing it:

```bash
read -rsp 'Groq API key: ' GROQ_API_KEY
export GROQ_API_KEY
printf '\n'
python -m agentic.run --allow-groq 'Find fan bearing lubrication instructions with sources.'
```

To analyze a normal-training recording chosen by you:

```bash
python -m agentic.run --allow-groq --wav '/c/path/to/normal_training.wav' --machine fan --id id_00 'Analyze the registered recording, then find relevant documented checks. Do not diagnose a specific fault.'
```

The model receives a registered ID, never a tool argument accepting arbitrary paths.
For a real approved revision, supply an existing review record and a text file:

```bash
python -m agentic.run --allow-groq --report '/c/path/to/record.json' --review-text '/c/path/to/reviewed.txt' 'Save the exact host-approved report revision.'
```

The host displays the exact text, requests reviewer identity and applicability
confirmation, then issues a single-use approval. Cancellation saves nothing.
The CLI is for one trusted local user, not an authenticated multi-user service.
Clear the key when finished: `unset GROQ_API_KEY`.

### Five requests to demonstrate on actual assets

- Analyze a registered fan recording (requires normal-training WAV).
- Retrieve fan bearing lubrication passages.
- Analyze unusual pump sound and retrieve relevant documented checks (requires WAV).
- Compare manual instructions; ask for missing equipment context if applicability is unknown.
- Save an exact technician-reviewed report after host confirmation (requires record/text).

These align with `docs/agent_sheet.md`, which is the current repository's five-case
sheet. The older root S1 proposal included tickets/history comparison that are not
implemented. Do not claim all five live runs have passed: recordings, cached
embedding runtime, human review and provider credentials are required locally.

## S6: one agent and two-minute kickoff draft

One agent is sufficient: audio prediction and document retrieval are tools with
well-defined contracts, not independent conversational agents. This keeps traces,
budgets and approval ownership in one session. Multi-agent operation adds no
measured benefit at this stage.

MachineEar helps technicians investigate unusual sounds from fans and pumps.
Our existing detector produces an anomaly score and a frozen threshold. Our RAG
retrieves maintenance manual passages with physical PDF page citations. The new
agent decides when to analyze a recording, search documentation or ask for missing
context. A sound anomaly is not a mechanical diagnosis and a normal score is not
an operating clearance. We preserve the existing predictor and retrieve only
verified passages. Report revisions require explicit human review of the exact
text. We use one bounded LangGraph loop, plus a read-only MCP endpoint for manual
search. Our automated tests cover contracts, approval gates, orchestration and
MCP discovery; live evidence must separately demonstrate the five requests using
real project assets. We will report unsupported passages and missing resources
as limitations rather than invent results.

## Remaining evidence / later sessions

- S3: capture a real successful manual query in the session notebook, not just discovery.
- S5: run the five requests locally and retain reviewed outputs; fixture tests are not model evaluation.
- S7: build/import a real n8n workflow and verify a human-approved write. Not supplied as completed.
- S8: AGENTS.md already exists. Ask OpenCode for one test/README change and review its diff. This package was not produced by OpenCode and does not count as that exercise.
- S9: `docs/agentic_evaluation.json` contains 20 planned cases in three categories; populate actual outcomes. No performance/security scores are claimed.

References: https://py.sdk.modelcontextprotocol.io/v1/ and
https://reference.langchain.com/python/langgraph/graph/state/StateGraph
