# S6–S7 · MachineEar Langfuse tracing

Five live traces were captured on 25 November 2026. The table records the
latest successful fan run and the first live run of each other request.
The review below records answer-quality limitations found in the outputs.

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
| 1 · Fan audio | `3f81e7d0499b2d9039fcfae0c5638036` | 2 | 1 | 2,331 | 6.101 s |
| 2 · Fan lubrication | `368a89eba31f723ed4e119cd7c546166` | 2 | 1 | 4,324 | 13.665 s |
| 3 · Pump investigation | `892251d1242e82a63ae61fff48d8a47c` | 3 | 2 | 6,732 | 18.166 s |
| 4 · Conflicting manuals | `da3b0eb9b79c2e59ad76b83b3ba092b4` | 3 | 2 | 7,642 | 22.952 s |
| 5 · Approved revision | `8b0339fbae5c29669cee8dda82b063a2` | 2 | 1 | 2,236 | 2.182 s |

Times cover the graph request span and exclude human approval before execution.
The sample revision in case 5 was approved by the user and saved locally.
Cases 2 and 4 returned cited passages. In case 4 the model reversed increased
lubrication frequency into a longer interval. Two instruction-adjusted reruns
asked for equipment context without performing the comparison, so the complete
case and correction remain unverified. The case 3 answer hit its completion
limit and ended mid-sentence. Technician review remains required.

## Trace-driven fix

The first fan request, trace `09ee218bbe68ac93b3354c5b8e0eb945`, made
three model calls and two tool calls, including an unrequested manual search,
and used 5,616 tokens in 17.188 seconds. The agent instructions now request
audio analysis alone when the user asks only for an audio result. On the same
input, the table's fan trace made two model calls and one audio tool call,
used 2,331 tokens and completed in 6.101 seconds. This is one observed run,
not a guarantee of future model behavior.

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
