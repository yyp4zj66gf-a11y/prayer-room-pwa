const SCRIPTURES = [
  "Psalm 23:1 — The LORD is my shepherd; I shall not want.",
  "Isaiah 41:10 — Fear thou not; for I am with thee...",
  "Matthew 11:28 — Come unto me... and I will give you rest.",
  "John 3:16 — For God so loved the world...",
  "Romans 8:28 — All things work together for good..."
];

const DOCTRINES = [
  "We believe that the Scriptures of the Old and New Testaments were given by inspiration of God, and that they only constitute the Divine rule of Christian faith and practice.",
  "We believe that there is only one God, who is infinitely perfect, the Creator, Preserver, and Governor of all things, and who is the only proper object of religious worship.",
  "We believe that there are three persons in the Godhead — the Father, the Son and the Holy Ghost, undivided in essence and co-equal in power and glory."
];

const $ = (id) => document.getElementById(id);

const K = {
  name: "pr_name",
  daily: "pr_daily_list",
  prayers: "pr_prayers_by_date",
  scrIdx: "pr_scripture_idx",
  docIdx: "pr_doctrine_idx"
};

function isoDate(d) {
  const x = new Date(d);
  const yyyy = x.getFullYear();
  const mm = String(x.getMonth() + 1).padStart(2, "0");
  const dd = String(x.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}
function dayOrdinal(d) {
  const x = new Date(d); x.setHours(0,0,0,0);
  return Math.floor(x.getTime() / 86400000);
}
function rotateIndex(mod) { return mod > 0 ? (dayOrdinal(new Date()) % mod) : 0; }

function loadJson(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || ""); } catch { return fallback; }
}
function saveJson(key, value) { localStorage.setItem(key, JSON.stringify(value)); }

function setStatus(msg) {
  const s = $("status");
  s.textContent = msg || "";
  clearTimeout(setStatus._t);
  setStatus._t = setTimeout(() => (s.textContent = ""), 3000);
}

function renderHeader(name) {
  $("title").textContent = `${name}'s Prayer Room`;
  $("dateLabel").textContent = new Date().toLocaleDateString(undefined, {
    weekday:"long", year:"numeric", month:"long", day:"numeric"
  });
}

function registerSW() {
}

function exportBackup() {
  const payload = {
    meta: { app:"Prayer Room PWA", exportedAt:new Date().toISOString(), version:1 },
    name: localStorage.getItem(K.name) || "",
    daily: localStorage.getItem(K.daily) || "",
    prayers: loadJson(K.prayers, {}),
    scriptureIndex: Number(localStorage.getItem(K.scrIdx) || "0"),
    doctrineIndex: Number(localStorage.getItem(K.docIdx) || "0")
  };
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type:"application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `PrayerRoom-Backup-${stamp}.json`;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
  setStatus("Exported backup.");
}

async function importBackup(file) {
  let payload;
  try { payload = JSON.parse(await file.text()); } catch { alert("Invalid backup file."); return; }

  const replace = confirm("Import backup:\n\nOK = Replace everything\nCancel = Merge");
  if (replace) localStorage.clear();

  if (payload?.name !== undefined) localStorage.setItem(K.name, String(payload.name || ""));
  if (payload?.daily !== undefined) localStorage.setItem(K.daily, String(payload.daily || ""));

  const currentPrayers = loadJson(K.prayers, {});
  const incoming = payload?.prayers && typeof payload.prayers === "object" ? payload.prayers : {};
  const merged = replace ? incoming : { ...currentPrayers, ...incoming };
  saveJson(K.prayers, merged);

  if (Number.isFinite(payload?.scriptureIndex)) localStorage.setItem(K.scrIdx, String(payload.scriptureIndex));
  if (Number.isFinite(payload?.doctrineIndex)) localStorage.setItem(K.docIdx, String(payload.doctrineIndex));

  location.reload();
}

function main() {
  registerSW();

  let name = (localStorage.getItem(K.name) || "").trim();
  if (!name) {
    const got = prompt("Welcome! What is your first name? (You can skip.)", "");
    if (got !== null) {
      name = got.trim() || "Friend";
      localStorage.setItem(K.name, name);
    } else {
      name = "Friend";
    }
  }
  renderHeader(name);

  const prayersByDate = loadJson(K.prayers, {});
  const today = isoDate(new Date());
  $("prayerDate").value = today;

  $("dailyList").value = localStorage.getItem(K.daily) || "";
  $("prayerText").value = prayersByDate[today] || "";

  let scrIdx = localStorage.getItem(K.scrIdx);
  let docIdx = localStorage.getItem(K.docIdx);
  let scriptureIndex = scrIdx === null ? rotateIndex(SCRIPTURES.length) : Number(scrIdx || "0");
  let doctrineIndex = docIdx === null ? rotateIndex(DOCTRINES.length) : Number(docIdx || "0");

  function renderScr() { $("scriptureText").textContent = SCRIPTURES[scriptureIndex] || ""; }
  function renderDoc() {
    $("doctrineTitle").textContent = `Salvation Army Doctrine #${doctrineIndex + 1}`;
    $("doctrineText").textContent = DOCTRINES[doctrineIndex] || "";
  }
  renderScr(); renderDoc();

  $("changeNameBtn").onclick = () => {
    const got = prompt("Enter your first name:", name);
    if (got === null) return;
    name = got.trim() || "Friend";
    localStorage.setItem(K.name, name);
    renderHeader(name);
    setStatus("Name saved.");
  };

  $("saveList").onclick = () => {
    localStorage.setItem(K.daily, $("dailyList").value || "");
    setStatus("Saved Daily Prayer List.");
  };

  $("savePrayer").onclick = () => {
    const d = $("prayerDate").value || today;
    prayersByDate[d] = $("prayerText").value || "";
    saveJson(K.prayers, prayersByDate);
    setStatus(`Saved prayer for ${d}.`);
  };

  $("prayerDate").onchange = () => {
    const d = $("prayerDate").value || today;
    $("prayerText").value = prayersByDate[d] || "";
    setStatus(`Loaded ${d}.`);
  };

  $("todayBtn").onclick = () => {
    $("prayerDate").value = today;
    $("prayerText").value = prayersByDate[today] || "";
  };

  $("scrPrev").onclick = () => {
    scriptureIndex = (scriptureIndex - 1 + SCRIPTURES.length) % SCRIPTURES.length;
    localStorage.setItem(K.scrIdx, String(scriptureIndex));
    renderScr();
  };
  $("scrNext").onclick = () => {
    scriptureIndex = (scriptureIndex + 1) % SCRIPTURES.length;
    localStorage.setItem(K.scrIdx, String(scriptureIndex));
    renderScr();
  };
  $("scrCopy").onclick = async () => {
    try { await navigator.clipboard.writeText($("scriptureText").textContent || ""); setStatus("Copied scripture."); }
    catch { setStatus("Copy not available."); }
  };

  $("docPrev").onclick = () => {
    doctrineIndex = (doctrineIndex - 1 + DOCTRINES.length) % DOCTRINES.length;
    localStorage.setItem(K.docIdx, String(doctrineIndex));
    renderDoc();
  };
  $("docNext").onclick = () => {
    doctrineIndex = (doctrineIndex + 1) % DOCTRINES.length;
    localStorage.setItem(K.docIdx, String(doctrineIndex));
    renderDoc();
  };

  $("exportBtn").onclick = () => exportBackup();
  $("importFile").onchange = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f) await importBackup(f);
  };
}

main();
