from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "results" / "per_machine"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(
    ROOT / "data/processed/machineear_features_all_snr.csv"
)
splits = pd.read_csv(
    ROOT / "results/baseline/data_splits.csv"
)

# Réutiliser exactement le découpage du premier entraînement.
df = df.merge(
    splits[["file_path", "split"]],
    on="file_path",
    how="left",
    validate="one_to_one",
)

if df["split"].isna().any():
    raise ValueError("Découpage absent pour certains audios")

if df.groupby("recording_group")["split"].nunique().max() != 1:
    raise ValueError("Un même enregistrement traverse plusieurs ensembles")

metadata = {
    "file_path", "machine_type", "machine_id", "label",
    "duration_sec", "snr_db", "recording_group", "split",
}
features = [c for c in df.columns if c not in metadata]

if len(features) != 52:
    raise ValueError("Le fichier doit contenir 52 caractéristiques")

if not np.isfinite(df[features]).all().all():
    raise ValueError("Caractéristiques manquantes ou invalides")


def evaluate(part, machine, machine_id, snr):
    y = part["label"]
    prediction = part["prediction"]
    tn, fp, fn, tp = confusion_matrix(
        y, prediction, labels=[0, 1]
    ).ravel()

    return {
        "machine_type": machine,
        "machine_id": machine_id,
        "snr_db": snr,
        "n_validation": len(part),
        "precision": precision_score(y, prediction, zero_division=0),
        "recall": recall_score(y, prediction, zero_division=0),
        "f1": f1_score(y, prediction, zero_division=0),
        "roc_auc": (
            roc_auc_score(y, part["anomaly_score"])
            if y.nunique() == 2 else np.nan
        ),
        "false_alarm_rate": fp / (fp + tn) if fp + tn else np.nan,
        "missed_anomalies": int(fn),
        "detected_anomalies": int(tp),
    }


predictions = []
metrics = []

for (machine, machine_id), subset in df.groupby(
    ["machine_type", "machine_id"]
):
    train = subset[subset["split"] == "train"]
    validation = subset[subset["split"] == "validation"].copy()

    if train.empty or validation.empty:
        raise ValueError(f"Données insuffisantes : {machine}/{machine_id}")

    assert (train["label"] == 0).all()

    print(f"Entraînement : {machine}/{machine_id}", flush=True)

    model = IsolationForest(
        n_estimators=300,
        max_samples="auto",
        contamination="auto",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train[features])

    validation["anomaly_score"] = -model.score_samples(
        validation[features]
    )

    normal_scores = validation.loc[
        validation["label"] == 0, "anomaly_score"
    ]
    threshold = float(np.quantile(normal_scores, 0.95))

    validation["prediction"] = (
        validation["anomaly_score"] > threshold
    ).astype(int)
    validation["threshold"] = threshold

    joblib.dump(
        {
            "model": model,
            "features": features,
            "threshold": threshold,
            "machine_type": machine,
            "machine_id": machine_id,
        },
        OUTPUT / f"{machine}_{machine_id}.joblib",
    )

    predictions.append(validation)

    metrics.append(evaluate(
        validation, machine, machine_id, "tous"
    ))

    for snr, part in validation.groupby("snr_db"):
        metrics.append(evaluate(part, machine, machine_id, snr))

combined = pd.concat(predictions, ignore_index=True)

# Résultats regroupés par type de machine.
summary = []
for machine, part in combined.groupby("machine_type"):
    summary.append(evaluate(part, machine, "ensemble", "tous"))

    for snr, snr_part in part.groupby("snr_db"):
        summary.append(evaluate(
            snr_part, machine, "ensemble", snr
        ))

pd.DataFrame(metrics).to_csv(
    OUTPUT / "validation_metrics_per_machine.csv", index=False
)
summary = pd.DataFrame(summary)
summary.to_csv(
    OUTPUT / "validation_metrics_summary.csv", index=False
)
combined[
    ["file_path", "machine_type", "machine_id", "snr_db",
     "label", "anomaly_score", "threshold", "prediction"]
].to_csv(OUTPUT / "validation_predictions.csv", index=False)

print("\nRésultats de VALIDATION :")
print(summary[
    ["machine_type", "snr_db", "precision", "recall",
     "f1", "roc_auc", "false_alarm_rate"]
].round(3).to_string(index=False))

print(f"\nRésultats enregistrés : {OUTPUT}")
print("Les données de test n'ont pas été évaluées.")
