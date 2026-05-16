(() => {
  const SESSION_KEY = "atik_session_v1";

  const $ = (sel) => document.querySelector(sel);

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

  document.addEventListener("DOMContentLoaded", () => {
    const selectEl = $('select[name="logisticsLocality"]');
    const verifyBtn = $("#logistics-verify-location-btn");
    const msgEl = $("#logistics-verify-location-msg");
    const metaEl = $("#logistics-verify-location-meta");
    const latEl = $('input[name="logisticsLat"]');
    const lonEl = $('input[name="logisticsLon"]');

    if (!selectEl || !verifyBtn) return;

    fillProvinceSelect(selectEl);

    verifyBtn.addEventListener("click", async () => {
      verifyBtn.disabled = true;
      verifyBtn.classList.add("opacity-60", "cursor-not-allowed");

      if (msgEl) {
        msgEl.textContent = "Konum alınıyor...";
        msgEl.classList.remove("hidden");
      }
      if (metaEl) {
        metaEl.textContent = "";
        metaEl.classList.add("hidden");
      }

      try {
        const coords = await getBrowserCoords();
        if (msgEl) msgEl.textContent = "Konum doğrulanıyor...";

        const province = await reverseGeocodeProvince(coords.lat, coords.lon);
        if (!province) throw new Error("İl bilgisi tespit edilemedi.");

        const matchValue = findProvinceValue(selectEl, province);
        if (!matchValue) throw new Error(`İl eşleştirilemedi: ${province}`);

        selectEl.value = matchValue;

        if (latEl) latEl.value = String(coords.lat);
        if (lonEl) lonEl.value = String(coords.lon);

        if (msgEl) msgEl.textContent = `Konum doğrulandı: ${matchValue}`;
        if (metaEl) {
          metaEl.textContent = `Koordinat: ${coords.lat.toFixed(5)}, ${coords.lon.toFixed(5)}`;
          metaEl.classList.remove("hidden");
        }
      } catch (e) {
        const msg = e?.message || "Konum doğrulaması başarısız oldu.";
        if (msgEl) msgEl.textContent = msg;
        if (metaEl) metaEl.classList.add("hidden");
      } finally {
        verifyBtn.disabled = false;
        verifyBtn.classList.remove("opacity-60", "cursor-not-allowed");
      }
    });
  });
})();

