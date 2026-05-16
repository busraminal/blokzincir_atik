(() => {
  const SESSION_KEY = "atik_session_v1";
  const CHAT_THREADS_KEY = "atik_contact_threads_v1";
  const INBOX_NOTIFICATIONS_KEY = "atik_inbox_notifications_v1";

  function getSession() {
    try {
      return JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    } catch {
      return null;
    }
  }

  function normEmail(s) {
    return String(s || "")
      .trim()
      .toLowerCase();
  }

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
    return "http://127.0.0.1:5055";
  }

  const API_BASE = resolveApiBase();
  function apiUrl(p) {
    if (!p) return p;
    return API_BASE ? API_BASE + p : p;
  }

  function escapeHtml(str) {
    return String(str ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatTime(ts) {
    try {
      const d = new Date(Number(ts));
      if (Number.isNaN(d.getTime())) return "-";
      return new Intl.DateTimeFormat("tr-TR", { year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
    } catch {
      return "-";
    }
  }

  function getOtherInPair(threadId, viewerEmail) {
    const m = String(threadId || "").match(/^pair:(.+)\|(.+)$/);
    if (!m) return null;
    const a = m[1];
    const b = m[2];
    const v = String(viewerEmail || "");
    if (a === v) return b;
    if (b === v) return a;
    return null;
  }

  function loadNotificationsRaw() {
    try {
      const list = JSON.parse(localStorage.getItem(INBOX_NOTIFICATIONS_KEY) || "[]");
      return Array.isArray(list) ? list : [];
    } catch {
      return [];
    }
  }

  function saveNotifications(list) {
    try {
      localStorage.setItem(INBOX_NOTIFICATIONS_KEY, JSON.stringify(list.slice(0, 200)));
    } catch (_e) {}
  }

  function markNotificationRead(id) {
    const list = loadNotificationsRaw();
    let changed = false;
    const next = list.map((n) => {
      if (String(n.id) === String(id) && !n.read) {
        changed = true;
        return { ...n, read: true };
      }
      return n;
    });
    if (changed) saveNotifications(next);
  }

  function markNotificationsReadForThread(threadId, viewerEmail) {
    const ve = normEmail(viewerEmail);
    const tid = String(threadId || "");
    const list = loadNotificationsRaw();
    let changed = false;
    const next = list.map((n) => {
      if (normEmail(n.recipientEmail) === ve && String(n.threadId) === tid && !n.read) {
        changed = true;
        return { ...n, read: true };
      }
      return n;
    });
    if (changed) saveNotifications(next);
  }

  function buildLocalThreadsSummary(viewerEmail) {
    const ve = normEmail(viewerEmail);
    let threads = {};
    try {
      threads = JSON.parse(localStorage.getItem(CHAT_THREADS_KEY) || "{}");
    } catch {
      threads = {};
    }
    const out = [];

    Object.keys(threads).forEach((tid) => {
      const other = getOtherInPair(tid, viewerEmail);
      if (!other) return;

      const t = threads[tid];
      const msgs = Array.isArray(t.messages) ? t.messages : [];
      const readBy = t.readBy || {};
      const lastReadAt = readBy[viewerEmail] != null ? Number(readBy[viewerEmail]) : null;

      const unreadCount = msgs.filter((m) => {
        const at = Number(m?.at || 0);
        const from = normEmail(m?.fromEmail);
        if (from === ve) return false;
        if (lastReadAt == null) return true;
        return at > lastReadAt;
      }).length;

      let otherName = "Kullanıcı";
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (normEmail(msgs[i]?.fromEmail) === normEmail(other)) {
          otherName = msgs[i]?.fromName || otherName;
          break;
        }
      }

      const lastMsg = msgs.length ? msgs[msgs.length - 1] : null;
      const lastPreview = t.lastMessagePreview || lastMsg?.text || "";
      const lastAt = t.lastMessageAt || lastMsg?.at || t.updatedAt || 0;

      out.push({
        threadId: tid,
        recipientName: otherName,
        lastMessagePreview: lastPreview,
        lastMessageAt: lastAt,
        unreadCount,
      });
    });

    return out.sort((a, b) => Number(b.lastMessageAt || 0) - Number(a.lastMessageAt || 0));
  }

  async function fetchThreads(viewerEmail) {
    const url = apiUrl("/api/contact/threads?viewerEmail=" + encodeURIComponent(viewerEmail));
    const r = await fetch(url, { method: "GET", headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error("API hatası " + r.status);
    return await r.json();
  }

  function navigateToThread(threadId) {
    const params = new URLSearchParams(window.location.search || "");
    params.set("contactThreadId", threadId);
    const apiBase = params.get("apiBase");
    const port = params.get("port");
    if (!apiBase && port) params.set("port", port);
    window.location.href = "Atik.html?" + params.toString();
  }

  function renderNotifications(viewerEmail) {
    const wrap = document.getElementById("profile-notifications-wrap");
    const listEl = document.getElementById("profile-notifications-list");
    if (!wrap || !listEl) return 0;

    const all = loadNotificationsRaw().filter((n) => normEmail(n.recipientEmail) === normEmail(viewerEmail));
    const unread = all.filter((n) => !n.read);

    if (unread.length === 0) {
      wrap.classList.add("hidden");
      listEl.innerHTML = "";
      return 0;
    }

    wrap.classList.remove("hidden");
    listEl.innerHTML = "";

    unread.slice(0, 12).forEach((n) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className =
        "w-full text-left rounded-xl bg-white/80 border border-amber-200/60 px-3 py-2.5 hover:bg-white transition";
      const title = n.fromName || n.fromEmail || "Kullanıcı";
      const sub = [n.wasteType, n.region].filter(Boolean).join(" · ");
      btn.innerHTML = `
        <p class="text-sm font-semibold text-ecoGray">${escapeHtml(title)} size mesaj gönderdi</p>
        <p class="mt-1 text-xs text-gray-600 leading-snug line-clamp-3">${escapeHtml(n.previewText || "")}</p>
        ${sub ? `<p class="mt-1 text-[11px] text-slate-500">${escapeHtml(sub)}</p>` : ""}
        <p class="mt-1 text-[10px] text-slate-400">${escapeHtml(formatTime(n.at))}</p>
      `;
      btn.addEventListener("click", () => {
        markNotificationRead(n.id);
        markNotificationsReadForThread(n.threadId, viewerEmail);
        navigateToThread(n.threadId);
      });
      listEl.appendChild(btn);
    });

    return unread.length;
  }

  function renderList(threads) {
    const listEl = document.getElementById("profile-thread-list");
    const unreadEl = document.getElementById("profile-unread-count");
    const unreadBadge = document.getElementById("profile-unread-badge");
    if (!listEl || !unreadEl || !unreadBadge) return;

    const threadUnread = Array.isArray(threads) ? threads.reduce((a, t) => a + Number(t.unreadCount || 0), 0) : 0;

    unreadEl.textContent = threadUnread ? `${threadUnread} okunmamış mesaj` : "Okunmamış mesaj yok";
    unreadBadge.textContent = String(threadUnread || 0);
    unreadBadge.classList.toggle("hidden", !threadUnread);

    listEl.innerHTML = "";
    if (!Array.isArray(threads) || threads.length === 0) {
      listEl.innerHTML = `<div class="text-xs text-gray-600">Henüz mesaj yok.</div>`;
      return;
    }

    threads.forEach((t) => {
      const unread = Number(t.unreadCount || 0);
      const preview = t.lastMessagePreview || "-";
      const name = t.recipientName || "Kullanıcı";
      const when = t.lastMessageAt ? formatTime(t.lastMessageAt) : "";

      const row = document.createElement("button");
      row.type = "button";
      row.className =
        "w-full text-left rounded-xl bg-white/80 border border-slate-200/70 px-3 py-2 hover:bg-white transition";
      row.setAttribute("data-thread-id", t.threadId);
      row.innerHTML = `
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <p class="text-sm font-semibold text-ecoGray truncate">${escapeHtml(name)}</p>
            <p class="mt-1 text-xs text-gray-600 truncate">${escapeHtml(preview)}</p>
            ${when ? `<p class="mt-1 text-[11px] text-slate-500">${escapeHtml(when)}</p>` : ""}
          </div>
          ${
            unread
              ? `<span class="inline-flex items-center justify-center rounded-full bg-ecoBlue/15 text-ecoBlue text-xs font-semibold px-2 py-1">${escapeHtml(
                  String(unread)
                )}</span>`
              : `<span class="inline-flex items-center justify-center rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold px-2 py-1 border border-emerald-200/60">Okundu</span>`
          }
        </div>
      `;

      listEl.appendChild(row);
    });
  }

  function bindClicks(sessionEmail) {
    const listEl = document.getElementById("profile-thread-list");
    if (!listEl) return;
    listEl.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-thread-id]");
      if (!btn) return;
      const threadId = btn.getAttribute("data-thread-id");
      if (!threadId) return;
      markNotificationsReadForThread(threadId, sessionEmail);
      navigateToThread(threadId);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const session = getSession();
    if (!session?.email) return;

    bindClicks(session.email);

    const run = async () => {
      renderNotifications(session.email);

      let threads = [];
      try {
        const data = await fetchThreads(session.email);
        threads = data?.threads || [];
      } catch (_e) {
        threads = [];
      }

      if (!threads.length) {
        threads = buildLocalThreadsSummary(session.email);
      }

      renderList(threads);
    };

    run();

    window.setInterval(run, 6000);

    window.addEventListener("storage", (e) => {
      if (e.key === INBOX_NOTIFICATIONS_KEY || e.key === CHAT_THREADS_KEY) run();
    });

    window.addEventListener("atik-inbox-updated", () => run());
  });
})();
