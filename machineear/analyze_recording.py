"""Connect a single WAV prediction to local, page-cited document retrieval."""

import argparse
import json
from pathlib import Path
import re
import sqlite3
from time import perf_counter

from machineear.paths import LOGMEL_MODEL_DIR as MODEL_DIR, MACHINE_IDS, MACHINE_TYPES
from machineear.audio_bridge import predict_audio
from machineear.rag.retrieve_documents import INDEX_DIR, LocalRetriever


def build_retrieval_query(machine_type, is_anomaly, *, technician_notes="", equipment_context="", language="en"):
    """Use the flag for general search intent, never to infer a fault category."""
    if machine_type not in MACHINE_TYPES or type(is_anomaly) is not bool:
        raise ValueError("Select fan/pump and a Boolean anomaly flag")
    for name, value, limit in (("technician_notes", technician_notes, 1000),
                               ("equipment_context", equipment_context, 400)):
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f"{name} must be text of at most {limit} characters; it will not be silently truncated")
    if not isinstance(language, str) or not re.fullmatch(r"auto|all|[a-z]{2,3}(?:-[a-z]{2})?", language):
        raise ValueError("Use auto, all, or a language code such as en/fr")
    notes, context = technician_notes.strip(), equipment_context.strip()
    query_language = language
    if language in ("auto", "all"):
        from machineear.rag.chunk_documents import detect_language

        detected, _ = detect_language(" ".join((notes, context)))
        query_language = "en" if detected == "und" else detected
    if query_language == "fr":
        family = "ventilateur industriel" if machine_type == "fan" else "pompe industrielle"
        purpose = ("Quels contrôles d'inspection sont documentés après un signal sonore inhabituel ?"
                   if is_anomaly else "Quels contrôles de routine et de maintenance sont documentés ?")
        parts = [f"Équipement : {family}.", purpose]
        if context:
            parts.append(f"Contexte fourni par le technicien : {context}")
        if notes:
            parts.append(f"Observations ou question du technicien : {notes}")
    else:
        family = "industrial fan" if machine_type == "fan" else "industrial pump"
        purpose = ("Which inspection checks are documented after unusual sound is flagged?"
                   if is_anomaly else "Which routine inspection and maintenance checks are documented?")
        parts = [f"Equipment: {family}.", purpose]
        if context:
            parts.append(f"Technician-supplied equipment context: {context}")
        if notes:
            parts.append(f"Technician observations or question: {notes}")
    return {"query": "\n".join(parts), "language": "all" if language == "all" else query_language,
            "intent": "unusual_sound_inspection" if is_anomaly else "routine_inspection",
            "basis": ["machine_family", "audio_anomaly_flag"]
                     + (["technician_notes"] if notes else []) + (["equipment_context"] if context else []),
            "specific_fault_inferred": False,
            "context_limitations": "Technician-supplied text is unverified. The dataset ID and raw score are not document query terms."}


def _retrieve(service, plan, machine_type, top_k):
    response = service.search(plan["query"], machine_type, language=plan["language"], top_k=top_k)
    if response.get("machine_type") != machine_type:
        raise ValueError("Retrieval returned a different machine family")
    if response.get("status") not in ("passages_for_review", "no_supported_passages"):
        raise ValueError("Retrieval returned an unsupported status")
    results = response.get("results")
    if not isinstance(results, list) or len(results) > top_k:
        raise ValueError("Retrieval returned an invalid passage list")
    if bool(results) != (response["status"] == "passages_for_review"):
        raise ValueError("Retrieval status disagrees with its passage list")
    for passage in results:
        if (passage.get("citation_verified") is not True
                or passage.get("machine_scope") not in (machine_type, "both")
                or passage.get("needs_review")
                or not all(passage.get(key) for key in ("text", "citation", "source_relative_path", "pdf_page_number"))):
            raise ValueError("Retrieval returned an unverified or ineligible passage")
    return response


def analyze_recording(wav_source, machine_type="fan", machine_id="id_00", *, technician_notes="",
                      equipment_context="", language="en", top_k=5, model_dir=MODEL_DIR,
                      index_dir=INDEX_DIR, retriever=None):
    """Return measured audio results, unverified context and cited passages.

    Invalid audio/model inputs raise the existing prediction errors. Retrieval
    failures preserve the measured audio result with an explicit audio_only
    status and no passages. A supplied retriever is reused and left open.
    """
    started = perf_counter()
    if machine_type not in MACHINE_TYPES or machine_id not in MACHINE_IDS:
        raise ValueError("Select fan/pump and machine ID id_00, id_02, id_04 or id_06")
    if type(top_k) is not int or not 1 <= top_k <= 20:
        raise ValueError("top_k must be an integer between 1 and 20")
    # Validate context before processing audio or initializing the embedding worker.
    build_retrieval_query(machine_type, False, technician_notes=technician_notes,
                          equipment_context=equipment_context, language=language)
    audio = predict_audio(wav_source, machine_type, machine_id, model_dir=model_dir)
    audio_finished = perf_counter()
    plan = build_retrieval_query(machine_type, audio["is_anomaly"], technician_notes=technician_notes,
                                 equipment_context=equipment_context, language=language)
    try:
        if retriever is None:
            with LocalRetriever(index_dir) as service:
                retrieved = _retrieve(service, plan, machine_type, top_k)
        else:
            retrieved = _retrieve(retriever, plan, machine_type, top_k)
    except (OSError, ValueError, RuntimeError, ImportError, sqlite3.Error) as exc:
        retrieved = {"query": plan["query"], "machine_type": machine_type,
                     "language_filter": None if plan["language"] == "all" else plan["language"],
                     "status": "unavailable", "results": [],
                     "error": {"type": type(exc).__name__, "message": str(exc)},
                     "action": "Check local PDF, extraction, index and embedding assets using docs/setup.md; rebuild stale artifacts before retrying."}
    finished = perf_counter()
    return {
        "schema_version": 1,
        "status": "audio_only" if retrieved["status"] == "unavailable" else "analysis_complete",
        "audio": audio,
        "technician_context": {"notes": technician_notes.strip(), "equipment": equipment_context.strip(),
                               "verified": False},
        "query_plan": plan,
        "retrieval": retrieved,
        "interpretation": {"specific_fault_diagnosed": False, "equipment_applicability_verified": False,
                           "human_review_required": True,
                           "message": "The score flags unusual sound, not a mechanical fault. A below-threshold result does not verify machine health. Retrieved manuals are generic guidance; technician observations and equipment applicability remain unverified."},
        "timings_sec": {"audio": audio_finished - started, "retrieval": finished - audio_finished,
                        "total": finished - started},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wav", required=True)
    parser.add_argument("--machine-type", choices=MACHINE_TYPES, default="fan")
    parser.add_argument("--machine-id", choices=MACHINE_IDS, required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--equipment-context", default="")
    parser.add_argument("--language", default="en")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    parser.add_argument("--index-dir", type=Path, default=INDEX_DIR)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = analyze_recording(args.wav, args.machine_type, args.machine_id,
                                   technician_notes=args.notes, equipment_context=args.equipment_context,
                                   language=args.language, top_k=args.top_k,
                                   model_dir=args.model_dir, index_dir=args.index_dir)
        serialized = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(serialized)
    return 2 if result["status"] == "audio_only" else 0


if __name__ == "__main__":
    raise SystemExit(main())
