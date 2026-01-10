// loader.js — canonical, authoritative loader
// Produces ONE resolved payload. No DOM access.

async function loadPayload() {
  const today = new Date().toISOString().slice(0, 10);

  // Load scripture JSON
  const scriptureResp = await fetch("nlt_for_app_365.json");
  const scriptureData = await scriptureResp.json();

  const scriptureEntry =
    scriptureData.find(v => v.date === today) || scriptureData[0];

  // Salvation Army Doctrine rotation (1–11)
  const doctrines = [
    "We believe that the Scriptures of the Old and New Testaments were given by inspiration of God, and that they only constitute the Divine rule of Christian faith and practice.",
    "We believe that there is only one God, who is infinitely perfect, the Creator, Preserver, and Governor of all things, and who is the only proper object of religious worship.",
    "We believe that there are three persons in the Godhead—the Father, the Son, and the Holy Ghost, undivided in essence and co-equal in power and glory.",
    "We believe that in the person of Jesus Christ the Divine and human natures are united, so that He is truly and properly God and truly and properly man.",
    "We believe that our first parents were created in a state of innocency, but by their disobedience they lost their purity and happiness, and that in consequence of their fall all men have become sinners, totally depraved, and as such are justly exposed to the wrath of God.",
    "We believe that the Lord Jesus Christ has by His suffering and death made an atonement for the whole world so that whosoever will may be saved.",
    "We believe that repentance toward God, faith in our Lord Jesus Christ, and regeneration by the Holy Spirit are necessary to salvation.",
    "We believe that we are justified by grace through faith in our Lord Jesus Christ and that he that believeth hath the witness in himself.",
    "We believe that continuance in a state of salvation depends upon continued obedient faith in Christ.",
    "We believe that it is the privilege of all believers to be wholly sanctified, and that their whole spirit and soul and body may be preserved blameless unto the coming of our Lord Jesus Christ.",
    "We believe in the immortality of the soul, the resurrection of the body, the general judgment at the end of the world, the eternal happiness of the righteous, and the endless punishment of the wicked."
  ];

  const doctrineIndex =
    Math.floor((Date.now() / 86400000)) % doctrines.length;

  return {
    date: today,
    scripture: scriptureEntry.text,
    doctrine: doctrines[doctrineIndex],
    "prayer-list": localStorage.getItem("prayer-list") || "",
    "daily-prayer": localStorage.getItem("daily-prayer") || "",
    "daily-petitions": localStorage.getItem("daily-petitions") || ""
  };
}

window.loadPayload = loadPayload;

