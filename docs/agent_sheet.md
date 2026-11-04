| # | Real user request | Decision | Justification |
|---|---|---|---|
| 1 | “Analyze this fan recording using machine ID `id_00` and tell me whether its sound is unusual.” | **Workflow** | The system follows fixed steps to validate the recording, run the detector, and return its anomaly score and flag. |
| 2 | “Find the instructions for lubricating fan bearings and show me the manual pages.” | **Workflow** | The system follows a predefined retrieval pipeline to return relevant passages with citations. |
| 3 | “Help me investigate this pump’s unusual noise. Ask for missing information and find the relevant documented checks.” | **Agent** | The system decides which clarification questions to ask, which searches to perform, and when it has enough evidence. |
| 4 | “These two manuals give different lubrication instructions. Determine which applies to my machine and explain any remaining uncertainty.” | **Agent** | The system investigates equipment details and conflicting sources, deciding whether to retrieve more evidence or request clarification. |
| 5 | “Draft a maintenance report, check that every recommendation has supporting evidence, and revise unsupported statements before submitting it for my approval.” | **Agent** | The system evaluates its draft and decides whether to search again, revise recommendations, or report insufficient evidence. |
