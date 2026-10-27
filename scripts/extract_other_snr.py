from pathlib import Path
import json

import librosa
import numpy as np
import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "processed"
OUTPUT.mkdir(parents=True, exist_ok=True)

SOURCES = {
    ("fan", -6): ROOT / "data" / "-6_dB_fan",
    ("pump", -6): ROOT / "data" / "-6_dB_pump",
    ("fan", 6): ROOT / "data" / "6_dB_fan",
    ("pump", 6): ROOT / "data" / "6_dB_pump",
}

SAMPLE_RATE = 16000


def extract_features(path):
    y, sr = librosa.load(path, sr=SAMPLE_RATE, mono=True)

    if y.size == 0 or not np.isfinite(y).all():
        raise ValueError("Audio vide ou contenant des valeurs invalides")

    # Calcul commun pour les caractéristiques spectrales
    magnitude = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    power = magnitude ** 2

    mel = librosa.feature.melspectrogram(
        S=power, sr=sr, n_mels=128
    )
    mfcc = librosa.feature.mfcc(
        S=librosa.power_to_db(mel), n_mfcc=20
    )

    features = {}

    for i, values in enumerate(mfcc, start=1):
        features[f"mfcc_{i:02d}_mean"] = float(values.mean())
        features[f"mfcc_{i:02d}_std"] = float(values.std())

    statistics = {
        "rms": librosa.feature.rms(S=magnitude),
        "zcr": librosa.feature.zero_crossing_rate(y),
        "centroid": librosa.feature.spectral_centroid(S=magnitude, sr=sr),
        "bandwidth": librosa.feature.spectral_bandwidth(S=magnitude, sr=sr),
        "rolloff": librosa.feature.spectral_rolloff(S=magnitude, sr=sr),
        "flatness": librosa.feature.spectral_flatness(S=magnitude),
    }

    for name, values in statistics.items():
        features[f"{name}_mean"] = float(values.mean())
        features[f"{name}_std"] = float(values.std())

    if not np.isfinite(list(features.values())).all():
        raise ValueError("Caractéristiques numériques invalides")

    return len(y) / sr, features


jobs = []

for (machine_type, snr_db), folder in SOURCES.items():
    if not folder.is_dir():
        raise FileNotFoundError(f"Dossier introuvable : {folder}")

    files = sorted(
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() == ".wav"
    )

    if not files:
        raise ValueError(f"Aucun audio dans : {folder}")

    for path in files:
        parts = path.relative_to(folder).parts
        labels = [part for part in parts if part in ("normal", "abnormal")]
        ids = [part for part in parts if part.startswith("id_")]

        if len(labels) != 1 or len(ids) != 1:
            raise ValueError(f"Label ou identifiant ambigu : {path}")

        jobs.append((machine_type, ids[0], labels[0], path, snr_db))

print(f"{len(jobs)} audios à traiter.", flush=True)

rows, errors = [], []

for machine_type, machine_id, label, path, snr_db in tqdm(
    jobs, desc="Extraction", unit="audio"
):
    try:
        duration, features = extract_features(path)
        rows.append({
            "file_path": path.relative_to(ROOT).as_posix(),
            "machine_type": machine_type,
            "snr_db": snr_db,
            "machine_id": machine_id,
            "label": 0 if label == "normal" else 1,
            "duration_sec": duration,
            **features,
        })
    except Exception as exc:
        errors.append({
            "file_path": path.relative_to(ROOT).as_posix(),
            "error": str(exc),
        })

    # Sauvegarde intermédiaire toutes les 250 tentatives
    if (len(rows) + len(errors)) % 250 == 0:
        pd.DataFrame(rows).to_csv(
            OUTPUT / "features_other_snr_checkpoint.csv", index=False
        )

pd.DataFrame(errors, columns=["file_path", "error"]).to_csv(
    OUTPUT / "extraction_other_snr_errors.csv", index=False
)

if not rows:
    raise RuntimeError("Aucun audio traité. Consulter extraction_errors.csv.")

df = pd.DataFrame(rows)
destination = OUTPUT / "machineear_features_other_snr.csv"
df.to_csv(destination, index=False)

feature_columns = [
    name for name in df.columns
    if name not in (
        "file_path", "machine_type", "machine_id", "label", "duration_sec", "snr_db"
    )
]
(OUTPUT / "feature_columns_other_snr.json").write_text(
    json.dumps(feature_columns, indent=2), encoding="utf-8"
)

print(f"\nExtraction terminée : {len(df)} audios réussis.")
print(f"Erreurs : {len(errors)}")
print(f"Caractéristiques par audio : {len(feature_columns)}")
print(f"CSV : {destination}")
print("\nRépartition : 0 = normal, 1 = anormal")
print(
    df.groupby(["machine_type", "machine_id", "label"])
      .size()
      .unstack(fill_value=0)
      .to_string()
)
