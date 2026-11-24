# MachineEar agent sheet

MachineEar helps technicians investigate unusual fan and pump sounds with the frozen audio predictor and verified manual passages. A technician determines equipment applicability and makes operational decisions.

## S1 · Five demonstration requests

| # | Exact request | Classification and justification | Expected evidence |
|---|---|---|---|
| 1 | Analyze this fan recording using machine ID id_00 and report whether its sound is unusual. | **Workflow.** The registered recording has a known machine ID and requires one predictor call. | Original score, threshold, anomaly flag and window results. |
| 2 | Find the fan bearing lubrication instructions and show me the manual pages. | **Workflow.** One scoped manual search can return passages and physical PDF page citations. | Relevant verified citations or an explicit evidence gap. |
| 3 | Investigate this pump's unusual noise using the registered recording and the pump manuals. What checks do the manuals describe? | **Agent.** The audio and available equipment context determine what to search and which questions remain open. | Predictor result and cited checks, with uncertainty and applicability clearly stated. |
| 4 | Compare the bearing lubrication guidance in IM-1080 and IM-995. Which applies to my fan? Ask for the equipment identifier if you cannot tell. | **Agent.** The evidence determines whether to search again, compare passages or ask for missing identifiers. | Citations to both manuals, a comparison and any unresolved applicability question. |
| 5 | Save the exact report revision I reviewed and approved in the terminal. | **Workflow.** The host binds approval to the exact text before the agent can make a single approved save. | A revision ID after approval, with no write when approval is absent or the text differs. |

## S2 and S3 · Tools and MCP

| Tool | Access | Contract |
|---|---|---|
| `analyze_audio` | Read | Return the frozen predictor's results for a registered recording. |
| `search_manuals` | Read | Return verified manual passages and physical PDF page citations. |
| `save_report_revision` | Write | Save the exact approved text as a new revision using a single-use host approval. |

See the [executable JSON schemas](../schemas/machineear_tools.json) and [Pydantic contracts](../machineear/agent_tools/models.py). [server.py](../server.py) exposes `search_manuals` over MCP stdio. The [executed S3 notebook](../notebooks/MachineEar_S3_MCP.ipynb) shows tool discovery and three verified passages.

## S4 · Strategy and memory

1. A bounded ReAct loop chooses tools or asks for missing context based on prior observations.
2. Model messages, tool results and errors stay in working memory for the current request.
3. Each new request starts with fresh state and receives any required context from the host.
4. A report revision persists in local history only after a technician approves its exact text and applicability.
5. Default budgets are eight model rounds, eight tool calls, 10,000 reported tokens and 120 seconds for starting actions.

## S5 · Framework

[LangGraph](../agentic/graph.py) implements the loop and [the CLI](../agentic/run.py) registers inputs and collects human approval.

## S6 · Agent count

Use one LangGraph agent with three validated tools. Audio prediction and manual retrieval already have defined contracts, so a single agent can use both results in the same request. The host controls report approval and the executor enforces it. Manual passages are evidence, and an audio anomaly is distinct from a diagnosed fault.
