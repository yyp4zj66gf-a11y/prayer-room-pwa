"use strict";

const APP_ID = "prayerRoom";
const STORAGE_PREFIX = `${APP_ID}:`;

function $(sel, root = document) { return root.querySelector(sel); }
function $all(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

function pickEl(selectors) {
  for (const sel of selectors) {
    const el = $(sel);
    if (el) return el;
  }
  return null;
}

function pickButtonByText(text) {
  const t = text.trim().toLowerCase();
  return $all("button").find((b) => (b.textContent || "").trim().toLowerCase() === t) || null;
}

function isoTodayLocal() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function addDaysISO(iso, deltaDays) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() + deltaDays);
  const yy = dt.getFullYear();
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const dd = String(dt.getDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

function dayOfYearFromISO(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  const start = new Date(dt.getFullYear(), 0, 1);
  return Math.floor((dt - start) / 86400000) + 1;
}

function storageKey(name, iso) {
  return iso ? `${STORAGE_PREFIX}${name}:${iso}` : `${STORAGE_PREFIX}${name}`;
}

function safeText(el, value) { if (el) el.textContent = value; }
function safeValue(el, value) { if (el && "value" in el) el.value = value; }

function getTextValue(el) {
  if (!el) return "";
  if ("value" in el) return String(el.value || "");
  if (el.isContentEditable) return el.innerHTML || "";
  return el.textContent || "";
}

function setTextValue(el, value) {
  if (!el) return;
  if ("value" in el) el.value = value;
  else if (el.isContentEditable) el.innerHTML = value;
  else el.textContent = value;
}

async function copyToClipboard(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}

/* ===== DOCTRINES (FULL TEXT) ===== */
const DOCTRINES = [
  { title:"Salvation Army Doctrine #1", text:"We believe that the Scriptures of the Old and New Testaments were given by inspiration of God, and that they only constitute the Divine rule of Christian faith and practice." },
  { title:"Salvation Army Doctrine #2", text:"We believe that there is only one God, who is infinitely perfect, the Creator, Preserver, and Governor of all things, and who is the only proper object of religious worship." },
  { title:"Salvation Army Doctrine #3", text:"We believe that there are three persons in the Godhead-the Father, the Son, and the Holy Ghost, undivided in essence and co-equal in power and glory." },
  { title:"Salvation Army Doctrine #4", text:"We believe that in the person of Jesus Christ the Divine and human natures are united, so that He is truly and properly God and truly and properly man." },
  { title:"Salvation Army Doctrine #5", text:"We believe that our first parents were created in a state of innocency, but by their disobedience, they lost their purity and happiness, and that in consequence of their fall, all men have become sinners, totally depraved, and as such are justly exposed to the wrath of God." },
  { title:"Salvation Army Doctrine #6", text:"We believe that the Lord Jesus Christ has by His suffering and death made an atonement for the whole world so that whosoever will may be saved." },
  { title:"Salvation Army Doctrine #7", text:"We believe that repentance toward God, faith in our Lord Jesus Christ and regeneration by the Holy Spirit are necessary to salvation." },
  { title:"Salvation Army Doctrine #8", text:"We believe that we are justified by grace through faith in our Lord Jesus Christ and that he that believeth hath the witness in himself." },
  { title:"Salvation Army Doctrine #9", text:"We believe that continuance in a state of salvation depends upon continued obedient faith in Christ." },
  { title:"Salvation Army Doctrine #10", text:"We believe that it is the privilege of all believers to be wholly sanctified, and that their whole spirit and soul and body may be preserved blameless unto the coming of our Lord Jesus Christ." },
  { title:"Salvation Army Doctrine #11", text:"We believe in the immortality of the soul, the resurrection of the body, in the general judgement at the end of the world, in the eternal happiness of the righteous, and in the endless punishment of the wicked." },
];

function doctrineForISO(iso) {
  const doy = dayOfYearFromISO(iso);
  return DOCTRINES[(doy - 1) % DOCTRINES.length];
}

/* ===== SCRIPTURE DATA ===== */
let scriptureData = null;

async function fetchFirstOk(urls) {
  let lastErr = null;
  for (const url of urls) {
    try {
      const r = await fetch(url, { cache: "no-store" });
      if (r.ok) return await r.json();
    } catch (e) { lastErr = e; }
  }
  throw lastErr || new Error("Scripture dataset not found");
}

function normalizeScriptureData(raw) {
  if (Array.isArray(raw)) return raw;
  if (raw && Array.isArray(raw.verses)) return raw.verses;
  if (raw && Array.isArray(raw.data)) return raw.data;
  return [];
}

async function loadScriptureData() {
  if (scriptureData) return scriptureData;

  // ✅ Correct: try BOTH filenames (with and without "for")
  const raw = await fetchFirstOk([
    "./nlt_for_app_365.json",
    "./nlt_for_app_365.json",
    "/nlt_for_app_365.json",
    "/nlt_for_app_365.json",
  ]);

  scriptureData = normalizeScriptureData(raw);
  return scriptureData;
}

function verseForISO(data, iso) {
  if (!Array.isArray(data) || data.length === 0) return null;
  const doy = dayOfYearFromISO(iso);
  const idx = Math.min(Math.max(doy - 1, 0), data.length - 1);
  return data[idx];
}

function verseText(v) { return v ? String(v.text || v.verse || v.content || "").trim() : ""; }
function verseRef(v) { return v ? String(v.reference || v.ref || v.verse_ref || v.citation || "").trim() : ""; }

/* ===== DOM ===== */
const dom = {
  title: pickEl(["#app-title", "#title", "header h1", "h1"]),
  dateInput: pickEl(["#prayer-date", "#date", "#date-input", 'input[type="date"]']),
  todayBtn: pickEl(["#today-btn", "#today"]) || pickButtonByText("today"),
  prevBtn: pickEl(["#prev-btn", "#prev"]) || pickButtonByText("prev"),
  nextBtn: pickEl(["#next-btn", "#next"]) || pickButtonByText("next"),
  copyBtn: pickEl(["#copy-btn", "#copy"]) || pickButtonByText("copy"),

  scriptureText: pickEl(["#scripture-text", ".scripture-text"]),
  scriptureRef: pickEl(["#scripture-ref", ".scripture-ref"]),

  doctrineTitle: pickEl(["#doctrine-title", ".doctrine-title"]),
  doctrineText: pickEl(["#doctrine-text", ".doctrine-text"]),

  prayerList: pickEl(["#prayer-list"]),
  praiseText: pickEl(["#prayers-text"]),
  petitionsText: pickEl(["#petitions-text"]),
  saveBtn: pickEl(["#save-btn"]) || pickButtonByText("save"),

  nameModal: pickEl(["#name-modal"]),
  nameInput: pickEl(["#name-input"]),
  nameSaveBtn: pickEl(["#save-name-btn"]),
};

/* ===== NAME ===== */
function initName() {
  const stored = localStorage.getItem(storageKey("userName"));
  if (stored) safeText(dom.title, `${stored}'s Prayer Room`);

  if (dom.nameModal && dom.nameInput && dom.nameSaveBtn) {
    if (!stored) dom.nameModal.hidden = false;

    dom.nameSaveBtn.addEventListener("click", () => {
      const name = String(dom.nameInput.value || "").trim();
      if (!name) return;
      localStorage.setItem(storageKey("userName"), name);
      safeText(dom.title, `${name}'s Prayer Room`);
      dom.nameModal.hidden = true;
    });
  }
}

/* ===== STORAGE ===== */
function loadForDate(iso) {
  setTextValue(dom.prayerList, localStorage.getItem(storageKey("prayerList")) || "");
  setTextValue(dom.praiseText, localStorage.getItem(storageKey("praise", iso)) || "");
  setTextValue(dom.petitionsText, localStorage.getItem(storageKey("petitions", iso)) || "");
}

function saveForDate(iso) {
  if (dom.prayerList) localStorage.setItem(storageKey("prayerList"), getTextValue(dom.prayerList));
  if (dom.praiseText) localStorage.setItem(storageKey("praise", iso), getTextValue(dom.praiseText));
  if (dom.petitionsText) localStorage.setItem(storageKey("petitions", iso), getTextValue(dom.petitionsText));
}

/* ===== RENDER ===== */
async function renderForDate(iso) {
  const d = doctrineForISO(iso);
  safeText(dom.doctrineTitle, d.title);
  safeText(dom.doctrineText, d.text);

  try {
    const data = await loadScriptureData();
    const v = verseForISO(data, iso);
    safeText(dom.scriptureText, verseText(v) || "(Scripture not available)");
    safeText(dom.scriptureRef, verseRef(v));
  } catch (e) {
    safeText(dom.scriptureText, "Could not load scripture dataset.");
    safeText(dom.scriptureRef, "");
    console.error(e);
  }

  loadForDate(iso);
}

/* ===== DATE UI ===== */
function initDateControls() {
  const setISO = async (iso) => {
    if (dom.dateInput) safeValue(dom.dateInput, iso);
    await renderForDate(iso);
  };

  const getISO = () => (dom.dateInput ? String(dom.dateInput.value || "").trim() : "") || isoTodayLocal();

  if (dom.dateInput) dom.dateInput.addEventListener("change", () => renderForDate(getISO()));
  if (dom.todayBtn) dom.todayBtn.addEventListener("click", () => setISO(isoTodayLocal()));
  if (dom.prevBtn) dom.prevBtn.addEventListener("click", () => setISO(addDaysISO(getISO(), -1)));
  if (dom.nextBtn) dom.nextBtn.addEventListener("click", () => setISO(addDaysISO(getISO(), 1)));

  if (dom.copyBtn) {
    dom.copyBtn.addEventListener("click", async () => {
      const text = `${(dom.scriptureText?.textContent || "").trim()} ${(dom.scriptureRef?.textContent || "").trim()}`.trim();
      const ok = await copyToClipboard(text);
      if (!ok) alert("Copy failed. Your browser may block clipboard access.");
    });
  }

  const saveHandler = () => saveForDate(getISO());
  if (dom.saveBtn) dom.saveBtn.addEventListener("click", saveHandler);
  else {
    for (const el of [dom.prayerList, dom.praiseText, dom.petitionsText]) {
      if (el) el.addEventListener("input", saveHandler);
    }
  }

  setISO(getISO());
}

/* ===== BOOT ===== */
document.addEventListener("DOMContentLoaded", () => {
  initName();
  initDateControls();
});

