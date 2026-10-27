from pathlib import Path
import json

import librosa
import numpy as np
import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/processed/logmel_windows_v1"
OUT.mkdir(parents=True, exist_ok=True)

CONFIG = {
    "sample_rate": 16000,
    "n_fft": 1024,
    "hop_length": 256,
    "n_mels": 64,
    "window_seconds": 2,
    "stride_seconds": 1,
    "representation": "logmel_mean_std_per_window",
}

config_path = OUT / "config.json"
if config_path.exists():
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    if saved != CONFIG:
        raise ValueError("Configuration différente : utiliser un nouveau dossier.")
else:
    config_path.write_text(
        json.dumps(CONFIG, indent=2), encoding="utf-8"
    )

metadata = pd.read_csv(
    ROOT / "data/processed/machineear_features_all_snr.csv"
)
splits = pd.read_csv(ROOT / "results/baseline/data_splits.csv")

metadata = metadata.merge(
    splits[["file_path", "split"]],
    on="file_path",
    how="left",
    validate="one_to_one",
)

if metadata["split"].isna().any():
    raise ValueError("Découpage absent pour certains fichiers")

if metadata.groupby("recording_group")["split"].nunique().max() != 1:
    raise ValueError("Un enregistrement traverse plusieurs ensembles")

sr = CONFIG["sample_rate"]
window_size = int(CONFIG["window_seconds"] * sr)
stride = int(CONFIG["stride_seconds"] * sr)

rows = []
errors = []
reused = 0

for record in tqdm(
    metadata.to_dict("records"), desc="Extraction log-Mel", unit="audio"
):
    try:
        relative = Path(record["file_path"].replace("\\", "/"))
        # Conserver la structure : SNR / appareil / label / fichier.
        target = OUT / relative.relative_to("data").with_suffix(".npz")
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            with np.load(target, allow_pickle=False) as saved:
                x = saved["features"]
                starts = saved["start_seconds"]
            reused += 1
        else:
            audio, _ = librosa.load(
                ROOT / relative, sr=sr, mono=True
            )

            if len(audio) < window_size:
                raise ValueError("Audio inférieur à 2 secondes")

            if not np.isfinite(audio).all():
                raise ValueError("Signal contenant des valeurs invalides")

            positions = list(
                range(0, len(audio) - window_size + 1, stride)
            )

            # Inclure également la fin de l'audio.
            last = len(audio) - window_size
            if positions[-1] != last:
                positions.append(last)

            features = []

            for start in positions:
                segment = audio[start:start + window_size]

                mel = librosa.feature.melspectrogram(
                    y=segment,
                    sr=sr,
                    n_fft=CONFIG["n_fft"],
                    hop_length=CONFIG["hop_length"],
                    n_mels=CONFIG["n_mels"],
                    power=2.0,
                    center=False,
                )
                logmel = librosa.power_to_db(mel, ref=1.0)

                # 64 moyennes + 64 écarts-types = 128 valeurs.
                features.append(np.concatenate([
                    logmel.mean(axis=1),
                    logmel.std(axis=1),
                ]))

            x = np.asarray(features, dtype=np.float32)
            starts = np.asarray(positions, dtype=np.float32) / sr

            # Écriture temporaire pour permettre une reprise propre.
            temporary = target.with_suffix(".tmp")
            with temporary.open("wb") as handle:
                np.savez_compressed(
                    handle, features=x, start_seconds=starts
                )
            temporary.replace(target)

        if (
            x.ndim != 2 or x.shape[1] != 128
            or len(x) == 0 or len(starts) != len(x)
            or not np.isfinite(x).all()
        ):
            raise ValueError("Caractéristiques invalides")

        rows.append({
            **{
                key: record[key]
                for key in (
                    "file_path", "machine_type", "machine_id",
                    "label", "snr_db", "recording_group", "split"
                )
            },
            "feature_path": target.relative_to(ROOT).as_posix(),
            "n_windows": len(x),
        })

    except Exception as exc:
        errors.append({
            "file_path": record["file_path"],
            "error": str(exc),
        })

pd.DataFrame(rows).to_csv(OUT / "manifest.csv", index=False)
pd.DataFrame(
    errors, columns=["file_path", "error"]
).to_csv(OUT / "errors.csv", index=False)

print(f"\nAudios préparés : {len(rows)} / {len(metadata)}")
print(f"Audios déjà préparés et réutilisés : {reused}")
print(f"Erreurs : {len(errors)}")
print(f"Nombre total de fenêtres : {sum(r['n_windows'] for r in rows)}")
print(f"Résultats : {OUT}")

if errors:
    print("Consulter errors.csv avant de poursuivre.")
