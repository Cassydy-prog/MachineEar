# Local retrieval development findings

Indexed 3,353 exact passages from 828 physical PDF pages across 12 PDFs.

14/17 development checks passed. Every returned passage matched text re-extracted directly from its original PDF page; all source hashes match extraction.

Raised from 0.75 after two unrelated development questions returned irrelevant passages; these examples are not independent validation.

## Reference pages missed in the first five results

- **fan_noise**: What should be checked when a centrifugal fan has excessive noise or vibration? Reference: Fan_Docs/463687CentFans_iom.pdf, physical PDF pages [15]. Returned: [Fan_Docs/463687CentFans_iom.pdf, PDF p. 10]; [Fan_Docs/Inline-Centrifugal-Mixed-Flow-Fans-IM-895.pdf, PDF p. 17]; [Fan_Docs/Centrifugal-Fans-IM-995.pdf, PDF p. 17]; [Fan_Docs/Centrifugal-Fans-IM-995.pdf, PDF p. 29]; [Fan_Docs/Troubleshooting-Vibration-Problems-ES-202-1.pdf, PDF p. 1]
- **fan_vibration_measurements**: What measurements and information are needed to troubleshoot fan vibration? Reference: Fan_Docs/Troubleshooting-Vibration-Problems-ES-202-1.pdf, physical PDF pages [1]. Returned: [Fan_Docs/463687CentFans_iom.pdf, PDF p. 10]; [Fan_Docs/Centrifugal-Fans-IM-995.pdf, PDF p. 17]; [Fan_Docs/Inline-Centrifugal-Mixed-Flow-Fans-IM-895.pdf, PDF p. 17]; [Fan_Docs/Centrifugal-Fans-IM-995.pdf, PDF p. 29]; [Fan_Docs/463687CentFans_iom.pdf, PDF p. 15]
- **pump_six_months**: What alignment checks are required every six months for the A-C 2000 pump? Reference: Pump_Docs/p2002569b-1.pdf, physical PDF pages [32]. Returned: [Pump_Docs/p2002569b-1.pdf, PDF p. 1]; [Pump_Docs/p2002569b-1.pdf, PDF p. 17]; [Pump_Docs/p2002569b-1.pdf, PDF p. 11]; [Pump_Docs/p2002569b-1.pdf, PDF p. 3]; [Pump_Docs/p2002569b-1.pdf, PDF p. 10]

These references were declared before inspecting search results. Some returned pages may be valid alternatives; the reference list has not been changed to make the checks pass.

## What to improve next

1. Review the three reference misses and rank troubleshooting instructions ahead of cover pages, contents and generic model-name matches. Add separately authored fan/pump questions with relevance labels before further tuning.
2. Proofread all three OCR pages against the page images before enabling them. Review tables, drawings and column order when they affect an instruction.
3. Match manuals to actual equipment. Family filters do not establish manufacturer/model applicability.
4. Connect retrieval to optional report generation only with explicit uncertainty, verifiable citations, an insufficient-evidence outcome and human approval of maintenance advice.

The 0.82 cosine cutoff is a development heuristic, not a probability or a guarantee of safe abstention. English/French retrieval is smoke-tested; the other corpus languages are retained but not evaluated. No LLM report is generated yet. No acoustic model, split or held-out test evaluation was changed.
