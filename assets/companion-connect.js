(function (root) {
  "use strict";
  function connectionURL(value) {
    const url = new URL(value);
    const trusted = [".trycloudflare.com", ".pinggy-free.link", ".free.pinggy.net"].some((suffix) => url.hostname.endsWith(suffix));
    if (url.protocol !== "https:" || !trusted || url.port || url.username || url.password) {
      throw new Error("Enter the private HTTPS connection link from your computer's Studio.");
    }
    const key = new URLSearchParams(url.hash.slice(1)).get("pair");
    if (!key || !/^[A-Za-z0-9_-]{43,128}$/.test(key) || url.pathname !== "/connect" || url.search) {
      throw new Error("This connection link is incomplete. Copy the current private link from Studio.");
    }
    return `${url.origin}/connect#pair=${key}`;
  }
  root.CineSceneConnection = { connectionURL };
  const triggers = document.querySelectorAll("[data-connect-computer]");
  if (!triggers.length) return;
  const dialog = document.createElement("dialog");
  dialog.className = "confirm-dialog connection-dialog";
  dialog.setAttribute("aria-labelledby", "connectionHeading");
  dialog.innerHTML = `<form id="connectionForm"><h2 id="connectionHeading">Connect your computer</h2>
    <label class="field-label">Private connection link<input id="connectionInput" type="url" required autocomplete="off" spellcheck="false" placeholder="Paste your private HTTPS link"></label>
    <p class="dialog-error" role="alert" hidden></p><div class="title-dialog-actions">
    <button class="button secondary" type="button" data-local>Open local Studio</button>
    <button class="button primary" type="submit"><i data-lucide="plug"></i>Connect</button>
    <button class="icon-button ghost" type="button" data-close title="Cancel connection" aria-label="Cancel connection"><i data-lucide="x"></i></button></div></form>`;
  document.body.append(dialog);
  dialog.querySelector("[data-close]").onclick = () => dialog.close();
  dialog.querySelector("[data-local]").onclick = () => { root.location.assign("http://127.0.0.1:8000/#ingest"); };
  dialog.querySelector("form").onsubmit = (event) => {
    event.preventDefault();
    try {
      const destination = connectionURL(dialog.querySelector("input").value.trim());
      dialog.querySelector("input").value = "";
      root.location.assign(destination);
    } catch (error) {
      const notice = dialog.querySelector(".dialog-error");
      notice.hidden = false;
      notice.textContent = error.message;
    }
  };
  dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener("close", () => { dialog.querySelector("input").value = ""; });
  triggers.forEach((trigger) => trigger.addEventListener("click", () => {
    dialog.querySelector(".dialog-error").hidden = true;
    dialog.showModal();
    root.lucide?.createIcons({ root: dialog });
  }));
})(window);
