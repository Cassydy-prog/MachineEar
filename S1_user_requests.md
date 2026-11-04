# MachineEar — Session 1 : cinq demandes utilisateur

Ces demandes décrivent les fonctionnalités visées pour notre projet.

Un workflow suit des étapes prédéfinies. Un agent choisit ses actions selon les résultats obtenus.

| Demande utilisateur | Choix | Justification |
|---|---|---|
| Analyse cet enregistrement de pompe et indique si une anomalie est détectée. | Workflow | Les étapes sont fixes : préparer l’audio, appliquer le modèle et afficher le score et le seuil. |
| Retrouve les consignes d’entretien de ce ventilateur dans son manuel. | Workflow | Une recherche documentaire suivie d’une réponse avec ses sources suffit. |
| Cette pompe fait un bruit inhabituel : analyse l’audio et recherche les vérifications pertinentes dans les manuels. | Agent | Le système adapte ses recherches documentaires aux résultats audio et demande des précisions si nécessaire. |
| Compare cette analyse aux précédentes et recherche dans les manuels les vérifications utiles pour comprendre les écarts. | Agent | Le système choisit les recherches complémentaires selon les écarts observés et les informations manquantes. |
| Prépare un ticket de maintenance à partir de cette analyse, puis crée-le après ma confirmation. | Workflow | La préparation, la validation humaine et la création du ticket suivent une procédure prédéfinie. |

Une anomalie audio ne suffit pas à identifier une panne précise.
Les recommandations doivent être appuyées par des sources pertinentes.
La création de tickets et la comparaison avec l’historique sont des fonctionnalités à développer ou à connecter.
