"""Call Ballystone's original CLI and adapt its JSON for document retrieval."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from machineear.paths import ROOT, LOGMEL_MODEL_DIR, MACHINE_IDS, MACHINE_TYPES, resolve_audio_path

MODEL_DIR = LOGMEL_MODEL_DIR
PREDICTOR = ROOT / "scripts" / "predict_audio.py"
EVALUATION_CONFIG = ROOT / "results" / "final_test" / "evaluation_config.json"


def predict_audio(wav_source, machine_type="fan", machine_id="id_00", *, model_dir=MODEL_DIR):
    """Run the team's predictor; never implement extraction, scoring or training."""
    if machine_type not in MACHINE_TYPES or machine_id not in MACHINE_IDS:
        raise ValueError("Select fan/pump and machine ID id_00, id_02, id_04 or id_06")
    if Path(model_dir).resolve() != MODEL_DIR.resolve():
        raise ValueError("The bridge uses Ballystone's original results/logmel_knn models")
    model = MODEL_DIR / f"{machine_type}_{machine_id}.joblib"
    manifest = json.loads(EVALUATION_CONFIG.read_text(encoding="utf-8"))
    expected = manifest["models"][f"{machine_type}/{machine_id}"]["sha256"]
    with model.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
            raise ValueError("The original frozen model checksum changed")
    if not PREDICTOR.is_file():
        raise FileNotFoundError("Restore the team's original scripts/predict_audio.py")
    with tempfile.TemporaryDirectory(prefix="machineear-") as directory:
        temporary = Path(directory)
        if isinstance(wav_source, (bytes, bytearray)):
            if not wav_source:
                raise ValueError("Uploaded WAV is empty")
            audio_path = temporary / "upload.wav"
            audio_path.write_bytes(wav_source)
        elif isinstance(wav_source, (str, Path)):
            audio_path = Path(wav_source).expanduser()
            if not audio_path.is_file():
                audio_path = resolve_audio_path(wav_source)
        else:
            raise TypeError("Expected a WAV path or uploaded WAV bytes")
        output = temporary / "prediction.json"
        # Native runtime setup is confined to the child process. The original
        # script has top-level execution, so it is never imported into the app.
        runner = ("from machineear.runtime import prepare_native_runtime; prepare_native_runtime(); "
                  "import runpy,sys; script=sys.argv[1]; sys.argv=sys.argv[1:]; "
                  "runpy.run_path(script,run_name='__main__')")
        command = [sys.executable, "-B", "-c", runner, str(PREDICTOR),
                   "--audio", str(audio_path.resolve()), "--machine", machine_type,
                   "--id", machine_id, "--output", str(output)]
        process = subprocess.run(command, cwd=ROOT,
                                 env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                                 capture_output=True, text=True, encoding="utf-8", timeout=120)
        if process.returncode:
            raise ValueError("Ballystone's audio predictor failed: " +
                             (process.stderr.strip() or process.stdout.strip()))
        result = json.loads(output.read_text(encoding="utf-8"))
    if result.get("model") != "logmel_knn5_mean" or result.get("machine_type") != machine_type or result.get("machine_id") != machine_id:
        raise ValueError("The original predictor returned an unexpected model or machine")
    result.pop("audio", None)  # Uploaded temporary filenames do not survive a call.
    result.update(is_anomaly=result["anomaly_flag"], duration_sec=result["duration_seconds"],
                  aggregation="mean", prediction=int(result["anomaly_flag"]),
                  message="Measured unusual-sound result; no mechanical fault is confirmed.")
    return result
