"use strict";

/**
 * /app.js
 * Matched to prayer-room.html IDs.
 * Null-safe so one missing element never breaks the whole app.
 */

function todayISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function dayOfYearFromISO(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  const start = new Date(dt.getFullYear(), 0, 1);
  return Math.floor((dt - start) / 86400000) + 1;
}

function safe(el, fn) {
  if (!el) return;
  fn(el);
}

/* ===== NAME PERSONALIZATION ===== */

const appTitle = document.getElementById("app-title");
const nameModal = document.getElementById("name-modal");
const nameInput = document.getElementById("name-input");
const saveNameBtn = document.getElementById("save-name-btn");

const storedName = localStorage.getItem("prayerRoom:userName");

if (!storedName) {
  if (nameModal) nameModal.hidden = false;
} else {
  safe(appTitle, (el) => (el.textContent = `${storedName}'s Prayer Room`));
}

if (saveNameBtn) {
  saveNameBtn.onclick = () => {
    const name = (nameInput?.value || "").trim();
    if (!name) return;
    localStorage.setItem("prayerRoom:userName", name);
    safe(appTitle, (el) => (el.textContent = `${name}'s Prayer Room`));
    if (nameModal) nameModal.hidden = true;
  };
}

/* ===== DATE CONTROLS ===== */

const dateInput = document.getElementById("prayer-date");
const todayBtn = document.getElementById("today-btn");

if (dateInput) dateInput.value = todayISO();

if (todayBtn) {
  todayBtn.onclick = () => {
    if (dateInput) dateInput.value = todayISO();
    loadByDate(todayISO());
    renderForDate(todayISO());
  };
}

/* ===== DOCTRINES (FULL TEXT) ===== */

const doctrines = [
  { title:"Salvation Army Doctrine #1",  text:"We believe that the Scriptures of the Old and New Testaments were given by inspiration of God, and that they only constitute the Divine rule of Christian faith and practice." },
  { title:"Salvation Army Doctrine #2",  text:"We believe that there is only one God, who is infinitely perfect, the Creator, Preserver, and Governor of all things, and who is the only proper object of religious worship." },
  { title:"Salvation Army Doctrine #3",  text:"We believe that there are three persons in the Godhead-the Father, the Son, and the Holy Ghost, undivided in essence and co-equal in power and glory." },
  { title:"Salvation Army Doctrine #4",  text:"We believe that in the person of Jesus Christ the Divine and human natures are united, so that He is truly and properly God and truly and properly man." },
  { title:"Salvation Army Doctrine #5",  text:"We believe that our first parents were created in a state of innocency, but by their disobedience, they lost their purity and happiness, and that in consequence of their fall, all men have become sinners, totally depraved, and as such are justly exposed to the wrath of God." },
  { title:"Salvation Army Doctrine #6",  text:"We believe that the Lord Jesus Christ has by His suffering and death made an atonement for the whole world so that whosoever will may be saved." },
  { title:"Salvation Army Doctrine #7",  text:"We believe that repentance toward God, faith in our Lord Jesus Christ and regeneration by the Holy Spirit are necessary to salvation." },
  { title:"Salvation Army Doctrine #8",  text:"We believe that we are justified by grace through faith in our Lord Jesus Christ and that he that believeth hath the witness in himself." },
  { title:"Salvation Army Doctrine #9",  text:"We believe that continuance in a state of salvation depends upon continued obedient faith in Christ." },
  { title:"Salvation Army Doctrine #10", text:"We believe that it is the privilege of all believers to be wholly sanctified, and that their whole spirit and soul and body may be preserved blameless unto the coming of our Lord Jesus Christ." },
  { title:"Salvation Army Doctrine #11", text:"We believe in the immortality of the soul, the resurrection of the body, in the general judgement at the end of the world, in the eternal happiness of the righteous, and in the endless punishment of the wicked." }
];

function doctrineForISO(iso) {
  const doy = dayOfYearFromISO(iso);
  return doctrines[(doy - 1) % doctrines.length];
}

function renderDoctrine(iso) {
  const d = doctrineForISO(iso);
  const titleEl = document.getElementById("doctrine-title");
  const textEl = document.getElementById("doctrine-text");
  safe(titleEl, (el) => (el.textContent = d.title));
  safe(textEl, (el) => (el.textContent = d.text));
}

/* ===== SCRIPTURE ===== */

async function loadScriptureJSON() {
  const urls = ["nlt_for_app_365.json", "nlt_for_app_365.json"];
  for (const url of urls) {
    try {
      const r = await fetch(url, { cache: "no-store" });
      if (r.ok) return await r.json();
    } catch {}
  }
  throw new Error("Scripture dataset not found");
}

async function renderScripture(iso) {
  const textEl = document.getElementById("scripture-text");
  const refEl = document.getElementById("scripture-ref");
  safe(textEl, (el) => (el.textContent = "Loading..."));
  safe(refEl, (el) => (el.textContent = ""));

  try {
    const data = await loadScriptureJSON();
    const arr = Array.isArray(data) ? data : (data?.verses || data?.data || []);
    const doy = dayOfYearFromISO(iso);
    const idx = Math.min(Math.max(doy - 1, 0), arr.length - 1);
    const v = arr[idx];

    const verseText = String(v?.text || v?.verse || v?.content || "").trim();
    const verseRef = String(v?.reference || v?.ref || v?.verse_ref || v?.citation || "").trim();

    safe(textEl, (el) => (el.textContent = verseText || "(No verse found)"));
    safe(refEl, (el) => (el.textContent = verseRef));
  } catch (e) {
    safe(textEl, (el) => (el.textContent = "Could not load scripture dataset."));
    safe(refEl, (el) => (el.textContent = ""));
    console.error(e);
  }
}

function renderForDate(iso) {
  renderDoctrine(iso);
  renderScripture(iso);
}

/* ===== STORAGE ===== */

const prayerList = document.getElementById("prayer-list");
const prayersText = document.getElementById("prayers-text");
const petitionsText = document.getElementById("petitions-text");

function key(t, d) { return `prayerRoom:${t}:${d}`; }

function loadByDate(d) {
  safe(prayersText, (el) => (el.innerHTML = localStorage.getItem(key("prayer", d)) || ""));
  safe(petitionsText, (el) => (el.innerHTML = localStorage.getItem(key("petitions", d)) || ""));
}

const initialISO = todayISO();
loadByDate(initialISO);
renderForDate(initialISO);

if (dateInput) {
  dateInput.onchange = () => {
    loadByDate(dateInput.value);
    renderForDate(dateInput.value);
  };
}

safe(prayerList, (el) => (el.innerHTML = localStorage.getItem("prayerRoom:prayerList") || ""));
if (prayerList) prayerList.oninput = () => localStorage.setItem("prayerRoom:prayerList", prayerList.innerHTML);

if (prayersText && dateInput) prayersText.oninput = () => localStorage.setItem(key("prayer", dateInput.value), prayersText.innerHTML);
if (petitionsText && dateInput) petitionsText.oninput = () => localStorage.setItem(key("petitions", dateInput.value), petitionsText.innerHTML);

