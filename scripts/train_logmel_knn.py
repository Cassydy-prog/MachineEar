from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from tqdm import tqdm
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data/processed/logmel_windows_v1"
OUT = ROOT / "results/logmel_knn"
OUT.mkdir(parents=True, exist_ok=True)

manifest = pd.read_csv(SOURCE / "manifest.csv")

if manifest["file_path"].duplicated().any():
    raise ValueError("Audios présents plusieurs fois")

if manifest.groupby("recording_group")["split"].nunique().max() != 1:
    raise ValueError("Un enregistrement traverse plusieurs ensembles")

# Ne charger que l'entraînement et la validation.
manifest = manifest[
    manifest["split"].isin(["train", "validation"])
].copy()


def load_features(row):
    with np.load(
        ROOT / row["feature_path"], allow_pickle=False
    ) as saved:
        x = saved["features"]

    if (
        x.ndim != 2 or x.shape[1] != 128
        or len(x) == 0 or not np.isfinite(x).all()
    ):
        raise ValueError(f"Données invalides : {row['file_path']}")

    return x


predictions = []

for (machine, machine_id), part in manifest.groupby(
    ["machine_type", "machine_id"]
):
    print(f"\nEntraînement : {machine}/{machine_id}", flush=True)

    train = part[part["split"] == "train"]
    validation = part[part["split"] == "validation"]

    if train.empty or validation.empty:
        raise ValueError("Ensemble vide")

    if not (train["label"] == 0).all():
        raise ValueError("Le train contient des anomalies")

    x_train = np.concatenate([
        load_features(row)
        for row in train.to_dict("records")
    ])

    # Normalisation apprise uniquement sur les fenêtres du train.
    scaler = StandardScaler()
    x_train = scaler.fit_transform(x_train)

    knn = NearestNeighbors(
        n_neighbors=5,
        algorithm="brute",
        n_jobs=-1,
    )
    knn.fit(x_train)

    rows = []

    for row in tqdm(
        validation.to_dict("records"),
        desc=f"Validation {machine}/{machine_id}",
        unit="audio",
    ):
        x = scaler.transform(load_features(row))
        distances, _ = knn.kneighbors(x)
        window_scores = distances.mean(axis=1)

        rows.append({
            **{
                key: row[key]
                for key in (
                    "file_path", "machine_type", "machine_id",
                    "snr_db", "label", "recording_group"
                )
            },
            "mean_score": float(window_scores.mean()),
            "top3_score": float(
                np.sort(window_scores)[-3:].mean()
            ),
        })

    scores = pd.DataFrame(rows)
    thresholds = {}

    for aggregation in ("mean", "top3"):
        result = scores.drop(
            columns=["mean_score", "top3_score"]
        ).copy()

        result["method"] = f"logmel_knn5_{aggregation}"
        result["anomaly_score"] = scores[f"{aggregation}_score"]

        threshold = float(np.quantile(
            result.loc[result["label"] == 0, "anomaly_score"],
            0.95,
        ))
        thresholds[aggregation] = threshold

        result["threshold"] = threshold
        result["prediction"] = (
            result["anomaly_score"] > threshold
        ).astype(int)

        predictions.append(result)

    joblib.dump(
        {
            "model": knn,
            "scaler": scaler,
            "thresholds": thresholds,
            "machine_type": machine,
            "machine_id": machine_id,
            "extraction_config": (
                SOURCE / "config.json"
            ).read_text(encoding="utf-8"),
            "window_score": "mean_distance_to_5_neighbors",
        },
        OUT / f"{machine}_{machine_id}.joblib",
    )

    # Sauvegarde des appareils déjà terminés.
    pd.concat(predictions, ignore_index=True).to_csv(
        OUT / "validation_predictions_checkpoint.csv",
        index=False,
    )

predictions = pd.concat(predictions, ignore_index=True)
predictions.to_csv(
    OUT / "validation_predictions.csv", index=False
)


def metrics(part):
    y = part["label"]
    pred = part["prediction"]

    return {
        "n": len(part),
        "precision": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred, zero_division=0),
        "false_alarm_rate": float(pred[y == 0].mean()),
    }


for columns, filename in [
    (["method", "machine_type"], "summary.csv"),
    (
        ["method", "machine_type", "machine_id", "snr_db"],
        "per_machine_snr.csv",
    ),
]:
    rows = []

    for keys, part in predictions.groupby(columns):
        row = dict(zip(columns, keys))
        row.update(metrics(part))

        if "machine_id" in columns and part["label"].nunique() == 2:
            row["roc_auc"] = roc_auc_score(
                part["label"], part["anomaly_score"]
            )

        rows.append(row)

    table = pd.DataFrame(rows)
    table.to_csv(OUT / filename, index=False)

    if filename == "summary.csv":
        print("\nRÉSULTATS LOG-MEL SUR LA VALIDATION")
        print(table.round(3).to_string(index=False))

        old_path = ROOT / "results/comparison/summary.csv"
        if old_path.exists():
            old = pd.read_csv(old_path)
            old = old[old["method"] == "kNN_5_appareil"]

            comparison = pd.concat(
                [old, table], ignore_index=True
            )
            columns_to_show = [
                "method", "machine_type", "precision",
                "recall", "f1", "false_alarm_rate",
            ]

            comparison[columns_to_show].to_csv(
                OUT / "comparison_with_previous.csv",
                index=False,
            )

            print("\nCOMPARAISON AVEC LE PRÉCÉDENT kNN")
            print(
                comparison[columns_to_show]
                .round(3).to_string(index=False)
            )

print(f"\nRésultats : {OUT}")
print("Le test n'a pas été évalué.")
