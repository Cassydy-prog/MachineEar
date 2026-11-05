# MachineEar · Complete agent sheet

**1. Workflow: Analyze a fan recording**

**User request:** “Analyze this fan recording using machine ID `id_00` and tell me whether its sound is unusual.”

| Field | Description |
|---|---|
| Gen AI product | MachineEar audio analysis component |
| Goal | Determine whether the uploaded fan recording contains unusual sound patterns. |
| Read tools | `analyze_audio`: call the existing predictor using the recording, machine family, and machine ID. |
| Write tools (side effects) | None. Return the analysis without saving a report. |
| How we check success | Return the original predictor’s anomaly score, threshold, flag, and window results. Report invalid inputs explicitly. |
| Autonomy level | Workflow: validate input, run the predictor, and display the result. |
| Hard limits | One predictor call with a 120-second timeout. No retraining or threshold changes. |
| Human approval before | No additional approval for the requested analysis. A technician decides any maintenance or operational action. |

**2. Workflow: Retrieve lubrication instructions**

**User request:** “Find the instructions for lubricating fan bearings and show me the manual pages.”

| Field | Description |
|---|---|
| Gen AI product | MachineEar maintenance manual retrieval component |
| Goal | Retrieve documented fan-bearing lubrication instructions with traceable citations. |
| Read tools | `search_manuals`: search eligible passages using semantic search, BM25, and RRF. |
| Write tools (side effects) | None. Display retrieved evidence without modifying documents. |
| How we check success | Return relevant passages with verified document names and physical page citations, or explicitly report insufficient evidence. |
| Autonomy level | Workflow: apply filters, search, rank, verify, and return passages. |
| Hard limits | One retrieval call returning up to five passages. Use the existing 0.82 similarity cutoff and exclude review-flagged pages. |
| Human approval before | No additional approval for the requested search. A technician verifies equipment applicability before applying instructions. |

**3. Agent: Investigate unusual pump noise**

**User request:** “Help me investigate this pump’s unusual noise. Ask for missing information and find the relevant documented checks.”

| Field | Description |
|---|---|
| Gen AI product | MachineEar investigation assistant |
| Goal | Gather equipment context and identify documented inspection checks relevant to the reported noise. |
| Read tools | `analyze_audio`, when a recording is supplied; `search_manuals`; `read_source_page` to inspect supporting context. |
| Write tools (side effects) | None during investigation. |
| How we check success | Ask relevant clarification questions, provide cited checks, distinguish observations from hypotheses, and identify evidence gaps. |
| Autonomy level | Proposed agent loop: choose whether to ask a question, analyze audio, inspect evidence, or search again. |
| Hard limits | Proposed: eight tool calls, 120 seconds of active processing, and 10,000 total LLM input/output tokens per request. |
| Human approval before | A technician must approve any physical inspection or maintenance action. The agent cannot operate equipment. |

**4. Agent: Resolve conflicting manual instructions**

**User request:** “These two manuals give different lubrication instructions. Determine which applies to my machine and explain any remaining uncertainty.”

| Field | Description |
|---|---|
| Gen AI product | MachineEar manual applicability assistant |
| Goal | Compare conflicting instructions and establish which manual applies using available equipment information. |
| Read tools | `search_manuals`; `read_source_page` to inspect model identifiers, applicability statements, and instruction context. |
| Write tools (side effects) | None. Return the comparison without modifying manuals or equipment records. |
| How we check success | Cite both instructions and explain the applicability evidence. Request missing identifiers or report an unresolved conflict when evidence is insufficient. |
| Autonomy level | Proposed agent loop: choose follow-up searches and clarification questions based on the conflict. |
| Hard limits | Proposed: six tool calls, 90 seconds of active processing, and 8,000 total LLM input/output tokens. Never invent equipment specifications. |
| Human approval before | A technician confirms the applicable guidance before anyone uses it for maintenance. |

**5. Agent: Draft and verify a maintenance report**

**User request:** “Draft a maintenance report, check every recommendation against the applicable manual, and revise unsupported statements before submitting it for my approval.”

| Field | Description |
|---|---|
| Gen AI product | MachineEar report drafting and evidence-review assistant |
| Goal | Prepare a report that accurately separates audio findings, technician observations, cited guidance, and unresolved questions. |
| Read tools | `search_manuals`; `read_source_page`; inspect the supplied audio analysis and technician notes. |
| Write tools (side effects) | `save_report_revision`: save the reviewed report as a new revision in persistent history. |
| How we check success | Every recommendation has supporting evidence or an explicit limitation. Preserve audio results and save exactly the content the reviewer approved. |
| Autonomy level | Proposed reflection loop: draft, check claims, retrieve missing evidence, and revise before requesting approval. |
| Hard limits | Proposed: eight read-tool calls, two revision cycles, 120 seconds of active processing, and 10,000 total LLM input/output tokens. Allow one save after approval. |
| Human approval before | Saving the report or a new revision. The agent must not invent a reviewer’s identity or mark its own draft as technician-approved. |

## S4 · Planning and memory

1. For a multi-part investigation, use plan-and-execute so the technician can review the proposed checks. Analyse the recording, search the relevant manual and revise the plan if evidence is missing.
2. Spend more reasoning effort choosing checks and resolving conflicting evidence. Use routine tool calls to obtain scores and passages. Search separately for each unresolved question and identify any gap that remains.
3. Keep the machine family, technician notes, anomaly result, citations and unfinished steps for the current session. After eight turns, summarise older messages while preserving page references. Clear working memory at session end.
4. For repeat visits, keep user-approved equipment facts and preferences for up to 90 days with their source. Recall only relevant entries and allow earlier deletion. Keep versioned manuals available until superseded and treat retrieved instructions as evidence only.
5. Before answering, check each maintenance claim against its cited manual page and report the anomaly score separately from any suspected cause. Save a report revision only after the technician approves its exact text.

