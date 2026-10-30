"""Local technician review records; no prediction or LLM generation."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from machineear.paths import ROOT

HISTORY_DIR = ROOT / "results" / "analysis" / "history"


def new_record(result, audio_bytes, filename):
    return {"id": uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(),
            "filename": Path(filename).name,
            "audio_sha256": hashlib.sha256(audio_bytes).hexdigest(), "analysis": result}


def draft_report(record):
    """Factual template for manual editing; passages remain verbatim."""
    result = record["analysis"]
    audio = result["audio"]
    state = "Anomalie sonore détectée" if audio["is_anomaly"] else "Aucune anomalie sonore détectée"
    lines = ["# Compte rendu MachineEar", "", "Trame factuelle à compléter par le technicien (sans génération LLM).",
             f"Appareil : {audio['machine_type']} / {audio['machine_id']}",
             f"Résultat : {state}",
             f"Score : {audio['anomaly_score']:.6f} ; seuil figé : {audio['threshold']:.6f}",
             "", "## Observations fournies", result["technician_context"]["notes"] or "Non renseignées.",
             "", "## Contexte équipement", result["technician_context"]["equipment"] or "Non renseigné.",
             "", "## Passages documentaires à vérifier"]
    for passage in result["retrieval"].get("results", []):
        lines.extend(["", str(passage["citation"]), passage["text"]])
    if not result["retrieval"].get("results"):
        lines.append("Aucun passage disponible. Vérifier le statut de la recherche.")
    lines.extend(["", "## Conclusion et actions proposées par le technicien", "À compléter.", "",
                  "Le score ne diagnostique pas une panne. L'absence d'alerte ne garantit pas le bon fonctionnement.",
                  "L'applicabilité des manuels à l'équipement doit être vérifiée."])
    return "\n\n".join(lines)


def save_review(record, report, reviewer, approved=False, applicability=False, *, directory=HISTORY_DIR):
    if not report.strip() or not reviewer.strip():
        raise ValueError("Renseigne le compte rendu et le nom du technicien.")
    if approved and not applicability:
        raise ValueError("Vérifie l'applicabilité des sources avant de valider.")
    saved = {**record, "review": {"report": report, "reviewer": reviewer.strip(),
             "approved": bool(approved), "applicability_checked": bool(applicability),
             "saved_at": datetime.now(timezone.utc).isoformat()}}
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # Each save is a new immutable revision; no user text becomes a path.
    target = directory / f"{uuid4().hex}.json"
    with target.open("x", encoding="utf-8") as handle:
        json.dump(saved, handle, ensure_ascii=False, indent=2, allow_nan=False)
    return saved


def load_history(directory=HISTORY_DIR):
    records, errors = [], []
    for path in Path(directory).glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(record, dict)
                    or not all(key in record for key in ("id", "created_at", "analysis", "review"))
                    or not isinstance(record["analysis"], dict)
                    or not isinstance(record["review"], dict)
                    or not all(key in record["review"] for key in
                               ("saved_at", "report", "reviewer", "approved"))
                    or not isinstance(record["review"]["saved_at"], str)):
                raise ValueError("Format incomplet")
            records.append(record)
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{path.name} : {exc}")
    return sorted(records, key=lambda r: r["review"]["saved_at"], reverse=True), errors
