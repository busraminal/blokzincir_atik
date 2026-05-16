/**
 * Blokzincir / formlar için EWC (Excel json) yardımcıları.
 * ewc_codes_from_xlsx.json ile aynı kodlar; fetch başarısız olursa catalogFallback kullanılır.
 */
(function (global) {
  var catalogFallback = [
    { code: "080409", description: "Atık yapıştırıcı ve macunlar", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "070213", description: "Atık plastik (plastik üretimi)", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "070215", description: "Atık katkı maddeleri (plastik/kauçuk)", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100101", description: "Dip külü, cüruf ve kazan tozu", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100201", description: "Cüruf işleme atıkları", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100309", description: "İkincil üretim siyah cüruflar", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100321", description: "Alüminyum üretiminden tozlar", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100809", description: "Diğer cüruflar (demir dışı metalürji)", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100903", description: "Ergitme cürufları", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100908", description: "Tehlikeli madde içeren döküm kalıpları", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "100910", description: "Tehlikesiz döküm kalıp/maça", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "110109", description: "Tehlikeli madde içeren çamur", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "150106", description: "Karışık ambalajlar", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "150202", description: "Tehlikeli kirlenmiş emiciler/bezler", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "150110", description: "Tehlikeli madde kalıntılı ambalaj", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "160305", description: "Tehlikeli organik atıklar", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "080111", description: "Atık boya ve vernikler", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "080113", description: "Boya/vernik içeren sulu çamurlar", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "160602", description: "Ni-Cd piller", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "160604", description: "Alkalin piller", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "190805", description: "Kentsel atıksu arıtma çamurları", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "190205", description: "Fiziksel/kimyasal işlem çamurları", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "200301", description: "Karışık belediye atıkları", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "191212", description: "Mekanik işleme diğer atıklar", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "200133", description: "Piller ve aküler", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "200134", description: "Diğer pil ve aküler", source: "Ara İşlem Tablosu (1).xlsx" },
    { code: "200139", description: "Plastikler (belediye atığı)", source: "Ara İşlem Tablosu (1).xlsx" },
  ];

  var byBlokzincirCategory = {
    "Kağıt / karton": ["150106", "150110", "150202", "080409"],
    Plastik: ["070213", "070215", "200139"],
    Cam: ["100101", "100201", "100309", "191212"],
    Metal: ["100321", "100809", "100903", "100908", "100910"],
    "Tehlikeli atık": ["150110", "080111", "080113", "160305", "110109"],
    Organik: ["190805", "190205", "200301", "191212"],
    Elektronik: ["160602", "160604", "200133", "200134"],
  };

  function formatEwcCode(digits) {
    var s = String(digits || "")
      .replace(/\D/g, "")
      .padStart(6, "0");
    return s.slice(0, 2) + " " + s.slice(2, 4) + " " + s.slice(4, 6);
  }

  global.ATIK_EWC = {
    formatEwcCode: formatEwcCode,
    byBlokzincirCategory: byBlokzincirCategory,
    catalogFallback: catalogFallback,
  };
})(typeof window !== "undefined" ? window : this);
