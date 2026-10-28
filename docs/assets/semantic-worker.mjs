import { pipeline, AutoTokenizer, AutoModelForSequenceClassification, env } from "./vendor/transformers.min.js";
import { createSearchRuntime } from "./search-runtime.mjs?v=20261028-parity-v25";

env.allowLocalModels = false;
env.useBrowserCache = true;
env.backends.onnx.wasm.numThreads = 1;
env.backends.onnx.wasm.proxy = false;
env.backends.onnx.wasm.wasmPaths = new URL("./vendor/", import.meta.url).href;
let currentId = 0;
const runtime = createSearchRuntime({
  pipeline, AutoTokenizer, AutoModelForSequenceClassification,
  async fetchAsset(path) {
    const response = await fetch(new URL(path, import.meta.url));
    if (!response.ok) throw new Error(`Search data could not load (HTTP ${response.status}).`);
    return response.arrayBuffer();
  },
  progress(message) { self.postMessage({ id: currentId, type: "progress", message }); },
});
self.onmessage = async ({ data }) => {
  currentId = data.id;
  try { self.postMessage({ id: currentId, type: "result", ...await runtime.search(data) }); }
  catch (error) { self.postMessage({ id: currentId, type: "error", message: error.message || String(error) }); }
};
