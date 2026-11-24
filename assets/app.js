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
  searching: false,
  searchController: null,
  catalogLoaded: false,
  semantic: new window.CineSceneSemanticSearch(),
};
let catalogReady;

const ids = [
  "viewTitle", "mobileMenuButton", "installButton", "statusDot", "sidebarStatus", "sidebarModel",
  "metricCatalog", "metricIndexed", "metricOffline", "metricScenes", "metricLatency", "queryInput",
  "topKInput", "sourceFilter", "searchButton", "clearButton", "resultMeta", "results", "statusPill",
  "sceneTimeline", "historyList", "favoriteList", "videoDropZone", "videoInput", "videoDropTitle",
  "videoDropMeta", "chooseVideoButton", "selectedVideo", "removeVideoButton",
  "previewVideoButton", "playerDialog", "scenePlayer", "playerTitle", "playerTimecode", "playerCaption",
  "closePlayerButton", "toastRegion",
  "recentSearches", "shareSearchButton", "clearHistoryButton",
  "searchWarning", "queryInterpretation", "translatedQuery", "translationInput",
];
const els = Object.fromEntries(ids.map((id) => [id, document.getElementById(id)]));
const ui = window.CineSceneUI;
const navigation = ui.navigation();
ui.memoryTabs();

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

function setView(view, { historyMode = "replace", focus = false } = {}) {
  const importing = view === "import-video";
  if (view === "videos" || importing) view = "scenes";
  const next = ["discover", "scenes", "library", "system"].includes(view) ? view : "discover";
  const titles = { discover: "Search", scenes: "Video library", library: "Saved & history", system: "Settings" };
  const changed = navigation.show(next, titles[next]);
  const hash = importing ? "#import-video" : `#${next}`;
  if (historyMode && location.hash !== hash) history[historyMode === "push" ? "pushState" : "replaceState"](null, "", hash);
  if (changed || importing) window.scrollTo({ top: 0, behavior: "instant" });
  if (focus) (importing ? document.getElementById("videoConnectionHeading") : els.viewTitle).focus({ preventScroll: true });
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

function chips(items, limit = 7) {
  return (items || []).slice(0, limit).map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("");
}

function renderResults(entries, query, elapsedMs, alternatives = []) {
  state.results = entries;
  state.history = [{ query, at: new Date().toISOString(), count: entries.length }, ...state.history.filter((entry) => entry.query !== query)].slice(0, 24);
  saveMemory();
  ui.recent(els.recentSearches, state.history.map((item) => item.query));
  els.metricLatency.textContent = `${elapsedMs.toFixed(0)}ms`;
  if (!entries.length && alternatives.length) {
    ui.weakMatch(els.results, els.resultMeta, alternatives.length, () => drawResults(alternatives, true));
    return;
  }
  drawResults(entries);
}

function drawResults(entries, approximate = false) {
  state.results = entries;
  els.resultMeta.textContent = entries.length ? `${entries.length} ${entries.length === 1 ? "match" : "matches"} · ${entries[0].method || "Semantic"}` : "No matches";
  if (!entries.length) {
    els.results.className = "results-grid empty-results";
    els.results.innerHTML = `<div class="empty-visual"><i data-lucide="circle-slash-2"></i></div><strong>No indexed titles in this selection.</strong>`;
    if (els.sourceFilter.value === "dialogue") els.results.textContent = "No matching dialogue in the public sample transcripts.";
    refreshIcons(els.results);
    return;
  }

  els.results.className = "results-grid";
  if (approximate) els.resultMeta.textContent = `${entries.length} possible leads`;
  els.results.innerHTML = entries.map(({ item, score, scene, episode, evidence }, index) => {
    const image = scene?.keyframe || item.poster;
    const media = image
      ? `<div class="result-media"><img src="./${escapeHtml(image)}" alt="Keyframe from ${escapeHtml(item.title)}" loading="lazy" /><span class="result-rank">Rank ${index + 1}</span><span class="result-source">${escapeHtml(sourceLabel(item))}</span></div>`
      : `<div class="catalog-result-header"><i data-lucide="${item.media_type === "series" ? "tv" : "film"}"></i><b>Rank ${index + 1}</b><span class="catalog-source">${escapeHtml(sourceLabel(item))}</span></div>`;
    const sceneCopy = scene?.transcript || scene?.visual_caption || (item.scenes || [])[0] || "No scene transcript is available in the public sample.";
    const tags = [...new Set([...(scene?.mood_tags || []), ...(item.genres || []), ...(item.mood || [])])].slice(0, 3);
    return `<article class="result-card ${image ? "has-frame" : "catalog-only"}">
      ${media}
      <div class="result-body">
        <div class="result-title-row"><div><button class="title-link" data-details="${index}" type="button">${escapeHtml(item.title)}</button><small>${escapeHtml(mediaLabel(item))}${ui.known(item.year) ? ` &middot; ${escapeHtml(item.year)}` : ""}${item.director && item.director !== "Unknown" ? ` &middot; ${escapeHtml(item.director)}` : ""}</small></div><span class="result-kind"><i data-lucide="${scene ? "film" : episode ? "tv" : "book-open"}"></i>${scene ? "Timed scene" : episode ? "Episode summary" : "Story match"}</span></div>
        ${item.source === "offline_video_ingestion" ? "" : `<p class="result-overview">${escapeHtml(item.overview || "")}</p>`}
        ${scene ? `<div class="matched-scene"><div class="scene-label"><span>Best matching scene</span><time>${timecode(scene.start_sec)} - ${timecode(scene.end_sec)}</time></div><p dir="auto">${escapeHtml(sceneCopy)}</p></div>` : ""}
        ${!scene && evidence ? `<details class="story-evidence"><summary>${episode ? `Episode S${String(episode.season).padStart(2, "0")}E${String(episode.episode).padStart(2, "0")} · ${escapeHtml(episode.name)}` : "Matching story passage"}</summary><p dir="auto">${escapeHtml(evidence)}</p>${episode?.source_url ? `<a href="${escapeHtml(episode.source_url)}" target="_blank" rel="noopener">Episode summary: TVmaze · CC BY-SA</a>` : ui.storyAttribution(item)}</details>` : ""}
        <div class="chip-row">${chips(tags)}</div>
        <div class="result-actions">
          <button class="button secondary" type="button" data-details="${index}"><i data-lucide="info"></i>Details</button>
          ${item.source === "offline_video_ingestion" ? `<button class="button secondary compact" type="button" data-open-media="${escapeHtml(item.id)}" data-scene-number="${escapeHtml(scene?.scene_number || (scene ? item.scene_timeline?.indexOf(scene) + 1 : "") || "")}"><i data-lucide="list-video"></i>Scene timeline</button>` : ""}
          <button class="icon-button ghost" type="button" data-favorite="${escapeHtml(item.id)}" aria-pressed="${isSaved(item)}" title="${isSaved(item) ? "Remove from saved" : "Save title"}" aria-label="${isSaved(item) ? "Remove from saved" : "Save title"}"><i data-lucide="bookmark"></i></button>
        </div>
      </div>
    </article>`;
  }).join("");
  refreshIcons(els.results);

}

function cancelSearch() {
  state.searchController?.abort();
  state.semantic.cancel();
}

async function waitForCatalog(signal) {
  let onAbort;
  const cancelled = new Promise((_, reject) => {
    onAbort = () => reject(signal.reason);
    signal.addEventListener("abort", onAbort, { once: true });
  });
  try { return await Promise.race([ensureCatalog(), cancelled]); }
  finally { signal.removeEventListener("abort", onAbort); }
}

async function runSearch(queryOverride) {
  if (state.searching) { cancelSearch(); return; }
  const query = String(queryOverride || els.queryInput.value).trim();
  if (!query) {
    toast("Describe a scene first.", "error");
    els.queryInput.focus();
    return;
  }
  const exact = els.sourceFilter.value === "dialogue";
  const quick = els.sourceFilter.value === "quick";
  let translatePersian = !exact && !quick && /[\u0600-\u06ff]/u.test(query) && els.translationInput.checked;
  if (translatePersian && localStorage.getItem("cinescene-pwa-translation-consent") !== "1") {
    const accepted = await ui.confirmAction("The Persian model adds about 870 MB to this browser's storage. CC BY-NC 4.0: research/non-commercial use. Download it?", "Download model");
    if (accepted) localStorage.setItem("cinescene-pwa-translation-consent", "1");
    else {
      translatePersian = false;
      els.translationInput.checked = false;
      localStorage.setItem("cinescene-pwa-translation", "0");
    }
  }
  setView("discover");
  state.query = query;
  ui.searchState(query, els.sourceFilter.value, els.topKInput.value);
  els.shareSearchButton.disabled = false;
  els.queryInput.value = query;
  const controller = new AbortController();
  state.searchController = controller;
  state.searching = true;
  state.results = [];
  els.results.replaceChildren();
  els.searchWarning.hidden = true;
  els.queryInterpretation.hidden = true;
  els.searchButton.innerHTML = '<i data-lucide="square"></i><span>Cancel</span>';
  els.sourceFilter.disabled = true;
  els.results.setAttribute("aria-busy", "true");
  const status = document.getElementById("searchProgress");
  status.hidden = false;
  refreshIcons(els.searchButton);
  const start = performance.now();
  try {
    if (!state.catalogLoaded) {
      els.resultMeta.textContent = "Loading catalog";
      status.textContent = "Search will start when the catalog is ready.";
      if (!await waitForCatalog(controller.signal)) return;
      controller.signal.throwIfAborted();
    }
    els.resultMeta.textContent = exact ? "Searching dialogue" : quick ? "Preparing text search" : "Preparing semantic search";
    status.textContent = exact ? "Searching dialogue" : quick ? "Loading text search" : "Loading semantic search";
    if (exact) {
      const entries = ui.dialogueResults(query, state.catalog, Number(els.topKInput.value || 8));
      renderResults(entries, query, performance.now() - start);
      setStatus("Dialogue search ready", true);
      return;
    }
    const entries = await state.semantic.search(query, els.sourceFilter.value, Number(els.topKInput.value || 8), (message) => {
      status.textContent = message;
      els.resultMeta.textContent = "Searching";
    }, { translatePersian });
    const interpretation = state.semantic.interpretation;
    els.searchWarning.textContent = interpretation.warning || "";
    els.searchWarning.hidden = !interpretation.warning;
    els.translatedQuery.textContent = interpretation.translated_query || "";
    els.queryInterpretation.hidden = !interpretation.translated_query;
    renderResults(entries, query, performance.now() - start, state.semantic.alternatives);
    setStatus(quick ? "Text search ready" : "Semantic search ready", true);
  } catch (error) {
    if (error.name === "AbortError") {
      els.resultMeta.textContent = "Cancelled";
      els.results.className = "results-grid empty-results";
      els.results.textContent = "Search cancelled.";
    } else {
      setStatus("Search unavailable", false);
      els.resultMeta.textContent = "Search error";
      els.results.className = "results-grid empty-results";
      els.results.innerHTML = `<div class="empty-visual"><i data-lucide="triangle-alert"></i></div><strong>${quick ? "Text search could not load" : "Semantic search could not load"}</strong><span>${escapeHtml(error.message)}</span>`;
      state.results = [];
    }
  } finally {
    state.searching = false;
    state.searchController = null;
    status.hidden = true;
    els.results.removeAttribute("aria-busy");
    els.sourceFilter.disabled = false;
    els.searchButton.innerHTML = '<i data-lucide="search"></i><span></span>';
    els.searchButton.querySelector("span").textContent = (window.cinesceneWord || String)("Search");
    refreshIcons();
  }
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

function ensureCatalog() {
  if (!catalogReady) {
    catalogReady = loadCatalog().then(ready => {
      if (!ready) catalogReady = null;
      return ready;
    });
  }
  return catalogReady;
}

async function loadCatalog() {
  try {
    const response = await fetch("./data/catalog-summary.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`Catalog HTTP ${response.status}`);
    const bytes = await response.arrayBuffer();
    const releaseResponse = await fetch("./data/release.json", { cache: "no-cache" });
    if (!releaseResponse.ok) throw new Error(`Release HTTP ${releaseResponse.status}`);
    const manifest = await releaseResponse.json();
    const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map((n) => n.toString(16).padStart(2, "0")).join("");
    if (digest !== manifest.summary_sha256) throw new Error("Catalog release changed. Reload the app.");
    const payload = JSON.parse(new TextDecoder().decode(bytes));
    state.catalog = payload.items || [];
    const offline = state.catalog.filter((item) => item.source === "offline_video_ingestion");
    const seriesCount = state.catalog.filter((item) => item.media_type === "series").length;
    const sceneCount = offline.reduce((sum, item) => sum + Number(item.scene_count || (item.scene_timeline || []).length), 0);
    els.metricCatalog.textContent = state.catalog.length.toLocaleString();
    els.metricIndexed.textContent = manifest.titles.toLocaleString();
    document.getElementById("metricEpisodes").textContent = manifest.episode_records.toLocaleString();
    document.getElementById("metricRelease").textContent = manifest.index_generation ? manifest.index_generation.replace("T", " ").slice(0, 19) + " UTC" : manifest.fusion_version;
    els.metricOffline.textContent = seriesCount.toLocaleString();
    els.metricScenes.textContent = sceneCount.toLocaleString();
    setStatus("Catalog ready", true);
    renderTimeline();
    renderMemory();
    state.catalogLoaded = true;
    return true;
  } catch (error) {
    setStatus("Catalog unavailable", false);
    els.resultMeta.textContent = "Load error";
    els.results.className = "results-grid empty-results";
    els.results.innerHTML = `<div class="empty-visual"><i data-lucide="triangle-alert"></i></div><strong>Could not load the public catalog.</strong><span>${escapeHtml(error.message)}</span>`;
    refreshIcons(els.results);
    return false;
  }
}

function restoreInitialSearch() {
  const shared = ui.readSearch();
  const params = new URLSearchParams(location.search);
  const discover = !location.hash || location.hash === "#discover";
  if (shared.query) els.queryInput.value = shared.query;
  else if (discover && params.has("draft")) els.queryInput.value = params.get("draft").slice(0, 1000);
  if ([...els.sourceFilter.options].some((option) => option.value === shared.type)) els.sourceFilter.value = shared.type;
  els.topKInput.value = discover && params.has("count") ? shared.count : Math.min(20, Math.max(1, Number(localStorage.getItem("cinescene-pwa-results-count")) || 8));
  return discover ? shared.query : "";
}

document.addEventListener("click", (event) => {
  const viewLink = event.target.closest("[data-view-link]");
  const queryLink = event.target.closest("[data-query]");
  const details = event.target.closest("[data-details]");
  const favorite = event.target.closest("[data-favorite]");
  if (viewLink) {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    setView(viewLink.dataset.viewLink, { historyMode: "push", focus: true });
  }
  if (queryLink?.closest(".prompt-list")) {
    if (state.searching) return;
    els.sourceFilter.value = "all";
    els.queryInput.value = queryLink.dataset.query;
    els.queryInput.focus();
  } else if (queryLink) runSearch(queryLink.dataset.query);
  if (details) { const entry = state.results[Number(details.dataset.details)]; if (entry) state.details.open(asMovie(entry.item, entry.scene, entry.episode)); }
  if (favorite) {
    const item = state.results.find((entry) => String(entry.item.id) === favorite.dataset.favorite)?.item
      || state.catalog.find((entry) => String(entry.id) === favorite.dataset.favorite);
    if (item) { try { toggleFavorite(item); } catch (error) { toast(error.message, "error"); } }
  }
  const saved = event.target.closest("[data-open-saved]");
  const remove = event.target.closest("[data-remove-saved]");
  if (saved) state.details.open(asMovie(state.favorites[Number(saved.dataset.openSaved)]));
  if (remove) { try { toggleFavorite(state.favorites[Number(remove.dataset.removeSaved)]); } catch (error) { toast(error.message, "error"); } }
  const scene = event.target.closest("[data-open-media]");
  if (scene) state.explorer.open(scene.dataset.openMedia, scene.dataset.sceneNumber);
});

els.searchButton.addEventListener("click", () => runSearch());
document.getElementById("clearModelsButton").addEventListener("click", async () => {
  if (!await ui.confirmAction("Remove downloaded search models from this device? Saved titles and history will stay.", "Remove models")) return;
  cancelSearch();
  try {
    await caches.delete("transformers-cache");
    setStatus("Models not downloaded", true);
    toast("Downloaded models removed.");
  } catch (error) { toast(error.message, "error"); }
});
document.addEventListener("visibilitychange", () => { if (document.hidden) state.semantic.release(); });
els.clearButton.addEventListener("click", () => {
  cancelSearch();
  els.searchWarning.hidden = true;
  els.queryInterpretation.hidden = true;
  els.queryInput.value = "";
  state.query = "";
  state.results = [];
  els.resultMeta.textContent = "Ready";
  els.results.className = "results-grid empty-results";
  els.results.innerHTML = `<div class="empty-visual"><i data-lucide="scan-search"></i></div><strong data-search-idle>No search yet</strong>`;
  els.shareSearchButton.disabled = true;
  ui.searchState("", "all", 8);
  refreshIcons();
  els.queryInput.focus();
});
els.sourceFilter.addEventListener("change", () => {
  if (!state.searching && state.query && els.queryInput.value.trim() === state.query) runSearch(state.query);
});
els.topKInput.addEventListener("change", () => { els.topKInput.value = Math.min(20, Math.max(1, Number(els.topKInput.value) || 8)); localStorage.setItem("cinescene-pwa-results-count", els.topKInput.value); });
els.translationInput.checked = localStorage.getItem("cinescene-pwa-translation") !== "0";
els.translationInput.addEventListener("change", () => localStorage.setItem("cinescene-pwa-translation", els.translationInput.checked ? "1" : "0"));
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

window.addEventListener("hashchange", () => setView(location.hash.slice(1), { historyMode: null, focus: true }));
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
function asMovie(item, scene, episode) {
  const match = scene || item.matched_scene;
  return { ...item, first_keyframe_url: item.poster ? `./${item.poster}` : null,
    matched_episode: episode || item.matched_episode || null,
    matched_scene: match ? { ...match, keyframe_url: match.keyframe ? `./${match.keyframe}` : null } : null };
}
state.details = new ui.TitleDetails({ saved: isSaved, save: toggleFavorite, timeline: (movie) => state.explorer.open(String(movie.id)) });
refreshIcons();
setView(location.hash.slice(1) || "discover", { historyMode: null });
const initialSearch = restoreInitialSearch();
ensureCatalog();
if (initialSearch) runSearch(initialSearch);
