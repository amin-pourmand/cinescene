function storedArray(name) { try { const value = JSON.parse(localStorage.getItem(name) || "[]"); return Array.isArray(value) ? value : []; } catch (_) { return []; } }

const state = {
  catalog: [],
  history: storedArray("cinescene-pwa-history"),
  favorites: storedArray("cinescene-pwa-favorites"),
  installPrompt: null,
  selectedVideo: null,
  selectedVideoUrl: "",
  query: "",
  results: [],
};

const ids = [
  "viewTitle", "mobileMenuButton", "installButton", "statusDot", "sidebarStatus", "sidebarModel",
  "metricCatalog", "metricIndexed", "metricOffline", "metricScenes", "metricLatency", "queryInput",
  "topKInput", "sourceFilter", "searchButton", "clearButton", "resultMeta", "results", "statusPill",
  "sceneTimeline", "historyList", "favoriteList", "videoDropZone", "videoInput", "videoDropTitle",
  "videoDropMeta", "chooseVideoButton", "selectedVideo", "removeVideoButton",
  "previewVideoButton", "playerDialog", "scenePlayer", "playerTitle", "playerTimecode", "playerCaption",
  "closePlayerButton", "toastRegion",
  "recentSearches", "shareSearchButton", "clearHistoryButton",
];
const els = Object.fromEntries(ids.map((id) => [id, document.getElementById(id)]));
const ui = window.CineSceneUI;
const navigation = ui.navigation();
ui.memoryTabs();

const persianExpansions = {
  "کارآگاه": "detective investigation mystery",
  "کارآگاهی": "detective investigation mystery",
  "تنها": "lonely alone isolated",
  "تاریک": "dark shadow night",
  "اتاق": "room interior",
  "سرنخ": "clue mystery investigation",
  "فضا": "space science fiction",
  "فضایی": "space science fiction alien",
  "رویا": "dream surreal mind bending",
  "خواب": "dream surreal",
  "عاشقانه": "romance romantic love",
  "ترسناک": "horror frightening supernatural",
  "تعقیب": "chase pursuit action",
  "باران": "rain rainy",
  "جنگ": "war battle soldiers",
  "دریا": "ocean sea water",
  "کودک": "child children family",
};

