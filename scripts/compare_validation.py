from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import (
    confusion_matrix, precision_score,
    recall_score, f1_score, roc_auc_score,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "comparison"
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(
    ROOT / "data/processed/machineear_features_all_snr.csv"
)
splits = pd.read_csv(ROOT / "results/baseline/data_splits.csv")

df = df.merge(
    splits[["file_path", "split"]],
    on="file_path", how="left", validate="one_to_one",
)

if df["split"].isna().any():
    raise ValueError("Découpage manquant")

if df.groupby("recording_group")["split"].nunique().max() != 1:
    raise ValueError("Fuite entre les ensembles")

# Écarter le test avant toute comparaison.
df = df[df["split"].isin(["train", "validation"])].copy()

metadata = {
    "file_path", "machine_type", "machine_id", "label",
    "duration_sec", "snr_db", "recording_group", "split",
}
features = [c for c in df if c not in metadata]

if len(features) != 52:
    raise ValueError("52 caractéristiques attendues")

if not np.isfinite(df[features]).all().all():
    raise ValueError("Caractéristiques numériques invalides")

predictions = []


def add_predictions(validation, scores, method):
    result = validation[
        ["file_path", "machine_type", "machine_id", "snr_db",
         "recording_group", "label"]
    ].copy()

    result["method"] = method
    result["anomaly_score"] = scores

    # Même règle de calibration pour toutes les méthodes.
    threshold = float(np.quantile(
        result.loc[result["label"] == 0, "anomaly_score"], 0.95
    ))

    result["threshold"] = threshold
    result["prediction"] = (
        result["anomaly_score"] > threshold
    ).astype(int)

    result["error_type"] = np.select(
        [
            (result["label"] == 0) & (result["prediction"] == 1),
            (result["label"] == 1) & (result["prediction"] == 0),
        ],
        ["false_alert", "missed_anomaly"],
        default="correct",
    )

    predictions.append(result)
    return threshold


# 1. Modèles communs à chaque type de machine.
for machine in ("fan", "pump"):
    validation = df[
        (df["machine_type"] == machine)
        & (df["split"] == "validation")
    ]

    bundle = joblib.load(
        ROOT / f"results/baseline/{machine}_isolation_forest.joblib"
    )
    scores = -bundle["model"].score_samples(
        validation[bundle["features"]]
    )
    add_predictions(validation, scores, "IF_type")


# 2 et 3. Modèles propres à chaque appareil.
for (machine, machine_id), subset in df.groupby(
    ["machine_type", "machine_id"]
):
    print(f"Comparaison : {machine}/{machine_id}", flush=True)

    train = subset[subset["split"] == "train"]
    validation = subset[subset["split"] == "validation"]

    if train.empty or validation.empty:
        raise ValueError("Ensemble vide")

    assert (train["label"] == 0).all()

    # Isolation Forest déjà entraîné.
    bundle = joblib.load(
        ROOT / f"results/per_machine/{machine}_{machine_id}.joblib"
    )
    scores = -bundle["model"].score_samples(
        validation[bundle["features"]]
    )
    add_predictions(validation, scores, "IF_appareil")

    # kNN : normalisation apprise uniquement sur le train.
    scaler = StandardScaler()
    x_train = scaler.fit_transform(train[features])
    x_validation = scaler.transform(validation[features])

    # Petit nombre de variantes, comparées sur la validation.
    for k in (5, 20):
        knn = NearestNeighbors(n_neighbors=k, n_jobs=-1)
        knn.fit(x_train)

        distances, _ = knn.kneighbors(x_validation)
        scores = distances.mean(axis=1)

        method = f"kNN_{k}_appareil"
        threshold = add_predictions(validation, scores, method)

        joblib.dump(
            {
                "model": knn,
                "scaler": scaler,
                "features": features,
                "threshold": threshold,
                "machine_type": machine,
                "machine_id": machine_id,
                "score_definition": "mean_neighbor_distance",
            },
            OUT / f"{machine}_{machine_id}_knn_{k}.joblib",
        )

predictions = pd.concat(predictions, ignore_index=True)


def summarize(part):
    y = part["label"]
    pred = part["prediction"]
    tn, fp, fn, tp = confusion_matrix(
        y, pred, labels=[0, 1]
    ).ravel()

    return {
        "n": len(part),
        "precision": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred, zero_division=0),
        "false_alarm_rate": fp / (fp + tn) if fp + tn else np.nan,
        "false_alerts": int(fp),
        "missed_anomalies": int(fn),
        "detected_anomalies": int(tp),
    }


# Résumés aux trois niveaux : type, appareil, appareil et bruit.
for columns, filename in [
    (["method", "machine_type"], "summary.csv"),
    (
        ["method", "machine_type", "machine_id"],
        "per_machine.csv",
    ),
    (
        ["method", "machine_type", "machine_id", "snr_db"],
        "per_machine_snr.csv",
    ),
]:
    rows = []

    for keys, part in predictions.groupby(columns):
        row = dict(zip(columns, keys))
        row.update(summarize(part))

        # AUC comparable directement dans un même appareil.
        # Éviter de mélanger les scores de modèles distincts.
        if "machine_id" in columns and part["label"].nunique() == 2:
            row["roc_auc"] = roc_auc_score(
                part["label"], part["anomaly_score"]
            )

        rows.append(row)

    table = pd.DataFrame(rows)
    table.to_csv(OUT / filename, index=False)

    if filename == "summary.csv":
        print("\nCOMPARAISON SUR LA VALIDATION")
        print(table[
            ["method", "machine_type", "precision", "recall",
             "f1", "false_alarm_rate"]
        ].round(3).to_string(index=False))

predictions.to_csv(OUT / "validation_predictions.csv", index=False)
predictions[
    predictions["error_type"] != "correct"
].to_csv(OUT / "validation_errors.csv", index=False)

print(f"\nRésultats enregistrés : {OUT}")
print("Aucune prédiction sur le test n'a été calculée.")
