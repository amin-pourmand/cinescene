(() => {
  let fa = false;
  try { fa = localStorage.getItem("cinescene-language") === "fa"; } catch {}
  const labels = {Search:"جست‌وجو","Your videos":"ویدیوهای شما",Videos:"ویدیوها","Saved & history":"ذخیره‌شده‌ها و تاریخچه",Settings:"تنظیمات",
    "Video library":"مجموعهٔ ویدیوها","Video import guide":"راهنمای افزودن ویدیو",Language:"زبان",
    "Open navigation":"باز کردن منو","Close navigation":"بستن منو",
    "Add a video":"افزودن ویدیو","Add a film to your collection":"افزودن فیلم به مجموعه","Connect to Studio":"اتصال به استودیو",
    "Preview a local file":"پخش فایل در مرورگر","Processed videos":"ویدیوهای پردازش‌شده","Scene examples":"نمونهٔ صحنه‌ها",
    "Silent video test":"آزمون ویدیوی بی‌صدا","Open recorded test":"مشاهدهٔ آزمون ثبت‌شده",
    "To add a film and find it in Search later, connect to CineScene Studio. The preview below only plays the file in your browser.":"برای افزودن فیلم و پیدا کردن آن در جست‌وجو، به استودیو سین‌سین وصل شوید. پیش‌نمایش فقط فایل را در مرورگر پخش می‌کند.",
    "Choose a film file and select Add to collection. When CineScene finishes, you can find the film by describing a scene from it.":"فایل فیلم را انتخاب کنید و «افزودن به مجموعه» را بزنید. بعد از پایان کار، می‌توانید فیلم را با توصیف یک صحنه پیدا کنید.",
    "Choose a film":"انتخاب فیلم","Drop a video here":"فایل ویدیو را اینجا رها کنید","Choose file":"انتخاب فایل","Video selected":"ویدیو انتخاب شد",
    "Title or episode name":"نام فیلم یا قسمت سریال","Subtitle files":"فایل زیرنویس","Add subtitles":"افزودن زیرنویس",
    "Optional · SRT, VTT, ASS or SSA":"اختیاری؛ SRT، VTT، ASS یا SSA","subtitle file selected":"فایل زیرنویس انتخاب شد","subtitle files selected":"فایل زیرنویس انتخاب شد",
    "Processing settings":"تنظیمات پردازش","Add to collection":"افزودن به مجموعه","Prepare the film":"آماده‌سازی فیلم",
    "Waiting for a film":"در انتظار انتخاب فیلم","Receive the file":"دریافت فایل","Video and any subtitles you added":"ویدیو و زیرنویس‌هایی که اضافه کرده‌اید",
    "Find the scenes":"تشخیص صحنه‌ها","Save where scenes start, key images and any available dialogue":"ثبت زمان شروع صحنه‌ها، تصاویر مهم و دیالوگ‌های در دسترس",
    "Add the film":"افزودن فیلم","Make the film available in Search":"اضافه شدن فیلم به جست‌وجو",
    "Ready to add a film.":"آمادهٔ افزودن فیلم.","Ready to add films":"آمادهٔ افزودن فیلم","Video import unavailable":"افزودن ویدیو در دسترس نیست",
    "Find the film in Search":"پیدا کردن فیلم در جست‌وجو","Go to Search":"رفتن به جست‌وجو","No processed videos yet.":"هنوز ویدیویی پردازش نشده است.",
    "After CineScene adds the film, look for it by describing a scene. You can also open the scene list from the processed videos below.":"وقتی فیلم اضافه شد، صحنه‌ای از آن را توصیف کنید تا پیدایش کنید. فهرست صحنه‌ها هم از بخش ویدیوهای پردازش‌شده قابل مشاهده است.",
    "Finished":"آماده‌سازی تمام شد","Preparing the film":"در حال آماده‌سازی فیلم","The film could not be added":"فیلم اضافه نشد","Finished with notes":"آماده‌سازی تمام شد؛ پیام پردازش را ببینید",
    "Could not reconnect to processing":"ارتباط با پردازش دوباره برقرار نشد","Reconnect to processing":"اتصال دوباره به پردازش",
    "The previous import was not found. Select the file again to restart.":"پردازش قبلی پیدا نشد. برای شروع دوباره، فایل را انتخاب کنید.",
    "Film added to the collection. You can now look for it in Search.":"فیلم به مجموعه اضافه شد. حالا می‌توانید آن را در جست‌وجو پیدا کنید.",
    "Videos added to the collection. You can now look for them in Search.":"ویدیوها به مجموعه اضافه شدند. حالا می‌توانید آن‌ها را در جست‌وجو پیدا کنید.",
    "See how images captured at different times helped identify a scene in a clip with no dialogue.":"ببینید تصاویر ثبت‌شده در زمان‌های مختلف چگونه به شناسایی یک صحنه در ویدیویی بدون دیالوگ کمک کردند.",
    "Find a film or series":"جست‌وجوی فیلم یا سریال","Scene description":"توصیف صحنه","Search example":"نمونهٔ جست‌وجو",Examples:"نمونه‌ها",
    "Recent searches":"جست‌وجوهای اخیر",Results:"نتایج",Cancel:"لغو","No matches":"نتیجه‌ای پیدا نشد",
    "Add video":"افزودن ویدیو","Compare frames":"مقایسه فریم‌ها","Connect computer":"اتصال به رایانه",
    "Search scope":"محدودهٔ جست‌وجو","Movies & series":"فیلم‌ها و سریال‌ها",Movies:"فیلم‌ها",Series:"سریال‌ها",
    "Exact dialogue":"عین دیالوگ","Text search (no models)":"جست‌وجوی متنی (بدون مدل)","With scene evidence":"دارای شاهد صحنه","Details":"جزئیات",
    "Scene timeline":"خط زمانی صحنه‌ها","Timed scene":"صحنهٔ زمان‌دار","Episode summary":"خلاصهٔ قسمت","Story match":"شاهد داستانی"};
  const word = text => (fa && labels[text]) || text;
  window.cinesceneWord = word;
  if (!fa) return;
  const selectors = ".nav-item > span, .search-heading h2, .examples-label, .search-button span, " +
    ".topbar-actions .button span, .section-header h3, .recent-section > span, .page-heading h2, .search-settings option, " +
    ".add-media-panel summary span, .video-example summary span, .video-example p, .video-example button span, " +
    ".video-connection h3, .video-connection p, .video-connection button span, [data-workspace-copy]";
  document.querySelectorAll(selectors).forEach(node => {
    const english = node.textContent.trim();
    if (!labels[english]) return;
    node.textContent = labels[english];
    node.lang = "fa";
    node.dir = "auto";
  });
  const field = document.getElementById("queryInput"), label = document.querySelector('label[for="queryInput"]');
  if (label?.lastChild) label.lastChild.textContent = " توصیف صحنه";
  field?.setAttribute("aria-label", word("Scene description"));
  field?.setAttribute("placeholder","دیالوگ یا صحنه‌ای را که به خاطر دارید توصیف کنید…");
  document.querySelector(".search-settings select")?.setAttribute("aria-label",word("Search scope"));
  const addVideo = document.querySelector('.topbar [data-view-link="import-video"]');
  for (const attr of ["aria-label","title"]) addVideo?.setAttribute(attr, word("Add video"));
  document.getElementById("movieTitleInput")?.setAttribute("placeholder","به‌صورت پیش‌فرض از نام فایل");
})();
