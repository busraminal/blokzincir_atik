(() => {
  const USERS_KEY = "atik_users_v1";
  const SESSION_KEY = "atik_session_v1";
  const DEMO_SEED_KEY = "atik_demo_role_accounts_v1";

  const USER_ROLES = ["producer", "carrier", "receiver", "disposer", "admin"];

  /** Kayıt formunda seçilebilir; admin burada yok (güvenlik). */
  const REGISTERABLE_ROLES = ["producer", "carrier", "receiver", "disposer"];

  const ROLE_LABELS = {
    producer: "Atık üreten",
    carrier: "Taşıyıcı",
    receiver: "Alan firma",
    disposer: "Bertaraf eden",
    admin: "Yönetici",
  };

  const ROLE_REGISTER_ORDER = ["producer", "carrier", "receiver", "disposer"];

  /** İsteğe bağlı: kendi e-postanızı buraya ekleyin (git’e koymayın — yerel kopyada bırakın). */
  const PROMOTED_ADMIN_EMAILS = [];

  const DEFAULT_ROLE = "producer";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  function normalizeRole(r) {
    const t = String(r || "").trim();
    return USER_ROLES.includes(t) ? t : DEFAULT_ROLE;
  }

  function roleLabel(role) {
    return ROLE_LABELS[normalizeRole(role)] || role;
  }

  /** Oturum + kullanıcı kaydından rol listesi (çoklu rol destekler). */
  function sessionRoles(session) {
    if (!session?.email) return [];
    const users = loadUsers();
    const u = users[session.email];
    if (normalizeRole(u?.role) === "admin" || normalizeRole(session?.role) === "admin") {
      return ["admin"];
    }
    if (u?.roles && Array.isArray(u.roles) && u.roles.length) {
      return [...new Set(u.roles.map(normalizeRole))].filter((x) => USER_ROLES.includes(x));
    }
    const single = normalizeRole(session.role || u?.role);
    return single ? [single] : [];
  }

  function userHasRole(session, roleId) {
    const need = normalizeRole(roleId);
    if (!session?.email) return false;
    if (need === "admin") {
      return normalizeRole(session.role) === "admin" || loadUsers()[session.email]?.role === "admin";
    }
    if (normalizeRole(session.role) === "admin" || loadUsers()[session.email]?.role === "admin") {
      return true;
    }
    return sessionRoles(session).includes(need);
  }

  function rolesDisplay(session) {
    const rs = sessionRoles(session);
    if (!rs.length) return "—";
    if (rs.length === 1) return roleLabel(rs[0]);
    return rs.map((r) => roleLabel(r)).join(" · ");
  }

  function migrateUsers() {
    const users = loadUsers();
    let changed = false;
    for (const email of Object.keys(users)) {
      const u = users[email];
      const next = u.role ? normalizeRole(u.role) : DEFAULT_ROLE;
      if (u.role !== next) {
        u.role = next;
        changed = true;
      }
      if (!u.roles || !Array.isArray(u.roles) || !u.roles.length) {
        u.roles = [normalizeRole(u.role || DEFAULT_ROLE)];
        changed = true;
      }
    }
    for (const raw of PROMOTED_ADMIN_EMAILS) {
      const k = raw.toLowerCase().trim();
      if (users[k] && (users[k].role !== "admin" || !users[k].roles || !users[k].roles.includes("admin"))) {
        users[k].role = "admin";
        users[k].roles = ["admin"];
        changed = true;
      }
    }
    if (changed) saveUsers(users);
  }

  async function seedDemoRoleAccounts() {
    if (localStorage.getItem(DEMO_SEED_KEY)) return;
    const demoPassword = "AtikDemo2026!";
    const hash = await sha256Hex(demoPassword);
    const users = loadUsers();
    const seeds = [
      { email: "yonetici@atik.demo", name: "Demo Yönetici", companyName: "Atık AI Yönetim", role: "admin" },
      { email: "uretici@atik.demo", name: "Demo Üretici", companyName: "Örnek Üretim A.Ş.", role: "producer" },
      { email: "tasiyici@atik.demo", name: "Demo Taşıyıcı", companyName: "Örnek Lojistik Ltd.", role: "carrier" },
      { email: "alan@atik.demo", name: "Demo Alan Firma", companyName: "Örnek Geri Kazanım A.Ş.", role: "receiver" },
      { email: "bertaraf@atik.demo", name: "Demo Bertaraf", companyName: "Örnek Bertaraf Tesisi", role: "disposer" },
    ];
    for (const row of seeds) {
      if (!users[row.email]) {
        users[row.email] = {
          email: row.email,
          name: row.name,
          companyName: row.companyName,
          location: "Ankara",
          passwordHash: hash,
          role: row.role,
          roles: [row.role],
          createdAt: Date.now(),
        };
      }
    }
    saveUsers(users);
    localStorage.setItem(DEMO_SEED_KEY, "1");
  }

  function refreshSessionRole() {
    const s = getSession();
    if (!s?.email) return;
    const users = loadUsers();
    const u = users[s.email];
    if (!u) return;
    const role = normalizeRole(u.role);
    const roles =
      u.roles && Array.isArray(u.roles) && u.roles.length
        ? u.roles.map(normalizeRole).filter((x) => USER_ROLES.includes(x))
        : [role];
    const next = { ...s, role, roles };
    if (s.role !== role || JSON.stringify(s.roles) !== JSON.stringify(roles)) {
      setSession(next);
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

  function getSession() {
    try {
      return JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    } catch {
      return null;
    }
  }

  function setSession(session) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }

  function clearSession() {
    localStorage.removeItem(SESSION_KEY);
  }

  async function sha256Hex(input) {
    const data = new TextEncoder().encode(String(input));
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  function formatDate(ts) {
    try {
      const date = new Date(Number(ts));
      if (Number.isNaN(date.getTime())) return "-";
      return new Intl.DateTimeFormat("tr-TR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date);
    } catch {
      return "-";
    }
  }

  function setMessage(text, kind = "error") {
    const el = $("#auth-message");
    if (!el) return;

    el.classList.remove("hidden");
    el.textContent = text;
    el.classList.remove("border-red-200", "bg-red-50", "text-red-700", "border-green-200", "bg-green-50", "text-green-700");
    if (kind === "success") {
      el.classList.add("border-green-200", "bg-green-50", "text-green-700");
    } else {
      el.classList.add("border-red-200", "bg-red-50", "text-red-700");
    }
  }

  function clearMessage() {
    const el = $("#auth-message");
    if (!el) return;
    el.classList.add("hidden");
    el.textContent = "";
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
        (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        (err) => {
          if (err && err.code === 1) reject(new Error("Konum izni vermelisin."));
          else if (err && err.code === 3) reject(new Error("Konum alma zaman aşımına uğradı."));
          else reject(new Error("Konum alınamadı."));
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
      );
    });
  }

  function setActiveTab(tab) {
    const loginTab = $("#auth-tab-login");
    const registerTab = $("#auth-tab-register");
    const loginForm = $("#auth-form-login");
    const registerForm = $("#auth-form-register");
    if (!loginTab || !registerTab || !loginForm || !registerForm) return;

    const showLogin = tab === "login";
    loginTab.setAttribute("aria-selected", showLogin ? "true" : "false");
    registerTab.setAttribute("aria-selected", showLogin ? "false" : "true");

    // Simple visual swap (same tailwind classes used in HTML)
    loginTab.classList.toggle("bg-white", showLogin);
    loginTab.classList.toggle("text-ecoGray", showLogin);
    loginTab.classList.toggle("text-gray-500", !showLogin);

    registerTab.classList.toggle("bg-white", !showLogin);
    registerTab.classList.toggle("text-gray-500", showLogin);
    registerTab.classList.toggle("text-ecoGray", !showLogin);

    loginForm.classList.toggle("hidden", !showLogin);
    registerForm.classList.toggle("hidden", showLogin);
  }

  function syncAuthNav() {
    const session = getSession();
    const isLoggedIn = !!session?.email;

    $$("[data-auth-nav='login']").forEach((el) => {
      el.classList.toggle("hidden", isLoggedIn);
    });
    $$("[data-auth-nav='profile']").forEach((el) => {
      el.classList.toggle("hidden", !isLoggedIn);
    });

    $$("[data-auth-roles]").forEach((el) => {
      const raw = el.getAttribute("data-auth-roles") || "";
      const roles = raw
        .split("|")
        .map((s) => s.trim())
        .filter(Boolean);
      const ok =
        isLoggedIn &&
        session &&
        roles.some((r) => userHasRole(session, r));
      el.classList.toggle("hidden", !ok);
    });

    $$("[data-auth-hide-admin]").forEach((el) => {
      const hide = isLoggedIn && session && userHasRole(session, "admin");
      el.classList.toggle("hidden", hide);
    });
  }

  function bindAuthUI() {
    const tabLogin = $("#auth-tab-login");
    const tabRegister = $("#auth-tab-register");

    if (tabLogin && tabRegister) {
      tabLogin.addEventListener("click", () => {
        clearMessage();
        setActiveTab("login");
      });
      tabRegister.addEventListener("click", () => {
        clearMessage();
        setActiveTab("register");
      });
    }

    const linkToRegister = $("#auth-switch-to-register");
    const linkToLogin = $("#auth-switch-to-login");
    linkToRegister?.addEventListener("click", (e) => {
      e.preventDefault();
      clearMessage();
      setActiveTab("register");
    });
    linkToLogin?.addEventListener("click", (e) => {
      e.preventDefault();
      clearMessage();
      setActiveTab("login");
    });

    const loginForm = $("#auth-form-login");
    loginForm?.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearMessage();

      const email = ($("#login-email")?.value || "").trim().toLowerCase();
      const password = ($("#login-password")?.value || "").trim();

      if (!email || !password) {
        setMessage("Lütfen e-posta ve şifre girin.");
        return;
      }

      const users = loadUsers();
      const user = users[email];
      if (!user) {
        setMessage("Bu e-posta ile kayıt bulunamadı.");
        return;
      }

      const passwordHash = await sha256Hex(password);
      if (user.passwordHash !== passwordHash) {
        setMessage("Şifre yanlış.");
        return;
      }

      const now = Date.now();
      const role = normalizeRole(user.role);
      const roles =
        user.roles && Array.isArray(user.roles) && user.roles.length
          ? user.roles.map(normalizeRole).filter((x) => USER_ROLES.includes(x))
          : [role];
      setSession({
        email: user.email,
        name: user.name,
        companyName: user.companyName,
        location: user.location,
        role,
        roles,
        createdAt: user.createdAt || now,
        loggedInAt: now,
        lastLoginAt: now,
      });
      syncAuthNav();
      window.location.href = role === "admin" ? "admin.html" : "profil.html";
    });

    const registerForm = $("#auth-form-register");
    registerForm?.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearMessage();

      const name = ($("#register-name")?.value || "").trim();
      const email = ($("#register-email")?.value || "").trim().toLowerCase();
      const companyName = ($("#register-company")?.value || "").trim();
      const location = ($("#register-location")?.value || "").trim();
      const password = ($("#register-password")?.value || "").trim();
      const passwordConfirm = ($("#register-password-confirm")?.value || "").trim();
      const termsAccepted = $("#register-terms")?.checked;

      if (!name || !email || !companyName || !location || !password || !passwordConfirm) {
        setMessage("Lütfen tüm alanları doldurun.");
        return;
      }
      const pickedRoles = ROLE_REGISTER_ORDER.filter((id) => $("#reg-role-" + id)?.checked);
      if (!pickedRoles.length) {
        setMessage("En az bir hesap rolü seçin (ör. hem atık üreten hem alan firma işaretleyebilirsiniz).");
        return;
      }
      if (!email.includes("@")) {
        setMessage("Geçerli bir e-posta girin.");
        return;
      }
      if (password.length < 6) {
        setMessage("Şifre en az 6 karakter olmalı.");
        return;
      }
      if (password !== passwordConfirm) {
        setMessage("Şifreler eşleşmiyor.");
        return;
      }
      if (!termsAccepted) {
        setMessage("Lütfen platform kurallarını kabul edin.");
        return;
      }

      const users = loadUsers();
      if (users[email]) {
        setMessage("Bu e-posta zaten kayıtlı.");
        return;
      }

      const passwordHash = await sha256Hex(password);
      const primaryRole = pickedRoles[0];
      users[email] = {
        email,
        name,
        companyName,
        location,
        passwordHash,
        role: primaryRole,
        roles: pickedRoles.slice(),
        createdAt: Date.now(),
      };
      saveUsers(users);

      // Auto-login after registration
      setSession({
        email,
        name,
        companyName: users[email].companyName,
        location: users[email].location,
        role: primaryRole,
        roles: pickedRoles.slice(),
        createdAt: users[email].createdAt,
        loggedInAt: Date.now(),
        lastLoginAt: Date.now(),
      });
      syncAuthNav();
      window.location.href = "profil.html";
    });
  }

  function bindProfileUI() {
    const logoutBtn = $("#auth-logout-btn");
    logoutBtn?.addEventListener("click", () => {
      clearSession();
      syncAuthNav();
      window.location.href = "giris.html";
    });

    const session = getSession();
    if (!session) return;

    const nameEl = $("#profile-name");
    const emailEl = $("#profile-email");
    const companyEl = $("#profile-company");
    const locationEl = $("#profile-location");
    const initialsEl = $("#profile-initials");
    const subtitleEl = $("#profile-subtitle");
    const sinceEl = $("#profile-since");
    const lastLoginEl = $("#profile-last-login");
    const roleEl = $("#profile-role");

    const name = session.name || session.email || "-";
    if (nameEl) nameEl.textContent = name;
    if (emailEl) emailEl.textContent = session.email || "";
    if (companyEl) companyEl.textContent = session.companyName || "-";
    if (locationEl) locationEl.textContent = session.location || "-";
    if (roleEl) roleEl.textContent = rolesDisplay(session);

    if (initialsEl) {
      const parts = String(name)
        .trim()
        .split(/\s+/)
        .filter(Boolean);
      const a = parts[0]?.[0] || "";
      const b = parts[1]?.[0] || "";
      initialsEl.textContent = (a + b).toUpperCase() || "-";
    }

    if (subtitleEl) {
      const loc = session.location ? String(session.location) : "";
      subtitleEl.textContent = session.email ? (loc ? `Kurumsal hesap · ${loc}` : "Kurumsal hesap") : "-";
    }

    if (sinceEl) {
      const createdAt = session.createdAt || session.loggedInAt;
      sinceEl.textContent = createdAt ? formatDate(createdAt) : "-";
    }

    if (lastLoginEl) {
      const lastLoginAt = session.lastLoginAt || session.loggedInAt;
      lastLoginEl.textContent = lastLoginAt ? formatDate(lastLoginAt) : "-";
    }

    const updateForm = $("#profile-update-form");
    const companyInput = $("#profile-company-input");
    const locationSelect = $("#profile-location-input");
    const updateMsgEl = $("#profile-update-message");

    const verifyBtn = $("#profile-verify-location-btn");
    const verifyMsgEl = $("#profile-verify-location-msg");
    const verifyMetaEl = $("#profile-verify-location-meta");

    if (verifyBtn && locationSelect) {
      verifyBtn.addEventListener("click", async () => {
        if (!session?.email) return;

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

          const matchValue = findProvinceValue(locationSelect, province);
          if (!matchValue) throw new Error(`İl eşleştirilemedi: ${province}`);

          locationSelect.value = matchValue;

          // Persist location to session + user record so ilanlarım da güncellensin.
          const updatedSession = {
            ...session,
            location: matchValue,
            roles: session.roles?.length ? session.roles : sessionRoles(session),
          };
          setSession(updatedSession);

          const users = loadUsers();
          if (users?.[session.email]) {
            users[session.email].location = matchValue;
            saveUsers(users);
          }

          if (verifyMsgEl) verifyMsgEl.textContent = `Konum doğrulandı: ${matchValue}`;
          if (verifyMetaEl) {
            verifyMetaEl.textContent = `Koordinat: ${coords.lat.toFixed(5)}, ${coords.lon.toFixed(5)}`;
            verifyMetaEl.classList.remove("hidden");
          }

          if (locationEl) locationEl.textContent = matchValue;
          if (subtitleEl) subtitleEl.textContent = `Kurumsal hesap · ${matchValue}`;
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

    if (updateForm && companyInput && locationSelect) {
      companyInput.value = session.companyName || "";
      locationSelect.value = session.location || "";

      updateForm.addEventListener("submit", (ev) => {
        ev.preventDefault();

        const newCompany = String(companyInput.value || "").trim();
        const newLocation = String(locationSelect.value || "").trim();

        if (!newCompany || !newLocation) {
          if (updateMsgEl) {
            updateMsgEl.classList.remove("hidden");
            updateMsgEl.textContent = "Lütfen işletme adı ve konum/bölge gir.";
            updateMsgEl.classList.remove("text-green-700");
          }
          return;
        }

        const users = loadUsers();
        if (!users?.[session.email]) {
          if (updateMsgEl) {
            updateMsgEl.classList.remove("hidden");
            updateMsgEl.textContent = "Oturum bilgisi bulunamadı. Lütfen tekrar giriş yap.";
            updateMsgEl.classList.remove("text-green-700");
          }
          return;
        }

        users[session.email].companyName = newCompany;
        users[session.email].location = newLocation;
        saveUsers(users);

        const newSession = {
          ...session,
          companyName: newCompany,
          location: newLocation,
          role: normalizeRole(session.role),
          roles: session.roles && session.roles.length ? session.roles : sessionRoles(session),
          loggedInAt: Date.now(),
          lastLoginAt: Date.now(),
        };
        setSession(newSession);

        if (companyEl) companyEl.textContent = newCompany;
        if (locationEl) locationEl.textContent = newLocation;
        if (subtitleEl) subtitleEl.textContent = `Kurumsal hesap · ${newLocation}`;

        if (updateMsgEl) {
          updateMsgEl.classList.remove("hidden");
          updateMsgEl.textContent = "Bilgiler kaydedildi.";
          updateMsgEl.classList.add("text-green-700");
        }
      });
    }

    // Password change (localStorage users)
    const passForm = $("#profile-password-change-form");
    const oldPassEl = $("#profile-old-password");
    const newPassEl = $("#profile-new-password");
    const newPassConfirmEl = $("#profile-new-password-confirm");
    const passMsgEl = $("#profile-password-change-message");

    function setPassMsg(text, kind) {
      if (!passMsgEl) return;
      if (!text) {
        passMsgEl.classList.add("hidden");
        passMsgEl.textContent = "";
        return;
      }
      passMsgEl.textContent = text;
      passMsgEl.classList.remove("hidden");
      // Minimal styling (avoid relying on global auth message styles)
      passMsgEl.classList.remove("border-red-200", "bg-red-50", "text-red-700", "border-green-200", "bg-green-50", "text-green-700");
      if (kind === "success") {
        passMsgEl.classList.add("border-green-200", "bg-green-50", "text-green-700");
      } else {
        passMsgEl.classList.add("border-red-200", "bg-red-50", "text-red-700");
      }
    }

    if (passForm && oldPassEl && newPassEl && newPassConfirmEl) {
      passForm.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        if (!session?.email) return;

        const oldPass = String(oldPassEl.value || "").trim();
        const newPass = String(newPassEl.value || "").trim();
        const newPassConfirm = String(newPassConfirmEl.value || "").trim();

        if (!oldPass || !newPass || !newPassConfirm) {
          setPassMsg("Lütfen tüm şifre alanlarını doldurun.");
          return;
        }
        if (newPass.length < 6) {
          setPassMsg("Yeni şifre en az 6 karakter olmalı.");
          return;
        }
        if (newPass !== newPassConfirm) {
          setPassMsg("Yeni şifreler eşleşmiyor.");
          return;
        }

        const users = loadUsers();
        if (!users?.[session.email]) {
          setPassMsg("Oturum bilgisi bulunamadı, tekrar giriş yapın.", null);
          return;
        }

        const oldHash = await sha256Hex(oldPass);
        if (users[session.email].passwordHash !== oldHash) {
          setPassMsg("Mevcut şifre hatalı.");
          return;
        }

        users[session.email].passwordHash = await sha256Hex(newPass);
        saveUsers(users);

        setPassMsg("Şifre güncellendi. Lütfen tekrar giriş yapın.", "success");

        clearSession();
        syncAuthNav();
        window.location.href = "giris.html";
      });
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    await seedDemoRoleAccounts();
    migrateUsers();
    refreshSessionRole();

    const page = document.body.getAttribute("data-page");
    const session = getSession();
    const reqRole = document.body.getAttribute("data-required-role");

    if (reqRole) {
      const s = getSession();
      if (!s?.email) {
        window.location.href = "giris.html";
        return;
      }
      if (!userHasRole(s, reqRole)) {
        window.location.href = "profil.html";
        return;
      }
    }

    if (page === "giris" && session?.email) {
      window.location.href = normalizeRole(session.role) === "admin" ? "admin.html" : "profil.html";
      return;
    }
    if ((page === "profil" || page === "ilanlarim") && !session?.email) {
      window.location.href = "giris.html";
      return;
    }

    syncAuthNav();
    bindAuthUI();
    if (page === "profil") bindProfileUI();
    if (page === "admin") bindAdminUI();
  });

  function bindAdminUI() {
    const s = getSession();
    const emailEl = $("#admin-session-email");
    if (emailEl && s?.email) emailEl.textContent = s.email;
    const roleEl = $("#admin-session-role");
    if (roleEl && s?.role) roleEl.textContent = rolesDisplay(s);
  }
})();

