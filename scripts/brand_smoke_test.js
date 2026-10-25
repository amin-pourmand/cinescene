const { chromium } = require("playwright-core");
const path = require("path");

const root = path.resolve(__dirname, "..");
const base = (process.argv[2] || "http://127.0.0.1:8000").replace(/\/$/, "");
const label = process.argv[3] || "local";

(async () => {
  const browser = await chromium.launch({ executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", headless: true });
  try {
    const report = [];
    for (const [name, width, height] of [["desktop", 1440, 1000], ["mobile", 390, 844]]) {
      const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 2 });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(base + "/", { waitUntil: "domcontentloaded" });
      await page.evaluate(() => document.fonts.ready);
      if (name === "mobile") await page.click("#mobileMenuButton");
      await page.waitForFunction(() => {
        const logo = document.querySelector("img.brand-mark");
        return logo && logo.complete && logo.naturalWidth > 0;
      });
      const result = await page.locator(".brand").evaluate((brand) => {
        const box = brand.getBoundingClientRect();
        const logo = brand.querySelector("img").getBoundingClientRect();
        const text = brand.querySelector(".brand-copy").getBoundingClientRect();
        return { logo_width: logo.width, logo_height: logo.height,
          fits: logo.right <= text.left && text.right <= box.right + 1,
          overflow: document.body.scrollWidth > innerWidth + 1 };
      });
      await page.locator(".brand").screenshot({ path: path.join(root, "artifacts", `brand-${label}-${name}.png`), animations: "disabled" });
      await page.screenshot({ path: path.join(root, "artifacts", `brand-${label}-${name}-page.png`) });
      report.push({ viewport: name, ...result, errors });
      if (!result.fits || result.overflow || errors.length) throw new Error(JSON.stringify(report));
      await page.close();
    }
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
