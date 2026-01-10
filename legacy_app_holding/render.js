// render.js — dumb renderer, no logic

(async function () {
  const payload = await window.loadPayload();

  document.querySelectorAll("[data-bind]").forEach(el => {
    const key = el.getAttribute("data-bind");

    if (el.tagName === "TEXTAREA") {
      el.value = payload[key] || "";
      el.addEventListener("input", () => {
        localStorage.setItem(key, el.value);
      });
    } else {
      el.textContent = payload[key] || "";
    }
  });
})();

