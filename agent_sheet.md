# Agent sheet · MachineEar
| | |
|---|---|
| Gen AI product | MachineEar : détection d’anomalies audio de pompes et ventilateurs, associée à un RAG sur les manuels techniques. |
| Goal | Analyser un enregistrement, consulter les manuels pertinents et proposer des vérifications documentées. Préparer un ticket de maintenance si l’utilisateur le demande. |
| Read tools | analyze_machine_audio, search_manuals, get_analysis_history |
| Write tools (side effects) | create_maintenance_ticket |
| How we check success | Analyse audio obtenue avec score et seuil ; recommandations appuyées par des sources ; ticket créé avec un identifiant après confirmation. |
| Autonomy level | 3 · Agent loop |
| Hard limits | 8 étapes maximum, 60 secondes maximum, 10 000 tokens maximum par demande. |
| Human approval before | Toute création de ticket de maintenance. Aucune commande ni intervention physique sur la machine. |