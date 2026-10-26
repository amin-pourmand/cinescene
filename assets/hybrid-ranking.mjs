export function normalize(value) {
  return String(value || "").replaceAll("ي", "ی").replaceAll("ك", "ک").replaceAll("\u200c", " ")
    .replace(/[۰-۹٠-٩]/g, (c) => String(c.charCodeAt(0) - (c >= "۰" ? 1776 : 1632)));
}
const escaped = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
export function tokens(value, processor) {
  const stop = new Set(processor.stopwords);
  return (normalize(value).toLowerCase().match(/[\p{L}\p{N}]+/gu) || []).map((word) => {
    if (/^[\x00-\x7F]+$/.test(word)) {
      if (word.length > 4 && word.endsWith("ies")) return word.slice(0, -3) + "y";
      if (word.length > 4 && word.endsWith("es") && "sxz".includes(word.at(-3))) return word.slice(0, -2);
      if (word.length > 3 && word.endsWith("s") && !word.endsWith("ss")) return word.slice(0, -1);
    }
    return word;
  }).filter((word) => word.length > 2 && !stop.has(word));
}
export function processQuery(value, processor) {
  const query = normalize(value).trim(), lower = query.toLowerCase();
  const filters = { genres: [], excluded: [], years: null, director: "" };
  const years = [...lower.matchAll(/(?:\b(?:from|released(?:\s+in)?|release\s+year|year)\s+|(?:محصول|ساخته شده در)\s+)(19\d{2}|20\d{2})\b/g)].map((m) => Number(m[1]));
  const range = lower.match(/\b(?:between\s+)?(19\d{2}|20\d{2})\s*(?:-|to|and)\s*(19\d{2}|20\d{2})\b/);
  if (range) years.splice(0, years.length, Number(range[1]), Number(range[2]));
  if (years.length) filters.years = [Math.min(...years), Math.max(...years)];
  for (const [alias, genre] of Object.entries(processor.genre_aliases)) {
    const pattern = new RegExp(`(?<![\\p{L}\\p{N}_])${escaped(alias)}(?![\\p{L}\\p{N}_])`, "gu");
    for (const match of lower.matchAll(pattern)) {
      const prefix = lower.slice(Math.max(0, match.index - 35), match.index);
      const negated = /(?:\b(?:no|not|without|exclude|excluding|except)\s+(?:any\s+|a\s+)?|(?:بدون|غیر|نه)\s*)$/.test(prefix);
      const target = negated ? filters.excluded : filters.genres;
      if (!target.includes(genre)) target.push(genre);
    }
  }
  filters.genres = filters.genres.filter((genre) => !filters.excluded.includes(genre));
  const director = query.match(/\bdirected by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)/);
  if (director) filters.director = director[1];
  const cleaned = query.replace(/\b(?:from|released(?:\s+in)?|release\s+year|year)\s+(?:19\d{2}|20\d{2})\b/gi, " ")
    .replace(/\bdirected by\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*/g, " ").replace(/\s+/g, " ").trim();
  const additions = [];
  for (const [phrase, synonyms] of Object.entries(processor.expansions)) {
    if (new RegExp(`(?<![\\p{L}\\p{N}_])${escaped(phrase)}(?![\\p{L}\\p{N}_])`, "u").test(cleaned.toLowerCase())) additions.push(...synonyms.slice(0, 4));
  }
  const expanded = [...new Set([cleaned, ...additions])].join(" ");
  const persian = /[\u0600-\u06ff]/u.test(cleaned);
  const concepts = persian ? expanded.split(/\s+/).filter((word) => /^[\x00-\x7F]+$/.test(word)).join(" ") : "";
  return { cleaned, expanded, filters, persian, concepts, translated: persian && tokens(concepts, processor).length >= 3 };
}
export function similarities(query, vectors, dimension) {
  if (query.length !== dimension || vectors.length % dimension) throw new Error("The query model and index dimensions differ.");
  const scores = new Float32Array(vectors.length / dimension);
  for (let i = 0; i < scores.length; i++) {
    let sum = 0;
    for (let d = 0; d < dimension; d++) sum += query[d] * vectors[i * dimension + d];
    scores[i] = sum;
  }
  return scores;
}
const ranked = (scores, limit) => [...scores.entries()].filter(([, score]) => Number.isFinite(score))
  .sort((a, b) => b[1] - a[1] || a[0] - b[0]).slice(0, limit);
