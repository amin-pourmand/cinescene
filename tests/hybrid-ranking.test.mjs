import test from "node:test";
import assert from "node:assert/strict";
import { normalize, tokens, processQuery, lexicalScores, fuseAndCollapse, collapseRecords, evidencePairs, rankEvidence, similarities, rerankingText, relevanceConsensus, storyWindows, selectStoryEvidence } from "../docs/assets/hybrid-ranking.mjs";

const processor = { stopwords: ["the"], expansions: { "جنگ": ["war"], "هکر": ["hacker", "computer", "simulation"] }, genre_aliases: { horror: "Horror" } };
test("normalization, boundaries and narrative dates match native intent", () => {
  assert.equal(normalize("۲۰۱۴ ك ي"), "2014 ک ی");
  assert.deepEqual(tokens("the stories soldiers", processor), ["story", "soldier"]);
  assert.equal(processQuery("جنگل", processor).expanded, "جنگل");
  assert.equal(processQuery("a soldier fights in 1944", processor).filters.years, null);
  assert.deepEqual(processQuery("from 2014 without horror", processor).filters.excluded, ["Horror"]);
  assert.equal(processQuery("هکر", processor).translated, false);
  assert.equal(processQuery("هکری", processor).english, null);
  assert.deepEqual(processQuery("a horror in his past", processor).filters.genres, []);
  assert.deepEqual(processQuery("horror movies", processor).filters.genres, ["Horror"]);
});
test("independent evidence reserves a second record and does not merge incompatible passages", () => {
  const catalog = [{title:"A show",overview:"Series context"},{title:"Other"}];
  const manifest = {processor,records:[{item:0,kind:"episode",episode:0,overview:"An ordinary event"},
    {item:0,kind:"episode",episode:1,overview:"The hidden clockwork bird"},{item:1,kind:"title",overview:"A different event"}]};
  const records = [{index:0,item:0,score:.04,scene:null},{index:1,item:0,score:.03,scene:null},{index:2,item:1,score:.02,scene:null}];
  const candidates = collapseRecords(records);
  const pairs = evidencePairs("clockwork bird",candidates,records,manifest,catalog);
  assert.equal(pairs.length,3);
  assert.ok(pairs.some((row)=>row.index===1));
  assert.ok(!pairs.some((row)=>row.text.includes("ordinary event") && row.text.includes("clockwork bird")));
  const ranked = rankEvidence(candidates,pairs,[-5,8,-2]);
  assert.equal(ranked[0].index,1);
});
test("a verified story winner cannot inherit an unverified scene", () => {
  const catalog = [{title:"Example",overview:"A witness hides a letter",plot:"A witness hides a letter",scene_timeline:[{transcript:"Unrelated scene"}]}];
  const manifest = {processor,records:[{item:0,kind:"title",overview:catalog[0].overview},{item:0,kind:"scene",scene:0}]};
  const rows = [{index:0,item:0,score:.04,scene:null},{index:1,item:0,score:.03,scene:0}];
  const candidates = collapseRecords(rows);
  const pairs = evidencePairs("hidden letter",candidates,rows,manifest,catalog);
  const ranked = rankEvidence(candidates,pairs,[5,-5]);
  assert.equal(ranked[0].scene,null);
  assert.throws(()=>rankEvidence(candidates,pairs,[1]),/invalid scores/);
});
test("BM25 repeated terms accumulate but evidence overlap is unique", () => {
  const manifest = { processor, records: [{}, {}], lexical: { terms: { soldier: [0, 2] } } };
  const result = lexicalScores("soldiers soldiers", manifest, new Uint32Array([0, 1]), new Float32Array([1, 2]));
  assert.deepEqual(result.ranks, [[1, 4], [0, 2]]);
  assert.deepEqual([...result.overlap], [1, 1]);
});
test("max pooling cannot reward many scenes; strongest scene is retained", () => {
  const records = [0, 1, 2].map((scene) => ({ item: 0, scene, kind: "scene", title_tokens: [], transcript_tokens: [] }));
  records.push({ item: 1, scene: null, kind: "title", title_tokens: [], transcript_tokens: [] });
  const query = processQuery("remembered moment", processor);
  const result = fuseAndCollapse(query, { processor, records }, [{}, {}], [[3, 1], [2, .9], [0, .8], [1, .7]], { ranks: [], overlap: new Uint16Array(4) }, [], "all");
  assert.equal(result.length, 2);
  assert.equal(result[0].item, 1);
  assert.equal(result[1].scene, 2);
});
test("episode reranking uses episode evidence rather than unrelated parent summary", () => {
  assert.equal(rerankingText({ index: 0, scene: null }, [{ item: 0, overview: "A fly in the lab." }], [{ title: "Show", overview: "The series synopsis" }]), "Show. A fly in the lab.");
});
test("retrieved passage and parent context survive reranking", () => {
  const text = rerankingText({ index: 0, scene: null, passage: "A detailed event." },
    [{ item: 0, kind: "episode", overview: "An episode event." }], [{ title: "Show", overview: "Series premise." }]);
  assert.match(text, /Series premise/);
  assert.match(text, /A detailed event/);
});
test("full story selection preserves a later clue rather than only opening sentences", () => {
  const plot = "Ordinary opening events. ".repeat(50) + "A detective discovers a rare clockwork bird hidden in a cupboard.";
  const windows = storyWindows(plot);
  assert.ok(windows.length > 1);
  assert.match(selectStoryEvidence("clockwork bird cupboard", windows, "An ordinary opening.", processor), /clockwork bird/);
});
test("vector dimension mismatch is a visible error", () => {
  assert.throws(() => similarities([1], new Float32Array(4), 2), /dimensions/);
});
test("relevance consensus preserves retrieval evidence and uses ranks, not logit scale", () => {
  const rows = [{ item: 0 }, { item: 1 }, { item: 2 }];
  assert.deepEqual(relevanceConsensus(rows, [-8, -1, -2]).map((row) => row.item), [1, 0, 2]);
  assert.deepEqual(relevanceConsensus(rows, [2, 100, 90]).map((row) => row.item), [1, 0, 2]);
});
