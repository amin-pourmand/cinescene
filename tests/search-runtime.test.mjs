import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createSearchRuntime } from "../docs/assets/search-runtime.mjs";

const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
function fixture({ translationError = false } = {}) {
  const calls = [];
  const catalog = Buffer.from(JSON.stringify({ items: [{ id: 1, title: "Example", overview: "A witness hides a letter", plot: "A witness hides a letter", scene_timeline: [] }] }));
  const english = Buffer.from(new Float32Array([1, 0]).buffer);
  const multilingual = Buffer.from(new Float32Array([1, 0]).buffer);
  const lexical = Buffer.from(new Uint8Array(0));
  const assets = { "catalog.sample.json": catalog, "hybrid-en.f32": english, "hybrid-multilingual.f32": multilingual, "hybrid-lexical.bin": lexical };
  const manifest = { version: 3, ranking_policy: "independent-evidence-v1", catalog_sha256: digest(catalog), files: Object.fromEntries(Object.entries(assets).filter(([name]) => name !== "catalog.sample.json").map(([name, bytes]) => [name, { bytes: bytes.length, sha256: digest(bytes) }])),
    english: { model: "english", dimension: 2, prefix: "instruction: ", pooling: "cls" },
    multilingual: { model: "multilingual", dimension: 2, prefix: "query: ", pooling: "mean", records: [0], texts: ["A witness hides a letter"] },
    translation: { model: "translation", src_lang: "pes_Arab", tgt_lang: "eng_Latn", max_new_tokens: 320 }, reranker: { model: "reranker", max_length: 384 },
    lexical: { postings: 0, terms: {} }, processor: { stopwords: [], expansions: { "نامه": ["letter", "hidden", "witness"] }, genre_aliases: {} },
    records: [{ item: 0, kind: "title", scene: null, episode: null, overview: "A witness hides a letter", title_tokens: [], transcript_tokens: [] }] };
  assets["hybrid-index.json"] = Buffer.from(JSON.stringify(manifest));
  const runtime = createSearchRuntime({
    async fetchAsset(path) { const b = assets[path.split("/").at(-1)]; assert.ok(b, path); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); },
    async pipeline(task, model) {
      calls.push(["load", model]);
      if (task === "translation" && translationError) throw new Error("test translator failure");
      const pipeline = async (text, options) => {
        calls.push([model, text, options]);
        return task === "translation" ? [{ translation_text: "A witness hides a letter" }] : { data: [1, 0] };
      };
      pipeline.tokenizer = () => ({ input_ids: { data: [1, 2] } });
      pipeline.dispose = async () => calls.push(["dispose", model]);
      return pipeline;
    },
    AutoTokenizer: { async from_pretrained() { return (query, options) => ({ query, text: options.text_pair }); } },
    AutoModelForSequenceClassification: { async from_pretrained() { const model = async (input) => ({ logits: { data: input.text.map(() => 4) } }); model.dispose = async () => calls.push(["dispose", "reranker"]); return model; } },
  });
  return { runtime, calls, assets };
}
test("complete Persian translation, not generated keywords, reaches the English encoder", async () => {
  const { runtime, calls } = fixture();
  const query = "یک شاهد نامه را پنهان می کند";
  const result = await runtime.search({ query, translatePersian: true, count: 5, source: "all" });
  assert.equal(result.interpretation.translated_query, "A witness hides a letter");
  assert.equal(result.results[0].item.id, 1);
  assert.ok(calls.some(([model, text]) => model === "translation" && text === query));
  assert.ok(calls.some(([model, text]) => model === "multilingual" && text === "query: " + query));
  assert.ok(calls.some(([model, text]) => model === "english" && text === "instruction: A witness hides a letter"));
  assert.ok(calls.some(([event, model]) => event === "dispose" && model === "translation"));
});
test("failed or disabled translation remains explicit and never invokes the English encoder", async () => {
  for (const disabled of [false, true]) {
    const { runtime, calls } = fixture({ translationError: true });
    const result = await runtime.search({ query: "یک شاهد نامه را پنهان می کند", translatePersian: !disabled, source: "all" });
    assert.ok(result.interpretation.warning);
    assert.equal(result.interpretation.translation, disabled ? "unavailable" : "failed");
    assert.ok(!calls.some(([model]) => model === "english"));
    assert.equal(result.results[0].method, "multilingual + BM25");
  }
});
test("mismatched catalog bytes fail before model downloads", async () => {
  const { runtime, calls, assets } = fixture();
  assets["catalog.sample.json"] = Buffer.from("{}");
  await assert.rejects(runtime.search({ query: "a scene" }), /versions differ/);
  assert.equal(calls.length, 0);
});
