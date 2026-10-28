(() => {
  class SemanticSearch {
    constructor() { this.worker = null; this.sequence = 0; this.pending = null; this.idleTimer = null; this.interpretation = {}; }
    search(query, source, count, onProgress, options = {}) {
      if (this.pending) return Promise.reject(new Error("A search is already running."));
      clearTimeout(this.idleTimer);
      if (!this.worker) {
        this.worker = new Worker(new URL("./semantic-worker.mjs?v=20261028-parity-v25", document.currentScript?.src || new URL("./assets/semantic-client.js", location.href)), { type: "module" });
        this.worker.onmessage = ({ data }) => {
          if (!this.pending || data.id !== this.pending.id) return;
          if (data.type === "progress") return this.pending.onProgress?.(data.message);
          const pending = this.pending;
          this.pending = null;
          this.idleTimer = setTimeout(() => this.release(), 60000);
          if (data.type === "error") { this.release(); pending.reject(new Error(data.message)); }
          else { this.interpretation = data.interpretation || {}; pending.resolve(data.results); }
        };
        this.worker.onerror = () => {
          const pending = this.pending;
          this.pending = null;
          this.worker?.terminate();
          this.worker = null;
          pending?.reject(new Error("The semantic search worker could not start. Reload and try again."));
        };
      }
      return new Promise((resolve, reject) => {
        const id = ++this.sequence;
        this.pending = { id, resolve, reject, onProgress };
        this.worker.postMessage({ id, query, source, count, ...options });
      });
    }
    cancel() {
      clearTimeout(this.idleTimer);
      this.worker?.terminate();
      this.worker = null;
      const pending = this.pending;
      this.pending = null;
      pending?.reject(new DOMException("Search cancelled", "AbortError"));
    }
    release() {
      if (this.pending) return;
      this.worker?.terminate();
      this.worker = null;
    }
  }
  window.CineSceneSemanticSearch = SemanticSearch;
})();
