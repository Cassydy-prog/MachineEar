# S6–S7 · MachineEar Langfuse tracing

The five live traces are pending. The tool-budget fix was verified with a
local Langfuse SDK trace, described below.

Install the optional tracing dependencies in the MachineEar environment.

```powershell
python -m pip install -r requirements/tracing.txt
```

Create a Langfuse project and set `LANGFUSE_BASE_URL`, `LANGFUSE_PUBLIC_KEY` and
`LANGFUSE_SECRET_KEY` in the ignored repository `.env`. Configure the separately
authorized model provider before making live model requests. The CLI loads
`.env` when tracing is selected.

Use the exact prompts from the [submission sheet](docs/agent_sheet.md) and pass
`--trace-langfuse --case N` along with the normal CLI arguments for that case.
The CLI prints the trace ID. The request span measures graph execution,
including model and tool calls. Terminal approval happens before graph
execution. Trace metadata is limited to case number, model and known tool
names, token counts, timestamps, call counts and statuses.

| Case | Trace ID | Model calls | Tool calls | Total tokens | Duration |
|---|---|---|---|---|---|
| 1 · Fan audio | Pending | | | | |
| 2 · Fan lubrication | Pending | | | | |
| 3 · Pump investigation | Pending | | | | |
| 4 · Conflicting manuals | Pending | | | | |
| 5 · Approved revision | Pending | | | | |

## Trace-driven fix

Using the Langfuse SDK with an in-memory exporter, I ran the same fixture
twice with a one-call tool budget and a scripted model response. The first
trace ended after a successful search. The graph now allows a final model
response with tool access disabled when the tool budget is spent and the
other budgets still allow a response.

| Local SDK trace | Result | Model calls | Tool calls | Fixture tokens |
|---|---|---|---|---|
| `5441a4ad848a3463c9b9424ce757f048` | Budget exhausted, no final answer | 1 | 1 | 7 |
| `38c05e640ad22a65b046152a2a1dfb76` | Final response used the tool observation | 2 | 1 | 12 |

The fixture verifies span parenting, model and tool counts, and the final
answer behavior. These trace IDs are local and the token counts are scripted.
