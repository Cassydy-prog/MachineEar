# MachineEar — Web Interface

A bilingual French/English interface for analyzing machine recordings, reviewing relevant manual excerpts, and discussing results with an AI assistant.

This documentation covers the `interface-react-docker` branch of the [MachineEar repository](https://github.com/Cassydy-prog/MachineEar). Despite the branch name, the current frontend uses **HTML, CSS, and JavaScript**, with no React build step. The **FastAPI** backend serves both the pages and the API.

## Features

- Upload a WAV file and select the machine type and ID.
- Detect unusual sounds using the existing audio model.
- View analysis results and recording quality checks.
- Add observations and equipment context.
- Review retrieved document excerpts and open their source PDFs.
- Ask a Groq assistant questions based on the analysis and previously retrieved sources.
- View a factual report, generate an AI report, and export the saved report as a PDF.
- Reopen previous analyses from the history.
- Use the interface in French or English.

## Architecture

| Component | Purpose |
| --- | --- |
| `frontend/` | French/English pages, styles, and JavaScript interactions |
| `backend/main.py` | API, WAV validation, history, chat, and reports |
| `machineear/analyze_recording.py` | Connects audio detection to document retrieval |
| `machineear/audio_bridge.py` | Calls the original audio predictor |
| `scripts/predict_audio.py` | Runs inference with the trained audio models |
| `machineear/rag/` | Local hybrid document retrieval |
| `results/logmel_knn/` | Existing audio models |
| `data/manuals/` | Original PDF manuals |
| `results/rag/` | Prepared passages, index, and document resources |
| `results/web_analyses/` | Analyses, conversations, and reports saved as JSON |

The `logmel_knn5_mean` audio model uses a log-mel representation and distances to reference neighbors. Document retrieval combines multilingual E5 embeddings and BM25 through rank fusion. The interface reuses these components without retraining the detector or changing its thresholds.

## Get the Project

Install Git, then run:

```bash
git clone --branch interface-react-docker --single-branch https://github.com/Cassydy-prog/MachineEar.git
cd MachineEar
```

Run all subsequent commands from the `MachineEar` repository root, which contains `compose.yaml` and the `backend` directory.

## Configure Groq

Create a file named exactly `.env` at the repository root:

```dotenv
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
```

Replace `your_groq_api_key` with your personal key. Keep this file on your computer and do not publish it on GitHub.

The key is required for AI chat and AI report generation. Without it, audio analysis, local retrieval, and factual reports remain available when their dependencies and resources are installed. PDF export uses the currently saved report.

Audio detection and document retrieval run locally. When you request an AI chat response or report, the backend sends Groq the structured results, observations, equipment context, and relevant document excerpts. Chat requests also include recent conversation history. These requests do not transmit the raw WAV file.

## Run with Docker

Install Docker Desktop with Docker Compose, and open Docker Desktop before starting.

### First Launch

```bash
docker compose up --build -d
```

The first build installs dependencies and downloads the local embedding model. It requires an Internet connection and may take several minutes. The repository's audio models and document index are reused.

Then open [http://localhost:8000](http://localhost:8000).

### Subsequent Launches

```bash
docker compose up -d
```

Use `--build` again after changing the application code or image dependencies. After editing `.env`, run `docker compose up -d` to update the service configuration.

### Status, Logs, and Shutdown

```bash
docker compose ps
docker compose logs -f machineear
docker compose down
```

Press `Ctrl+C` to stop following the logs. `docker compose down` stops the application and removes its containers, but preserves history in the named `analyses` volume. Adding `-v` would also delete that volume and its history.

The Docker port is published only on `127.0.0.1`, so the application is accessible from the computer running it.

## Run without Docker

Python, Node.js, and npm are required. The Dockerfile uses Python 3.13 and Node.js 22; these are the reference versions for the containerized setup. Because the audio dependencies are pinned, native installation depends on compatible packages being available for your operating system and Python version.

### 1. Create a Python Environment

In Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

In Windows Git Bash, activate it with:

```bash
source .venv/Scripts/activate
```

On Linux/macOS, activate it with:

```bash
source .venv/bin/activate
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` instead of `python` in the following commands.

### 2. Install and Prepare Dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-docker.txt
python -m pip check
node --version
npm --version
python -m machineear.rag.local_embeddings --prepare
```

Despite its name, `requirements-docker.txt` is a pip requirements file that can be used without Docker. It includes the audio, web, and document dependencies used by the image. Node.js runs local ONNX embeddings; it is not used to compile the frontend.

On Debian/Ubuntu, install the native libraries used by the image with:

```bash
sudo apt-get update
sudo apt-get install -y libsndfile1 libgomp1 libstdc++6
```

The preparation step downloads the required embedding weights and runtime. You do not need to rebuild the document index or download the entire audio dataset.

### 3. Start the Server

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open [http://localhost:8000](http://localhost:8000). Keep the terminal open; press `Ctrl+C` to stop the server. For subsequent launches, reactivate the environment and run this server command again.

Access the interface through FastAPI. Opening `frontend/index.html` directly does not start the API.

## Usage

1. Choose the interface language.
2. Upload a non-silent, standard RIFF/WAVE file lasting at least **2 seconds**, with a maximum size of **50 MiB**.
3. Select `fan` for a fan or `pump` for a pump.
4. Select the ID matching the trained model: `id_00`, `id_02`, `id_04`, or `id_06`.
5. Confirm the equipment match. The application does not identify the machine automatically.
6. Optionally add observations and equipment context, then start the analysis.
7. Review the result, audio checks, and document excerpts.
8. Ask a chat question, view or generate the report, and download its PDF.
9. Use the history to reopen a previous analysis.

For a functional demonstration, use a normal training WAV with its matching machine type and ID. This check does not measure performance on independent data. Recordings are not included in the repository.

## API

Interactive FastAPI documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Check server status and whether Groq is configured |
| POST | `/api/analyses` | Analyze a WAV and its context using multipart form data |
| GET | `/api/analyses` | List analysis history |
| GET | `/api/analyses/{identifier}` | Load an analysis |
| POST | `/api/analyses/{identifier}/chat` | Ask a question using JSON containing `message` and `language` |
| POST | `/api/analyses/{identifier}/report` | Generate an AI report with `language` as a form field |
| GET | `/api/analyses/{identifier}/report.pdf` | Download the saved report as a PDF |
| GET | `/api/analyses/{identifier}/sources/{number}` | Open a source PDF, numbered from 1 |

`/api/health` does not fully validate the models, index, or Groq access. An `ok` response confirms that the API responds; an actual analysis checks the complete workflow.

## Troubleshooting

| Problem | Check or action |
| --- | --- |
| The page does not open | Check the terminal or `docker compose ps`, then port 8000 |
| Docker does not start | Open Docker Desktop and wait for the engine to be ready |
| Port 8000 is already in use locally | Start Uvicorn with `--port 8001`, then open `http://localhost:8001` |
| Analysis returns error 422 | Check the WAV format, duration, level, size, and equipment confirmation |
| Missing engine or models, error 503 | Check repository resources, dependencies, and server logs |
| Document retrieval is unavailable | Check Node/npm, prepare embeddings, and inspect logs; an audio-only result may be retained |
| Chat or report reports a missing key | Check `.env` at the repository root, then restart the server or update the Compose service |
| Groq is unavailable, error 502 | Check connectivity, API access, quota, and the configured model |
| Source PDF is missing | Check the original file and its path under `data/manuals/` |

## Persistence and Limitations

Without Docker, analyses are stored in `results/web_analyses/`. With Docker, this directory is mounted on the `analyses` volume. JSON records include observations, retrieved passages, conversations, and reports. The analysis endpoint does not save the raw WAV file.

Audio quality checks can flag low recording levels or peaks near full scale. They do not measure background noise or the signal-to-noise ratio.

An unusual sound does not identify a specific fault. No alert does not guarantee that a machine is healthy. An anomaly score is not a probability of failure. Manuals may provide general guidance without matching the analyzed equipment exactly.

The chat uses the existing analysis and previously retrieved sources. Each message does not trigger a new audio analysis or document search. Reports remain drafts requiring human review.

The current interface does not provide user authentication. The documented setup is intended for local use.

## Contributions

The bilingual web interface and FastAPI backend were developed by **Bally-Stone Papin MOUDIANGO-MOUDIANGO**. They integrate his existing audio detector and the MachineEar team's document retrieval work.

This documentation was prepared from the `interface-react-docker` branch, commit `516639a6b33b643f48654314c263e44dc1ac285d`. Commands were checked against the configuration files and source code; no full installation or audio analysis was performed while preparing this README.
