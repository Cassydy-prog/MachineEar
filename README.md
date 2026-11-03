# MachineEar — Web Interface

MachineEar provides a French/English web interface for detecting unusual machine sounds and consulting technical documentation. It combines an audio anomaly detector, document retrieval, and an assistant powered by a model served through Groq.

**The application flags sound anomalies. It does not diagnose a specific mechanical fault or certify machine health.**

## Features

- French and English interface.
- WAV upload for supported fans and pumps.
- Optional user observations and equipment context.
- Audio result with an anomaly score and a decision threshold.
- Basic recording quality checks.
- Questions entered by text or microphone, with the speech module installed.
- Documentary references and access to the original local PDF manuals.
- Analysis history stored locally.
- Structured report generation through Groq and PDF export.

## How it works

1. Select the machine category and the corresponding trained equipment ID.
2. Confirm the equipment selection and upload a WAV recording.
3. Optionally describe observed symptoms and the equipment context.
4. Run the analysis and review the score, threshold, and decision.
5. Ask questions using the chat or microphone and review the cited sources.
6. Generate the report with Groq, then download the PDF.

Supported selections are `fan` and `pump`, with IDs `id_00`, `id_02`, `id_04`, and `id_06` in each category. A pump and fan sharing an ID are separate equipment selections. Selecting an ID does not make the detector suitable for arbitrary real-world equipment.

## Requirements

For local execution:

- Python and an activated virtual environment compatible with the repository dependencies.
- The repository's Python dependencies, including FastAPI, Uvicorn, Python Multipart, NumPy, SoundFile, ReportLab, and Groq.
- The `machineear` package, trained audio assets, and RAG assets expected by the project.
- Technical manuals under `data/manuals/`, consistent with the retrieval metadata.
- `backend/speech.py` and its dependencies for the microphone feature. The backend imports this module at startup.
- A microphone-enabled browser and microphone permission for voice input.
- A Groq API key for generated answers and reports.

Use the dependency files supplied by your checkout. Installing only the web packages does not install the complete audio and retrieval pipeline.

## Configuration

Create a `.env` file at the repository root:

```dotenv
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
```

The model name is the application's configured default; access depends on your Groq account. You can select another compatible model through `GROQ_MODEL`.

Do not commit `.env` or include it in shared archives. Keep the API key on the backend.

Without a Groq key, the audio analysis and initial factual report can still operate if their dependencies and assets are available. Generated chat answers and Groq report drafting require the key. Voice transcription may have additional requirements defined by `backend/speech.py`.

## Install and run on Windows (Git Bash)

The following steps use **Git Bash on Windows**. Install Git and Python first. Node.js is needed if your checkout uses Node-based tooling; the backend command below serves the existing frontend directly.

### 1. Clone the project branch

Open Git Bash in an empty working folder and run:

```bash
git clone --branch "Pipeline-de-détection-d'anomalies-audio" --single-branch https://github.com/Cassydy-prog/MachineEar.git
cd MachineEar
```

**Copy the branch name exactly.** The apostrophe in `d'anomalies` is the straight character `'`, not the typographic character `’`. Double quotes do not make these two characters equivalent.

### 2. Configure Groq

Use `.env.example` as a starting point:

```bash
cp .env.example .env
```

Edit `.env` at the repository root and enter your own key:

```dotenv
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
```

Preserve any other settings required by `.env.example`. Never publish your API key.

