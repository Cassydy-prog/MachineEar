FROM node:22-bookworm-slim AS node-runtime

FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

# Node.js est utilisé par les embeddings ONNX du RAG.
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Bibliothèques natives pour l'audio et ONNX.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       libsndfile1 \
       libgomp1 \
       libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-audio.txt requirements-web.txt requirements-docker.txt ./

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-docker.txt \
    && python -m pip check

COPY . .

# Télécharger les poids d'embedding vérifiés et installer ONNX.
# Cette étape ne réentraîne pas les modèles audio et ne reconstruit pas l'index.
RUN python -m machineear.rag.local_embeddings --prepare

RUN mkdir -p results/web_analyses

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]