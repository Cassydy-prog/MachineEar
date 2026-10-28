// Local CPU-only ONNX inference worker. No network APIs or remote code loading.
'use strict';
const path = require('node:path');
const readline = require('node:readline');

async function main() {
  const runtimeDir = process.argv[2], modelPath = process.argv[3];
  const ort = require(path.join(runtimeDir, 'node_modules', 'onnxruntime-node'));
  const session = await ort.InferenceSession.create(modelPath, {
    executionProviders: ['cpu'], intraOpNumThreads: 4, interOpNumThreads: 1,
    graphOptimizationLevel: 'all', logSeverityLevel: 3,
  });
  const send = value => process.stdout.write(JSON.stringify(value) + '\n');
  send({ready: true, node: process.version, onnxruntime: ort.env.versions.node,
        inputNames: session.inputNames, outputNames: session.outputNames});
  const lines = readline.createInterface({input: process.stdin, crlfDelay: Infinity});
  for await (const line of lines) {
    try {
      const request = JSON.parse(line);
      if (request.close) break;
      const batch = request.input_ids.length, length = request.input_ids[0].length;
      const feeds = {};
      for (const name of session.inputNames) {
        if (!request[name]) throw new Error(`Missing model input ${name}`);
        feeds[name] = new ort.Tensor('int64', BigInt64Array.from(request[name].flat(), BigInt), [batch, length]);
      }
      const outputs = await session.run(feeds);
      const hidden = outputs.last_hidden_state || outputs[session.outputNames[0]];
      if (hidden.dims.length !== 3 || hidden.dims[2] !== 384) throw new Error('Unexpected token embedding dimensions');
      const vectors = [];
      for (let b = 0; b < batch; b++) {
        const vector = new Array(384).fill(0);
        let count = 0;
        for (let t = 0; t < length; t++) {
          if (!request.attention_mask[b][t]) continue;
          count++;
          const offset = (b * length + t) * 384;
          for (let d = 0; d < 384; d++) vector[d] += hidden.data[offset + d];
        }
        for (let d = 0; d < 384; d++) vector[d] /= count;
        const norm = Math.sqrt(vector.reduce((sum, value) => sum + value * value, 0));
        if (!Number.isFinite(norm) || norm === 0) throw new Error('Invalid pooled embedding norm');
        vectors.push(vector.map(value => value / norm));
      }
      send({vectors});
    } catch (error) { send({error: String(error.stack || error)}); }
  }
  await session.release();
}
main().catch(error => {
  process.stdout.write(JSON.stringify({error: String(error.stack || error)}) + '\n');
  process.exitCode = 1;
});
