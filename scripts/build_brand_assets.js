const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright-core");

const root = path.resolve(__dirname, "..");
const source = path.join(root, "frontend/assets");
const target = path.join(root, "docs/assets");
const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

(async () => {
  const browser = await chromium.launch({ executablePath: chrome, headless: true });
  try {
    const page = await browser.newPage();
    const artwork = fs.readFileSync(path.join(source, "brand-symbol.jpg"));
    const imageUrl = "data:image/jpeg;base64," + artwork.toString("base64");
    const dimensions = await page.evaluate(async (url) => {
      const image = new Image();
      image.src = url;
      await image.decode();
      return { width: image.naturalWidth, height: image.naturalHeight };
    }, imageUrl);
    if (dimensions.width !== dimensions.height || dimensions.width < 1024) {
      throw new Error("Expected the supplied square artwork at 1024px or larger; refusing to upscale.");
    }
    // SVG compatibility assets embed the original artwork; they are not vector redraws.
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${dimensions.width} ${dimensions.height}" role="img" aria-label="CineScene"><image width="${dimensions.width}" height="${dimensions.height}" href="${imageUrl}"/></svg>\n`;
    for (const name of ["brand-mark.svg", "icon.svg"]) {
      fs.writeFileSync(path.join(source, name), svg);
      fs.writeFileSync(path.join(target, name), svg);
    }
    for (const [name, size, inset] of [
      ["icon-192.png", 192, 0], ["icon-512.png", 512, 0],
      ["icon-1024.png", 1024, 0], ["icon-maskable-512.png", 512, .06],
      ["apple-touch-icon.png", 180, 0], ["favicon-32.png", 32, 0],
      ["brand-mark-512.png", 512, 0],
    ]) {
      const data = await page.evaluate(async ({ name, imageUrl, size, inset }) => {
        const image = new Image();
        image.src = imageUrl;
        await image.decode();
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = size;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#050c1a";
        ctx.fillRect(0, 0, size, size);
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(image, size * inset, size * inset, size * (1 - inset * 2), size * (1 - inset * 2));
        if (name === "icon-maskable-512.png") {
          const pixels = ctx.getImageData(0, 0, size, size).data;
          for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
              const i = (y * size + x) * 4;
              if (pixels[i + 3] !== 255) throw new Error("Maskable icon must be fully opaque.");
              const isReel = pixels[i] > 100 && pixels[i] > pixels[i + 2] * 1.3;
              if (isReel && Math.hypot(x - size / 2, y - size / 2) > size * .4) {
                throw new Error("Film-reel artwork exceeds the maskable icon safe zone.");
              }
            }
          }
        }
        return canvas.toDataURL("image/png").split(",")[1];
      }, { name, imageUrl, size, inset });
      const bytes = Buffer.from(data, "base64");
      fs.writeFileSync(path.join(source, name), bytes);
      fs.writeFileSync(path.join(target, name), bytes);
      console.log(`${name}: ${size}x${size}, ${bytes.length} bytes`);
    }
    for (const name of ["brand-symbol.jpg", "brand-lockup.jpg"]) {
      fs.copyFileSync(path.join(source, name), path.join(target, name));
    }
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