### 3. Create the Python environment

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-docker.txt
```

Run these commands from the repository root. Despite its name, this requirements file can be used with pip outside Docker. It must include or reference the full dependencies required by your checkout; if preparation reports a missing package, inspect this file and the repository dependency instructions.

### 4. Check Node.js if required by your checkout

If Node.js is installed in its default Windows location but Git Bash cannot find it:

```bash
export PATH="/c/Program Files/nodejs:$PATH"
export PATHEXT='.COM;.EXE;.BAT;.CMD'
node --version
npm --version
```

These exports apply to the current terminal session. Adapt the path if Node.js is installed elsewhere. This step checks availability; it does not install Node.js or build a frontend. No `npm install` or `npm run` step is required merely to serve the existing static frontend through FastAPI.

### 5. Prepare local embeddings

```bash
python -m machineear.rag.local_embeddings --prepare
```

Allow preparation to finish successfully before starting the application. Initial preparation may need network access and local cache space. This command prepares the embedding resources exposed by the project module; it does not replace missing manuals, trained audio models, or an absent retrieval index. Follow any additional asset-preparation instructions provided by the checkout.

### 6. Start MachineEar

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** in your browser. Keep the terminal running while using the application.

The same FastAPI application serves the API and the existing files in `frontend/`. Binding to `127.0.0.1` makes this instance accessible only from your own computer.

### Start again later

Open Git Bash in the cloned `MachineEar` folder:

```bash
source .venv/Scripts/activate
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

You do not need to clone, recreate the virtual environment, or prepare embeddings again on every launch. Repeat installation or preparation when dependencies or relevant resources change.

Stop the server with **Ctrl+C**. Restart it after changing `.env`. For development, add `--reload` to the Uvicorn command to reload Python code changes automatically.

## Run with Docker

If your checkout includes the project's `Dockerfile` and `compose.yaml`, open Docker Desktop and run from the repository root:

```bash
docker compose up --build -d
```

Open the host address and port defined in `compose.yaml`. To inspect the port mapping and logs:

```bash
docker compose ps
docker compose logs --tail=100
```

Start existing containers without rebuilding:

```bash
docker compose up -d
```

After code or dependency changes that are copied into the image, rebuild with `docker compose up --build -d`.

Stop the application:

```bash
docker compose down
```

Ensure Compose passes the Groq environment variables to the backend: a root `.env` alone does not guarantee that they are available inside the container. For persistent history, configure a volume or bind mount for the results directory. Availability of model assets and manuals also depends on the Docker configuration.

## Audio input and interpretation

The API accepts standard RIFF/WAVE files up to 50 MiB and requires at least two seconds of readable, finite, non-silent audio. Passing these checks does not guarantee compatibility with the trained model.

The interface checks recording level and the proportion of samples near full scale. These are heuristic checks; they do not measure background noise or estimate the signal-to-noise ratio.

The detector compares the anomaly score with its configured threshold. A higher score indicates greater departure from the reference according to that detector; it is not a probability of failure or a severity rating. No anomaly detected does not guarantee that the equipment is healthy.

For evaluation, use held-out recordings with the correct equipment selection. Running an analysis on a training recording is a functional demonstration, not an independent performance test.

## Voice questions

The microphone is for asking the assistant a question; the WAV upload is for analysing machine sound. These are separate inputs.

Allow browser microphone access when prompted. Microphone capture generally requires localhost or an HTTPS page. If voice input is unavailable, check browser permissions, the speech module, and its configuration. Confirm any transcription before relying on the answer.

## Documentary answers and reports

The backend sends the audio result, recording checks, user context, and up to six previously retrieved excerpts to Groq. In this implementation, report drafting and chat reuse the retrieval results saved during the analysis; they do not perform a fresh document search for each request.

Generated report sections include:

- Analysis identification and the measured sound result.
- A summary that preserves the detector's decision.
- Recording characteristics and user observations.
- Comparison with user observations when available.
- Relevant documentary findings with references.
- Up to three suggested checks, subject to human review.
- Limitations and the sources used.

The backend validates the JSON structure and source identifiers. It retains at most three suggested checks. For an analysis without user notes, it inserts an explicit statement that agreement or contradiction cannot be assessed. The report summary is populated directly from the detector's decision.

**These checks do not establish that every generated claim is supported by its citation.** Review recommendations against the original passages, including their conditions of application.

General manuals may provide useful context when the exact equipment model is unknown. They must not be treated as confirmed instructions for that particular unit. Storage, installation, and operating procedures have different conditions of application.

