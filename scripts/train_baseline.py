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
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "results" / "baseline"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(
    ROOT / "data" / "processed" / "machineear_features_all_snr.csv"
)

metadata = {
    "file_path", "machine_type", "machine_id",
    "label", "duration_sec", "snr_db", "recording_group",
}
features = [column for column in df.columns if column not in metadata]

if len(features) != 52:
    raise ValueError(f"52 caractéristiques attendues, trouvé : {len(features)}")

if df.isna().any().any() or not np.isfinite(df[features]).all().all():
    raise ValueError("Valeurs manquantes ou numériques invalides")

groups = df.groupby("recording_group")
for column in ("machine_type", "machine_id", "label"):
    if (groups[column].nunique() != 1).any():
        raise ValueError(f"Informations contradictoires : {column}")

# Découpage par enregistrement, avant toute utilisation des caractéristiques.
# Les trois versions bruitées d'un son restent toujours ensemble.
records = df.drop_duplicates("recording_group").copy()
assignments = {}

for (machine, machine_id, label), subset in records.groupby(
    ["machine_type", "machine_id", "label"]
):
    ids = sorted(subset["recording_group"].tolist())

    if label == 0:
        train_ids, remaining = train_test_split(
            ids, test_size=0.40, random_state=42
        )
        validation_ids, test_ids = train_test_split(
            remaining, test_size=0.50, random_state=42
        )
    else:
        # Aucun son anormal utilisé pour apprendre le fonctionnement normal.
        train_ids = []
        validation_ids, test_ids = train_test_split(
            ids, test_size=0.50, random_state=42
        )

    for split, values in (
        ("train", train_ids),
        ("validation", validation_ids),
        ("test", test_ids),
    ):
        assignments.update({value: split for value in values})

df["split"] = df["recording_group"].map(assignments)

if df["split"].isna().any():
    raise ValueError("Certains enregistrements n'ont pas été affectés")

assert df.groupby("recording_group")["split"].nunique().max() == 1

df[
    ["file_path", "machine_type", "machine_id", "label",
     "snr_db", "recording_group", "split"]
].to_csv(OUTPUT / "data_splits.csv", index=False)

metrics = []
predictions = []

for machine in ("fan", "pump"):
    subset = df[df["machine_type"] == machine]

    train = subset[subset["split"] == "train"]
    validation = subset[subset["split"] == "validation"]
    test = subset[subset["split"] == "test"].copy()

    assert (train["label"] == 0).all()

    print(f"\nEntraînement : {machine}", flush=True)
    print(
        f"Train : {len(train)} | Validation : {len(validation)}"
        f" | Test : {len(test)}",
        flush=True,
    )

    model = IsolationForest(
        n_estimators=300,
        max_samples="auto",
        contamination="auto",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train[features])

    # Plus le score est élevé, plus le son est inhabituel.
    normal_validation = validation[validation["label"] == 0]
    validation_scores = -model.score_samples(
        normal_validation[features]
    )

    # Seuil initial : environ 5 % de fausses alertes sur les sons
    # normaux de validation. Le taux réel sera mesuré au test.
    threshold = float(np.quantile(validation_scores, 0.95))

    test["anomaly_score"] = -model.score_samples(test[features])
    test["prediction"] = (
        test["anomaly_score"] > threshold
    ).astype(int)
    test["threshold"] = threshold

    joblib.dump(
        {
            "model": model,
            "features": features,
            "threshold": threshold,
            "machine_type": machine,
        },
        OUTPUT / f"{machine}_isolation_forest.joblib",
    )

    predictions.append(test[
        ["file_path", "machine_type", "machine_id", "snr_db",
         "recording_group", "label", "anomaly_score",
         "threshold", "prediction"]
    ])

    evaluations = [("tous", test)]
    evaluations += list(test.groupby("snr_db"))

    for snr, part in evaluations:
        y = part["label"]
        predicted = part["prediction"]
        tn, fp, fn, tp = confusion_matrix(
            y, predicted, labels=[0, 1]
        ).ravel()

        metrics.append({
            "machine_type": machine,
            "snr_db": snr,
            "n_test": len(part),
            "precision": precision_score(y, predicted, zero_division=0),
            "recall": recall_score(y, predicted, zero_division=0),
            "f1": f1_score(y, predicted, zero_division=0),
            "roc_auc": roc_auc_score(y, part["anomaly_score"]),
            "false_alarm_rate": fp / (fp + tn),
            "normal_correct": int(tn),
            "false_alerts": int(fp),
            "missed_anomalies": int(fn),
            "detected_anomalies": int(tp),
        })

report = pd.DataFrame(metrics)
report.to_csv(OUTPUT / "metrics.csv", index=False)
pd.concat(predictions, ignore_index=True).to_csv(
    OUTPUT / "test_predictions.csv", index=False
)

print("\nRésultats sur les données de TEST :")
print(report[
    ["machine_type", "snr_db", "precision", "recall",
     "f1", "roc_auc", "false_alarm_rate"]
].round(3).to_string(index=False))

print(f"\nModèles et résultats enregistrés dans : {OUTPUT}")
