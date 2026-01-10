(function () {
  "use strict";

  function hardFail(message) {
    document.body.innerHTML = `
      <div style="font-family:system-ui;background:#5b0f14;color:#fff;padding:40px;text-align:center">
        <h1>Prayer Room Load Error</h1>
        <p>${message}</p>
      </div>`;
    throw new Error(message);
  }

  const today = new Date();
  if (isNaN(today)) hardFail("Invalid system date.");

  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, "0");
  const dd = String(today.getDate()).padStart(2, "0");
  const dateKey = `${yyyy}-${mm}-${dd}`;

  const DOCTRINES = [
    "We believe that the Scriptures of the Old and New Testaments were given by inspiration of God, and that they only constitute the Divine rule of Christian faith and practice.",
    "We believe that there is only one God, who is infinitely perfect, the Creator, Preserver, and Governor of all things, and who is the only proper object of religious worship.",
    "We believe that there are three persons in the Godhead—the Father, the Son, and the Holy Ghost, undivided in essence and co-equal in power and glory.",
    "We believe that in the person of Jesus Christ the Divine and human natures are united, so that He is truly and properly God and truly and properly man.",
    "We believe that our first parents were created in a state of innocency, but by their disobedience they lost their purity and happiness.",
    "We believe that the Lord Jesus Christ has by His suffering and death made an atonement for the whole world.",
    "We believe that repentance toward God, faith in our Lord Jesus Christ, and regeneration by the Holy Spirit are necessary to salvation.",
    "We believe that we are justified by grace through faith in our Lord Jesus Christ.",
    "We believe that continuance in a state of salvation depends upon continued obedient faith in Christ.",
    "We believe that it is the privilege of all believers to be wholly sanctified.",
    "We believe in the immortality of the soul, the resurrection of the body, the general judgment, eternal happiness, and endless punishment."
  ];

  const epoch = new Date(1970, 0, 1);
  const doctrineIndex = Math.floor((today - epoch) / 86400000) % 11;

  function load(key) {
    try { return localStorage.getItem(key) || ""; }
    catch { hardFail("localStorage unavailable."); }
  }

  const userContent = {
    prayerList: load("prayer_list"),
    dailyPrayer: load("daily_prayer"),
    dailyPetitions: load("daily_petitions")
  };

  fetch("nlt_for_app_365.json", { cache: "no-store" })
    .then(r => r.ok ? r.json() : hardFail("Scripture file missing."))
    .then(data => {
      const start = new Date(today.getFullYear(), 0, 0);
      const dayOfYear = Math.floor((today - start) / 86400000) - 1;
      const verse = data[dayOfYear];

      if (!verse || !verse.ref || !verse.text)
        hardFail("Invalid scripture entry.");

      window.PRAYER_ROOM_PAYLOAD = {
        date: dateKey,
        doctrine: { index: doctrineIndex + 1, text: DOCTRINES[doctrineIndex] },
        scripture: verse,
        userContent
      };

      document.dispatchEvent(new Event("PrayerRoomPayloadReady"));
    })
    .catch(e => hardFail(e.message));
})();

