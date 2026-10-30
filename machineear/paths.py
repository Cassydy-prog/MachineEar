"""Workspace paths and translation of the CSV's original recording keys."""

from pathlib import Path, PurePosixPath
import os
import re

ROOT = Path(__file__).resolve().parent.parent
RESOURCE_ROOT = Path(os.environ.get("MACHINEEAR_RESOURCE_ROOT", ROOT)).expanduser().resolve()
LOGMEL_MODEL_DIR = ROOT / "results" / "logmel_knn"
MACHINE_IDS = ("id_00", "id_02", "id_04", "id_06")
MACHINE_TYPES = ("fan", "pump")
SNR_LEVELS = (-6, 0, 6)


def source_folder(machine_type, snr_db):
    if machine_type not in MACHINE_TYPES or snr_db not in SNR_LEVELS:
        raise ValueError("Expected fan/pump and SNR -6, 0 or 6 dB")
    prefix = "FAN" if machine_type == "fan" else "Pump"
    return RESOURCE_ROOT / "data" / "audio" / machine_type.title() / f"{prefix}{snr_db}"


def resolve_audio_path(file_path):
    """Resolve a dataset-relative key without rewriting either input CSV."""
    key = PurePosixPath(str(file_path).replace("\\", "/"))
    if key.is_absolute() or ".." in key.parts or ":" in str(key):
        raise ValueError("Expected a safe dataset-relative audio path")
    parts = key.parts
    if len(parts) == 5 and parts[0] == "data":
        match = re.fullmatch(r"(-6|0|6)_dB_(fan|pump)", parts[1])
        if not match or parts[2] not in MACHINE_IDS or parts[3] not in ("normal", "abnormal"):
            raise ValueError(f"Unrecognized recording key: {file_path}")
        path = source_folder(match[2], int(match[1])).joinpath(*parts[2:])
    elif len(parts) == 6 and parts[0] == "RawData":
        # Historical local paths remain accepted after moving the audio folder.
        path = RESOURCE_ROOT.joinpath("data", "audio", *parts[1:])
    elif len(parts) == 7 and parts[:2] == ("data", "audio"):
        path = RESOURCE_ROOT.joinpath(*parts)
    else:
        raise ValueError(f"Unrecognized recording key: {file_path}")
    if path.suffix.lower() != ".wav":
        raise ValueError("Expected a WAV recording")
    if not path.is_file():
        raise FileNotFoundError(f"Recording is missing: {path}")
    return path
