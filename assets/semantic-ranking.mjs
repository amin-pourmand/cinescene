export function eligible(item, source) {
  return source === "offline" ? item.source === "offline_video_ingestion"
    : source === "series" ? item.media_type === "series"
    : source === "movies" ? item.media_type !== "series" : true;
}

export function relevanceText(item, evidence = "") {
  const title = String(item.title || "Untitled");
  const overview = String(item.overview || "").trim();
  const parts = [`Title: ${title}.`, `Genres: ${(item.genres || []).join(", ")}.`, `Keywords: ${(item.keywords || []).slice(0, 18).join(", ")}.`];
  const summaryPassage = `${title} (${item.year ?? ""}). ${overview}`;
  if (evidence && evidence !== summaryPassage) parts.push(`Evidence: ${evidence}`);
  if (overview) parts.push(`Plot: ${overview}`);
  return parts.join(" ");
}

export function nearestTitles(query, vectors, manifest, items, source = "all", count = 40) {
  const dimension = manifest.dimension;
  if (query.length !== dimension || vectors.length !== manifest.passages.length * dimension) {
    throw new Error("Search index dimensions do not match the encoder.");
  }
  const titles = new Map();
  for (let row = 0; row < manifest.passages.length; row++) {
    const passage = manifest.passages[row];
    const item = items[passage.item];
    if (!item || !eligible(item, source)) continue;
    let score = 0;
    for (let d = 0; d < dimension; d++) score += query[d] * vectors[row * dimension + d];
    if (!Number.isFinite(score)) continue;
    const previous = titles.get(passage.item);
    // Max-pool rather than sum: long plots must not win by document count alone.
    if (!previous || score > previous.score) titles.set(passage.item, { index: passage.item, row, score });
  }
  return [...titles.values()].sort((a, b) => b.score - a.score || a.index - b.index).slice(0, count);
}

export function rerankCandidates(candidates, scores) {
  if (candidates.length !== scores.length || scores.some((score) => !Number.isFinite(score))) {
    throw new Error("The reranker returned an invalid score batch.");
  }
  return candidates.map((entry, i) => ({ ...entry, semanticScore: entry.score, score: scores[i] }))
    .sort((a, b) => b.score - a.score || a.index - b.index);
}

export function fuseVerification(candidates, scores) {
  const order = candidates.map((_, i) => i).sort((a, b) => scores[b] - scores[a]);
  const ranks = new Map(order.map((index, i) => [index, i + 1]));
  return candidates.map((row, i) => ({ ...row, score: 1 / (61 + i) + 1 / (60 + ranks.get(i)), method: "rank-fusion" }))
    .sort((a, b) => b.score - a.score);
}
