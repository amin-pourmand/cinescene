(() => {
  const params = new URLSearchParams(location.search);
  const intro = new URL("assets/intro/index.html", location.href);
  if (params.get("intro") === "1") {
    intro.searchParams.set("choose", "1");
    location.replace(intro);
    return;
  }
  // Only direct workspace links bypass the introduction.
  if (location.hash || ["q", "draft", "type"].some(key => params.has(key))) return;
  location.replace(intro);
})();
