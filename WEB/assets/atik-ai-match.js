/**
 * EWC eşleştirme modal — assets/ewc_kodlari_extracted.json (PDF OCR listesi) + API tamamlama
 */
(function () {
  var STATIC_FALLBACK = [
    { code: "150106", label: "Kağıt/karton ambalaj" },
    { code: "150110", label: "Plastik ambalaj" },
    { code: "020106", label: "Zararsız toprak, taş" },
    { code: "170401", label: "Bakır" },
    { code: "170405", label: "Demir-çelik" },
    { code: "170302", label: "Bitümlü karışımlar" },
    { code: "160601", label: "Kurşun bataryalar" },
    { code: "200301", label: "Karışık belediye atığı" },
  ];

  var modal = document.getElementById("atik-ai-modal");
  var form = document.getElementById("atik-ai-match-form");
  var inputEwc = document.getElementById("atik-ai-ewc");
  var inputKm = document.getElementById("atik-ai-km");
  var inputSourceFacility = document.getElementById("atik-ai-source-facility");
  var filterInput = document.getElementById("atik-ai-ewc-filter");
  var statusEl = document.getElementById("atik-ai-match-status");
  var resultEl = document.getElementById("atik-ai-match-result");
  var datalistEl = document.getElementById("atik-ai-ewc-datalist");
  var chipsEl = document.getElementById("atik-ai-ewc-chips");
  var countEl = document.getElementById("atik-ai-ewc-count");
  var lastFocus = null;
  var ewcFullList = [];

  function setStatus(msg, isError) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.className =
      "mt-4 text-sm min-h-[1.25rem]" + (isError ? " text-red-600 font-medium" : " text-gray-600");
  }

  function showResult(html, show) {
    if (!resultEl) return;
    resultEl.classList.toggle("hidden", !show);
    resultEl.innerHTML = html || "";
  }

  function escapeHtml(s) {
    if (s == null) return "";
    var d = document.createElement("div");
    d.textContent = String(s);
    return d.innerHTML;
  }

  function isModalOpen() {
    return modal && modal.classList.contains("is-open");
  }

  function openModal() {
    if (!modal) return;
    lastFocus = document.activeElement;
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    if (inputEwc) {
      setTimeout(function () {
        inputEwc.focus();
      }, 10);
    }
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    if (lastFocus && typeof lastFocus.focus === "function") {
      try {
        lastFocus.focus();
      } catch (_e) {}
    }
  }

  function fillDatalist(list) {
    if (!datalistEl) return;
    datalistEl.innerHTML = "";
    list.forEach(function (row) {
      var opt = document.createElement("option");
      opt.value = row.code;
      var lab = row.label || "";
      opt.label = lab.length > 120 ? lab.slice(0, 120) + "…" : lab;
      datalistEl.appendChild(opt);
    });
  }

  function renderChips(list) {
    if (!chipsEl) return;
    var q = filterInput && filterInput.value ? filterInput.value.trim().toLowerCase() : "";
    var qDigits = q.replace(/\s/g, "");
    chipsEl.innerHTML = "";
    var frag = document.createDocumentFragment();
    var shown = 0;
    list.forEach(function (row) {
      var code = String(row.code || "");
      var lab = String(row.label || "").toLowerCase();
      if (q) {
        var hit =
          code.indexOf(qDigits) !== -1 ||
          code.replace(/\s/g, "").indexOf(qDigits) !== -1 ||
          lab.indexOf(q) !== -1;
        if (!hit) return;
      }
      var b = document.createElement("button");
      b.type = "button";
      b.className =
        "rounded-lg border border-ecoBlue/20 bg-white px-2 py-1 text-xs font-medium text-ecoGray hover:bg-ecoBlue/10 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-ecoBlue/40";
      b.textContent = code;
      b.title = row.label ? row.label : code;
      b.addEventListener("click", function () {
        if (inputEwc) {
          inputEwc.value = code;
          inputEwc.dispatchEvent(new Event("input", { bubbles: true }));
        }
      });
      frag.appendChild(b);
      shown++;
    });
    chipsEl.appendChild(frag);
    if (countEl) {
      countEl.textContent =
        q && shown !== list.length ? shown + " / " + list.length + " kod" : list.length + " kod";
    }
  }

  function mergeApiEwcIntoDatalist(data) {
    if (!datalistEl || !Array.isArray(data)) return;
    var seen = {};
    var opts = datalistEl.querySelectorAll("option");
    for (var i = 0; i < opts.length; i++) {
      seen[opts[i].value] = true;
    }
    data.slice(0, 80).forEach(function (row) {
      var code = row && row.code != null ? String(row.code) : "";
      if (!code || seen[code]) return;
      seen[code] = true;
      var opt = document.createElement("option");
      opt.value = code;
      var desc = row && row.description != null ? String(row.description) : "";
      opt.label = desc ? code + " — " + desc.slice(0, 80) : code;
      datalistEl.appendChild(opt);
    });
  }

  async function loadEwcFromApi() {
    try {
      var r = await fetch("/api/atik-ai/matching/ewc-codes", {
        headers: { Accept: "application/json" },
      });
      if (!r.ok) return;
      var data = await r.json();
      mergeApiEwcIntoDatalist(data);
    } catch (_e) {}
  }

  async function loadEwcJson() {
    try {
      var r = await fetch("assets/ewc_kodlari_extracted.json", { cache: "no-cache" });
      if (!r.ok) throw new Error("no json");
      var data = await r.json();
      if (!Array.isArray(data) || !data.length) throw new Error("empty");
      ewcFullList = data;
      fillDatalist(data);
      renderChips(data);
      loadEwcFromApi();
    } catch (_e) {
      ewcFullList = STATIC_FALLBACK.slice();
      fillDatalist(ewcFullList);
      renderChips(ewcFullList);
      if (countEl) countEl.textContent = "yerel örnek (PDF yok)";
      loadEwcFromApi();
    }
  }

  if (filterInput) {
    filterInput.addEventListener("input", function () {
      renderChips(ewcFullList.length ? ewcFullList : STATIC_FALLBACK);
    });
  }

  async function runMatch(ev) {
    ev.preventDefault();
    var raw = inputEwc && inputEwc.value ? inputEwc.value.trim() : "";
    var code = raw.replace(/\s+/g, "");
    var km =
      inputKm && inputKm.value
        ? Math.min(500, Math.max(1, parseInt(inputKm.value, 10) || 50))
        : 50;

    showResult("", false);
    if (!code) {
      setStatus("Lütfen bir EWC kodu girin veya listeden seçin.", true);
      return;
    }

    setStatus("Eşleştirme isteği gönderiliyor…", false);
    var btn = form && form.querySelector('button[type="submit"]');
    if (btn) btn.disabled = true;

    var qs = new URLSearchParams({
      waste_code: code,
      max_distance_km: String(km),
      limit: "20",
      min_quality_score: "0",
    });
    if (inputSourceFacility && inputSourceFacility.value) {
      var sid = parseInt(String(inputSourceFacility.value).trim(), 10);
      if (!isNaN(sid) && sid > 0) qs.set("source_facility_id", String(sid));
    }
    var url = "/api/atik-ai/matching/search?" + qs.toString();

    try {
      var r = await fetch(url, {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      var text = await r.text();
      var body;
      try {
        body = JSON.parse(text);
      } catch (_e) {
        body = { raw: text };
      }

      if (r.status === 404) {
        setStatus(
          "ATIK AI köprüsü bu ortamda kapalı görünüyor. Sunucuda ATIK_AI_PROXY_URL ve çalışan uvicorn gerekir.",
          true
        );
        showResult("", false);
        return;
      }
      if (r.status === 502) {
        setStatus("Python (ATIK AI) servisine şu an ulaşılamıyor. Port 8000’de uvicorn çalışıyor mu?", true);
        showResult("", false);
        return;
      }
      if (!r.ok) {
        var detail = body.detail != null ? String(body.detail) : text.slice(0, 200);
        setStatus("Sunucu yanıtı: " + r.status + (detail ? " — " + detail : ""), true);
        showResult(
          '<pre class="text-xs whitespace-pre-wrap break-words">' + escapeHtml(text) + "</pre>",
          true
        );
        return;
      }

      setStatus("Yanıt alındı.", false);
      var desc = body.description != null ? body.description : "";
      var msg = body.message != null ? body.message : "";
      var matches = Array.isArray(body.matches) ? body.matches : [];
      var parts = [];
      parts.push(
        '<p class="font-semibold text-ecoGray">Kod: ' + escapeHtml(body.waste_code || code) + "</p>"
      );
      if (desc) parts.push('<p class="mt-2 text-gray-600">' + escapeHtml(desc) + "</p>");
      if (msg) parts.push('<p class="mt-3 text-sm text-ecoBlue">' + escapeHtml(msg) + "</p>");
      if (matches.length === 0) {
        parts.push(
          '<p class="mt-3 text-sm text-gray-500">Eşleşme yok. PostgreSQL’de tesis ve EWC verisi varsa, kaynak tesis ID’si girerek çok katmanlı motoru (NACE–EWC + mesafe) çalıştırabilirsiniz.</p>'
        );
      } else {
        parts.push('<ul class="mt-3 list-disc pl-5 space-y-1">');
        matches.forEach(function (m) {
          parts.push(
            '<li><pre class="text-xs whitespace-pre-wrap">' +
              escapeHtml(JSON.stringify(m, null, 2)) +
              "</pre></li>"
          );
        });
        parts.push("</ul>");
      }
      showResult(parts.join(""), true);
    } catch (e) {
      setStatus("Ağ hatası: " + (e && e.message ? e.message : String(e)), true);
      showResult("", false);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function onDocKeydown(ev) {
    if (ev.key === "Escape" && isModalOpen()) {
      ev.preventDefault();
      closeModal();
    }
  }

  if (modal) {
    document.querySelectorAll("[data-open-atik-ai-modal]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.preventDefault();
        openModal();
      });
    });
    document.querySelectorAll("[data-close-atik-ai-modal]").forEach(function (el) {
      el.addEventListener("click", function () {
        closeModal();
      });
    });
    document.addEventListener("keydown", onDocKeydown);
  }

  if (form) form.addEventListener("submit", runMatch);
  loadEwcJson();
})();
