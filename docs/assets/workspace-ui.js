(() => {
  const html = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const known = (value) => value != null && !["", "n/a", "unknown", "none", "nan"].includes(String(value).trim().toLowerCase());
  const key = (movie) => String(movie.id ?? movie.title);
  const icons = () => window.lucide?.createIcons();

  function formatDate(value) {
    const raw = /^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$/.test(String(value)) ? String(value).replace(" ", "T") + "Z" : value;
    const date = new Date(raw);
    return Number.isNaN(date.getTime()) ? String(value || "") : new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
  }

  function navigation() {
    const sidebar = document.querySelector(".sidebar");
    const button = document.querySelector("#mobileMenuButton");
    const backdrop = document.createElement("button");
    backdrop.className = "nav-backdrop";
    backdrop.type = "button";
    backdrop.setAttribute("aria-label", "Close navigation");
    backdrop.hidden = true;
    document.body.append(backdrop);
    sidebar.id ||= "workspaceSidebar";
    button.setAttribute("aria-controls", sidebar.id);
    const mobile = matchMedia("(max-width: 920px)");
    const update = () => {
      const open = mobile.matches && document.body.classList.contains("nav-open");
      backdrop.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
      button.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
      sidebar.inert = mobile.matches && !open;
      sidebar.setAttribute("aria-hidden", String(mobile.matches && !open));
    };
    const close = (restore = true) => {
      const wasOpen = document.body.classList.contains("nav-open");
      document.body.classList.remove("nav-open");
      update();
      if (restore && wasOpen && mobile.matches) button.focus();
    };
    button.onclick = () => { document.body.classList.toggle("nav-open"); update(); if (!backdrop.hidden) sidebar.querySelector(".nav-item.active")?.focus(); };
    backdrop.onclick = () => close(true);
    document.addEventListener("keydown", (event) => {
      if (backdrop.hidden) return;
      if (event.key === "Escape") { event.preventDefault(); close(true); }
      if (event.key === "Tab") {
        const items = [...sidebar.querySelectorAll('a[href], button:not([disabled]):not([hidden])')];
        const first = items[0], last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    });
    mobile.addEventListener("change", () => close());
    update();
    return { close };
  }

  function searchState(query, type, count) {
    const url = new URL(location.href);
    for (const [name, value] of Object.entries({ q: query, type, count })) {
      if (query && value != null) url.searchParams.set(name, value);
      else url.searchParams.delete(name);
    }
    url.hash = "discover";
    history.replaceState(null, "", url);
  }

  function readSearch() {
    const params = new URL(location.href).searchParams;
    return { query: (params.get("q") || "").slice(0, 1000), type: params.get("type") || "all", count: Math.min(20, Math.max(1, Number(params.get("count")) || 8)) };
  }

  function recent(container, queries) {
    const unique = [...new Set(queries.filter(Boolean))].slice(0, 4);
    container.innerHTML = unique.map((query) => `<button type="button" data-query="${html(query)}" title="${html(query)}"><i data-lucide="history"></i><span dir="auto">${html(query)}</span></button>`).join("");
    container.parentElement.hidden = !unique.length;
    icons();
  }

  function memoryTabs() {
    document.querySelectorAll("[data-memory-tab]").forEach((button) => {
      const panel = document.querySelector(`[data-memory-panel="${button.dataset.memoryTab}"]`);
      button.id = `memory-tab-${button.dataset.memoryTab}`;
      button.tabIndex = button.getAttribute("aria-selected") === "true" ? 0 : -1;
      if (panel) {
        panel.id = `memory-panel-${button.dataset.memoryTab}`;
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-labelledby", button.id);
        button.setAttribute("aria-controls", panel.id);
      }
      button.onclick = () => {
        document.querySelectorAll("[data-memory-tab]").forEach((item) => { item.setAttribute("aria-selected", String(item === button)); item.classList.toggle("active", item === button); item.tabIndex = item === button ? 0 : -1; });
        document.querySelectorAll("[data-memory-panel]").forEach((panel) => { panel.hidden = panel.dataset.memoryPanel !== button.dataset.memoryTab; });
      };
      button.onkeydown = (event) => {
        const tabs = [...document.querySelectorAll("[data-memory-tab]")];
        let next = tabs.indexOf(button);
        if (event.key === "ArrowRight") next = (next + 1) % tabs.length;
        else if (event.key === "ArrowLeft") next = (next - 1 + tabs.length) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else return;
        event.preventDefault(); tabs[next].click(); tabs[next].focus();
      };
    });
  }

  class TitleDetails {
    constructor(options) {
      this.options = options;
      this.dialog = document.createElement("dialog");
      this.dialog.className = "title-dialog";
      this.dialog.setAttribute("aria-labelledby", "titleDetailsHeading");
      document.body.append(this.dialog);
      this.dialog.addEventListener("click", (event) => { if (event.target === this.dialog) this.dialog.close(); });
    }

    open(movie) {
      if (!movie) return;
      const scene = movie.matched_scene;
      const episode = movie.matched_episode;
      const sourceUrl = /^https?:\/\//i.test(episode?.source_url || "") ? episode.source_url : "";
      const image = scene?.keyframe_url || movie.first_keyframe_url;
      const fields = [
        ["Type", movie.media_type === "series" ? "Series" : "Movie"], ["Year", movie.year], ["Director", movie.director],
        ["Episode", movie.season != null && movie.episode != null ? `S${String(movie.season).padStart(2, "0")}E${String(movie.episode).padStart(2, "0")}` : null],
        ["Cast", (movie.cast || []).map((item) => typeof item === "object" ? item.name : item).filter(known).join(", ")],
        ["Genres", (movie.genres || []).join(", ")],
      ].filter(([, value]) => known(value));
      const time = (seconds) => new Date(Math.max(0, Number(seconds || 0)) * 1000).toISOString().slice(11, 19);
      this.dialog.innerHTML = `<header class="title-dialog-heading"><div><span class="evidence-label">${scene ? "Scene evidence" : "Story match"}</span><h2 id="titleDetailsHeading">${html(movie.title)}</h2></div><button class="icon-button ghost" data-close type="button" aria-label="Close details" title="Close details"><i data-lucide="x"></i></button></header>
        <div class="title-dialog-body">${image ? `<img class="title-detail-frame" src="${html(image)}" alt="Scene from ${html(movie.title)}" />` : ""}<dl class="title-metadata">${fields.map(([label, value]) => `<div><dt>${label}</dt><dd>${html(value)}</dd></div>`).join("")}</dl>
        ${movie.overview && movie.source !== "offline_video_ingestion" ? `<section><h3>Story</h3><p dir="auto">${html(movie.overview)}</p></section>` : ""}
        ${movie.plot && movie.plot !== movie.overview ? `<details class="story-evidence"><summary>Full plot</summary><p dir="auto">${html(movie.plot)}</p></details>` : ""}
        ${episode ? `<section><h3>Matched episode · S${String(episode.season).padStart(2, "0")}E${String(episode.episode).padStart(2, "0")}</h3><strong>${html(episode.name)}</strong><p dir="auto">${html(episode.summary)}</p>${sourceUrl ? `<a href="${html(sourceUrl)}" target="_blank" rel="noopener">TVmaze · CC BY-SA</a>` : ""}</section>` : ""}
        ${scene ? `<section><h3>Matched scene <time>${time(scene.start_sec)} - ${time(scene.end_sec)}</time></h3>${scene.transcript ? `<span class="evidence-label">Dialogue</span><p dir="auto">${html(scene.transcript)}</p>` : ""}${scene.visual_caption ? `<span class="evidence-label">${String(scene.caption_source || "").includes("blip") ? "Visual description" : "Visual signals"}</span><p dir="auto">${html(scene.visual_caption)}</p>` : ""}</section>` : ""}
        <p class="dialog-error" role="alert" hidden></p></div><footer class="title-dialog-actions"><button class="button secondary" data-save type="button"></button>${movie.video_url && scene && this.options.play ? `<button class="button primary" data-play type="button"><i data-lucide="play"></i>Play scene</button>` : ""}${movie.source === "offline_video_ingestion" && this.options.timeline ? `<button class="button secondary" data-timeline type="button"><i data-lucide="list-video"></i>All scenes</button>` : ""}</footer>`;
      this.dialog.querySelector("[data-close]").onclick = () => this.dialog.close();
      const save = this.dialog.querySelector("[data-save]");
      const updateSave = () => { const saved = this.options.saved(movie); save.setAttribute("aria-pressed", String(saved)); save.innerHTML = `<i data-lucide="bookmark${saved ? "-check" : ""}"></i>${saved ? "Remove from saved" : "Save title"}`; icons(); };
      updateSave();
      save.onclick = async () => {
        save.disabled = true;
        try { await this.options.save(movie); updateSave(); }
        catch (error) { const notice = this.dialog.querySelector(".dialog-error"); notice.hidden = false; notice.textContent = error.message; }
        finally { save.disabled = false; }
      };
      for (const action of ["play", "timeline"]) {
        const button = this.dialog.querySelector(`[data-${action}]`);
        if (button) button.onclick = () => { this.dialog.close(); this.options[action](movie); };
      }
      if (!this.dialog.open) this.dialog.showModal();
      icons();
    }
  }

  async function confirmAction(title, action) {
    const dialog = document.createElement("dialog");
    dialog.className = "confirm-dialog";
    dialog.setAttribute("aria-labelledby", "confirmTitle");
    dialog.innerHTML = `<form method="dialog"><h2 id="confirmTitle">${html(title)}</h2><div><button class="button secondary" value="cancel">Cancel</button><button class="button primary" value="confirm">${html(action)}</button></div></form>`;
    document.body.append(dialog);
    const result = new Promise((resolve) => dialog.addEventListener("close", () => { resolve(dialog.returnValue === "confirm"); dialog.remove(); }, { once: true }));
    dialog.showModal();
    return result;
  }

  window.CineSceneUI = { html, key, known, formatDate, navigation, recent, searchState, readSearch, memoryTabs, TitleDetails, confirmAction };
})();
