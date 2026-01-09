function todayISO() {
  return new Date().toISOString().split("T")[0];
}

const currentDateEl = document.getElementById("current-date");
const prayerListEl = document.getElementById("prayer-list");
const prayersTextEl = document.getElementById("prayers-text");
const prayerDateEl = document.getElementById("prayer-date");
const todayBtn = document.getElementById("today-btn");

currentDateEl.textContent = new Date().toLocaleDateString();
prayerDateEl.value = todayISO();

prayerListEl.innerHTML = localStorage.getItem("prayerList") || "";
prayersTextEl.innerHTML = localStorage.getItem("prayersText") || "";

prayerListEl.addEventListener("input", () => {
  localStorage.setItem("prayerList", prayerListEl.innerHTML);
});

prayersTextEl.addEventListener("input", () => {
  localStorage.setItem("prayersText", prayersTextEl.innerHTML);
});

todayBtn.addEventListener("click", () => {
  prayerDateEl.value = todayISO();
});