function refreshIcons(root = document) {
  if (window.lucide?.createIcons) window.lucide.createIcons({ root });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .replaceAll("ي", "ی")
    .replaceAll("ك", "ک")
    .replaceAll("\u200c", " ")
    .replace(/[^\p{L}\p{N}\s-]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function expandedQuery(query) {
  const normalized = normalizeText(query);
  const expansions = [];
  for (const [term, replacement] of Object.entries(persianExpansions)) {
    if (normalized.includes(term)) expansions.push(replacement);
  }
  return `${normalized} ${expansions.join(" ")}`.trim();
}

function tokenize(value) {
  return [...new Set(expandedQuery(value).split(/\s+/).filter((token) => token.length > 2))];
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function timecode(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds || 0)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  return hours
    ? `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function saveMemory() {
  localStorage.setItem("cinescene-pwa-history", JSON.stringify(state.history.slice(0, 24)));
  localStorage.setItem("cinescene-pwa-favorites", JSON.stringify(state.favorites.slice(0, 36)));
}

function toast(message, type = "info") {
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.textContent = message;
  els.toastRegion.appendChild(item);
  window.setTimeout(() => item.remove(), 4200);
}

function setView(view, updateHash = true) {
  const next = ["discover", "scenes", "library", "system"].includes(view) ? view : "discover";
  document.querySelectorAll(".view").forEach((item) => item.classList.toggle("active", item.dataset.view === next));
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.viewLink === next));
  const titles = { discover: "Search", scenes: "Videos", library: "Saved & history", system: "Settings" };
  els.viewTitle.textContent = titles[next];
  navigation.close();
  document.querySelectorAll(".nav-item").forEach((item) => { if (item.dataset.viewLink === next) item.setAttribute("aria-current", "page"); else item.removeAttribute("aria-current"); });
  if (updateHash) history.replaceState(null, "", `#${next}`);
  if (next === "library") renderMemory();
}

function setStatus(message, ok = true) {
  els.statusPill.textContent = message;
  els.statusPill.className = `status-pill ${ok ? "ok" : "warn"}`;
  els.statusDot.className = `status-dot ${ok ? "ok" : "error"}`;
  els.sidebarStatus.textContent = message;
}

function sourceLabel(item) {
  return item.source === "offline_video_ingestion" ? "Scene match" : "Story match";
}

function mediaLabel(item) {
  if (item.media_type === "series" && item.season && item.episode) {
    return `Series S${String(item.season).padStart(2, "0")}E${String(item.episode).padStart(2, "0")}`;
  }
  return item.media_type === "series" ? "Series" : "Movie";
}

function sceneText(scene) {
  return normalizeText([
    scene.visual_caption,
    scene.transcript,
    ...(scene.mood_tags || []),
    ...(scene.keywords || []),
    ...(scene.visual_tags || []),
  ].join(" "));
}

function scoreText(text, terms, weight = 1) {
  let score = 0;
  for (const term of terms) {
    if (text.includes(term)) score += weight;
  }
  return score;
}

function bestScene(item, terms) {
  let best = null;
  let bestScore = 0;
  for (const scene of item.scene_timeline || []) {
    const transcript = normalizeText(scene.transcript);
    const visual = normalizeText(`${scene.visual_caption || ""} ${(scene.visual_tags || []).join(" ")}`);
    const tags = normalizeText(`${(scene.keywords || []).join(" ")} ${(scene.mood_tags || []).join(" ")}`);
    const score = scoreText(transcript, terms, 3.1) + scoreText(visual, terms, 2.6) + scoreText(tags, terms, 1.8);
    if (score > bestScore) {
      best = scene;
      bestScore = score;
    }
  }
  return { scene: best, score: bestScore };
}

function scoreItem(item, query) {
  const terms = tokenize(query);
  if (!terms.length) return { score: 0, scene: null };
  const title = normalizeText(item.title);
  const overview = normalizeText(item.overview);
  const genres = normalizeText((item.genres || []).join(" "));
  const moods = normalizeText((item.mood || []).join(" "));
  const keywords = normalizeText((item.keywords || []).join(" "));
  const scenes = normalizeText((item.scenes || []).join(" "));
  const match = bestScene(item, terms);
  let score = match.score;
  score += scoreText(title, terms, 4.2);
  score += scoreText(scenes, terms, 2.4);
  score += scoreText(keywords, terms, 2.0);
  score += scoreText(moods, terms, 1.8);
  score += scoreText(genres, terms, 1.5);
  score += scoreText(overview, terms, 1.2);
  if (score === 0) return { score: 0, scene: null };
  score += Math.min(1.8, Number(item.rating || 0) / 5);
  if (item.source === "offline_video_ingestion" && match.score >= 4) score += 5;
  return { score, scene: match.scene };
}

function searchCatalog(query) {
  const source = els.sourceFilter.value;
  const topK = Number(els.topKInput.value || 8);
  return state.catalog
    .filter((item) => {
      if (source === "all") return true;
      if (source === "offline") return item.source === "offline_video_ingestion";
      if (source === "series") return item.media_type === "series";
      if (source === "movies") return item.media_type !== "series";
      return true;
    })
    .map((item) => ({ item, ...scoreItem(item, query) }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);
}

function chips(items, limit = 7) {
  return (items || []).slice(0, limit).map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("");
}

function renderResults(entries, query, elapsedMs) {
  state.results = entries;
  state.history = [{ query, at: new Date().toISOString(), count: entries.length }, ...state.history.filter((entry) => entry.query !== query)].slice(0, 24);
  saveMemory();
  ui.recent(els.recentSearches, state.history.map((item) => item.query));
  els.metricLatency.textContent = `${elapsedMs.toFixed(0)}ms`;
  els.resultMeta.textContent = entries.length ? `${entries.length} ranked titles` : "No matches";
  if (!entries.length) {
    els.results.className = "results-grid empty-results";
    els.results.innerHTML = `<div class="empty-visual"><i data-lucide="circle-slash-2"></i></div><strong>No close match in the public sample.</strong><span>Try a dialogue fragment, location, action, or mood.</span>`;
    refreshIcons(els.results);
    return;
  }

  els.results.className = "results-grid";
  els.results.innerHTML = entries.map(({ item, score, scene }, index) => {
    const image = scene?.keyframe || item.poster;
    const media = image
      ? `<div class="result-media"><img src="./${escapeHtml(image)}" alt="Keyframe from ${escapeHtml(item.title)}" loading="lazy" /><span class="result-rank">Rank ${index + 1}</span><span class="result-source">${escapeHtml(sourceLabel(item))}</span></div>`
      : `<div class="catalog-result-header"><i data-lucide="${item.media_type === "series" ? "tv" : "film"}"></i><b>Rank ${index + 1}</b><span class="catalog-source">${escapeHtml(sourceLabel(item))}</span></div>`;
    const sceneCopy = scene?.transcript || scene?.visual_caption || (item.scenes || [])[0] || "No scene transcript is available in the public sample.";
    const tags = [...new Set([...(scene?.mood_tags || []), ...(item.genres || []), ...(item.mood || [])])].slice(0, 3);
    return `<article class="result-card ${image ? "has-frame" : "catalog-only"}">
      ${media}
      <div class="result-body">
        <div class="result-title-row"><div><button class="title-link" data-details="${index}" type="button">${escapeHtml(item.title)}</button><small>${escapeHtml(mediaLabel(item))}${ui.known(item.year) ? ` &middot; ${escapeHtml(item.year)}` : ""}${item.director && item.director !== "Unknown" ? ` &middot; ${escapeHtml(item.director)}` : ""}</small></div></div>
        ${item.source === "offline_video_ingestion" ? "" : `<p class="result-overview">${escapeHtml(item.overview || "")}</p>`}
        ${scene ? `<div class="matched-scene"><div class="scene-label"><span>Best matching scene</span><time>${timecode(scene.start_sec)} - ${timecode(scene.end_sec)}</time></div><p dir="auto">${escapeHtml(sceneCopy)}</p></div>` : ""}
        <div class="chip-row">${chips(tags)}</div>
        <div class="result-actions">
          <button class="button secondary" type="button" data-details="${index}"><i data-lucide="info"></i>Details</button>
          ${item.source === "offline_video_ingestion" ? `<button class="icon-button ghost" type="button" data-open-media="${escapeHtml(item.id)}" title="Explore scenes" aria-label="Explore scenes"><i data-lucide="list-video"></i></button>` : ""}
          <button class="icon-button ghost" type="button" data-favorite="${escapeHtml(item.id)}" aria-pressed="${isSaved(item)}" title="${isSaved(item) ? "Remove from saved" : "Save title"}" aria-label="${isSaved(item) ? "Remove from saved" : "Save title"}"><i data-lucide="bookmark"></i></button>
        </div>
      </div>
    </article>`;
  }).join("");
  refreshIcons(els.results);

}

function runSearch(queryOverride) {
  const query = String(queryOverride || els.queryInput.value).trim();
  if (!query) {
    toast("Describe a scene first.", "error");
    els.queryInput.focus();
    return;
  }
  setView("discover");
  state.query = query;
  ui.searchState(query, els.sourceFilter.value, els.topKInput.value);
  els.shareSearchButton.disabled = false;
  els.queryInput.value = query;
  els.resultMeta.textContent = "Searching scene memory";
  const start = performance.now();
  const entries = searchCatalog(query);
  renderResults(entries, query, performance.now() - start);
}

function renderMemory() {
  els.historyList.innerHTML = state.history.length
    ? state.history.map((item) => `<article class="memory-row"><button type="button" data-query="${escapeHtml(item.query)}"><strong dir="auto">${escapeHtml(item.query)}</strong><span>${item.count} results &middot; ${escapeHtml(ui.formatDate(item.at))}</span></button><i data-lucide="arrow-up-right"></i></article>`).join("")
    : `<div class="empty-inline">No search history yet.</div>`;
  els.favoriteList.innerHTML = state.favorites.length
    ? state.favorites.map((item, index) => `<article class="memory-row"><button type="button" data-open-saved="${index}"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(mediaLabel(item))}${ui.known(item.year) ? ` &middot; ${escapeHtml(item.year)}` : ""}</span></button><button class="icon-button ghost" type="button" data-remove-saved="${index}" title="Remove from saved" aria-label="Remove ${escapeHtml(item.title)} from saved"><i data-lucide="bookmark-minus"></i></button></article>`).join("")
    : `<div class="empty-inline">No saved titles yet.</div>`;
  els.clearHistoryButton.disabled = !state.history.length;
  ui.recent(els.recentSearches, state.history.map((item) => item.query));
  refreshIcons();
}

function renderTimeline() {
  const offline = state.catalog.filter((item) => item.source === "offline_video_ingestion");
  if (!offline.length) {
    els.sceneTimeline.className = "media-timeline empty-inline";
    els.sceneTimeline.textContent = "No processed scene records are bundled in this public build.";
    return;
  }
  els.sceneTimeline.className = "media-timeline";
  els.sceneTimeline.innerHTML = offline.map((item) => {
    const frame = item.poster || item.scene_timeline?.find((scene) => scene.keyframe)?.keyframe;
    return `<article class="video-library-item">${frame ? `<img src="./${escapeHtml(frame)}" alt="Scene from ${escapeHtml(item.title)}" loading="lazy" />` : ""}<div class="video-library-copy"><h4>${escapeHtml(item.title)}</h4><p>${escapeHtml(mediaLabel(item))} &middot; ${item.scene_count || 0} scenes</p></div><button class="button secondary compact" data-open-media="${escapeHtml(item.id)}" type="button"><i data-lucide="list-video"></i>Explore scenes</button></article>`;
  }).join("");
  refreshIcons(els.sceneTimeline);
}

function selectVideo(file) {
  if (!file || (!file.type.startsWith("video/") && !/\.(mp4|mkv|avi|mov|webm|m4v|wmv)$/i.test(file.name))) {
    toast("Choose a supported video file.", "error");
    return;
  }
  state.selectedVideo = file;
  els.selectedVideo.hidden = false;
  els.selectedVideo.querySelector("strong").textContent = file.name;
  els.selectedVideo.querySelector("span").textContent = `${formatBytes(file.size)} - remains on this device`;
  els.videoDropTitle.textContent = "Video ready to preview";
  els.videoDropMeta.textContent = file.name;
  els.previewVideoButton.disabled = false;
}

function clearVideo() {
  state.selectedVideo = null;
  els.videoInput.value = "";
  els.selectedVideo.hidden = true;
  els.videoDropTitle.textContent = "Drop a video here";
  els.videoDropMeta.textContent = "MP4, MKV, MOV, AVI, WEBM";
  els.previewVideoButton.disabled = true;
  if (state.selectedVideoUrl) URL.revokeObjectURL(state.selectedVideoUrl);
  state.selectedVideoUrl = "";
}

function previewVideo() {
  if (!state.selectedVideo) return;
  if (state.selectedVideoUrl) URL.revokeObjectURL(state.selectedVideoUrl);
  state.selectedVideoUrl = URL.createObjectURL(state.selectedVideo);
  els.scenePlayer.src = state.selectedVideoUrl;
  els.playerTitle.textContent = state.selectedVideo.name;
  els.playerDialog.showModal();
  els.scenePlayer.play().catch(() => {});
}

async function loadCatalog() {
  try {
    const response = await fetch("./data/catalog.sample.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`Catalog HTTP ${response.status}`);
    const payload = await response.json();
    state.catalog = payload.items || [];
    const offline = state.catalog.filter((item) => item.source === "offline_video_ingestion");
    const seriesCount = state.catalog.filter((item) => item.media_type === "series").length;
    const sceneCount = offline.reduce((sum, item) => sum + Number(item.scene_count || (item.scene_timeline || []).length), 0);
    els.metricCatalog.textContent = state.catalog.length.toLocaleString();
    els.metricIndexed.textContent = state.catalog.length.toLocaleString();
    els.metricOffline.textContent = seriesCount.toLocaleString();
    els.metricScenes.textContent = sceneCount.toLocaleString();
    els.sidebarModel.textContent = `${sceneCount.toLocaleString()} scene records cached`;
    setStatus("Showcase ready", true);
    renderTimeline();
    renderMemory();
    const shared = ui.readSearch();
    if ([...els.sourceFilter.options].some((option) => option.value === shared.type)) els.sourceFilter.value = shared.type;
    els.topKInput.value = (!location.hash || location.hash === "#discover") && new URL(location.href).searchParams.has("count") ? shared.count : Math.min(20, Math.max(1, Number(localStorage.getItem("cinescene-pwa-results-count")) || 8));
    if (shared.query) {
      els.queryInput.value = shared.query;
      if (!location.hash || location.hash === "#discover") runSearch(shared.query);
    }
  } catch (error) {
    setStatus("Catalog unavailable", false);
    els.resultMeta.textContent = "Load error";
    els.results.className = "results-grid empty-results";
    els.results.innerHTML = `<div class="empty-visual"><i data-lucide="triangle-alert"></i></div><strong>Could not load the public catalog.</strong><span>${escapeHtml(error.message)}</span>`;
    refreshIcons(els.results);
  }
}

document.addEventListener("click", (event) => {
  const viewLink = event.target.closest("[data-view-link]");
  const queryLink = event.target.closest("[data-query]");
  const details = event.target.closest("[data-details]");
  const favorite = event.target.closest("[data-favorite]");
  if (viewLink) {
    event.preventDefault();
    setView(viewLink.dataset.viewLink);
  }
  if (queryLink) runSearch(queryLink.dataset.query);
  if (details) { const entry = state.results[Number(details.dataset.details)]; if (entry) state.details.open(asMovie(entry.item, entry.scene)); }
  if (favorite) {
    const item = state.catalog.find((entry) => String(entry.id) === favorite.dataset.favorite);
    if (item) { try { toggleFavorite(item); } catch (error) { toast(error.message, "error"); } }
  }
  const saved = event.target.closest("[data-open-saved]");
  const remove = event.target.closest("[data-remove-saved]");
  if (saved) state.details.open(asMovie(state.favorites[Number(saved.dataset.openSaved)]));
  if (remove) { try { toggleFavorite(state.favorites[Number(remove.dataset.removeSaved)]); } catch (error) { toast(error.message, "error"); } }
  const scene = event.target.closest("[data-open-media]");
  if (scene) state.explorer.open(scene.dataset.openMedia);
});

els.searchButton.addEventListener("click", () => runSearch());
els.clearButton.addEventListener("click", () => {
  els.queryInput.value = "";
  state.query = "";
  state.results = [];
  els.resultMeta.textContent = "Ready";
  els.results.className = "results-grid empty-results";
  els.results.innerHTML = `<div class="empty-visual"><i data-lucide="scan-search"></i></div><strong>No search yet</strong>`;
  els.shareSearchButton.disabled = true;
  ui.searchState("", "all", 8);
  refreshIcons();
  els.queryInput.focus();
});
els.sourceFilter.addEventListener("change", () => { if (state.query) runSearch(state.query); });
els.topKInput.addEventListener("change", () => { els.topKInput.value = Math.min(20, Math.max(1, Number(els.topKInput.value) || 8)); localStorage.setItem("cinescene-pwa-results-count", els.topKInput.value); });
els.shareSearchButton.addEventListener("click", async () => { try { await navigator.clipboard.writeText(location.href); toast("Search link copied."); } catch (_) { toast("The search URL is available in the address bar.", "error"); } });
els.clearHistoryButton.addEventListener("click", async () => { if (await ui.confirmAction("Clear your search history?", "Clear history")) { state.history = []; saveMemory(); renderMemory(); toast("Search history cleared."); } });
els.queryInput.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") runSearch();
});

els.chooseVideoButton.addEventListener("click", (event) => {
  event.stopPropagation();
  els.videoInput.click();
});
els.videoDropZone.addEventListener("click", () => els.videoInput.click());
els.videoDropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") els.videoInput.click();
});
els.videoInput.addEventListener("change", () => selectVideo(els.videoInput.files?.[0]));
els.videoDropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  els.videoDropZone.classList.add("dragging");
});
els.videoDropZone.addEventListener("dragleave", () => els.videoDropZone.classList.remove("dragging"));
els.videoDropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  els.videoDropZone.classList.remove("dragging");
  selectVideo(event.dataTransfer.files?.[0]);
});
els.removeVideoButton.addEventListener("click", clearVideo);
els.previewVideoButton.addEventListener("click", previewVideo);
els.closePlayerButton.addEventListener("click", () => els.playerDialog.close());
els.playerDialog.addEventListener("close", () => { els.scenePlayer.pause(); els.scenePlayer.removeAttribute("src"); els.scenePlayer.load(); });
els.scenePlayer.addEventListener("error", () => { if (els.playerDialog.open && els.scenePlayer.getAttribute("src")) els.playerCaption.textContent = "This video format cannot be played by your browser."; });

