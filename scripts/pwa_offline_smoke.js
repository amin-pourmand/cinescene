const { chromium } = require("playwright-core");

const base = (process.argv[2] || "http://127.0.0.1:4178").replace(/\/$/, "") + "/";
const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

(async () => {
  const browser = await chromium.launch({ executablePath: chrome, headless: true });
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(base + "manifest.webmanifest");
    await page.evaluate(async () => {
      await caches.open("unrelated-application-cache");
      await caches.open("cinescene-pwa-obsolete-test");
    });
    await page.goto(base, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => document.querySelector("#sidebarStatus")?.textContent === "Showcase ready");
    await page.evaluate(() => navigator.serviceWorker.ready);
    await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
    const cacheKeys = await page.evaluate(() => caches.keys());
    if (!cacheKeys.includes("unrelated-application-cache") || cacheKeys.includes("cinescene-pwa-obsolete-test")) {
      throw new Error("Service worker removed unrelated caches or failed to remove its stale cache.");
    }
    await context.setOffline(true);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => document.querySelector("#sidebarStatus")?.textContent === "Showcase ready");
    await page.fill("#queryInput", "lonely detective enters a dark room");
    await page.click("#searchButton");
    await page.waitForSelector(".result-card");
    console.log(JSON.stringify({ offline_shell: true, offline_catalog_search: true, unrelated_cache_preserved: true, cache_keys: cacheKeys }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
