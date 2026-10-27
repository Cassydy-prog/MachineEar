from pathlib import Path
import hashlib
import json

import joblib
import numpy as np
import pandas as pd
from tqdm import tqdm
from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data/processed/logmel_windows_v1"
MODELS = ROOT / "results/logmel_knn"
OUT = ROOT / "results/final_test"
OUT.mkdir(parents=True, exist_ok=True)

manifest = pd.read_csv(SOURCE / "manifest.csv")

if manifest["file_path"].duplicated().any():
    raise ValueError("Des audios apparaissent plusieurs fois")

if manifest.groupby("recording_group")["split"].nunique().max() != 1:
    raise ValueError("Un enregistrement traverse plusieurs ensembles")

test = manifest[manifest["split"] == "test"].copy()

if test.empty:
    raise ValueError("Aucune donnée de test")

# Vérifier que tous les audios de test attendus sont présents.
expected = pd.read_csv(
    ROOT / "results/baseline/data_splits.csv"
)
expected = expected[expected["split"] == "test"]

if set(test["file_path"]) != set(expected["file_path"]):
    raise ValueError("Le manifeste ne contient pas exactement le test attendu")

config = json.loads(
    (SOURCE / "config.json").read_text(encoding="utf-8")
)

# Identifier précisément les modèles utilisés pour cette évaluation.
model_files = {}
for machine, machine_id in test[
    ["machine_type", "machine_id"]
].drop_duplicates().itertuples(index=False, name=None):
    path = MODELS / f"{machine}_{machine_id}.joblib"
    model_files[f"{machine}/{machine_id}"] = {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }

(OUT / "evaluation_config.json").write_text(
    json.dumps({
        "method": "logmel_knn5_mean",
        "aggregation": "mean",
        "threshold_source": "normal_validation_95th_percentile",
        "extraction_config": config,
        "models": model_files,
    }, indent=2),
    encoding="utf-8",
)

rows = []

for (machine, machine_id), part in test.groupby(
    ["machine_type", "machine_id"]
):
    print(f"\nTest : {machine}/{machine_id}", flush=True)

    bundle = joblib.load(
        MODELS / f"{machine}_{machine_id}.joblib"
    )

    saved_config = json.loads(bundle["extraction_config"])
    if saved_config != config:
        raise ValueError("Configuration audio différente du modèle")

    # Réutiliser le seuil de validation, sans recalcul.
    threshold = float(bundle["thresholds"]["mean"])

    for record in tqdm(
        part.to_dict("records"), desc="Analyse", unit="audio"
    ):
        with np.load(
            ROOT / record["feature_path"],
            allow_pickle=False,
        ) as saved:
            x = saved["features"]

        if (
            x.ndim != 2 or x.shape[1] != 128
            or len(x) == 0 or not np.isfinite(x).all()
        ):
            raise ValueError(
                f"Caractéristiques invalides : {record['file_path']}"
            )

        x = bundle["scaler"].transform(x)
        distances, _ = bundle["model"].kneighbors(x)

        # Même calcul que pendant la validation :
        # moyenne des 5 distances, puis moyenne des fenêtres.
        score = float(distances.mean(axis=1).mean())
        prediction = int(score > threshold)

        rows.append({
            **{
                key: record[key]
                for key in (
                    "file_path", "machine_type", "machine_id",
                    "snr_db", "recording_group", "label"
                )
            },
            "anomaly_score": score,
            "threshold": threshold,
            "prediction": prediction,
        })

predictions = pd.DataFrame(rows)

predictions["error_type"] = np.select(
    [
        (predictions["label"] == 0)
        & (predictions["prediction"] == 1),
        (predictions["label"] == 1)
        & (predictions["prediction"] == 0),
    ],
    ["false_alert", "missed_anomaly"],
    default="correct",
)

predictions.to_csv(OUT / "test_predictions.csv", index=False)
predictions[
    predictions["error_type"] != "correct"
].to_csv(OUT / "test_errors.csv", index=False)


def metrics(part):
    y = part["label"]
    pred = part["prediction"]
    tn, fp, fn, tp = confusion_matrix(
        y, pred, labels=[0, 1]
    ).ravel()

    return {
        "n_test": len(part),
        "precision": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred, zero_division=0),
        "false_alarm_rate": fp / (fp + tn) if fp + tn else np.nan,
        "normal_correct": int(tn),
        "false_alerts": int(fp),
        "missed_anomalies": int(fn),
        "detected_anomalies": int(tp),
    }


for columns, filename in [
    (["machine_type"], "summary.csv"),
    (["machine_type", "snr_db"], "per_snr.csv"),
    (["machine_type", "machine_id"], "per_machine.csv"),
    (
        ["machine_type", "machine_id", "snr_db"],
        "per_machine_snr.csv",
    ),
]:
    results = []

    group_key = columns[0] if len(columns) == 1 else columns
    for keys, part in predictions.groupby(group_key):
        if len(columns) == 1:
            keys = (keys,)

        row = dict(zip(columns, keys))
        row.update(metrics(part))

        # Les scores bruts de modèles différents ne sont pas
        # directement comparables : AUC calculée par appareil.
        if "machine_id" in columns and part["label"].nunique() == 2:
            row["roc_auc"] = roc_auc_score(
                part["label"], part["anomaly_score"]
            )

        results.append(row)

    table = pd.DataFrame(results)
    table.to_csv(OUT / filename, index=False)

    if filename in ("summary.csv", "per_snr.csv"):
        print(f"\nTEST — {filename}")
        display_columns = columns + [
            "n_test", "precision", "recall",
            "f1", "false_alarm_rate",
        ]
        print(
            table[display_columns].round(3).to_string(index=False)
        )

print(f"\nRésultats enregistrés : {OUT}")
print("Aucun réentraînement ni ajustement de seuil effectué.")
