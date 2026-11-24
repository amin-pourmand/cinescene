(() => {
  const fa = {
    navSearch:"پیدا کردن فیلم",navVideo:"افزودن فیلم",navEvidence:"بررسی نتیجه",open:"ورود به سین‌سین",
    heroLead:"یه صحنه بگو،",heroSecond:"با هم فیلمش رو پیدا کنیم.",
    heroCaption:"با توصیف یک صحنه، فیلم یا سریال مرتبط را پیدا کنید.",
    example:"مشاهدهٔ نمونهٔ جست‌وجو",chapterOne:"پیدا کردن فیلم",
    memoryTitle:"جست‌وجوی فیلم از روی صحنه",
    memoryBody:"دیالوگ، حرکت شخصیت یا مکان صحنه را توصیف کنید. سین‌سین مفهوم توصیف شما را با داستان‌ها و صحنه‌های مجموعه مقایسه می‌کند.",
    memoryDetail:"لازم نیست نام فیلم یا عین دیالوگ را بدانید. همان چیزی را که به یاد دارید، به فارسی یا انگلیسی بنویسید. اگر چند فیلم شبیه هم بودند، جزئیات مشخص‌تری به توصیف اضافه کنید.",
    query:"مردی برای پیدا کردن قاتل همسرش سرنخ‌ها را روی بدنش خالکوبی می‌کند و از آدم‌ها عکس فوری می‌گیرد.",
    story:"تطبیق با داستان",try:"امتحان این جست‌وجو",
    exampleDetail:"در این نمونه، خالکوبی‌ها و عکس‌های فوری سرنخ‌هایی هستند که به فیلم Memento اشاره می‌کنند.",
    chapterTwo:"افزودن فیلم",videoTitle:"فیلم را به مجموعهٔ خود اضافه کنید",
    videoBody:"در استودیو، فایل فیلم را انتخاب کنید و «افزودن به مجموعه» را بزنید. سین‌سین فیلم را بررسی می‌کند و آن را به مجموعهٔ شما اضافه می‌کند تا در جست‌وجو پیدا شود.",
    videoResult:"بعد از آماده‌شدن فیلم، صحنه‌ای از آن را توصیف کنید. از نتیجه می‌توانید فیلم را پیدا کنید و اگر صحنهٔ مرتبط مشخص شد، همان بخش را ببینید.",
    import:"فایل فیلم را انتخاب کنید",segment:"سین‌سین فیلم را بررسی می‌کند",index:"فیلم را در جست‌وجو پیدا کنید",
    importDetail:"برای افزودن چند فیلم، می‌توانید مسیر پوشه را در استودیو وارد کنید. زیرنویس اختیاری است و به پیدا کردن دیالوگ‌ها کمک می‌کند.",
    segmentDetail:"سین‌سین شروع و پایان صحنه‌ها را پیدا می‌کند و اطلاعاتی مثل تصاویر مهم و دیالوگ‌های در دسترس را ثبت می‌کند.",
    indexDetail:"وقتی استودیو تأیید کرد که فیلم اضافه شده، وارد بخش جست‌وجو شوید و صحنه‌ای از آن را توصیف کنید.",
    chapterThree:"بررسی نتیجه",evidenceTitle:"از نتیجه به متن یا صحنه برسید",
    evidenceBody:"نتیجه را باز کنید تا ببینید سین‌سین چرا این عنوان را پیشنهاد کرده است. بسته به اطلاعاتی که از فیلم یا سریال در دسترس است، بخشی از داستان یا صحنهٔ مرتبط را می‌بینید.",
    evidenceDetail:"همهٔ فیلم‌ها زمان دقیق صحنه ندارند. نمونهٔ Memento از روی خلاصهٔ داستان پیدا شده است. در فیلمی که از طریق استودیو اضافه شده، نتیجهٔ صحنه‌محور می‌تواند شما را مستقیم به همان بخش ویدیو ببرد.",
    storyDetail:"در صورت وجود، بخش مرتبط از خلاصهٔ فیلم یا قسمت سریال را بخوانید.",
    scene:"صحنهٔ زمان‌دار",sceneDetail:"برای ویدیوهای پردازش‌شده در استودیو، صحنهٔ مرتبط را پیدا کنید و آن را در زمان ثبت‌شده باز کنید.",
    recordedExample:"مشاهدهٔ آزمون ثبت‌شدهٔ صحنه",recordedResult:"در یک ویدیوی بی‌صدای هشت‌ثانیه‌ای، با توصیف تغییر تصویر از یک گل به یک ساختمان، صحنهٔ دوم پیدا شد. این صحنه از ثانیهٔ ۴ آغاز می‌شود.",
    flower:"گل",tower:"برج",credits:"منابع تصاویر",
    endTitle:"کدام صحنه را به خاطر دارید؟",endBody:"از یک صحنه، بخشی از یک دیالوگ یا هر جزئیاتی که در خاطرتان مانده شروع کنید.",
    startSearch:"شروع جست‌وجو",openVideos:"افزودن فیلم در استودیو",
  };
  const en = Object.fromEntries([...document.querySelectorAll("[data-copy]")].map(el => [el.dataset.copy,el.textContent]));
  const read = key => { try { return localStorage.getItem(key); } catch { return null; } };
  const save = (key,value) => { try { localStorage.setItem(key,value); } catch {} };
  const gate = document.getElementById("languageGate"), journey = document.getElementById("journey");
  const change = document.getElementById("switchLanguage");
  const params = new URLSearchParams(location.search);
  const returnView = params.get("return");
  const motion = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  let language = "en";

  function pick(lang, {reset = false} = {}) {
    language = lang;
    save("cinescene-language", lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "fa" ? "rtl" : "ltr";
    document.title = lang === "fa" ? "سین‌سین" : "CineScene";
    const copy = lang === "fa" ? fa : en;
    document.querySelectorAll("[data-copy]").forEach(node => { node.textContent = copy[node.dataset.copy]; });
    change.querySelector("span").textContent = lang === "fa" ? "English" : "فارسی";
    change.querySelector("span").lang = lang === "fa" ? "en" : "fa";
    change.setAttribute("aria-label", lang === "fa" ? "Switch to English" : "تغییر زبان به فارسی");
    document.getElementById("chapterNav").hidden = false;
    document.getElementById("chapterNav").setAttribute("aria-label", lang === "fa" ? "فصل‌های معرفی" : "Introduction chapters");
    const root = new URL("../../", location.href);
    root.searchParams.set("draft", copy.query);
    root.hash = "discover";
    document.getElementById("tryExample").href = root;
    gate.hidden = true;
    journey.hidden = false;
    document.documentElement.classList.add("journey-open");
    change.hidden = false;
    if (reset) {
      const chapter = document.getElementById(location.hash.slice(1));
      if (chapter?.classList.contains("chapter")) {
        chapter.scrollIntoView({behavior:"instant"});
        chapter.querySelector("h2")?.focus({preventScroll:true});
      } else {
        window.scrollTo({top:0,behavior:"instant"});
        document.getElementById("mainTitle").focus({preventScroll:true});
      }
    }
    updateScroll();
  }

  document.querySelectorAll("[data-language]").forEach(button => {
    button.addEventListener("click", () => {
      if (params.has("choose") && ["discover","ingest","scenes","library","system"].includes(returnView)) {
        save("cinescene-language", button.dataset.language);
        const root = new URL("../../", location.href);
        root.hash = returnView;
        location.replace(root);
      } else {
        pick(button.dataset.language, {reset:true});
      }
    });
    button.disabled = false;
  });
  change.addEventListener("click", () => pick(language === "fa" ? "en" : "fa"));
  if (motion) document.documentElement.classList.add("motion-ready");
  let waiting = false;
  const links = [...document.querySelectorAll("#chapterNav a")];
  const hero = document.querySelector(".cinema-hero");
  const scenes = [...document.querySelectorAll("#journey .reveal, .chapter-splice")];
  const cues = [...document.querySelectorAll("[data-scroll-cue]")];
  const cueDelays = cues.map(node => node.closest(".process-rail") ? [...node.parentElement.children].indexOf(node) * .07 : 0);
  const clamp = value => Math.min(1, Math.max(0,value));
  const ease = value => value * value * (3 - 2 * value);
  function updateScroll() {
    if (journey.hidden) return;
    const distance = document.documentElement.scrollHeight - innerHeight;
    const progress = clamp(window.scrollY / Math.max(1, distance));
    const active = progress >= .999 ? links.at(-1) : links.findLast(link => document.getElementById(link.hash.slice(1)).getBoundingClientRect().top <= innerHeight * .45);
    document.documentElement.style.setProperty("--read", progress);
    if (motion) {
      const boxes = scenes.map(node => node.getBoundingClientRect());
      const cueTops = cues.map(node => node.getBoundingClientRect().top);
      const travel = clamp(window.scrollY / Math.max(1, hero.offsetHeight));
      hero.style.setProperty("--travel", travel.toFixed(3));
      hero.style.setProperty("--dim", (.24 * ease(travel)).toFixed(3));
      scenes.forEach((scene, i) => {
        const box = boxes[i];
        const arrival = clamp((innerHeight * .99 - box.top) / (innerHeight * .52));
        scene.style.setProperty("--arrival", ease(arrival).toFixed(3));
        scene.style.setProperty("--drift", (clamp((innerHeight - box.top) / (innerHeight + box.height)) - .5).toFixed(3));
        scene.style.setProperty("--light", (Math.sin(ease(arrival) * Math.PI) * .34).toFixed(3));
      });
      cues.forEach((node, i) => {
        const progress = clamp((innerHeight * (.96 - cueDelays[i]) - cueTops[i]) / (innerHeight * .30));
        node.style.setProperty("--cue", ease(progress).toFixed(3));
      });
    }
    links.forEach(link => { if (link === active) link.setAttribute("aria-current","location"); else link.removeAttribute("aria-current"); });
  }
  window.addEventListener("scroll", () => { if (!waiting) { waiting = true; requestAnimationFrame(() => { updateScroll(); waiting = false; }); } },{passive:true});
  window.addEventListener("resize", updateScroll);
  const savedLanguage = read("cinescene-language");
  if (!params.has("choose") && ["en","fa"].includes(savedLanguage)) {
    pick(savedLanguage);
    const chapter = document.getElementById(location.hash.slice(1));
    if (chapter?.classList.contains("chapter")) requestAnimationFrame(() => chapter.scrollIntoView({behavior:"instant"}));
  }
  window.lucide?.createIcons();
})();
