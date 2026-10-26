import test from "node:test";
import assert from "node:assert/strict";
import { nearestTitles, rerankCandidates, relevanceText } from "../docs/assets/semantic-ranking.mjs";

const items = [{ id: 1, media_type: "movie" }, { id: 2, media_type: "series" }];
const manifest = { dimension: 2, passages: [{ item: 0 }, { item: 0 }, { item: 1 }] };
const vectors = new Float32Array([0.5, 0, 0.5, 0, 0.8, 0]);

test("many weak passages cannot outvote one strong match", () => {
  assert.deepEqual(nearestTitles([1, 0], vectors, manifest, items).map((row) => row.index), [1, 0]);
});
test("type filter applies before the candidate limit", () => {
  assert.equal(nearestTitles([1, 0], vectors, manifest, items, "movies", 1)[0].index, 0);
});
test("invalid dimensions fail visibly", () => {
  assert.throws(() => nearestTitles([1], vectors, manifest, items), /dimensions/);
});
test("reranker order replaces rather than mixes score scales", () => {
  assert.equal(rerankCandidates([{ index: 0, score: 0.9 }, { index: 1, score: 0.8 }], [-8, 2])[0].index, 1);
  assert.throws(() => rerankCandidates([{ index: 0 }], [NaN]), /invalid/);
});
test("ranking evidence includes metadata without repeating its synopsis", () => {
  const item = { title: "Example", year: "2020", genres: ["Drama"], keywords: ["memory"], overview: "A short plot." };
  const text = relevanceText(item, "Example (2020). A short plot.");
  assert.equal(text.split("A short plot.").length - 1, 1);
  assert.equal(text, "Title: Example. Genres: Drama. Keywords: memory. Plot: A short plot.");
});