Generating a report updates the saved report. Downloading the PDF only exports the saved content; it does not rerun Groq. After changing the report prompt, generate a new report before exporting.

The current export can include `machineear-report-v2` as its report version. Reports are marked as unvalidated drafts.

## Project locations

| Location | Purpose |
| --- | --- |
| `backend/main.py` | FastAPI routes, analysis records, Groq requests, report validation, and PDF export |
| `backend/speech.py` | Voice-question API router |
| `frontend/` | Web interface served by FastAPI |
| `machineear/` | Audio analysis and retrieval integration |
| `data/manuals/` | Original PDF manuals |
| `results/web_analyses/` | Locally stored analysis records and chat/report content |
| `.env` | Local backend configuration |

Analysis records contain results, context, retrieved content, and conversation history. The shown web backend does not itself persist the uploaded WAV file; storage behaviour inside the analysis engine should be checked separately.

## Main API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Backend status and Groq-key configuration flag |
| POST | `/api/analyses` | Upload and analyse a WAV file |
| GET | `/api/analyses` | List saved analyses |
| GET | `/api/analyses/{identifier}` | Load an analysis |
| POST | `/api/analyses/{identifier}/chat` | Ask a text question |
| POST | `/api/analyses/{identifier}/report` | Generate and save a report |
| GET | `/api/analyses/{identifier}/report.pdf` | Export the saved report |
| GET | `/api/analyses/{identifier}/sources/{number}` | Open a retrieved PDF source |

Voice endpoint definitions are provided by `backend/speech.py`. Source numbers are one-based. The PDF-source route allows only existing PDFs located inside `data/manuals/`.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `GROQ_API_KEY missing on backend` | Root `.env`, backend restart, and container environment if using Docker |
| Groq returns 502 | Server logs, API access, quota, model availability, or response validation failure |
| `Rapport JSON invalide` | Groq must return the expected JSON and only supplied source IDs; the previous report is preserved on validation failure |
| PDF returns `Not Found` | Confirm the PDF route exists before the final static-files mount, check the URL and restart the correct backend |
| `Analysis not found` | The identifier must refer to a saved record in the running backend's results directory |
| A source PDF cannot be opened | Verify the manual exists and `source_relative_path` matches its location inside `data/manuals/` |
| No documentary sources | Inspect retrieval results, the document index, dependencies, and asset paths; Groq cannot cite missing excerpts |
| Audio analysis returns 503 | Check the engine, models, retrieval dependencies, and expected asset paths |
| Microphone unavailable | Browser permission, localhost/HTTPS, speech router, and transcription configuration |
| Report still contains old wording | Regenerate with Groq; PDF export alone does not update the report |

## Data handling and scope

Chat and report generation send the required result metadata, user observations, and documentary excerpts to Groq. Review what you enter or include in the corpus before using external generation. Speech transcription data handling depends on the speech implementation.

The provided backend has no authentication or user-level separation of analysis history. Use it as a local demonstration unless suitable access controls are added. Do not expose it publicly as-is.

## Evaluation

Evaluate audio detection separately from report generation. For generated reports, review ten cases and record:

1. Whether each citation supports its associated claim.
2. Whether any claim, symptom, or recommendation is unsupported.
3. Whether the detector's decision and the absence/presence of user observations are represented faithfully.
4. Whether recommendations preserve the document's conditions of application.

Do not report unperformed evaluations as completed. Document titles, provenance, and licences or usage conditions should be inventoried separately; a publicly accessible manual is not automatically openly licensed.

## Human evaluation page

The evaluation extension provides a separate page at:

```text
http://127.0.0.1:8000/evaluation
```

### Install the extension

Copy the supplied extension files into the existing project:

```text
backend/evaluation.py
frontend/evaluation.html
```

In `backend/main.py`, register both routers after creating the existing app:

```python
app = FastAPI(title='MachineEar API')

from backend.speech import router as speech_router
from backend.evaluation import router as evaluation_router

app.include_router(speech_router)
app.include_router(evaluation_router)
```

