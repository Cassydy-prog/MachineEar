from pathlib import Path
import argparse
import json

import joblib
import librosa
import numpy as np

ROOT = Path(__file__).resolve().parent.parent

parser = argparse.ArgumentParser(description="Analyse audio MachineEar")
parser.add_argument("--audio", required=True, help="Chemin du fichier WAV")
parser.add_argument("--machine", required=True, choices=["fan", "pump"])
parser.add_argument(
    "--id", required=True,
    choices=["id_00", "id_02", "id_04", "id_06"],
)
parser.add_argument("--output", help="Chemin facultatif du rapport JSON")
args = parser.parse_args()

audio_path = Path(args.audio).expanduser().resolve()
if not audio_path.is_file():
    raise SystemExit(f"Audio introuvable : {audio_path}")

model_path = (
    ROOT / "results/logmel_knn"
    / f"{args.machine}_{args.id}.joblib"
)
if not model_path.is_file():
    raise SystemExit(f"Modèle introuvable : {model_path}")

bundle = joblib.load(model_path)
config = json.loads(bundle["extraction_config"])

sr = config["sample_rate"]
audio, _ = librosa.load(audio_path, sr=sr, mono=True)

window_size = int(config["window_seconds"] * sr)
stride = int(config["stride_seconds"] * sr)

if len(audio) < window_size:
    raise SystemExit("L'audio doit durer au moins 2 secondes.")

if not np.isfinite(audio).all():
    raise SystemExit("Le signal contient des valeurs invalides.")

positions = list(range(0, len(audio) - window_size + 1, stride))
last = len(audio) - window_size
if positions[-1] != last:
    positions.append(last)

features = []

for start in positions:
    segment = audio[start:start + window_size]

    mel = librosa.feature.melspectrogram(
        y=segment,
        sr=sr,
        n_fft=config["n_fft"],
        hop_length=config["hop_length"],
        n_mels=config["n_mels"],
        power=2.0,
        center=False,
    )
    logmel = librosa.power_to_db(mel, ref=1.0)

    features.append(np.concatenate([
        logmel.mean(axis=1),
        logmel.std(axis=1),
    ]))

x = np.asarray(features, dtype=np.float32)

if not np.isfinite(x).all():
    raise SystemExit("Caractéristiques numériques invalides.")

x = bundle["scaler"].transform(x)
distances, _ = bundle["model"].kneighbors(x)
window_scores = distances.mean(axis=1)

score = float(window_scores.mean())
threshold = float(bundle["thresholds"]["mean"])
anomaly = score > threshold

result = {
    "audio": str(audio_path),
    "machine_type": args.machine,
    "machine_id": args.id,
    "model": "logmel_knn5_mean",
    "duration_seconds": len(audio) / sr,
    "n_windows": len(positions),
    "anomaly_score": score,
    "threshold": threshold,
    "anomaly_flag": bool(anomaly),
    "result": (
        "Anomalie signalée"
        if anomaly else "Aucune anomalie signalée"
    ),
    "windows": [
        {
            "start_seconds": start / sr,
            "end_seconds": (start + window_size) / sr,
            "score": float(value),
        }
        for start, value in zip(positions, window_scores)
    ],
}

print(f"\nMachine : {args.machine}/{args.id}")
print(f"Durée : {result['duration_seconds']:.2f} secondes")
print(f"Fenêtres analysées : {len(positions)}")
print(f"Score d'anomalie : {score:.6f}")
print(f"Seuil : {threshold:.6f}")
print(f"Résultat : {result['result']}")
print("Le score n'est pas une probabilité de panne.")

if args.output:
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Rapport JSON enregistré : {output.resolve()}")
