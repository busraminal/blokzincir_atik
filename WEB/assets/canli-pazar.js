(() => {
  const LISTINGS_KEY = "atik_listings_v1";
  const SESSION_KEY = "atik_session_v1";
  const CHAT_THREADS_KEY = "atik_contact_threads_v1";
  /** Profil: alıcıya düşen bildirimler (aynı tarayıcı / demo). */
  const INBOX_NOTIFICATIONS_KEY = "atik_inbox_notifications_v1";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  function loadListings() {
    try {
      return JSON.parse(localStorage.getItem(LISTINGS_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function getSession() {
    try {
      return JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    } catch {
      return null;
    }
  }

  function escapeHtml(str) {
    return String(str ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function truncate(str, maxLen) {
    const s = String(str ?? "");
    if (!s) return "";
    if (s.length <= maxLen) return s;
    return s.slice(0, Math.max(0, maxLen - 1)).trimEnd() + "…";
  }

  function formatDate(tsOrISO) {
    try {
      const d = new Date(tsOrISO);
      if (Number.isNaN(d.getTime())) return "-";
      return new Intl.DateTimeFormat("tr-TR", { year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
    } catch {
      return "-";
    }
  }

  // API base ayarı:
  // - Aynı origin/port üzerinden çalışıyorsa (atik-dlt ile UI aynı sunucu/port), relative url yeterli.
  // - Live Server kullanıyorsan: ör. Atik.html?port=5055 veya Atik.html?apiBase=http://127.0.0.1:5055
  function resolveApiBase() {
    try {
      const params = new URLSearchParams(window.location.search || "");
      const explicitBase = (params.get("apiBase") || params.get("base") || "").trim().replace(/\/+$/, "");
      if (explicitBase) return explicitBase;

      const port = (params.get("port") || "").trim();
      if (port) {
        const proto = window.location.protocol === "https:" ? "https" : "http";
        return `${proto}://${window.location.hostname}:${port}`;
      }
    } catch (_e) {}
    // No query params: assume backend is on default port 5055.
    // This removes the need for Live Server "port=5055" hacks.
    return "http://127.0.0.1:5055";
  }

  const API_BASE = resolveApiBase();
  function apiUrl(p) {
    if (!p) return p;
    return API_BASE ? API_BASE + p : p;
  }

  async function apiGetJson(url) {
    const r = await fetch(url, { method: "GET", headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error("API hatası " + r.status);
    return await r.json();
  }

  async function apiPostJson(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) throw new Error("API hatası " + r.status);
    return await r.json();
  }

  function loadThreads() {
    try {
      return JSON.parse(localStorage.getItem(CHAT_THREADS_KEY) || "{}");
    } catch {
      return {};
    }
  }

  function saveThreads(threads) {
    localStorage.setItem(CHAT_THREADS_KEY, JSON.stringify(threads));
  }

  function threadIdFor(listingId, aEmail, bEmail) {
    // Minimum backend senaryosunda listingId her cihazda aynı olmayabilir (localStorage).
    // Bu yüzden thread anahtarını iki tarafın e-posta çiftinden türetiyoruz.
    const parts = [String(aEmail || ""), String(bEmail || "")].sort();
    return `pair:${parts[0]}|${parts[1]}`;
  }

  function getOtherParticipantEmail(threadId, senderEmail) {
    const m = String(threadId || "").match(/^pair:(.+)\|(.+)$/);
    if (!m) return null;
    const a = m[1];
    const b = m[2];
    const s = String(senderEmail || "");
    if (a === s) return b;
    if (b === s) return a;
    return null;
  }

  function pushInboxNotificationForRecipient(payload) {
    const recipientEmail = String(payload?.recipientEmail || "").trim().toLowerCase();
    const fromEmail = String(payload?.fromEmail || "").trim();
    if (!recipientEmail || !fromEmail || recipientEmail === fromEmail.toLowerCase()) return;

    let list = [];
    try {
      list = JSON.parse(localStorage.getItem(INBOX_NOTIFICATIONS_KEY) || "[]");
    } catch {
      list = [];
    }
    if (!Array.isArray(list)) list = [];

    list.unshift({
      id: `n_${Date.now()}_${Math.random().toString(16).slice(2)}`,
      at: Date.now(),
      recipientEmail,
      fromEmail,
      fromName: String(payload?.fromName || ""),
      threadId: String(payload?.threadId || ""),
      wasteType: String(payload?.wasteType || ""),
      region: String(payload?.region || ""),
      previewText: String(payload?.previewText || "").slice(0, 220),
      read: false,
    });

    try {
      localStorage.setItem(INBOX_NOTIFICATIONS_KEY, JSON.stringify(list.slice(0, 200)));
    } catch (_e) {}

    try {
      window.dispatchEvent(new CustomEvent("atik-inbox-updated"));
    } catch (_e) {}
  }

  function ensureContactModal() {
    let modal = $("#atik-contact-modal");
    if (modal) return modal;

    modal = document.createElement("div");
    modal.id = "atik-contact-modal";
    modal.className = "fixed inset-0 z-[120] hidden items-center justify-center p-4 bg-slate-900/55";
    modal.innerHTML = `
      <div class="glass-panel max-w-2xl w-full rounded-2xl border border-white/80 p-5 shadow-2xl max-h-[92vh] overflow-y-auto">
        <div class="flex items-start justify-between gap-2 mb-3">
          <div>
            <h2 class="text-lg font-bold text-ecoGray">Mesajlaşma</h2>
            <p id="atik-contact-sub" class="text-xs text-gray-500 mt-1"></p>
          </div>
          <button type="button" class="modal-close-contact text-2xl leading-none text-gray-400 hover:text-gray-700">&times;</button>
        </div>

        <div class="rounded-2xl border border-slate-200/80 bg-white/70 p-3 mb-3">
          <div id="atik-contact-messages" class="space-y-2 max-h-[52vh] overflow-y-auto pr-1"></div>
        </div>

        <form id="atik-contact-form" class="mt-3 flex items-end gap-2">
          <div class="flex-1">
            <label class="sr-only" for="atik-contact-input">Mesaj</label>
            <textarea id="atik-contact-input" rows="2" class="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm bg-white outline-none focus:ring-2 focus:ring-ecoBlue/40" placeholder="Mesajını yaz..."></textarea>
          </div>
          <button type="submit" class="rounded-full bg-gradient-to-r from-ecoBlue to-ecoGreen px-5 py-3 text-sm font-semibold text-white shadow-md shadow-ecoBlue/20 hover:opacity-[0.97]">
            Gönder
          </button>
        </form>
      </div>
    `;
    document.body.appendChild(modal);
    return modal;
  }

  function escapeText(str) {
    return String(str ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  async function renderThread(threadId, myEmail) {
    const modal = $("#atik-contact-modal");
    const messagesEl = $("#atik-contact-messages");
    if (!modal || !messagesEl) return;

    // Race-condition guard: user may switch threads quickly.
    const mySeqThreadId = String(threadId || "");
    const checkStillActive = () => {
      try {
        return String(window.__atik_active_thread_id || "") === mySeqThreadId;
      } catch (_e) {
        return true;
      }
    };

    // Önce server'dan dene (farklı cihazlar için).
    let t = null;
    try {
      t = await apiGetJson(apiUrl("/api/contact/thread/" + encodeURIComponent(threadId)));
    } catch (_e) {}

    if (!checkStillActive()) return;

    // Server bulunamazsa localStorage fallback.
    if (!t || !Array.isArray(t.messages)) {
      const threads = loadThreads();
      t = threads[threadId];
    }

    if (!t || !Array.isArray(t.messages)) {
      messagesEl.innerHTML = `<p class="text-xs text-gray-500">Henüz mesaj yok.</p>`;
      return;
    }

    if (t.messages.length === 0) {
      messagesEl.innerHTML = `<p class="text-xs text-gray-500">Henüz mesaj yok.</p>`;
      return;
    }

    // Mini durumlar: unread + son mesaj bilgisi
    const readBy = t.readBy || {};
    const lastReadAt = readBy && readBy[myEmail] != null ? Number(readBy[myEmail]) : null;
    const unreadCount = t.messages.filter((m) => {
      const at = Number(m?.at || 0);
      const from = String(m?.fromEmail || "");
      if (from === String(myEmail || "")) return false;
      if (lastReadAt == null) return true;
      return at > lastReadAt;
    }).length;

    const sub = $("#atik-contact-sub");
    if (sub) {
      const pieces = [
        t.recipientName ? String(t.recipientName) : "Kullanıcı",
        t.wasteType ? String(t.wasteType) : null,
        t.region ? String(t.region) : null,
      ].filter(Boolean);

      const lastPreview = t.lastMessagePreview ? String(t.lastMessagePreview) : "";
      const lastAt = t.lastMessageAt ? String(t.lastMessageAt) : "";
      const lastTxt = lastPreview ? " · Son: " + lastPreview : "";
      sub.textContent = pieces.join(" · ") + (unreadCount > 0 ? ` · ${unreadCount} okunmamış` : " · Okundu") + (lastTxt || "");
    }

    messagesEl.innerHTML = "";
    t.messages
      .slice()
      .sort((a, b) => Number(a.at || 0) - Number(b.at || 0))
      .forEach((m) => {
        const mine = String(m.fromEmail || "") === String(myEmail || "");
        const senderName = mine ? "Sen" : m.fromName || "Kullanıcı";
        const time = m.at ? formatDate(m.at) : "";
        const bubbleCls = mine
          ? "bg-ecoGreen/10 border-ecoGreen/30 text-ecoGray ml-auto"
          : "bg-white/95 border-slate-200/80 text-gray-800 mr-auto";

        messagesEl.insertAdjacentHTML(
          "beforeend",
          `<div class="max-w-[85%] ${mine ? "text-right" : "text-left"}">
             <div class="text-[11px] text-gray-500 mb-1">${escapeText(senderName)}${time ? ` · ${escapeText(time)}` : ""}</div>
             <div class="rounded-2xl border px-4 py-2 text-sm leading-relaxed whitespace-pre-wrap ${bubbleCls}">
               ${escapeText(m.text)}
             </div>
           </div>`
        );
      });

    // auto-scroll
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function markThreadRead(threadId, myEmail) {
    if (!threadId || !myEmail) return;
    apiPostJson(apiUrl("/api/contact/thread/" + encodeURIComponent(threadId) + "/read"), { readerEmail: myEmail }).catch(
      function () {}
    );
    const threads = loadThreads();
    const t = threads[threadId];
    if (t) {
      t.readBy = t.readBy || {};
      t.readBy[String(myEmail)] = Date.now();
      saveThreads(threads);
    }
  }

  function upsertThread(threadId, meta) {
    const threads = loadThreads();
    if (!threads[threadId]) {
      threads[threadId] = {
        threadId,
        listingId: meta?.listingId,
        recipientEmail: meta?.recipientEmail,
        recipientName: meta?.recipientName || "",
        wasteType: meta?.wasteType || "",
        region: meta?.region || "",
        messages: [],
        updatedAt: Date.now(),
      };
    }
    saveThreads(threads);

    // Server'a meta gönder (best-effort)
    try {
      if (!API_BASE && window.location.pathname.indexOf("/Atik.html") === -1) {
        // relative url çalışır; burada sadece URL'ın yanlış origin'dan gelmesini engelle
      }
      apiPostJson(apiUrl("/api/contact/thread/" + encodeURIComponent(threadId) + "/meta"), {
        listingId: meta?.listingId ?? null,
        recipientEmail: meta?.recipientEmail ?? null,
        recipientName: meta?.recipientName ?? null,
        wasteType: meta?.wasteType ?? null,
        region: meta?.region ?? null,
      }).catch(function () {});
    } catch (_e) {}
  }

  async function sendMessage(threadId, fromEmail, fromName, text) {
    const msgText = String(text ?? "").trim();
    if (!msgText) return false;

    // Server'a mesaj gönder (best-effort)
    let serverOk = false;
    try {
      await apiPostJson(apiUrl("/api/contact/thread/" + encodeURIComponent(threadId) + "/message"), {
        fromEmail,
        fromName,
        text: msgText,
      });
      serverOk = true;
    } catch (_e) {}

    const threads = loadThreads();
    const t = threads[threadId];
    if (!t) return false;

    t.messages = Array.isArray(t.messages) ? t.messages : [];
    t.messages.push({
      id: `m_${Date.now()}_${Math.random().toString(16).slice(2)}`,
      fromEmail,
      fromName,
      text: msgText,
      at: Date.now(),
    });
    t.updatedAt = Date.now();
    t.lastMessagePreview = msgText.slice(0, 160);
    t.lastMessageAt = Date.now();
    saveThreads(threads);

    const recipientOther = getOtherParticipantEmail(threadId, fromEmail);
    if (recipientOther) {
      pushInboxNotificationForRecipient({
        recipientEmail: recipientOther,
        fromEmail,
        fromName,
        threadId,
        wasteType: t.wasteType || "",
        region: t.region || "",
        previewText: msgText,
      });
    }

    return serverOk || true;
  }

  const WASTE_TYPES = [
    {
      value: "Karton ve ambalaj",
      label: "Karton ve ambalaj",
      pill: "bg-ecoGreen/15 text-ecoGreen",
      icon: "♻",
      iconBg: "bg-ecoGreen/10",
      cta: "border border-ecoGreen/40 bg-white px-4 py-3 text-sm font-semibold text-ecoGreen hover:bg-ecoGreen/5 transition",
    },
    {
      value: "Plastik",
      label: "Plastik",
      pill: "bg-ecoBlue/15 text-ecoBlue",
      icon: "AI",
      iconBg: "bg-ecoBlue/10",
      cta: "border border-ecoBlue/40 bg-white px-4 py-3 text-sm font-semibold text-ecoBlue hover:bg-ecoBlue/5 transition",
    },
    {
      value: "Metal ve elektronik",
      label: "Metal ve elektronik",
      pill: "bg-ecoOrange/15 text-ecoOrange",
      icon: "⛓",
      iconBg: "bg-ecoOrange/10",
      cta: "border border-ecoOrange/40 bg-white px-4 py-3 text-sm font-semibold text-ecoOrange hover:bg-ecoOrange/5 transition",
    },
    { value: "Karışık", label: "Karışık", pill: "bg-slate-100 text-gray-700", icon: "...", iconBg: "bg-slate-100", cta: "border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-gray-700 hover:bg-slate-50 transition" },
  ];

  const PROVINCES_TR = [
    "Adana",
    "Adıyaman",
    "Afyonkarahisar",
    "Ağrı",
    "Aksaray",
    "Amasya",
    "Ankara",
    "Antalya",
    "Artvin",
    "Aydın",
    "Balıkesir",
    "Bartın",
    "Batman",
    "Bayburt",
    "Bilecik",
    "Bingöl",
    "Bitlis",
    "Bolu",
    "Burdur",
    "Bursa",
    "Çanakkale",
    "Çankırı",
    "Çorum",
    "Denizli",
    "Diyarbakır",
    "Düzce",
    "Edirne",
    "Elazığ",
    "Erzincan",
    "Erzurum",
    "Eskişehir",
    "Gaziantep",
    "Giresun",
    "Gümüşhane",
    "Hakkari",
    "Hatay",
    "Iğdır",
    "Isparta",
    "İstanbul",
    "İzmir",
    "Kahramanmaraş",
    "Karabük",
    "Karaman",
    "Kars",
    "Kastamonu",
    "Kayseri",
    "Kilis",
    "Kırıkkale",
    "Kırklareli",
    "Kırşehir",
    "Kocaeli",
    "Konya",
    "Kütahya",
    "Malatya",
    "Manisa",
    "Mardin",
    "Mersin",
    "Muğla",
    "Muş",
    "Nevşehir",
    "Niğde",
    "Ordu",
    "Osmaniye",
    "Rize",
    "Sakarya",
    "Samsun",
    "Şanlıurfa",
    "Siirt",
    "Sinop",
    "Sivas",
    "Şırnak",
    "Tekirdağ",
    "Tokat",
    "Trabzon",
    "Tunceli",
    "Uşak",
    "Van",
    "Yalova",
    "Yozgat",
    "Zonguldak",
  ];

  function getWasteMeta(wasteType) {
    return WASTE_TYPES.find((x) => String(x.value) === String(wasteType)) || WASTE_TYPES[3];
  }

  function buildCard(item) {
    const wasteMeta = getWasteMeta(item.wasteType);
    const title = item.ownerCompanyName || item.ownerName || item.ownerEmail || "Kullanıcı";
    const region = item.region || "-";
    const date = item.date ? formatDate(item.date) : "-";
    const quantity = item.quantity ?? "-";
    const unit = item.unit ? ` ${item.unit}` : "";
    const note = item.note ? String(item.note) : "";
    const ewcBlock =
      item.ewcCode || item.ewcDescription
        ? `<div class="mt-3 rounded-2xl bg-ecoBlue/5 border border-ecoBlue/15 p-3">
             <p class="text-xs font-semibold text-ecoGray">EWC (Excel)</p>
             ${
               item.ewcCode
                 ? `<p class="mt-1 text-sm font-semibold text-gray-800">${escapeHtml(String(item.ewcCode))}</p>`
                 : ""
             }
             ${
               item.ewcDescription
                 ? `<p class="mt-1 text-[11px] text-slate-600 leading-relaxed">${escapeHtml(truncate(item.ewcDescription, 160))}</p>`
                 : ""
             }
             ${
               item.ewcSource
                 ? `<p class="mt-2 text-[10px] text-slate-400">Kaynak: ${escapeHtml(truncate(String(item.ewcSource), 80))}</p>`
                 : ""
             }
           </div>`
        : "";
    const rec = window.getAraIslemRec ? window.getAraIslemRec(item.wasteType) : null;
    const recOperation = rec && rec.araIslem ? truncate(rec.araIslem, 150) : "";
    const recSource = rec && rec.kaynak ? String(rec.kaynak) : "";
    const recCost = rec && rec.maliyetPuan != null && rec.maliyetPuan !== "" ? String(rec.maliyetPuan) : "";
    const recTypeRaw = rec && rec.islemTipi != null && rec.islemTipi !== "" ? String(rec.islemTipi) : "";
    const shouldRecommendIntermediate = recTypeRaw === "1" || recTypeRaw === "1.0" || recTypeRaw === "1.00";
    const recTypeLabel =
      recTypeRaw === "1.0" || recTypeRaw === "1" ? "Uygun (1)" : recTypeRaw === "0.0" || recTypeRaw === "0" ? "Uygun değil (0)" : "";

    // Note: keep markup similar to site cards.
    return `
      <article class="rounded-3xl border border-gray-100 bg-white p-6 shadow-soft">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 rounded-2xl ${escapeHtml(wasteMeta.iconBg)} flex items-center justify-center text-xl">
            ${escapeHtml(wasteMeta.icon)}
          </div>
          <div>
            <h3 class="text-base font-semibold text-ecoGray">${escapeHtml(title)}</h3>
            <p class="text-xs text-gray-500">${escapeHtml(region)} • ${escapeHtml(date)}</p>
          </div>
        </div>
        <p class="mt-5 text-sm leading-6 text-gray-600">
          ${escapeHtml(wasteMeta.label)} ilanı: ${escapeHtml(String(quantity))}${escapeHtml(unit)}
        </p>
        <div class="mt-5 flex flex-wrap gap-2">
          <span class="px-3 py-1 rounded-full ${escapeHtml(wasteMeta.pill)} text-xs font-semibold">${escapeHtml(wasteMeta.label.split(" ")[0])}</span>
        </div>
        ${note ? `<p class="mt-3 text-sm text-gray-600">${escapeHtml(note)}</p>` : ""}
        ${ewcBlock}
        ${
          rec && recTypeLabel
            ? shouldRecommendIntermediate && recOperation
              ? `<div class="mt-3 rounded-2xl bg-slate-50 border border-slate-200/70 p-3">
                   <p class="text-xs font-semibold text-ecoGray">Önerilen ara işlem</p>
                   <p class="mt-1 text-xs text-gray-600 leading-relaxed">${escapeHtml(recOperation)}</p>
                   ${
                     recSource ? `<p class="mt-2 text-[11px] text-slate-500">Kaynak: ${escapeHtml(truncate(recSource, 70))}</p>` : ""
                   }
                   ${
                     recCost || recTypeLabel
                       ? `<p class="mt-2 text-[11px] text-slate-500">${escapeHtml(recCost ? `Maliyet: ${recCost}` : "")}${recCost && recTypeLabel ? " · " : ""}${escapeHtml(recTypeLabel ? `İşlem tipi: ${recTypeLabel}` : "")}</p>`
                       : ""
                   }
                 </div>`
              : `<div class="mt-3 rounded-2xl bg-slate-50 border border-slate-200/70 p-3">
                   <p class="text-xs font-semibold text-ecoGray">Sistem kararı</p>
                   <p class="mt-1 text-xs text-gray-600 leading-relaxed">Ara işlem gerekli değil (${escapeHtml(recTypeLabel)}).</p>
                   ${
                     recCost
                       ? `<p class="mt-2 text-[11px] text-slate-500">Maliyet: ${escapeHtml(recCost)}</p>`
                       : ""
                   }
                 </div>`
            : ""
        }
        <button
          type="button"
          class="mt-6 w-full rounded-full ${escapeHtml(wasteMeta.cta)}"
          data-contact-listing-id="${escapeHtml(item.id)}"
          data-contact-owner-email="${escapeHtml(item.ownerEmail || "")}"
          data-contact-owner-name="${escapeHtml(title)}"
          data-contact-waste-type="${escapeHtml(item.wasteType || "")}"
          data-contact-region="${escapeHtml(item.region || "")}"
        >
          İletişime geç
        </button>
      </article>
    `;
  }

  function render() {
    const gridEl = $("#canli-pazar-grid");
    if (!gridEl) return;

    const ilSelect = $("#canli-pazar-il-filter");
    const wasteSelect = $("#canli-pazar-waste-type-filter");
    const ilVal = ilSelect?.value || "";
    const wasteVal = wasteSelect?.value || "";

    const listings = loadListings();

    const filtered = listings.filter((x) => {
      const region = String(x.region || "");
      const wasteType = String(x.wasteType || "");
      const okIl = !ilVal || region === ilVal;
      const okType = !wasteVal || wasteType === wasteVal;
      return okIl && okType;
    });

    gridEl.innerHTML = "";

    if (filtered.length === 0) {
      gridEl.innerHTML = `
        <div class="col-span-full rounded-3xl border border-gray-100 bg-white p-8 text-center">
          <p class="text-sm font-semibold text-gray-800">Henüz ilan yok.</p>
          <p class="mt-1 text-xs text-gray-600">İlanlarım sayfasından ilan ekleyince burada anında görünecek.</p>
        </div>
      `;
      return;
    }

    filtered
      .slice()
      .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))
      .forEach((item) => {
        gridEl.insertAdjacentHTML("beforeend", buildCard(item));
      });
  }

  function fillProvinceSelect(selectEl) {
    if (!selectEl) return;
    const current = selectEl.value;
    selectEl.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "İl seçin";
    selectEl.appendChild(placeholder);

    PROVINCES_TR.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      selectEl.appendChild(opt);
    });

    if (current) selectEl.value = current;
  }

  function init() {
    if (window.__atik_canli_pazar_inited) return;
    window.__atik_canli_pazar_inited = true;

    const ilSelect = $("#canli-pazar-il-filter");
    const wasteSelect = $("#canli-pazar-waste-type-filter");
    const gridEl = $("#canli-pazar-grid");
    if (!gridEl || !ilSelect || !wasteSelect) return;

    fillProvinceSelect(ilSelect);
    const session = getSession();
    if (session?.location) {
      ilSelect.value = session.location;
    }

    // Initial render + interactions
    render();
    ilSelect.addEventListener("change", render);
    wasteSelect.addEventListener("change", render);

    // Live update (same device, different tabs)
    let lastSig = "";
    function computeSig(listings) {
      const maxCreatedAt = listings.reduce((acc, x) => Math.max(acc, Number(x.createdAt || 0)), 0);
      return `${listings.length}:${maxCreatedAt}`;
    }

    window.addEventListener("storage", (e) => {
      if (e.key !== LISTINGS_KEY) return;
      const listings = loadListings();
      const sig = computeSig(listings);
      if (sig !== lastSig) {
        lastSig = sig;
        render();
      }
    });

    // Same-tab quick refresh: poll lightweight signature.
    setInterval(() => {
      const listings = loadListings();
      const sig = computeSig(listings);
      if (sig !== lastSig) {
        lastSig = sig;
        render();
      }
    }, 4000);

    // Contact modal open/send
    const modal = ensureContactModal();
    let activeThreadId = null;
    let pollId = null;
    let lastModalOpenAt = 0;

    function openContact(listingId, ownerEmail, ownerName, wasteType, region) {
      const session = getSession();
      if (!session?.email) {
        alert("Mesaj göndermek için önce giriş yapmalısın.");
        window.location.href = "giris.html";
        return;
      }

      const myEmail = session.email;
      const myName = session.companyName ? `${session.name || session.companyName}` : session.name || "Sen";
      const tId = threadIdFor(listingId, myEmail, ownerEmail);
      activeThreadId = tId;
      lastModalOpenAt = Date.now();
      try {
        window.__atik_active_thread_id = tId;
      } catch (_e) {}

      upsertThread(tId, {
        listingId,
        recipientEmail: ownerEmail,
        recipientName: ownerName,
        wasteType,
        region,
      });

      const sub = $("#atik-contact-sub");
      if (sub) {
        sub.textContent = `${ownerName || "Kullanıcı"} ile · ${wasteType || "-"} · ${region || "-"}`;
      }

      // thread güncelliğini server'dan periyodik çek
      if (pollId) window.clearInterval(pollId);
      pollId = window.setInterval(function () {
        if (!activeThreadId) return;
        renderThread(activeThreadId, myEmail);
      }, 3500);

      renderThread(tId, myEmail);
      markThreadRead(tId, myEmail);

      modal.classList.remove("hidden");
      modal.classList.add("flex");
      const input = $("#atik-contact-input");
      input?.focus();
    }

    function openContactByThreadId(tId) {
      const session = getSession();
      if (!session?.email) {
        alert("Mesaj göndermek için önce giriş yapmalısın.");
        window.location.href = "giris.html";
        return;
      }
      const myEmail = session.email;
      activeThreadId = tId;
      lastModalOpenAt = Date.now();
      try {
        window.__atik_active_thread_id = tId;
      } catch (_e) {}

      // Start polling immediately
      if (pollId) window.clearInterval(pollId);
      pollId = window.setInterval(function () {
        if (!activeThreadId) return;
        renderThread(activeThreadId, myEmail);
      }, 3500);

      renderThread(tId, myEmail);
      markThreadRead(tId, myEmail);

      const modal = ensureContactModal();
      modal.classList.remove("hidden");
      modal.classList.add("flex");
      const input = $("#atik-contact-input");
      input?.focus();
    }

    modal.addEventListener("click", function (e) {
      // Dışarı tıklayınca kapatmayı devre dışı bırakıyoruz.
      // Bazı ortamlarda "open -> immediate outside click" gibi yarış durumu yaratıyordu.
      if (e.target === modal) return;
    });

    $(".modal-close-contact")?.addEventListener("click", function () {
      modal.classList.add("hidden");
      modal.classList.remove("flex");
      activeThreadId = null;
      try {
        window.__atik_active_thread_id = "";
      } catch (_e) {}
      if (pollId) window.clearInterval(pollId);
      pollId = null;
    });

    // Profile'dan gelen: Atik.html?contactThreadId=...
    try {
      const params = new URLSearchParams(window.location.search || "");
      const tId = (params.get("contactThreadId") || "").trim();
      if (tId) openContactByThreadId(tId);
    } catch (_e) {}

    function bindContactButtons() {
      const buttons = gridEl.querySelectorAll("[data-contact-listing-id]");
      buttons.forEach(function (btn) {
        if (btn.__contactBound) return;
        btn.__contactBound = true;
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          openContact(
            btn.getAttribute("data-contact-listing-id"),
            btn.getAttribute("data-contact-owner-email"),
            btn.getAttribute("data-contact-owner-name"),
            btn.getAttribute("data-contact-waste-type"),
            btn.getAttribute("data-contact-region")
          );
        });
      });
    }

    // Delegation fallback
    gridEl.addEventListener("click", function (e) {
      const btn = e.target.closest("[data-contact-listing-id]");
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      openContact(
        btn.getAttribute("data-contact-listing-id"),
        btn.getAttribute("data-contact-owner-email"),
        btn.getAttribute("data-contact-owner-name"),
        btn.getAttribute("data-contact-waste-type"),
        btn.getAttribute("data-contact-region")
      );
    });

    const form = $("#atik-contact-form");
    const input = $("#atik-contact-input");
    form?.addEventListener("submit", async function (e) {
      e.preventDefault();
      if (!activeThreadId) return;
      const session = getSession();
      if (!session?.email) return;

      const ok = await sendMessage(
        activeThreadId,
        session.email,
        session.companyName || session.name || "Sen",
        input?.value
      );
      if (ok) {
        input.value = "";
        renderThread(activeThreadId, session.email);
      }
    });

    // Live update across tabs/windows
    window.addEventListener("storage", function (e) {
      if (e.key !== CHAT_THREADS_KEY) return;
      if (!activeThreadId) return;
      const session = getSession();
      if (!session?.email) return;
      renderThread(activeThreadId, session.email);
    });

    // İlk render sonrası butonlara doğrudan binding.
    bindContactButtons();

    // Her render çağrısından sonra da (delegeye ek emniyet).
    const originalRender = render;
    render = function () {
      originalRender();
      bindContactButtons();
    };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

