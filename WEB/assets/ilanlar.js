(() => {
  const USERS_SESSION_KEY = "atik_session_v1";
  const USERS_KEY = "atik_users_v1";
  const LISTINGS_KEY = "atik_listings_v1";

  /** Atık türü → Excel JSON’undaki 6 haneli kodlar (sıra önemli değil). */
  const EWC_BY_WASTE_CATEGORY = {
    "Karton ve ambalaj": ["150106", "150110", "150202", "080409"],
    Plastik: ["070213", "070215", "200139"],
    "Metal ve elektronik": [
      "100321",
      "100809",
      "100903",
      "100908",
      "100910",
      "160602",
      "160604",
      "160107",
      "200133",
      "200134",
    ],
    Karışık: ["150106", "200301", "191212", "190805", "200139"],
  };

  /** fetch başarısız olursa (ör. file://) — Excel JSON ile aynı kayıtların özeti. */
  const EWC_CATALOG_FALLBACK = [
    { code: "080409", description: "Atık yapıştırıcı ve macunlar", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "070213", description: "Atık plastik (plastik üretimi)", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "070215", description: "Atık katkı maddeleri (plastik/kauçuk)", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100321", description: "Alüminyum üretiminden tozlar", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100809", description: "Diğer cüruflar (demir dışı metalürji)", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100903", description: "Ergitme cürufları", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100908", description: "Tehlikeli madde içeren döküm kalıpları", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100910", description: "Tehlikesiz döküm kalıp/maça", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "150106", description: "Karışık ambalajlar", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "150110", description: "Tehlikeli madde kalıntılı ambalaj", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "150202", description: "Tehlikeli kirlenmiş emiciler/bezler", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "160107", description: "Yağ filtreleri", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "160602", description: "Ni-Cd piller", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "160604", description: "Alkalin piller", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "190805", description: "Kentsel atıksu arıtma çamurları", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "191212", description: "Mekanik işleme diğer atıklar", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "200133", description: "Piller ve aküler", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "200134", description: "Diğer pil ve aküler", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "200139", description: "Plastikler (belediye atığı)", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "200301", description: "Karışık belediye atıkları", source: "Ara İşlem Tablosu (1).xlsx" },
  ];

  let ewcCatalog = [];

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  function formatEwcCode(digits) {
    const s = String(digits || "")
      .replace(/\D/g, "")
      .padStart(6, "0");
    return `${s.slice(0, 2)} ${s.slice(2, 4)} ${s.slice(4, 6)}`;
  }

  async function loadEwcCatalog() {
    try {
      const r = await fetch("assets/ewc_codes_from_xlsx.json", { cache: "no-store" });
      if (!r.ok) throw new Error("ewc");
      ewcCatalog = await r.json();
    } catch {
      ewcCatalog = EWC_CATALOG_FALLBACK.slice();
    }
  }

  function rebuildEwcSelect(wasteTypeVal) {
    const sel = $("#ilan-ewc-code");
    const hint = $("#ilan-ewc-hint");
    if (!sel) return;
    const codes = EWC_BY_WASTE_CATEGORY[wasteTypeVal] || [];
    sel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = codes.length ? "EWC kodu seçin" : "Önce atık türü seçin";
    sel.appendChild(opt0);
    const byCode = new Map(ewcCatalog.map((x) => [x.code, x]));
    for (const c of codes) {
      const row = byCode.get(c);
      if (!row) continue;
      const o = document.createElement("option");
      o.value = c;
      o.textContent = `${formatEwcCode(c)} — ${row.description}`;
      o.dataset.description = row.description;
      if (row.source) o.dataset.source = row.source;
      sel.appendChild(o);
    }
    if (hint) {
      hint.textContent = codes.length
        ? "Liste, Excel’den üretilen ewc_codes_from_xlsx.json ile eşleşir (yüklenemezse yerleşik yedek kullanılır)."
        : "";
    }
  }

  function getSession() {
    try {
      return JSON.parse(localStorage.getItem(USERS_SESSION_KEY) || "null");
    } catch {
      return null;
    }
  }

  function loadUsers() {
    try {
      return JSON.parse(localStorage.getItem(USERS_KEY) || "{}");
    } catch {
      return {};
    }
  }

  function saveUsers(users) {
    localStorage.setItem(USERS_KEY, JSON.stringify(users));
  }

  function setSession(session) {
    localStorage.setItem(USERS_SESSION_KEY, JSON.stringify(session));
  }

  function loadListings() {
    try {
      return JSON.parse(localStorage.getItem(LISTINGS_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveListings(list) {
    localStorage.setItem(LISTINGS_KEY, JSON.stringify(list));
  }

  function formatDate(tsOrISO) {
    try {
      const d = new Date(tsOrISO);
      if (Number.isNaN(d.getTime())) return "-";
      return new Intl.DateTimeFormat("tr-TR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(d);
    } catch {
      return "-";
    }
  }

  function setMessage(el, text) {
    if (!el) return;
    el.textContent = text;
    el.classList.remove("hidden");
  }

  function clearMessage(el) {
    if (!el) return;
    el.textContent = "";
    el.classList.add("hidden");
  }

  function makeId() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
    return "id_" + Math.random().toString(16).slice(2) + "_" + Date.now();
  }

  function getFormValues() {
    const wasteType = ($("#ilan-waste-type")?.value || "").trim();
    const ewcSel = $("#ilan-ewc-code");
    const ewcRaw = (ewcSel?.value || "").trim();
    const ewcIdx = ewcSel?.selectedIndex ?? -1;
    const ewcOpt = ewcIdx >= 0 && ewcSel?.options ? ewcSel.options[ewcIdx] : null;
    const ewcDescription = ewcOpt?.dataset?.description ? String(ewcOpt.dataset.description) : "";
    const ewcSource = ewcOpt?.dataset?.source ? String(ewcOpt.dataset.source) : "";
    const quantity = Number(($("#ilan-quantity")?.value || "").trim());
    const unit = ($("#ilan-unit")?.value || "").trim();
    const region = ($("#ilan-region")?.value || "").trim();
    const date = ($("#ilan-date")?.value || "").trim();
    const note = ($("#ilan-note")?.value || "").trim();

    return {
      wasteType,
      ewcRaw,
      ewcCode: ewcRaw ? formatEwcCode(ewcRaw) : "",
      ewcDescription,
      ewcSource,
      quantity,
      unit,
      region,
      date,
      note,
    };
  }

  function renderList(sessionEmail) {
    const listEl = $("#ilan-list");
    const emptyEl = $("#ilan-empty");
    if (!listEl || !emptyEl) return;

    const all = loadListings();
    const mine = all.filter((x) => String(x.ownerEmail || "") === String(sessionEmail || ""));

    listEl.innerHTML = "";
    if (mine.length === 0) {
      emptyEl.classList.remove("hidden");
      return;
    }
    emptyEl.classList.add("hidden");

    mine
      .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))
      .forEach((item) => {
        const card = document.createElement("div");
        card.className = "rounded-2xl bg-white/80 border border-white/60 p-4 shadow-soft";
        card.innerHTML = `
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-xs font-semibold uppercase tracking-wider text-slate-400">Atık Türü</p>
              <p class="mt-1 text-sm font-semibold text-ecoGray">${escapeHtml(item.wasteType || "-")}</p>
              ${
                item.ewcCode
                  ? `<p class="mt-1 text-xs text-slate-600"><span class="font-semibold text-ecoGray">EWC:</span> ${escapeHtml(item.ewcCode)}${
                      item.ewcDescription ? ` — ${escapeHtml(item.ewcDescription)}` : ""
                    }</p>`
                  : ""
              }

              <div class="mt-3 grid grid-cols-3 gap-3">
                <div class="col-span-1">
                  <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Miktar</p>
                  <p class="mt-1 text-sm font-semibold text-gray-800">${escapeHtml(String(item.quantity ?? "-"))} ${escapeHtml(item.unit || "")}</p>
                </div>
                <div class="col-span-1">
                  <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">İl</p>
                  <p class="mt-1 text-sm font-semibold text-gray-800">${escapeHtml(item.region || "-")}</p>
                </div>
                <div class="col-span-1">
                  <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Tarih</p>
                  <p class="mt-1 text-sm font-semibold text-gray-800">${escapeHtml(formatDate(item.date))}</p>
                </div>
              </div>

              ${item.note ? `<p class="mt-3 text-sm text-gray-600">Not: ${escapeHtml(item.note)}</p>` : ""}
            </div>

            <div class="flex flex-col gap-2">
              <button type="button" data-delete-id="${escapeAttr(item.id)}" class="rounded-full border border-red-200 bg-white px-4 py-2 text-xs font-semibold text-red-600 hover:bg-red-50 transition">
                Sil
              </button>
            </div>
          </div>
        `;
        listEl.appendChild(card);
      });
  }

  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function escapeAttr(str) {
    return escapeHtml(str).replaceAll("`", "&#96;");
  }

  function normalizeTr(str) {
    return String(str || "")
      .trim()
      .toLowerCase()
      .replaceAll("ç", "c")
      .replaceAll("ğ", "g")
      .replaceAll("ı", "i")
      .replaceAll("ö", "o")
      .replaceAll("ş", "s")
      .replaceAll("ü", "u")
      .replaceAll("İ", "i");
  }

  function findProvinceValue(selectEl, provinceName) {
    if (!selectEl || !provinceName) return null;
    const target = normalizeTr(provinceName);
    const options = Array.from(selectEl.options || []).filter((o) => String(o.value || "").trim());
    const match = options.find((o) => normalizeTr(o.value) === target || normalizeTr(o.textContent) === target);
    return match?.value || null;
  }

  async function reverseGeocodeProvince(lat, lon) {
    // Reverse geocode: returns address fields including "state" (province) for Turkey.
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);
    try {
      const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&lat=${encodeURIComponent(
        lat
      )}&lon=${encodeURIComponent(lon)}&zoom=10&accept-language=tr`;
      const res = await fetch(url, {
        method: "GET",
        headers: { "Accept-Language": "tr" },
        signal: controller.signal,
      });
      if (!res.ok) throw new Error("Konum servisi hatası.");
      const data = await res.json();
      const addr = data?.address || {};
      return addr.state || addr.province || addr.region || addr.county || null;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  function getBrowserCoords() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Tarayıcınız konum desteklemiyor."));
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        },
        (err) => {
          // 1=PERMISSION_DENIED, 2=POSITION_UNAVAILABLE, 3=TIMEOUT, ...
          if (err && err.code === 1) reject(new Error("Konum izni vermelisin."));
          else if (err && err.code === 3) reject(new Error("Konum alma zaman aşımına uğradı."));
          else reject(new Error("Konum alınamadı."));
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
      );
    });
  }

  function bindUI() {
    const session = getSession();
    if (!session?.email) return;

    const form = $("#ilan-form");
    const msgEl = $("#ilan-message");
    const listEl = $("#ilan-list");
    const emptyEl = $("#ilan-empty");

    const clearAllBtn = $("#ilan-clear-all-btn");
    const wasteTypeSelect = $("#ilan-waste-type");

    if (wasteTypeSelect) {
      rebuildEwcSelect(wasteTypeSelect.value);
      wasteTypeSelect.addEventListener("change", () => {
        rebuildEwcSelect(wasteTypeSelect.value);
      });
    }

    renderList(session.email);

    // Form varsayılanlarını oturumdaki değerlere göre doldur
    const regionSelect = $("#ilan-region");
    if (regionSelect && session.location) {
      regionSelect.value = session.location;
    }

    const verifyBtn = $("#ilan-verify-location-btn");
    const verifyMsgEl = $("#ilan-verify-location-msg");
    const verifyMetaEl = $("#ilan-verify-location-meta");
    if (verifyBtn && regionSelect) {
      verifyBtn.addEventListener("click", async () => {
        const currentSession = getSession();
        if (!currentSession?.email) return;

        verifyBtn.disabled = true;
        verifyBtn.classList.add("opacity-60", "cursor-not-allowed");

        if (verifyMsgEl) {
          verifyMsgEl.textContent = "Konum alınıyor...";
          verifyMsgEl.classList.remove("hidden");
        }
        if (verifyMetaEl) {
          verifyMetaEl.textContent = "";
          verifyMetaEl.classList.add("hidden");
        }

        try {
          const coords = await getBrowserCoords();
          if (verifyMsgEl) verifyMsgEl.textContent = "Konum doğrulanıyor...";

          const province = await reverseGeocodeProvince(coords.lat, coords.lon);
          if (!province) throw new Error("İl bilgisi tespit edilemedi.");

          const matchValue = findProvinceValue(regionSelect, province);
          if (!matchValue) throw new Error(`İl eşleştirilemedi: ${province}`);

          regionSelect.value = matchValue;

          // Persist location to session + user record so profil.html also updates.
          const updatedSession = { ...currentSession, location: matchValue, loggedInAt: Date.now(), lastLoginAt: Date.now() };
          setSession(updatedSession);

          const users = loadUsers();
          if (users?.[currentSession.email]) {
            users[currentSession.email].location = matchValue;
            saveUsers(users);
          }

          if (verifyMsgEl) verifyMsgEl.textContent = `Konum doğrulandı: ${matchValue}`;
          if (verifyMetaEl) {
            verifyMetaEl.textContent = `Koordinat: ${coords.lat.toFixed(5)}, ${coords.lon.toFixed(5)}`;
            verifyMetaEl.classList.remove("hidden");
          }
        } catch (e) {
          const msg = e?.message || "Konum doğrulaması başarısız oldu.";
          if (verifyMsgEl) verifyMsgEl.textContent = msg;
          if (verifyMetaEl) verifyMetaEl.classList.add("hidden");
        } finally {
          verifyBtn.disabled = false;
          verifyBtn.classList.remove("opacity-60", "cursor-not-allowed");
        }
      });
    }

    // Delete (event delegation)
    listEl?.addEventListener("click", (e) => {
      const btn = e.target?.closest?.("[data-delete-id]");
      const id = btn?.getAttribute?.("data-delete-id");
      if (!id) return;

      const ok = window.confirm("Bu ilanı silmek istediğine emin misin?");
      if (!ok) return;

      const all = loadListings();
      const next = all.filter((x) => String(x.id) !== String(id));
      saveListings(next);
      renderList(session.email);
    });

    clearAllBtn?.addEventListener("click", () => {
      const ok = window.confirm("Bu hesaba ait tüm ilanları temizlemek istiyor musun?");
      if (!ok) return;
      const all = loadListings();
      const next = all.filter((x) => String(x.ownerEmail || "") !== String(session.email));
      saveListings(next);
      renderList(session.email);
    });

    form?.addEventListener("submit", (e) => {
      e.preventDefault();
      clearMessage(msgEl);

      const { wasteType, ewcRaw, ewcCode, ewcDescription, ewcSource, quantity, unit, region, date, note } = getFormValues();

      if (!wasteType || !unit || !region || !date) {
        setMessage(msgEl, "Lütfen tüm zorunlu alanları doldur.");
        return;
      }
      if (!ewcRaw) {
        setMessage(msgEl, "Lütfen Excel listesinden bir EWC kodu seçin.");
        return;
      }
      if (!Number.isFinite(quantity) || quantity < 0) {
        setMessage(msgEl, "Miktar geçerli bir sayı olmalı.");
        return;
      }

      const all = loadListings();
      const item = {
        id: makeId(),
        ownerEmail: session.email,
        ownerName: session.name || "",
        ownerCompanyName: session.companyName || "",
        wasteType,
        ewcCodeRaw: ewcRaw,
        ewcCode,
        ewcDescription,
        ewcSource,
        quantity,
        unit,
        region,
        date,
        note,
        createdAt: Date.now(),
      };
      all.push(item);
      saveListings(all);

      // Reset
      $("#ilan-quantity") && ($("#ilan-quantity").value = "");
      $("#ilan-note") && ($("#ilan-note").value = "");

      renderList(session.email);
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    await loadEwcCatalog();
    bindUI();
  });
})();

