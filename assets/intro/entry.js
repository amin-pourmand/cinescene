(() => {
  // Keep deep links and shared searches out of the first-run journey.
  if (location.hash || location.search) return;
  try {
    if (localStorage.getItem("cinescene-intro-complete") !== "1") {
      location.replace(new URL("assets/intro/index.html", location.href));
    }
  } catch {
    // The workspace remains available when storage is denied.
  }
})();
