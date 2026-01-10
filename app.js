document.addEventListener("DOMContentLoaded", () => {
  fetch("nlt_for_app_300.json")
    .then(response => response.json())
    .then(data => {
      const verse = data[0];

      const scriptureBox = document.getElementById("scripture-text");
      if (scriptureBox) {
        scriptureBox.textContent =
          verse.ref + " — " + verse.text;
      }
    })
    .catch(err => {
      console.error("Scripture load failed:", err);
    });
});

