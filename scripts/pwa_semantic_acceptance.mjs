import { readFile, mkdir, writeFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import { createSearchRuntime } from "../docs/assets/search-runtime.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const { values } = parseArgs({ options: { output: { type: "string" }, limit: { type: "string", default: "26" } } });
const modulePath = process.env.CINESCENE_TRANSFORMERS_MODULE;
const cache = process.env.CINESCENE_MODEL_CACHE;
if (!modulePath || !cache || !values.output) throw new Error("Set CINESCENE_TRANSFORMERS_MODULE, CINESCENE_MODEL_CACHE and --output explicitly.");
if (process.platform === "win32" && /^[Cc]:[\\/]/.test(cache)) throw new Error("Model acceptance caches must stay off C.");
const { pipeline, AutoTokenizer, AutoModelForSequenceClassification, env } = await import(pathToFileURL(resolve(modulePath)).href);
env.cacheDir = resolve(cache);
env.allowLocalModels = false;
await mkdir(env.cacheDir, { recursive: true });
const manifest = JSON.parse(await readFile(resolve(root, "docs/data/hybrid-index.json"), "utf8"));
const suite = JSON.parse(await readFile(resolve(root, "benchmarks/recent-movie-scenarios.json"), "utf8"));
const cases = suite.topics.flatMap((item) => ["en", "fa"].map((language) => ({ query: item[language], language, id: String(item.target_id), title: item.title })));
const limit = Math.min(cases.length, Math.max(1, Number(values.limit) || 26));
const report = { generated_at: new Date().toISOString(), runtime: "Shared production JavaScript runtime; Node CPU int8 kernels, not browser WASM latency",
  limitations: "Manual development cohort; previously inspected cases, not held-out or population accuracy. Private uploads are absent from public artifacts. Browser/device performance can differ.",
  index_generation: manifest.index_generation, fusion_version: manifest.fusion_version, ranking_policy: manifest.ranking_policy,
  planned: limit, completed: 0, technical_errors: 0, reduced_capability: 0, rows: [] };
const runtime = createSearchRuntime({ pipeline, AutoTokenizer, AutoModelForSequenceClassification,
  modelOptions: { device: "cpu" },
  async fetchAsset(path) { const bytes = await readFile(new URL(path, new URL("../docs/assets/search-runtime.mjs", import.meta.url))); return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength); },
  progress(message) { if (!message.startsWith("Downloading")) console.log(message); },
});
await mkdir(dirname(resolve(values.output)), { recursive: true });
for (const item of cases.slice(0, limit)) {
  const row = { ...item, rank: null, top_3: [], interpretation: null, error: null };
  const started = performance.now();
  try {
    const result = await runtime.search({ query: item.query, source: "all", count: 10, translatePersian: item.language === "fa" });
    const rank = result.results.findIndex((entry) => String(entry.item.id) === item.id);
    row.rank = rank < 0 ? null : rank + 1;
    row.top_3 = result.results.slice(0, 3).map((entry) => ({ id: entry.item.id, title: entry.item.title }));
    row.interpretation = result.interpretation;
    if (result.interpretation.warning) report.reduced_capability++;
  } catch (error) { row.error = error.name + ": " + error.message; report.technical_errors++; }
  row.elapsed_sec = Math.round((performance.now() - started) / 10) / 100;
  report.rows.push(row);
  report.completed++;
  report.hit_at_1 = report.rows.filter((entry) => entry.rank === 1).length / report.completed;
  report.hit_at_5 = report.rows.filter((entry) => entry.rank !== null && entry.rank <= 5).length / report.completed;
  await writeFile(resolve(values.output), JSON.stringify(report, null, 2));
  console.log(`[${report.completed}/${limit}] ${item.language} ${item.title}: rank=${row.rank} error=${Boolean(row.error)}`);
  if (row.error) break;
}
if (report.completed !== limit || report.technical_errors || report.reduced_capability) process.exitCode = 1;
