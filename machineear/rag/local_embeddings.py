"""Offline multilingual E5 embeddings, using a local ONNX Node worker."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import Request, urlopen

from machineear.rag.extract_pdf_text import file_hash
from machineear.paths import ROOT, RESOURCE_ROOT

MODEL_DIR = RESOURCE_ROOT / ".venv" / "models" / "multilingual-e5-small"
RUNTIME_DIR = RESOURCE_ROOT / ".venv" / "embedding_node"
MODEL_REPO = "Xenova/multilingual-e5-small"
MODEL_REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78"
WEIGHTS_SHA256 = "f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193"
ONNX_VERSION = "1.31.1"
MODEL_FILES = ("config.json", "tokenizer_config.json", "tokenizer.json", "onnx/model_quantized.onnx")


def download_model(model_dir=MODEL_DIR):
    model_dir = Path(model_dir)
    records = []
    for name in MODEL_FILES:
        target = model_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{name}"
        if not target.is_file():
            print(f"Downloading local embedding asset: {name}", flush=True)
            temporary = target.with_suffix(target.suffix + ".part")
            with urlopen(Request(url, headers={"User-Agent": "MachineEar-local-retrieval"}), timeout=90) as response, temporary.open("wb") as handle:
                size, announced = 0, 0
                while block := response.read(1024 * 1024):
                    handle.write(block)
                    size += len(block)
                    if size // (20 * 1024 * 1024) > announced:
                        announced = size // (20 * 1024 * 1024)
                        print(f"  {size // (1024 * 1024)} MiB", flush=True)
            temporary.replace(target)
        digest = file_hash(target)
        if name.endswith(".onnx") and digest != WEIGHTS_SHA256:
            raise ValueError("Embedding model checksum does not match the published pinned weights")
        records.append({"path": name, "url": url, "sha256": digest, "bytes": target.stat().st_size})
    manifest = {"model_repo": MODEL_REPO, "revision": MODEL_REVISION, "files": records,
                "dimension": 384, "max_tokens": 512, "pooling": "attention-mask mean, then L2 normalization",
                "passage_prefix": "passage: ", "query_prefix": "query: ", "remote_code_executed": False}
    (model_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def prepare_runtime(runtime_dir=RUNTIME_DIR):
    runtime_dir = Path(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm or not shutil.which("node"):
        raise RuntimeError("Node.js and npm are required for the local ONNX embedding worker")
    package = {"name": "machineear-local-embedding-runtime", "version": "1.0.0", "private": True,
               "dependencies": {"onnxruntime-node": ONNX_VERSION}}
    (runtime_dir / "package.json").write_text(json.dumps(package, indent=2), encoding="utf-8")
    lock = ROOT / "requirements" / "embedding-runtime.lock.json"
    if lock.is_file():
        shutil.copyfile(lock, runtime_dir / "package-lock.json")
    command = [npm, "ci" if lock.is_file() else "install", "--prefix", str(runtime_dir),
               "--onnxruntime-node-install=skip", "--no-audit", "--no-fund"]
    subprocess.run(command, check=True)
    shutil.copyfile(runtime_dir / "package-lock.json", lock)


class LocalTokenizer:
    def __init__(self, model_dir=MODEL_DIR):
        from tokenizers import Tokenizer

        self.model_dir = Path(model_dir)
        path = self.model_dir / "tokenizer.json"
        if not path.is_file():
            raise FileNotFoundError("Embedding assets missing. Run python -m machineear.rag.local_embeddings --prepare")
        self.tokenizer = Tokenizer.from_file(str(path))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.pad_id = self.tokenizer.token_to_id("<pad>")

    def count(self, text, *, kind="passage"):
        return len(self.tokenizer.encode(f"{kind}: {text}").ids)


class LocalEmbedder(LocalTokenizer):
    def __init__(self, model_dir=MODEL_DIR, runtime_dir=RUNTIME_DIR):
        super().__init__(model_dir)
        self.process = None
        self.log = None
        self.runtime_dir = Path(runtime_dir)
        node = shutil.which("node")
        weights = self.model_dir / "onnx" / "model_quantized.onnx"
        if not node or not (self.runtime_dir / "node_modules" / "onnxruntime-node").is_dir():
            raise FileNotFoundError("Local embedding runtime missing. Run python -m machineear.rag.local_embeddings --prepare")
        if not weights.is_file() or file_hash(weights) != WEIGHTS_SHA256:
            raise ValueError("Embedding weights missing or checksum mismatch")
        env = dict(os.environ)
        env["PATH"] = str(Path(sys.prefix) / "Scripts") + os.pathsep + env.get("PATH", "")
        self.log = (self.runtime_dir / "worker.log").open("a", encoding="utf-8")
        self.process = subprocess.Popen(
            [node, str(Path(__file__).with_name("embedding_worker.cjs")), str(self.runtime_dir), str(weights)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            text=True, encoding="utf-8", bufsize=1, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            response = self._read()
            if not response.get("ready"):
                raise RuntimeError(f"Embedding worker failed: {response}")
        except Exception:
            self.close()
            raise
        self.runtime_info = response

    def _read(self):
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"Embedding worker stopped; inspect {self.runtime_dir / 'worker.log'}")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response

    def encode(self, texts, *, kind="passage"):
        import numpy as np

        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        encoded = self.tokenizer.encode_batch([f"{kind}: {text}" for text in texts])
        length = max(len(item.ids) for item in encoded)
        if length > 512:
            raise ValueError(f"Embedding input has {length} tokens; limit is 512. No silent truncation is allowed.")
        payload = {"input_ids": [item.ids + [self.pad_id] * (length - len(item.ids)) for item in encoded],
                   "attention_mask": [item.attention_mask + [0] * (length - len(item.ids)) for item in encoded],
                   "token_type_ids": [item.type_ids + [0] * (length - len(item.ids)) for item in encoded]}
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()
        vectors = np.asarray(self._read()["vectors"], dtype=np.float32)
        if vectors.shape != (len(texts), 384) or not np.isfinite(vectors).all():
            raise RuntimeError("Embedding worker returned invalid vectors")
        if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5):
            raise RuntimeError("Embedding vectors must have unit L2 norm")
        return vectors

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    self.process.stdin.write('{"close":true}\n')
                    self.process.stdin.flush()
                    self.process.wait(timeout=5)
                except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                    self.process.terminate()
                    self.process.wait(timeout=5)
            self.process.stdin.close()
            self.process.stdout.close()
            self.process = None
        if self.log:
            self.log.close()
            self.log = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args(argv)
    if args.prepare:
        download_model()
        prepare_runtime()
        print("Local multilingual embedding model and CPU runtime are ready.")


if __name__ == "__main__":
    main()