Keep existing routes. Do not create a second FastAPI app or duplicate the router registrations. Register the evaluation router before the final `app.mount('/', ...)`, then restart the backend.

To make the page visible in the navigation, add the following link alongside History in `frontend/en.html`:

```html
<a href="/evaluation">Evaluation</a>
```

Add the French equivalent alongside Historique in `frontend/index.html`:

```html
<a href="/evaluation">Évaluation</a>
```

Match the existing navigation classes for consistent styling. The direct URL works without these links.

### Evaluate a report

The dropdown lists saved audio analyses, not PDF files from your Downloads folder. Match a downloaded report to an analysis using the analysis ID printed in the PDF. The same WAV filename may occur in several analyses or equipment folders.

1. Select one of the ten reports chosen for your evaluation set.
2. Read the saved report and compare it against the audio result and user observations.
3. Expand the saved source excerpts and consult the original PDFs.
4. Enter your name or stable reviewer identifier.
5. Score each criterion: 0 = incorrect, 1 = partially correct, 2 = correct.
6. Count checked, fully supported, unverifiable, and unsupported claims.
7. Write specific evidence notes and save once.
8. Repeat for the other reports and export the CSV.

| Criterion | What to check |
| --- | --- |
| Audio fidelity | The report preserves the detector result without inferring a specific mechanical fault. |
| Source support | Statements are supported by supplied facts or documents. |
| Citation accuracy | The cited passage actually supports the associated statement. |
| Context relevance | The information concerns the appropriate category and preserves storage, installation, or operating conditions. |

### Understand the claim counters

These fields are counts, not scores:

- **Checked cited claims:** statements actually compared against available source material.
- **Fully supported cited claims:** the subset fully justified by those sources. This count cannot exceed checked claims.
- **Unverifiable cited claims:** statements that cannot be checked because the necessary evidence is absent or inaccessible. Exclude these from the checked denominator. A statement not yet examined is not automatically unverifiable.
- **Unsupported claims:** statements for which the supplied evidence provides no support, including uncited inventions. A checked but incorrect citation is still checked.

Split sentences containing several independent claims before counting. A partially supported statement is checked but not fully supported. A source citation alone does not establish factual correctness.

Example: six cited claims examined, four verifiable, three fully supported, and two unverifiable means entering **4 checked / 3 supported / 2 unverifiable**.

### Save and interpret evaluations

Reviews are saved under `results/report_evaluations/`, separately from analyses in `results/web_analyses/`. Each save creates a new review and preserves a snapshot; it does not overwrite an earlier review or train the model.

The dropdown displays the number of reviews for the current report version. Regenerating a report can make an older review outdated. CSV exports include `current_report` to identify this situation.

Use one retained review per reviewer and report version for your final analysis. Two independent reviewers may evaluate the same ten reports, then discuss disagreements. Keep their original scores. Reviews of different reports do not allow inter-reviewer agreement to be measured.

### Summarise the results

After completing genuine annotations, export the CSV and calculate separate indicators:

| Indicator | Calculation |
| --- | --- |
| Citation support rate | Sum of fully supported cited claims / sum of checked cited claims × 100 |
| Reports faithful to audio | Reports scored 2 for audio fidelity / reports evaluated × 100 |
| Reports containing unsupported claims | Reports with at least one unsupported claim / reports evaluated × 100 |

Report unverifiable counts separately. If no cited claim was checked, citation support is not calculable. For multiple reviewers, report per-reviewer results or define an explicit adjudication policy; do not silently mix duplicate reviews. Show raw counts alongside percentages, such as 8/10 (80%).

These are separate quality indicators, not a single global reliability score. Ten reports provide exploratory evidence, not production assurance. Demonstration entries must be labelled as illustrative and excluded from real performance claims.

The extension currently supports **human evaluation only**. LLM-as-a-judge, automated bias testing, and aggregate dashboards are possible future additions, not implemented features.