export function englishRanks(scores, records) {
  const titles = ranked(scores, scores.length).filter(([i]) => records[i].kind !== "scene").slice(0, 100);
  const scenes = ranked(scores, scores.length).filter(([i]) => records[i].kind === "scene").slice(0, 100);
  return [...titles, ...scenes].sort((a, b) => b[1] - a[1] || a[0] - b[0]);
}
export function multilingualRanks(scores, mapping) {
  const best = new Map();
  for (const [row, score] of ranked(scores, 600)) {
    const record = mapping[row];
    best.set(record, Math.max(best.get(record) ?? -Infinity, score));
  }
  return [...best.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]).slice(0, 150);
}
export function lexicalScores(query, manifest, ids, weights) {
  const scores = new Float64Array(manifest.records.length), overlap = new Uint16Array(scores.length);
  const seen = new Set();
  for (const token of tokens(query, manifest.processor)) {
    const posting = manifest.lexical.terms[token];
    if (!posting) continue;
    const [start, count] = posting;
    for (let i = start; i < start + count; i++) {
      scores[ids[i]] += weights[i];
      if (!seen.has(token)) overlap[ids[i]]++;
    }
    seen.add(token);
  }
  return { ranks: ranked(scores, 100).filter(([, score]) => score > 0), overlap };
}
export function fuseAndCollapse(query, manifest, catalog, vectors, lexical, multilingual, source) {
  const totals = new Map();
  const add = (list, weight = 1) => list.forEach(([index], i) => totals.set(index, (totals.get(index) || 0) + weight / (61 + i)));
  add(vectors);
  add(lexical.ranks, query.persian && !query.translated ? .15 : 1);
  add(multilingual);
  const queryTerms = new Set(tokens(query.cleaned, manifest.processor));
  const collapsed = new Map();
  for (const [index, value] of totals) {
    const record = manifest.records[index], item = catalog[record.item];
    if (source === "offline" && item.source !== "offline_video_ingestion") continue;
    if (source === "series" && item.media_type !== "series") continue;
    if (source === "movies" && item.media_type === "series") continue;
    const genres = (item.genres || []).map((genre) => genre.replace("Science-Fiction", "Science Fiction")), f = query.filters;
    if (f.genres.length && !f.genres.some((genre) => genres.includes(genre))) continue;
    if (f.excluded.some((genre) => genres.includes(genre))) continue;
    if (f.years && (!/^\d{4}$/.test(String(item.year)) || Number(item.year) < f.years[0] || Number(item.year) > f.years[1])) continue;
    if (f.director && !String(item.director).toLowerCase().includes(f.director.toLowerCase())) continue;
    const size = Math.max(1, queryTerms.size);
    const titleOverlap = record.title_tokens.filter((word) => queryTerms.has(word)).length;
    const transcriptOverlap = record.transcript_tokens.filter((word) => queryTerms.has(word)).length;
    let score = value + .008 * titleOverlap / size;
    if (!query.persian) score += .008 * lexical.overlap[index] / size;
    if (record.kind === "scene" && transcriptOverlap >= 2 && transcriptOverlap / size >= .65) score += .018 * transcriptOverlap / size;
    const previous = collapsed.get(record.item);
    const bestScene = record.scene !== null && score > (previous?.sceneScore ?? -Infinity);
    const scene = bestScene ? record.scene : previous?.scene ?? null;
    const sceneScore = bestScene ? score : previous?.sceneScore ?? -Infinity;
    if (!previous || score > previous.score) collapsed.set(record.item, { index, item: record.item, score, scene, sceneScore });
    else if (bestScene) Object.assign(previous, { scene, sceneScore });
  }
  return [...collapsed.values()].sort((a, b) => b.score - a.score || a.index - b.index);
}
export function rerankingText(candidate, records, catalog) {
  const record = records[candidate.index], item = catalog[record.item];
  let text = `${item.title}. ${record.overview ?? item.overview ?? ""}`;
  const scene = candidate.scene === null ? null : item.scene_timeline?.[candidate.scene];
  if (scene) text += ` Scene: ${scene.transcript || ""} ${scene.visual_caption || ""}`;
  return text;
}
export function relevanceConsensus(candidates, scores) {
  const order = scores.map((score, i) => [i, score]).sort((a, b) => b[1] - a[1]);
  const ranks = new Map(order.map(([i], rank) => [i, rank + 1]));
  return candidates.map((entry, i) => ({ ...entry, score: 2 / (60 + ranks.get(i)) + 1 / (61 + i) }))
    .sort((a, b) => b.score - a.score);
}