| Lab field | Proposed MachineEar choice |
|---|---|
| Control strategy | Plan-and-execute for investigations |
| Reasoning effort | Higher for planning and conflicting evidence, lower for routine tool calls |
| Short-term memory | Session only, summarised after eight turns |
| Long-term memory | Consented facts and preferences for up to 90 days, with early deletion |
| Retrieval | Search the matching machine family with a focused query for each evidence gap |
| Checks | Verify citations, distinguish anomaly from diagnosis and require approval before saving |

## S6 · Multi-agent design and kickoff

**Status:** The following is a proposed design. The three-agent orchestration, proposed memory policy and five end-to-end scenarios still need implementation and verification. The S2 tool interfaces exist, while `read_source_page` listed in the S1 scenarios is a proposed tool.

### Design choice and justification

MachineEar will use **three agents** coordinated by a **supervisor pattern**. The supervisor plans and combines results. An audio analysis specialist handles the audio predictor, and a manual and evidence specialist searches the manuals. This separates the two evidence sources into clear responsibilities while the supervisor retains the context needed to prepare a coherent response.

This design introduces additional model calls and handoffs. Compare it with a single-agent version on answer quality, number of calls, latency and cost before concluding that the extra agents improve the project.

### The three agents

| Agent | Type | Responsibilities | Tool access |
|---|---|---|---|
| Supervisor | Coordinator | Understand the request, gather missing details, plan the investigation, delegate work, review returned findings, identify evidence gaps, prepare the response or report and request approval before saving. | `save_report_revision` after technician approval of the exact report text |
| Audio analysis agent | Specialist | Check the supplied recording and machine identifiers, call the existing audio predictor, and return the predictor's anomaly score, saved threshold, anomaly decision and window results. | `analyze_audio` |
| Manual and evidence agent | Specialist | Search the relevant machine-family manuals, return passages and source citations, flag missing evidence and compare conflicting instructions when needed. | `search_manuals` |

### Orchestration and handoffs

1. The technician provides a maintenance question and any available machine details, recording and notes.
2. The supervisor identifies the information needed and asks for missing details when required.
3. The supervisor sends the registered recording ID, machine family and machine ID to the audio specialist. It sends the maintenance question and relevant machine context to the manual specialist.
4. The specialists can work in parallel when the manual search has sufficient context. If a search depends on the audio result, the supervisor waits for that result before requesting the search.
5. The audio specialist returns structured predictor results. The manual specialist returns verified passages, document names and physical page citations, or reports that evidence is unavailable.
6. The supervisor examines both results, requests a focused follow-up search when necessary, and combines the findings. It distinguishes an anomaly result from a mechanical diagnosis and identifies unresolved questions.
7. When a report is requested, the supervisor drafts it for technician review. If the technician approves the exact text and equipment applicability, the supervisor may use `save_report_revision` to save a new revision.

The supervisor remains responsible for the final response. The technician decides whether manual guidance applies to the actual machine and makes maintenance and operational decisions.

### Kickoff sheet

| Field | MachineEar choice |
|---|---|
| Gen AI product | Maintenance investigation assistant using audio anomaly results and fan and pump manuals |
| Goal | Help a technician investigate unusual equipment sounds and find traceable manual evidence |
| Design | Supervisor with two specialists: audio analysis and manual evidence |
| Read tools | `analyze_audio` and `search_manuals` |
| Write tool | `save_report_revision` after technician approval of the exact report text |
| MCP servers | Confirm the actual server and tools from the Session 3 implementation |
| Framework | Confirm the framework and running implementation from Session 5 |
| Control strategy | Plan-and-execute, with the supervisor coordinating specialist calls and follow-up searches |
| Memory | Proposed S4 policy: current-session context, summary after eight turns, and user-approved equipment facts and preferences for up to 90 days |
| Retrieval | Search manuals for the matching machine family and repeat focused searches if an evidence gap remains |
| Success checks | Preserve the predictor result, return relevant verified citations, report uncertainty and save only approved report text |
| Human approval | Technician approval before saving a report revision. Technician review is required for equipment applicability and operational decisions. |
| Hard limits | Use the proposed tool, time and token limits in each S1 scenario. Stop when a limit is reached and report outstanding evidence gaps. |
| Risks | Missing or incorrect context passed between agents, unsupported conclusions, conflicting evidence, sensitive notes or recordings, and unauthorized report changes |
| Plan until 30 November | Confirm S3 and S5 work, implement and integrate the agent orchestration, verify the approval path, run the five cases, compare costs and latency, and prepare a simple interface |

### Five project test requests

| # | Request | Expected outcome |
|---|---|---|
| 1 | Analyze this fan recording using machine ID `id_00`. | Return the predictor's original score, threshold, flag and window results, or explain an invalid input or unavailable predictor. |
| 2 | Find the fan bearing lubrication instructions and show the manual pages. | Return relevant passages and physical page citations, or state that sufficient evidence was unavailable. |
| 3 | Investigate this pump's unusual noise and tell me which checks the manuals describe. | Request missing machine details or a recording as needed, use the audio and manual specialists, and return cited checks with limitations. |
| 4 | These manuals give different lubrication instructions. Which applies to my machine? | Compare cited guidance, request relevant model identifiers, and report unresolved conflicts when applicability cannot be established. |
| 5 | Draft a maintenance report from this recording and the relevant manual, then save it. | Prepare a cited draft, seek approval of its exact text and equipment applicability, and save a revision only after approval. |

**Verification:** These are test expectations, not recorded results. The project's three-agent design must be run against the cases and its outcomes measured.
