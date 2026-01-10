(function () {
  "use strict";

  document.addEventListener("PrayerRoomPayloadReady", () => {
    const p = window.PRAYER_ROOM_PAYLOAD;
    if (!p) return;

    document.querySelector("[data-bind='date']").textContent = p.date;

    document.querySelector("[data-bind='scripture']").innerHTML =
      `<strong>${p.scripture.ref}</strong><br><br>${p.scripture.text}`;

    document.querySelector("[data-bind='doctrine']").innerHTML =
      `<strong>Doctrine #${p.doctrine.index}</strong><br><br>${p.doctrine.text}`;

    const pl = document.querySelector("[data-bind='prayer-list']");
    const dp = document.querySelector("[data-bind='daily-prayer']");
    const pe = document.querySelector("[data-bind='daily-petitions']");

    pl.value = p.userContent.prayerList;
    dp.value = p.userContent.dailyPrayer;
    pe.value = p.userContent.dailyPetitions;

    pl.oninput = () => localStorage.setItem("prayer_list", pl.value);
    dp.oninput = () => localStorage.setItem("daily_prayer", dp.value);
    pe.oninput = () => localStorage.setItem("daily_petitions", pe.value);
  });
})();

