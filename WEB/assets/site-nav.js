(function () {
  var yearEl = document.getElementById("site-year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  var page = document.body.getAttribute("data-page");
  if (page) {
    document.querySelectorAll("[data-nav]").forEach(function (el) {
      if (el.getAttribute("data-nav") === page) {
        el.classList.add("text-ecoBlue", "font-semibold", "bg-ecoBlue/10");
        if (el.tagName === "A") el.setAttribute("aria-current", "page");
      }
    });
  }

  var btn = document.querySelector("[data-site-menu-btn]");
  var panel = document.getElementById("site-mobile-menu");
  if (btn && panel) {
    btn.addEventListener("click", function () {
      panel.classList.toggle("hidden");
      var open = !panel.classList.contains("hidden");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }
})();