window.addEventListener("hashchange", () => setView(location.hash.slice(1), false));
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  state.installPrompt = event;
  els.installButton.hidden = false;
});
els.installButton.addEventListener("click", async () => {
  if (!state.installPrompt) return;
  state.installPrompt.prompt();
  await state.installPrompt.userChoice;
  state.installPrompt = null;
  els.installButton.hidden = true;
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js").catch(console.warn));
}

state.explorer = new window.SceneExplorer(async (mediaId, options) => {
  const item = state.catalog.find((entry) => String(entry.id) === mediaId);
  if (!item) throw new Error("The selected media is not in this showcase.");
  const terms = normalizeText(options.q).split(/\s+/).filter(Boolean);
  const scenes = (item.scene_timeline || []).map((scene, i) => ({ ...scene, scene_number: scene.scene_number || i + 1, keyframe_url: scene.keyframe ? `./${scene.keyframe}` : null }));
  const filtered = scenes.filter((scene) => {
    if (options.signal === "dialogue" && !scene.transcript) return false;
    if (options.signal === "vision" && !scene.caption_source?.includes("blip")) return false;
    const content = normalizeText(`${scene.transcript || ""} ${scene.visual_caption || ""} ${(scene.keywords || []).join(" ")}`);
    return terms.every((term) => content.includes(term));
  });
  return { title: item.title, quality: item.quality, total: filtered.length, has_more: options.offset + options.limit < filtered.length, scenes: filtered.slice(options.offset, options.offset + options.limit) };
});
function isSaved(movie) { return state.favorites.some((item) => ui.key(item) === ui.key(movie)); }
function toggleFavorite(movie) {
  if (!movie) return;
  const saved = isSaved(movie);
  const previous = state.favorites;
  state.favorites = saved ? state.favorites.filter((item) => ui.key(item) !== ui.key(movie)) : [movie, ...state.favorites].slice(0, 36);
  try { saveMemory(); } catch (error) { state.favorites = previous; throw error; }
  document.querySelectorAll("[data-favorite]").forEach((button) => { const active = state.favorites.some((item) => ui.key(item) === button.dataset.favorite); button.setAttribute("aria-pressed", String(active)); button.title = button.ariaLabel = active ? "Remove from saved" : "Save title"; });
  renderMemory();
  toast(saved ? `${movie.title} removed from saved.` : `${movie.title} saved.`);
}
function asMovie(item, scene) {
  const match = scene || item.scene_timeline?.[0];
  return { ...item, first_keyframe_url: item.poster ? `./${item.poster}` : null,
    matched_scene: match ? { ...match, keyframe_url: match.keyframe ? `./${match.keyframe}` : null } : null };
}
state.details = new ui.TitleDetails({ saved: isSaved, save: toggleFavorite, timeline: (movie) => state.explorer.open(String(movie.id)) });
refreshIcons();
setView(location.hash.slice(1) || "discover", false);
loadCatalog();
