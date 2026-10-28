"""Development retrieval checks against declared pages and the original PDFs."""

import html
import json
import os.path
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from machineear.rag.extract_pdf_text import PDF_ROOT, extract_blocks, file_hash, normalize_text
from machineear.rag.local_embeddings import LocalTokenizer
from machineear.paths import ROOT
from machineear.rag.retrieve_documents import LocalRetriever, verify_passage
from machineear.runtime import prepare_native_runtime

OUTPUT_DIR = ROOT / "results" / "rag" / "evaluation"

# Reference pages selected from the extracted source documents before inspecting
# these searches. Multiple manuals may give valid equivalent guidance; a miss
# needs review rather than automatically declaring every result irrelevant.
CASES = [
    ("fan_grease", "fan", "en", "What NLGI grease grade is specified for fan bearings?",
     "Fan_Docs/463687CentFans_iom.pdf", [11]),
    ("fan_belts", "fan", "en", "What happens if the fan drive belts are too tight?",
     "Fan_Docs/463687CentFans_iom.pdf", [12]),
    ("fan_noise", "fan", "en", "What should be checked when a centrifugal fan has excessive noise or vibration?",
     "Fan_Docs/463687CentFans_iom.pdf", [15]),
    ("fan_vibration_measurements", "fan", "en", "What measurements and information are needed to troubleshoot fan vibration?",
     "Fan_Docs/Troubleshooting-Vibration-Problems-ES-202-1.pdf", [1]),
    ("fan_motor", "fan", "en", "Why should dust and dirt be removed from a fan motor to prevent overheating?",
     "Fan_Docs/Centrifugal-Fans-IM-995.pdf", [16]),
    ("fan_french_grease", "fan", "fr", "Peut-on mélanger des graisses de bases différentes pour les roulements du ventilateur ?",
     "Fan_Docs/Fans-with-CE-Mark-French-IM-2-06.pdf", [10]),
    ("fan_french_vibration", "fan", "fr", "Quelles sont les causes possibles de vibrations excessives du ventilateur ?",
     "Fan_Docs/Fans-with-CE-Mark-French-IM-2-06.pdf", [13]),
    ("pump_cavitation", "pump", "en", "How does vapor pressure cause cavitation in a centrifugal pump?",
     "Pump_Docs/pump.pdf", [11, 12, 18]),
    ("pump_priming", "pump", "en", "How must an A-C 2000 pump be primed before starting?",
     "Pump_Docs/p2002569b-1.pdf", [23]),
    ("pump_alignment", "pump", "en", "How should pump and motor alignment be checked during installation?",
     "Pump_Docs/p2002569b-1.pdf", [17, 18, 19]),
    ("pump_six_months", "pump", "en", "What alignment checks are required every six months for the A-C 2000 pump?",
     "Pump_Docs/p2002569b-1.pdf", [32]),
    ("pump_overgreasing", "pump", "en", "Why can excessive grease make pump bearings overheat?",
     "Pump_Docs/p2002569b-1.pdf", [29]),
    ("pump_1710_grease", "pump", "en", "What grease grade and lubrication interval are specified for Series 1710 pump bearings?",
     "Pump_Docs/1710_iom_02_2023.pdf", [26]),
    ("pump_1710_dry", "pump", "en", "Can a Series 1710 pump operate dry or without being primed?",
     "Pump_Docs/1710_iom_02_2023.pdf", [23]),
    ("pump_efficiency", "pump", "en", "Why should a pump operate near its best efficiency point?",
     "Pump_Docs/pump.pdf", [18, 41]),
    ("out_of_scope_food", "fan", "en", "How do I bake a chocolate cake with buttercream frosting?", None, []),
    ("out_of_scope_geography", "pump", "en", "What is the capital city of France?", None, []),
]


