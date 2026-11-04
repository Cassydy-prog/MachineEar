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
