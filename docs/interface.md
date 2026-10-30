# Interface technicien MachineEar

Cette interface appelle directement `machineear.analyze_recording.analyze_recording`.
Les scripts audio, bundles, seuils et résultats existants restent inchangés.
La branche RAG propose des passages cités mais pas encore de génération LLM :
le compte rendu est donc une trame factuelle modifiable par le technicien.

## Installation dans Git Bash sous Windows

Depuis le dépôt contenant ces fichiers :

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements/ui.txt
python -m machineear.rag.local_embeddings --prepare
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

Node.js et npm doivent être installés pour préparer les embeddings locaux.
La préparation télécharge les poids et le runtime ; elle ne réentraîne pas
le détecteur et ne reconstruit pas les index préparés. Consulter `setup.md`
pour les prérequis détaillés. Utiliser un environnement compatible avec les
modèles enregistrés ; `requirements-audio.txt` reste la référence originale.

## Parcours

Choisir fan/pump et l'identifiant correspondant au modèle entraîné ; importer
un WAV d'au moins deux secondes ; renseigner observations et contexte ; lancer
l'analyse. Le résultat affiche les scores, le seuil figé et les passages exacts
avec citations. Toutes les langues sont sélectionnées par défaut pour éviter
d'exclure les manuels anglais sur un poste francophone.

Une panne de recherche affiche l'audio seul avec l'erreur. Une recherche sans
passage indique explicitement l'absence de source. L'application ne diagnostique
pas de panne à partir du score et ne garantit pas la santé d'un appareil sans alerte.

Le technicien édite le compte rendu et renseigne son nom. La validation exige
la case de vérification des sources ; il peut aussi enregistrer un brouillon.
Chaque sauvegarde crée une révision JSON distincte dans
`results/analysis/history/`, déjà exclu de Git. Aucun WAV n'est conservé par
l'interface. L'historique est commun aux sessions sur cet ordinateur : cette
version est un prototype local sans authentification ni signature certifiée.
Les comptes rendus sont exportables en Markdown et les analyses en JSON.

## Vérifications

```bash
python -B -m unittest discover -s tests -v
```

`tests/test_review.py` vérifie les révisions, la conservation des résultats,
les conditions de validation et la gestion d'un historique corrompu.
L'intégration audio/RAG complète requiert les prérequis locaux et un WAV normal
d'entraînement pour une vérification facultative. Ne pas réutiliser le test final
pour ajuster le modèle.
