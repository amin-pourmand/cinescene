(() => {
  const html = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const time = (seconds) => {
    const total = Math.max(0, Math.floor(Number(seconds || 0)));
    return [Math.floor(total / 3600), Math.floor(total / 60) % 60, total % 60]
      .map((part) => String(part).padStart(2, "0")).join(":");
  };
  const icons = () => window.lucide?.createIcons();

  class SceneExplorer {
    constructor(load) {
      this.load = load;
      this.request = 0;
      this.dialog = document.createElement("dialog");
      this.dialog.className = "scene-explorer";
      this.dialog.setAttribute("aria-labelledby", "explorerTitle");
      this.dialog.innerHTML = `
        <header class="explorer-header"><div><span class="section-kicker">Scene library</span><h2 id="explorerTitle">Timeline</h2></div><button class="icon-button ghost" data-close type="button" title="Close timeline" aria-label="Close timeline"><i data-lucide="x"></i></button></header>
        <div class="explorer-quality" aria-live="polite"></div>
        <form class="explorer-tools"><label class="explorer-search"><i data-lucide="search"></i><input name="query" type="search" dir="auto" aria-label="Search this video's scenes" placeholder="Search dialogue, objects, or a moment…" /></label><select name="signal" aria-label="Scene content"><option value="all">All scenes</option><option value="dialogue">With dialogue</option><option value="vision">With visual description</option></select><button class="button secondary compact" type="submit">Search</button></form>
        <div class="explorer-body"><section class="explorer-detail" aria-label="Selected scene"></section><section class="explorer-list" aria-label="Scenes" aria-live="polite"></section></div>
        <footer class="explorer-footer"><span class="explorer-count"></span><div><button class="icon-button ghost" data-page="previous" type="button" title="Previous scenes" aria-label="Previous scenes"><i data-lucide="chevron-left"></i></button><button class="icon-button ghost" data-page="next" type="button" title="Next scenes" aria-label="Next scenes"><i data-lucide="chevron-right"></i></button></div></footer>`;
      document.body.appendChild(this.dialog);
      this.form = this.dialog.querySelector("form");
      this.list = this.dialog.querySelector(".explorer-list");
      this.detail = this.dialog.querySelector(".explorer-detail");
      this.dialog.querySelector("[data-close]").onclick = () => this.dialog.close();
      this.dialog.addEventListener("close", () => {
        this.request++;
        this.detail.querySelector("video")?.pause();
        this.detail.replaceChildren();
      });
      this.form.onsubmit = (event) => { event.preventDefault(); this.offset = 0; this.refresh(); };
      this.form.elements.signal.onchange = () => { this.offset = 0; this.refresh(); };
      this.dialog.querySelectorAll("[data-page]").forEach((button) => {
        button.onclick = () => { this.offset += button.dataset.page === "next" ? 24 : -24; this.refresh(); };
      });
      this.list.onclick = (event) => {
        const button = event.target.closest("[data-scene]");
        if (button) this.select(Number(button.dataset.scene));
        if (event.target.closest("[data-retry]")) this.refresh();
      };
    }

    open(mediaId) {
      this.mediaId = mediaId;
      this.offset = 0;
      this.form.reset();
      if (!this.dialog.open) this.dialog.showModal();
      this.refresh();
    }

    async refresh() {
      const request = ++this.request;
      this.list.setAttribute("aria-busy", "true");
      this.list.innerHTML = `<p class="explorer-empty">Loading scenes…</p>`;
      this.dialog.querySelectorAll("[data-page]").forEach((button) => { button.disabled = true; });
      try {
        const data = await this.load(this.mediaId, { offset: this.offset, limit: 24, q: this.form.elements.query.value, signal: this.form.elements.signal.value });
        if (request !== this.request) return;
        this.data = data;
        this.dialog.querySelector("h2").textContent = data.title;
        const quality = data.quality || {};
        this.dialog.querySelector(".explorer-quality").innerHTML = `<span><b>${html(quality.scenes || data.total)}</b> scenes</span><span><b>${time(quality.duration_sec)}</b> duration</span><span><b>${html(quality.dialogue_scenes || 0)}</b> with dialogue</span><span><b>${html(quality.vision_scenes || 0)}</b> with vision captions</span>`;
        this.list.innerHTML = data.scenes.map((scene, index) => `<button class="explorer-row" data-scene="${index}" type="button"><span class="explorer-thumb">${scene.keyframe_url ? `<img src="${html(scene.keyframe_url)}" alt="" loading="lazy" />` : `<i data-lucide="film"></i>`}</span><span class="explorer-row-copy"><strong>Scene ${html(scene.scene_number)} <time>${time(scene.start_sec)}</time></strong><span dir="auto">${html(scene.transcript || scene.visual_caption || "No description available")}</span></span><i data-lucide="chevron-right"></i></button>`).join("") || `<p class="explorer-empty">No scenes match these filters.</p>`;
        this.dialog.querySelector(".explorer-count").textContent = data.total ? `${this.offset + 1}–${this.offset + data.scenes.length} of ${data.total} scenes` : "0 scenes";
        this.dialog.querySelector('[data-page="previous"]').disabled = this.offset <= 0;
        this.dialog.querySelector('[data-page="next"]').disabled = !data.has_more;
        if (data.scenes.length) this.select(0);
        else { this.detail.querySelector("video")?.pause(); this.detail.innerHTML = `<p class="explorer-empty">Select a different filter or search.</p>`; }
        this.list.scrollTop = 0;
      } catch (error) {
        if (request !== this.request) return;
        this.list.innerHTML = `<div class="explorer-empty"><p>${html(error.message)}</p><button class="button secondary" data-retry type="button">Retry</button></div>`;
      } finally {
        if (request === this.request) this.list.removeAttribute("aria-busy");
        icons();
      }
    }

    select(index) {
      const scene = this.data.scenes[index];
      if (!scene) return;
      this.detail.querySelector("video")?.pause();
      this.list.querySelectorAll("[data-scene]").forEach((row, i) => row.setAttribute("aria-pressed", String(i === index)));
      const source = scene.caption_source || "visual_signals";
      this.detail.innerHTML = `
        <div class="explorer-preview">${this.data.video_url ? `<video controls preload="metadata" playsinline ${scene.keyframe_url ? `poster="${html(scene.keyframe_url)}"` : ""}></video>` : scene.keyframe_url ? `<img src="${html(scene.keyframe_url)}" alt="Scene ${html(scene.scene_number)}" />` : `<div class="explorer-empty"><i data-lucide="film"></i><span>No preview available</span></div>`}</div>
        <div class="explorer-scene-heading"><h3>Scene ${html(scene.scene_number)}</h3><time>${time(scene.start_sec)} – ${time(scene.end_sec)}</time></div>
        ${scene.transcript ? `<div class="explorer-evidence"><span class="evidence-label"><i data-lucide="captions"></i>Dialogue</span><p dir="auto">${html(scene.transcript)}</p><small>${html((scene.subtitle_sources || []).join(" · "))}</small></div>` : `<p class="explorer-missing">No dialogue recovered for this scene.</p>`}
        <div class="explorer-evidence"><span class="evidence-label"><i data-lucide="image"></i>${source.includes("blip") ? "Visual description" : "Lighting and motion"}</span><p dir="auto">${html(scene.visual_caption || "No visual description")}</p></div>
        <div class="chip-row">${[...(scene.mood_tags || []), ...(scene.visual_tags || [])].slice(0, 10).map((tag) => `<span class="chip">${html(tag)}</span>`).join("")}</div>
        ${(scene.analysis_warnings || []).length ? `<div class="explorer-warning">${scene.analysis_warnings.map(html).join("<br />")}</div>` : ""}`;
      const video = this.detail.querySelector("video");
      if (video) {
        video.onloadedmetadata = () => { video.currentTime = scene.preview_url ? 0 : Number(scene.start_sec || 0); };
        video.ontimeupdate = () => { if (!scene.preview_url && scene.end_sec && video.currentTime >= scene.end_sec && !video.seeking) video.pause(); };
        video.src = scene.preview_url || this.data.video_url;
      }
      icons();
    }
  }
  window.SceneExplorer = SceneExplorer;
})();
