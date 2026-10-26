import { pipeline, AutoTokenizer, AutoModelForSequenceClassification, env } from "./vendor/transformers.min.js";
import { processQuery, similarities, englishRanks, multilingualRanks, lexicalScores, fuseAndCollapse, rerankingText, storyWindows, selectStoryEvidence } from "./hybrid-ranking.mjs?v=20261026-evidence-v20";

env.allowLocalModels = false;
env.useBrowserCache = true;
env.backends.onnx.wasm.numThreads = 1;
env.backends.onnx.wasm.proxy = false;
env.backends.onnx.wasm.wasmPaths = new URL("./vendor/", import.meta.url).href;

const session_options = { enableCpuMemArena: false, enableMemPattern: false };
let catalog, manifest, ids, weights, preparing;
const matrices = new Map();
let currentId = 0;
function progress(message) { self.postMessage({ id: currentId, type: "progress", message }); }
function downloadProgress(event) {
  if (event.status === "progress" && event.total) progress(`Downloading ${event.file?.includes("onnx") ? "search model" : "tokenizer"}: ${Math.floor(event.progress || 0)}% of ${Math.ceil(event.total / 1048576)} MB`);
}
async function checkedFetch(path) {
  const response = await fetch(new URL(path, import.meta.url));
  if (!response.ok) throw new Error(`Search data could not load (HTTP ${response.status}).`);
  return response.arrayBuffer();
}
async function sha256(buffer) {
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", buffer))].map((n) => n.toString(16).padStart(2, "0")).join("");
}
async function artifact(name) {
  const buffer = await checkedFetch(`../data/${name}`);
  const expected = manifest.files[name];
  if (buffer.byteLength !== expected.bytes || await sha256(buffer) !== expected.sha256) throw new Error("Search data versions differ. Reload to get the current release.");
  return buffer;
}
async function matrix(name) {
  if (!matrices.has(name)) matrices.set(name, new Float32Array(await artifact(name)));
  return matrices.get(name);
}
async function prepare() {
  progress("Loading the hybrid search index");
  manifest = JSON.parse(new TextDecoder().decode(await checkedFetch("../data/hybrid-index.json")));
  const bytes = await checkedFetch("../data/catalog.sample.json");
  if (await sha256(bytes) !== manifest.catalog_sha256) throw new Error("Catalog and search index versions differ. Reload to update.");
  catalog = JSON.parse(new TextDecoder().decode(bytes)).items;
  const postings = await artifact("hybrid-lexical.bin"), size = manifest.lexical.postings;
  ids = new Uint32Array(postings, 0, size);
  weights = new Float32Array(postings, size * 4, size);
}
async function encode(text, config) {
  progress(`Loading ${config.pooling === "cls" ? "English" : "multilingual"} search model`);
  const encoder = await pipeline("feature-extraction", config.model, {
    dtype: "q8", device: "wasm", revision: config.revision, progress_callback: downloadProgress, session_options,
  });
  try {
    progress("Understanding your scene");
    const output = await encoder(config.prefix + text, { pooling: config.pooling, normalize: true, truncation: true, max_length: config.max_length });
    return Float32Array.from(output.data);
  } finally { await encoder.dispose(); }
}
async function rerank(query, candidates) {
  if (!candidates.length) return candidates;
  progress("Loading the relevance reranker");
  const config = manifest.reranker;
  const options = { revision: config.revision, progress_callback: downloadProgress };
  const tokenizer = await AutoTokenizer.from_pretrained(config.model, options);
  const model = await AutoModelForSequenceClassification.from_pretrained(config.model, { ...options, dtype: "q8", device: "wasm", session_options });
  try {
    const selected = candidates.slice(0, 40), scores = [];
    for (let offset = 0; offset < selected.length; offset += 4) {
      progress(`Checking story evidence: ${Math.min(offset + 4, selected.length)}/${selected.length}`);
      const batch = selected.slice(offset, offset + 4);
      const inputs = tokenizer(batch.map(() => query), { text_pair: batch.map((entry) => rerankingText(entry, manifest.records, catalog, query, manifest.processor, manifest.lexical)), padding: true, truncation: true, max_length: config.max_length });
      const result = await model(inputs);
      scores.push(...Array.from(result.logits.data));
    }
    if (scores.length !== selected.length || scores.some((score) => !Number.isFinite(score))) throw new Error("The relevance model returned invalid scores.");
    return selected.map((entry, i) => ({ ...entry, score: scores[i] })).sort((a, b) => b.score - a.score).concat(candidates.slice(40));
  } finally { await model.dispose(); }
}
async function search({ query: value, source, count }) {
  if (!preparing) preparing = prepare().catch((error) => { preparing = null; throw error; });
  await preparing;
  const query = processQuery(value, manifest.processor);
  let english = [], multilingual = [];
  if (manifest.multilingual) {
    const vector = await encode(query.cleaned, manifest.multilingual);
    multilingual = multilingualRanks(similarities(vector, await matrix("hybrid-multilingual.f32"), manifest.multilingual.dimension), manifest.multilingual.records);
  }
  if (!query.persian || query.translated) {
    const vector = await encode(query.translated ? query.concepts : query.cleaned, manifest.english);
    english = englishRanks(similarities(vector, await matrix("hybrid-en.f32"), manifest.english.dimension), manifest.records);
  }
  const lexical = lexicalScores(query.translated ? query.concepts : query.cleaned, manifest, ids, weights);
  let candidates = fuseAndCollapse(query, manifest, catalog, english, lexical, multilingual, source);
  const evidence = new Map(multilingual.map(([index, , row]) => [index, manifest.multilingual.texts?.[row] || ""]));
  candidates = candidates.map((entry) => ({ ...entry, passage: selectStoryEvidence(query.translated ? query.concepts : query.cleaned,
    manifest.records[entry.index].kind === "title" ? storyWindows(catalog[entry.item].plot) : [],
    evidence.get(entry.index) || "", manifest.processor, manifest.lexical) }));
  const reranked = !query.persian || query.translated;
  if (reranked) candidates = await rerank(query.translated ? query.concepts : query.cleaned, candidates);
  return candidates.slice(0, Math.min(20, Math.max(1, count || 8))).map((entry) => {
    const item = catalog[entry.item], scene = entry.scene === null ? null : item.scene_timeline[entry.scene];
    const record = manifest.records[entry.index], episode = record.episode == null ? null : item.episodes[record.episode];
    return { item, score: entry.score, scene, episode, evidence: scene ? scene.transcript || scene.visual_caption : episode ? record.overview : entry.passage || record.overview || item.overview || "",
      evidenceKind: scene ? "scene" : episode ? "episode" : "story", method: reranked ? "hybrid + reranker" : "multilingual + BM25" };
  });
}
self.onmessage = async (event) => {
  currentId = event.data.id;
  try { self.postMessage({ id: currentId, type: "result", results: await search(event.data) }); }
  catch (error) { self.postMessage({ id: currentId, type: "error", message: error.message || String(error) }); }
};
