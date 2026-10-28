import { processQuery, similarities, englishRanks, multilingualRanks, lexicalScores, fuseRecords, collapseRecords, evidencePairs, rankEvidence, storyWindows, selectStoryEvidence } from "./hybrid-ranking.mjs?v=20261028-parity-v25";

export function createSearchRuntime({ pipeline, AutoTokenizer, AutoModelForSequenceClassification, fetchAsset, progress = () => {}, modelOptions = {} }) {
const session_options = { enableCpuMemArena: false, enableMemPattern: false };
let catalog, manifest, ids, weights, preparing;
const matrices = new Map();
function downloadProgress(event) {
  if (event.status === "progress" && event.total) progress(`Downloading ${event.file?.includes("onnx") ? "search model" : "tokenizer"}: ${Math.floor(event.progress || 0)}% of ${Math.ceil(event.total / 1048576)} MB`);
}
async function checkedFetch(path) {
  return fetchAsset(path);
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
  if (manifest.version !== 3 || manifest.ranking_policy !== "independent-evidence-v1") throw new Error("Search data is from an older release. Reload to update.");
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
    dtype: "q8", device: "wasm", ...modelOptions, revision: config.revision, progress_callback: downloadProgress, session_options,
  });
  try {
    progress("Understanding your scene");
    const output = await encoder(config.prefix + text, { pooling: config.pooling, normalize: true, truncation: true, max_length: config.max_length });
    return Float32Array.from(output.data);
  } finally { await encoder.dispose(); }
}
async function translate(text) {
  const config = manifest.translation;
  if (!config) throw new Error("This release does not include a Persian translation model.");
  progress("Loading Persian sentence understanding (additional download about 870 MB)");
  const translator = await pipeline("translation", config.model, {
    dtype: "q8", device: "wasm", ...modelOptions, revision: config.revision, progress_callback: downloadProgress, session_options,
  });
  try {
    progress("Interpreting the complete Persian description");
    const encoded = translator.tokenizer(text, { padding: false, truncation: false });
    if (encoded.input_ids.data.length > 482) throw new Error("The description is too long for sentence translation.");
    const result = await translator(text, { src_lang: config.src_lang, tgt_lang: config.tgt_lang, num_beams: 2, max_new_tokens: config.max_new_tokens });
    const sentence = result[0]?.translation_text?.trim();
    if (!sentence || !/[A-Za-z]/.test(sentence)) throw new Error("Sentence translation did not produce English text.");
    return sentence;
  } finally { await translator.dispose(); }
}
async function rerank(query, candidates, records) {
  if (!candidates.length) return candidates;
  const pairs = evidencePairs(query, candidates, records, manifest, catalog);
  if (!pairs.length) return candidates;
  progress("Loading the relevance reranker");
  const config = manifest.reranker;
  const options = { revision: config.revision, progress_callback: downloadProgress };
  const tokenizer = await AutoTokenizer.from_pretrained(config.model, options);
  const model = await AutoModelForSequenceClassification.from_pretrained(config.model, { ...options, dtype: "q8", device: "wasm", ...modelOptions, session_options });
  try {
    const scores = [];
    for (let offset = 0; offset < pairs.length; offset += 2) {
      progress(`Checking story evidence: ${Math.min(offset + 2, pairs.length)}/${pairs.length}`);
      const batch = pairs.slice(offset, offset + 2);
      const inputs = tokenizer(batch.map(() => query), { text_pair: batch.map((entry) => entry.text), padding: true, truncation: true, max_length: config.max_length });
      const result = await model(inputs);
      scores.push(...Array.from(result.logits.data));
    }
    return rankEvidence(candidates, pairs, scores);
  } finally { await model.dispose(); }
}
async function search({ query: value, source, count, translatePersian = false }) {
  if (!preparing) preparing = prepare().catch((error) => { preparing = null; throw error; });
  await preparing;
  const query = processQuery(value, manifest.processor);
  const interpretation = { language: query.persian ? "fa" : "en", translation: query.persian ? "unavailable" : "not_needed", translated_query: null };
  if (query.persian && translatePersian) {
    try {
      query.english = await translate(query.cleaned);
      query.translated = true;
      interpretation.translation = "offline";
      interpretation.translated_query = query.english;
    } catch (error) {
      interpretation.translation = "failed";
      progress("Translation unavailable; continuing with the multilingual model");
    }
  }
  if (query.persian && !query.translated) interpretation.warning = "English translation is unavailable. Search uses the original query without English reranking.";
  let english = [], multilingual = [];
  if (manifest.multilingual) {
    const vector = await encode(query.cleaned, manifest.multilingual);
    multilingual = multilingualRanks(similarities(vector, await matrix("hybrid-multilingual.f32"), manifest.multilingual.dimension), manifest.multilingual.records);
  }
  if (!query.persian || query.translated) {
    const vector = await encode(query.english || query.cleaned, manifest.english);
    english = englishRanks(similarities(vector, await matrix("hybrid-en.f32"), manifest.english.dimension), manifest.records);
  }
  const lexical = lexicalScores(query.english || query.cleaned, manifest, ids, weights);
  const originalLexical = query.translated ? lexicalScores(query.cleaned, manifest, ids, weights) : null;
  let records = fuseRecords(query, manifest, catalog, english, lexical, multilingual, source, originalLexical);
  const evidence = new Map(multilingual.map(([index, , row]) => [index, manifest.multilingual.texts?.[row] || ""]));
  records = records.map((entry) => ({ ...entry, passage: selectStoryEvidence(query.english || query.cleaned,
    manifest.records[entry.index].kind === "title" ? storyWindows(catalog[entry.item].plot) : [],
    evidence.get(entry.index) || "", manifest.processor, manifest.lexical) }));
  let candidates = collapseRecords(records);
  const reranked = !query.persian || query.translated;
  if (reranked) candidates = await rerank(query.english || query.cleaned, candidates, records);
  const results = candidates.slice(0, Math.min(20, Math.max(1, count || 8))).map((entry) => {
    const item = catalog[entry.item], scene = entry.scene === null ? null : item.scene_timeline[entry.scene];
    const record = manifest.records[entry.index], episode = record.episode == null ? null : item.episodes[record.episode];
    return { item, score: entry.score, scene, episode, evidence: scene ? scene.transcript || scene.visual_caption : episode ? record.overview : entry.passage || record.overview || item.overview || "",
      evidenceKind: scene ? "scene" : episode ? "episode" : "story", method: reranked ? "hybrid + reranker" : "multilingual + BM25" };
  });
  return { results, interpretation };
}
return { search };
}