def evaluate(output_dir=OUTPUT_DIR):
    prepare_native_runtime()
    import numpy as np
    import pymupdf

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    documents, native_pages = {}, {}
    cases = []
    try:
        with LocalRetriever() as retriever:
            tokenizer = LocalTokenizer()
            max_tokens = 0
            for chunk in retriever.chunks:
                verify_passage(chunk, retriever.pages[chunk["page_id"]])
                count = tokenizer.count(chunk["text"])
                if count != chunk["token_count"] or count > 480:
                    raise ValueError("Indexed passage violates the declared token budget")
                max_tokens = max(max_tokens, count)
            # Check all source files, including the sources with excluded pages.
            sources = {page["source_relative_path"]: page["source_sha256"] for page in retriever.pages.values()}
            for path, digest in sources.items():
                if file_hash(PDF_ROOT / path) != digest:
                    raise ValueError(f"PDF changed since extraction: {path}")
            if not np.allclose(np.linalg.norm(retriever.vectors, axis=1), 1, atol=1e-5):
                raise ValueError("Index embeddings are not normalized")
            for case_id, family, language, query, source, pages in CASES:
                response = retriever.search(query, family, language=language)
                for result in response["results"]:
                    key = (result["source_relative_path"], result["pdf_page_number"])
                    if key not in native_pages:
                        path, number = key
                        if path not in documents:
                            documents[path] = pymupdf.open(PDF_ROOT / path)
                        blocks = extract_blocks(documents[path][number - 1], pymupdf)
                        native_pages[key] = normalize_text("\n\n".join(block["text"] for block in blocks))
                    original = native_pages[key]
                    if original[result["char_start"]:result["char_end"]] != result["text"]:
                        raise ValueError(f"Citation failed direct PDF re-extraction: {key}")
                    result["original_pdf_text_verified"] = True
                rank = next((r["rank"] for r in response["results"]
                             if r["source_relative_path"] == source and r["pdf_page_number"] in pages), None)
                passed = rank is not None if source else not response["results"]
                cases.append({"case_id": case_id, "reference_source": source, "reference_pages": pages,
                              "reference_hit_rank": rank, "check_passed": passed, **response})
                print(f"{case_id}: {'PASS' if passed else 'REVIEW'}; reference rank={rank}; returned={len(response['results'])}", flush=True)
            summary = {
                "purpose": "Development smoke checks, not an independent retrieval benchmark or diagnosis assessment",
                "query_count": len(cases), "reference_checks_passed": sum(c["check_passed"] for c in cases),
                "reference_checks_for_review": sum(not c["check_passed"] for c in cases),
                "returned_passages": sum(len(c["results"]) for c in cases),
                "all_returned_citations_match_original_pdf_text": True,
                "indexed_passages_verified": len(retriever.chunks),
                "indexed_pages": len({c["page_id"] for c in retriever.chunks}),
                "max_passage_tokens_including_prefix": max_tokens,
                "language_counts": dict(Counter(c["language"] for c in retriever.chunks)),
                "machine_scope_counts": dict(Counter(c["machine_scope"] for c in retriever.chunks)),
                "original_pdf_hashes_verified": len(sources), "unreviewed_ocr_included": False,
                "source_applicability": "Generic guidance; equipment match unverified",
                "minimum_semantic_similarity": 0.82,
                "cutoff_development_note": "Raised from 0.75 after two unrelated development questions returned irrelevant passages; these examples are not independent validation.",
                "limitations": ["Reference-page checks can miss valid equivalent guidance from other manuals.",
                                "Similarity scores are not confidence probabilities; the cutoff does not guarantee relevance or safe abstention.",
                                "Tables, drawings and multi-column page reading order still need human review.",
                                "No maintenance diagnosis or LLM report is generated by retrieval."],
                "index_manifest": retriever.manifest,
            }
    finally:
        for document in documents.values():
            document.close()
    (output_dir / "results.json").write_text(json.dumps({"summary": summary, "cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(output_dir, summary, cases)
    write_findings(output_dir, summary, cases)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def write_report(output_dir, summary, cases):
    escape = html.escape
    sections = []
    for case in cases:
        passages = []
        for result in case["results"]:
            relative = Path(os.path.relpath(PDF_ROOT / result["source_relative_path"], output_dir)).as_posix()
            link = quote(relative) + f"#page={result['pdf_page_number']}"
            passages.append(f'<details><summary>{result["rank"]}. <a href="{link}">{escape(result["citation"])}</a>'
                            f' · similarity {result["semantic_similarity"]:.3f} · original PDF text verified</summary>'
                            f'<pre>{escape(result["text"])}</pre></details>')
        reference = f'{case["reference_source"]}, pages {case["reference_pages"]}' if case["reference_source"] else "No supported passages expected"
        sections.append(f'<section><h2>{escape(case["query"])}</h2><p>{case["machine_type"]} · {case["language_filter"]}'
                        f' · {"PASS" if case["check_passed"] else "REVIEW"} · reference rank: {case["reference_hit_rank"]}</p>'
                        f'<p>Declared reference: {escape(reference)}</p>{"".join(passages) or "<p>No supported passages returned.</p>"}</section>')
    report = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>MachineEar local retrieval checks</title>'
              '<style>body{max-width:1100px;margin:40px auto;padding:0 20px;font:16px/1.6 system-ui;background:#f6f8fa;color:#17252d}'
              'section{background:white;padding:20px;margin:20px 0;border:1px solid #ccd5dc;border-radius:8px}'
              'h2{font-size:20px}details{margin:12px 0}pre{white-space:pre-wrap;font:14px/1.6 system-ui}a{color:#126280}</style>'
              '<h1>MachineEar local retrieval checks</h1><p>Fan and pump manuals · local semantic search + BM25 · physical PDF page citations</p>'
              f'<p>{summary["indexed_passages_verified"]} exact passages from {summary["indexed_pages"]} pages. '
              f'{summary["reference_checks_passed"]}/{summary["query_count"]} development reference checks passed. '
              f'All {summary["returned_passages"]} returned passages match re-extracted original PDF text.</p>'
              '<p><strong>Generic guidance: equipment applicability is unverified. These checks are development examples, '
              'not independent accuracy evidence. The similarity cutoff cannot guarantee relevance. '
              'Unreviewed OCR pages are excluded. Human review of maintenance instructions remains necessary.</strong></p>'
              f'<p>{escape(summary["cutoff_development_note"])}</p>'
              + ''.join(sections) + '</html>')
    (output_dir / "report.html").write_text(report, encoding="utf-8")


def write_findings(output_dir, summary, cases):
    lines = ["# Local retrieval development findings", "",
             f"Indexed {summary['indexed_passages_verified']:,} exact passages from {summary['indexed_pages']} physical PDF pages across 12 PDFs.", "",
             f"{summary['reference_checks_passed']}/{summary['query_count']} development checks passed. Every returned passage matched text re-extracted directly from its original PDF page; all source hashes match extraction.", "",
             summary['cutoff_development_note'], "",
             "## Reference pages missed in the first five results", ""]
    for case in cases:
        if not case['check_passed']:
            lines.append(f"- **{case['case_id']}**: {case['query']} Reference: {case['reference_source']}, physical PDF pages {case['reference_pages']}. Returned: "
                         + "; ".join(r['citation'] for r in case['results']))
    lines.extend(["", "These references were declared before inspecting search results. Some returned pages may be valid alternatives; the reference list has not been changed to make the checks pass.", "",
                  "## What to improve next", "",
                  "1. Review the three reference misses and rank troubleshooting instructions ahead of cover pages, contents and generic model-name matches. Add separately authored fan/pump questions with relevance labels before further tuning.",
                  "2. Proofread all three OCR pages against the page images before enabling them. Review tables, drawings and column order when they affect an instruction.",
                  "3. Match manuals to actual equipment. Family filters do not establish manufacturer/model applicability.",
                  "4. Connect retrieval to optional report generation only with explicit uncertainty, verifiable citations, an insufficient-evidence outcome and human approval of maintenance advice.", "",
                  "The 0.82 cosine cutoff is a development heuristic, not a probability or a guarantee of safe abstention. English/French retrieval is smoke-tested; the other corpus languages are retained but not evaluated. No LLM report is generated yet. No acoustic model, split or held-out test evaluation was changed.", ""])
    (output_dir / "findings.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    evaluate()
