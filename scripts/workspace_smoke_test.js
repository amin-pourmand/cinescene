const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");
const { randomUUID } = require("crypto");

const root = path.resolve(__dirname, "..");
const base = (process.argv[2] || "http://127.0.0.1:8000").replace(/\/$/, "");
const isStatic = process.argv[3] === "static";
const upload = process.argv.includes("--upload");
const prefix = isStatic ? "workspace-pwa" : "workspace-local";
const query = "lonely detective enters a dark room";
const assert = (value, message) => { if (!value) throw new Error(message); };

(async () => {
  const browser = await chromium.launch({ executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", headless: true });
  const report = { mode: isStatic ? "showcase" : "studio", checks: [], errors: [] };
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: "block", reducedMotion: "reduce" });
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    const session = `workspace-test-${randomUUID()}`;
    if (!isStatic) await context.addInitScript((session) => { if (!localStorage.getItem("cinescene-session")) localStorage.setItem("cinescene-session", session); }, session);
    const page = await context.newPage();
    page.on("pageerror", (error) => report.errors.push(error.message));
    await page.goto(base + "/#discover", { waitUntil: "domcontentloaded" });
    await page.waitForFunction((expected) => document.querySelector("#sidebarStatus")?.textContent === expected, isStatic ? "Showcase ready" : "Engine online", { timeout: 180_000 });
    assert(await page.locator(".stat-strip:visible").count() === 0, "Technical counters leaked into Search");
    assert(await page.locator(".result-card").count() === 0, "The first screen ran an unsolicited search");
    assert(!await page.locator("#topKInput").isVisible(), "Advanced settings cluttered Search");
    await page.screenshot({ path: path.join(root, "artifacts", `${prefix}-desktop-search.png`), fullPage: true });
    report.checks.push("uncluttered-first-screen");

    await page.fill("#queryInput", query);
    await page.click("#searchButton");
    await page.waitForSelector(".result-card", { timeout: 90_000 });
    assert(await page.locator(".score-ring").count() === 0, "Raw ranking scores are still presented as confidence");
    await page.locator(".title-link").first().click();
    await page.waitForSelector(".title-dialog[open]");
    assert((await page.locator("#titleDetailsHeading").textContent()).includes("Benchmark Show"), "Unexpected fixture title");
    await page.locator(".title-dialog [data-save]").click();
    await page.waitForFunction(() => document.querySelector(".title-dialog [data-save]")?.getAttribute("aria-pressed") === "true");
    await page.screenshot({ path: path.join(root, "artifacts", `${prefix}-desktop-details.png`) });
    await page.keyboard.press("Escape");
    await page.locator('.nav-item[data-view-link="library"]').click();
    await page.waitForSelector("[data-open-saved]");
    await page.locator("[data-open-saved]").first().click();
    await page.waitForSelector(".title-dialog[open]");
    await page.keyboard.press("Escape");
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForSelector("[data-open-saved]");
    await page.locator("[data-remove-saved]").first().click();
    await page.waitForFunction(() => document.querySelector("#favoriteList")?.textContent.includes("No saved titles"));
    report.checks.push("title-details", "save-persist-open-remove");

    await page.click('[data-memory-tab="history"]');
    await page.waitForSelector("#historyList [data-query]");
    await page.click("#clearHistoryButton");
    await page.click('.confirm-dialog button[value="cancel"]');
    assert(await page.locator("#historyList [data-query]").count() > 0, "Cancel cleared the history");
    await page.click("#clearHistoryButton");
    await page.click('.confirm-dialog button[value="confirm"]');
    await page.waitForFunction(() => document.querySelector("#historyList")?.textContent.includes("No search history"));
    report.checks.push("history-confirm-and-cancel");

    await page.locator('.nav-item[data-view-link="discover"]').click();
    await page.fill("#queryInput", query);
    await page.click("#searchButton");
    await page.waitForSelector(".result-card");
    await page.click("#shareSearchButton");
    const shared = await page.evaluate(() => navigator.clipboard.readText());
    assert(new URL(shared).searchParams.get("q") === query, "Copied search link lost the query");
    await page.goto(shared, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".result-card", { timeout: 90_000 });
    assert(await page.inputValue("#queryInput") === query, "Shared search did not restore");
    await page.click("#clearButton");
    assert(await page.locator(".result-card").count() === 0 && !new URL(page.url()).searchParams.has("q"), "Clear left stale results or URL state");
    report.checks.push("copy-and-reopen-search", "clear-input-results-url");

    if (isStatic) {
      await page.fill("#queryInput", "qzxv987654321");
      await page.click("#searchButton");
      assert(await page.locator(".result-card").count() === 0, "Unrelated catalog ratings fabricated matches");
      assert(await page.locator("#subtitleInput").count() === 0 && await page.locator(".pipeline-steps").count() === 0, "Showcase exposes nonfunctional processing controls");
      report.checks.push("genuine-no-match-state", "no-fake-upload-controls");
    } else {
      await page.route("**/api/search", (route) => route.abort("failed"));
      await page.fill("#queryInput", query);
      await page.click("#searchButton");
      await page.waitForSelector("[data-retry-search]");
      await page.unroute("**/api/search");
      await page.click("[data-retry-search]");
      await page.waitForSelector(".result-card", { timeout: 60_000 });
      report.checks.push("connection-error-and-retry");
    }
    const persian = "کارآگاهی تنها وارد اتاق تاریک می‌شود و دنبال سرنخ می‌گردد";
    await page.fill("#queryInput", persian);
    await page.click("#searchButton");
    await page.waitForSelector(".result-card", { timeout: 60_000 });
    assert(await page.inputValue("#queryInput") === persian, "Persian query was altered");
    assert(await page.locator("#queryInput").evaluate((element) => getComputedStyle(element).direction) === "rtl", "Persian input direction is incorrect");
    report.checks.push("persian-query-and-direction");
    await page.screenshot({ path: path.join(root, "artifacts", `${prefix}-desktop-results.png`), fullPage: true });

    await page.locator(`.nav-item[data-view-link="${isStatic ? "scenes" : "ingest"}"]`).click();
    await page.waitForSelector(".video-library-item");
    await page.screenshot({ path: path.join(root, "artifacts", `${prefix}-desktop-videos.png`), fullPage: true });
    await page.locator(".video-library-item button[data-open-media]").first().click();
    await page.waitForSelector(".explorer-row");
    await page.keyboard.press("Escape");
    report.checks.push("video-library-and-full-timeline");

    if (!isStatic) {
      await page.locator("button[data-open-import]").click();
      await page.screenshot({ path: path.join(root, "artifacts", `${prefix}-desktop-upload.png`), fullPage: true });
      const video = fs.readFileSync(path.join(root, "data/offline_videos/benchmark_folder/Benchmark.Show.S01E01.mp4"));
      await page.setInputFiles("#videoInput", { name: "First.Show.mp4", mimeType: "video/mp4", buffer: video });
      await page.setInputFiles("#videoInput", { name: "Second.Show.mp4", mimeType: "video/mp4", buffer: video });
      assert(await page.inputValue("#movieTitleInput") === "Second Show", "Auto-detected title stayed attached to the previous video");
      await page.fill("#movieTitleInput", "Custom title");
      await page.setInputFiles("#videoInput", { name: "Third.Show.mp4", mimeType: "video/mp4", buffer: video });
      assert(await page.inputValue("#movieTitleInput") === "Custom title", "A custom title was overwritten");
      const subtitle = fs.readFileSync(path.join(root, "data/offline_videos/benchmark_folder/Benchmark.Show.S01E01.srt"));
      await page.setInputFiles("#subtitleInput", [
        { name: "one.srt", mimeType: "text/plain", buffer: subtitle }, { name: "two.srt", mimeType: "text/plain", buffer: subtitle },
      ]);
      assert(await page.locator("[data-remove-subtitle]").count() === 2, "Subtitle attachments were lost");
      await page.locator('[data-remove-subtitle="1"]').click();
      assert(await page.locator("[data-remove-subtitle]").count() === 1, "Subtitle removal failed");
      report.checks.push("video-selection-and-title", "subtitle-attachment-removal");

      if (upload) {
        await page.setInputFiles("#videoInput", { name: "Benchmark.Show.S01E01.mp4", mimeType: "video/mp4", buffer: video });
        await page.fill("#movieTitleInput", "Benchmark Show");
        await page.locator("#uploadMinSceneInput").evaluate((input) => { input.value = "1"; input.dispatchEvent(new Event("input", { bubbles: true })); });
        let uploads = 0;
        page.on("request", (request) => { if (request.method() === "POST" && request.url().endsWith("/api/ingest/video")) uploads++; });
        await page.click("#startAnalysisButton");
        await page.waitForSelector("#jobPanel:not([hidden])");
        assert(await page.isDisabled("#startAnalysisButton"), "Processing did not prevent duplicate uploads");
        await page.locator("#ingestForm").evaluate((form) => form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
        await page.waitForFunction(() => !localStorage.getItem("cinescene-active-job") && !document.querySelector("#addMediaPanel").open, null, { timeout: 240_000 });
        assert(uploads === 1, `Duplicate submit started ${uploads} uploads`);
        report.checks.push("real-ui-upload-to-search-ready", "duplicate-upload-prevention");
      }
      await page.locator(".folder-section > summary").click();
      await page.fill("#crawlPathInput", "E:\\CineSceneCache\\cinescene\\data\\offline_videos\\benchmark_folder");
      await page.click("#probeCrawlerPathButton");
      await page.waitForSelector("#probeList .probe-item");
      await page.locator(".folder-options > summary").click();
      await page.check("#crawlVisionInput");
      await page.fill("#crawlMinSceneInput", "6");
      let folderRequest;
      await page.route("**/api/crawl/offline-async", async (route) => {
        folderRequest = route.request().postDataJSON();
        await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Test connection interrupted" }) });
      });
      await page.locator('#crawlForm button[type="submit"]').click();
      await page.waitForFunction(() => document.querySelector("#crawlerNotice")?.textContent === "Test connection interrupted");
      assert(folderRequest.enable_vision && folderRequest.min_scene_sec === 6 && folderRequest.extract_embedded_subtitles, "Folder processing ignored its own settings");
      assert(!await page.isDisabled('#crawlForm button[type="submit"]'), "A failed folder request locked the form");
      await page.unroute("**/api/crawl/offline-async");
      report.checks.push("real-folder-probe", "independent-folder-settings-and-error-recovery");
    }
    assert(await page.evaluate(() => document.body.scrollWidth <= innerWidth + 1), "Desktop horizontal overflow");

    const mobile = await context.newPage();
    await mobile.setViewportSize({ width: 390, height: 844 });
    mobile.on("pageerror", (error) => report.errors.push(error.message));
    await mobile.goto(base + "/#discover", { waitUntil: "domcontentloaded" });
    await mobile.click("#mobileMenuButton");
    assert(await mobile.getAttribute("#mobileMenuButton", "aria-expanded") === "true", "Navigation state missing");
    await mobile.keyboard.press("Escape");
    await mobile.evaluate(() => scrollTo(0, 0));
    assert(await mobile.getAttribute("#mobileMenuButton", "aria-expanded") === "false", "Escape did not close navigation");
    await mobile.fill("#queryInput", query);
    await mobile.click("#searchButton");
    await mobile.waitForSelector(".result-card", { timeout: 90_000 });
    await mobile.locator(".title-link").first().click();
    await mobile.waitForSelector(".title-dialog[open]");
    assert(await mobile.locator(".title-dialog").evaluate((dialog) => dialog.scrollWidth <= dialog.clientWidth + 1), "Mobile details overflow");
    await mobile.screenshot({ path: path.join(root, "artifacts", `${prefix}-mobile-details.png`) });
    await mobile.keyboard.press("Escape");
    await mobile.evaluate(() => scrollTo(0, 0));
    assert(await mobile.evaluate(() => document.body.scrollWidth <= innerWidth + 1), "Mobile horizontal overflow");
    await mobile.screenshot({ path: path.join(root, "artifacts", `${prefix}-mobile-results.png`), fullPage: true });
    await mobile.click("#mobileMenuButton");
    await mobile.locator('.nav-item[data-view-link="system"]').click();
    await mobile.fill("#topKInput", "4");
    await mobile.locator("#topKInput").dispatchEvent("change");
    await mobile.reload({ waitUntil: "domcontentloaded" });
    await mobile.waitForFunction((expected) => document.querySelector("#sidebarStatus")?.textContent === expected, isStatic ? "Showcase ready" : "Engine online", { timeout: 180_000 });
    assert(await mobile.inputValue("#topKInput") === "4", "Search preference did not persist");
    assert(await mobile.locator("#topKInput").isVisible(), "Reload discarded the Settings view");
    await mobile.screenshot({ path: path.join(root, "artifacts", `${prefix}-mobile-settings.png`) });
    report.checks.push("settings-persist-without-navigation-reset");
    for (const width of [320, 768, 1024]) {
      await mobile.setViewportSize({ width, height: 844 });
      await mobile.goto(base + (isStatic ? "/#scenes" : "/#ingest"), { waitUntil: "domcontentloaded" });
      await mobile.waitForSelector(".video-library-item");
      if (!await mobile.locator(".add-media-panel").evaluate((panel) => panel.open)) await mobile.locator(".add-media-panel > summary").click();
      if (!isStatic && !await mobile.locator("#ingestForm .analysis-options").evaluate((panel) => panel.open)) await mobile.locator("#ingestForm .analysis-options > summary").click();
      assert(await mobile.evaluate(() => document.body.scrollWidth <= innerWidth + 1), `Video form overflows at ${width}px`);
      if (width === 320) await mobile.screenshot({ path: path.join(root, "artifacts", `${prefix}-mobile-upload.png`), fullPage: true });
      await mobile.goto(base + "/#system", { waitUntil: "domcontentloaded" });
      if (!await mobile.locator(".technical-details").evaluate((panel) => panel.open)) await mobile.locator(".technical-details > summary").click();
      assert(await mobile.evaluate(() => document.body.scrollWidth <= innerWidth + 1), `Diagnostics overflow at ${width}px`);
    }
    report.checks.push("forms-and-diagnostics-at-320-768-1024");
    report.checks.push("mobile-navigation-keyboard", "mobile-details-and-layout");
    assert(!report.errors.length, JSON.stringify(report.errors));
    console.log(JSON.stringify({ ok: true, ...report }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
