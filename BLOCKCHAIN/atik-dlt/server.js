"use strict";

const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env") });
const fs = require("fs");
const http = require("http");
const https = require("https");
const express = require("express");
const cors = require("cors");
const {
  ledger,
  loadOrInit,
  seedSamples,
  nowIso,
  defaultsChainFields,
  applyTransaction,
} = require("./lib/ledger");
const { attachWebSocketHub, hubBroadcast } = require("./lib/wsHub");

const USE_FABRIC = process.env.USE_FABRIC === "1" || process.env.USE_FABRIC === "true";
let fabric = null;
if (USE_FABRIC) {
  fabric = require("./lib/fabricClient");
}

const PORT = process.env.PORT || 5040;
const OPENAI_API_KEY = (process.env.OPENAI_API_KEY || "").trim();
const OPENAI_MODEL = process.env.OPENAI_MODEL || "gpt-4o-mini";
const OPENAI_API_URL = (process.env.OPENAI_API_URL || "https://api.openai.com/v1/chat/completions").trim();

const USE_OLLAMA_RAW = (process.env.USE_OLLAMA || "").trim().toLowerCase();
const USE_OLLAMA_FLAG =
  USE_OLLAMA_RAW === "1" || USE_OLLAMA_RAW === "true" || USE_OLLAMA_RAW === "yes";
const OLLAMA_BASE_RAW = (process.env.OLLAMA_BASE_URL || process.env.OLLAMA_HOST || "").trim().replace(/\/+$/, "");
const ollamaBase = OLLAMA_BASE_RAW || (USE_OLLAMA_FLAG ? "http://127.0.0.1:11434" : "");
const useOllama = Boolean(ollamaBase);
const CHAT_MODEL = useOllama ? (process.env.OLLAMA_MODEL || "llama3.2").trim() : OPENAI_MODEL;
const CHAT_URL = useOllama ? ollamaBase + "/v1/chat/completions" : OPENAI_API_URL;
const CHAT_ENABLED = useOllama || Boolean(OPENAI_API_KEY);

/** Ollama: arayüzden seçilebilecek modeller (virgülle). Boşsa gemma3:4b + qwen2.5:7b + OLLAMA_MODEL */
function buildOllamaAllowedModels() {
  if (!useOllama) return [];
  const raw = (process.env.OLLAMA_CHAT_MODELS || "").trim();
  const fallback = ["gemma3:4b", "qwen2.5:7b"];
  const parts = raw
    ? raw.split(",").map((s) => s.trim()).filter((s) => s.length > 0 && s.length <= 120)
    : fallback;
  const set = new Set(parts);
  set.add(CHAT_MODEL);
  const arr = Array.from(set);
  arr.sort((a, b) => a.localeCompare(b));
  const i = arr.indexOf(CHAT_MODEL);
  if (i > 0) {
    arr.splice(i, 1);
    arr.unshift(CHAT_MODEL);
  }
  return arr;
}
const OLLAMA_ALLOWED_MODELS = buildOllamaAllowedModels();
const OLLAMA_ALLOWED_SET = new Set(OLLAMA_ALLOWED_MODELS);

function resolveRequestChatModel(requested) {
  if (!useOllama) return CHAT_MODEL;
  if (typeof requested !== "string") return CHAT_MODEL;
  const t = requested.trim();
  if (!t || t.length > 120) return CHAT_MODEL;
  return OLLAMA_ALLOWED_SET.has(t) ? t : CHAT_MODEL;
}
const CHAT_TEMPERATURE_RAW = (process.env.CHAT_TEMPERATURE || "").trim();
let CHAT_TEMPERATURE = useOllama ? 0.22 : 0.35;
if (CHAT_TEMPERATURE_RAW) {
  const f = parseFloat(CHAT_TEMPERATURE_RAW);
  if (!Number.isNaN(f) && f >= 0 && f <= 1.5) CHAT_TEMPERATURE = f;
}
const CHAT_MAX_TOKENS_RAW = (process.env.CHAT_MAX_TOKENS || "").trim();
let CHAT_MAX_TOKENS = useOllama ? 512 : 1200;
if (CHAT_MAX_TOKENS_RAW) {
  const n = parseInt(CHAT_MAX_TOKENS_RAW, 10);
  if (!Number.isNaN(n) && n >= 64 && n <= 32000) CHAT_MAX_TOKENS = n;
}
const WS_HUB_ENABLED =
  process.env.WS_HUB !== "0" && String(process.env.WS_HUB || "").toLowerCase() !== "false";
/** Üst klasördeki statik site (chatbot LLM için aynı origin: http://localhost:PORT/chatbot.html) */
const WEB_STATIC = process.env.WEB_STATIC_ROOT
  ? path.resolve(process.env.WEB_STATIC_ROOT)
  : path.join(__dirname, "..", "..", "WEB");
/** Proje kökündeki DATA / RESULT (PDF, xlsx, çıktılar) — /data/* ve /results/* */
const DATA_STATIC = path.join(__dirname, "..", "..", "DATA");
const RESULT_STATIC = path.join(__dirname, "..", "..", "RESULT");

/** ATIK AI (FastAPI): /api/atik-ai/* → ATIK_AI_PROXY_URL/api/v1/* (boşsa proxy kapalı) */
const ATIK_AI_PROXY_URL = (process.env.ATIK_AI_PROXY_URL || "").trim().replace(/\/+$/, "");

if (!USE_FABRIC) {
  loadOrInit();
}

const app = express();
app.use(
  cors({
    origin: function (_origin, callback) {
      callback(null, true);
    },
    credentials: true,
  })
);

function rewriteAtikAiRedirectLocation(locationHeader, proxyBase) {
  if (!locationHeader || !proxyBase) return locationHeader;
  const raw = String(locationHeader).trim();
  try {
    const base = new URL(proxyBase.endsWith("/") ? proxyBase : proxyBase + "/");
    const u = new URL(raw, base);
    if (u.origin !== base.origin) return locationHeader;
    const p = u.pathname + u.search + u.hash;
    if (p.startsWith("/api/v1")) {
      return p.replace(/^\/api\/v1/, "/api/atik-ai");
    }
  } catch (_e) {}
  return locationHeader;
}

if (ATIK_AI_PROXY_URL) {
  app.use((req, res, next) => {
    if (!req.originalUrl.startsWith("/api/atik-ai")) return next();
    try {
      const u = new URL(req.originalUrl, "http://127.0.0.1");
      const targetPath =
        (u.pathname.replace(/^\/api\/atik-ai/, "/api/v1") || "/api/v1") + (u.search || "");
      const base = new URL(ATIK_AI_PROXY_URL);
      const lib = base.protocol === "https:" ? https : http;
      const opts = {
        hostname: base.hostname,
        port: base.port || (base.protocol === "https:" ? 443 : 80),
        path: targetPath,
        method: req.method,
        headers: Object.assign({}, req.headers),
      };
      delete opts.headers.host;
      opts.headers.host = base.host;
      const pReq = lib.request(opts, (upstream) => {
        const headers = Object.assign({}, upstream.headers);
        if (headers.location) {
          headers.location = rewriteAtikAiRedirectLocation(headers.location, ATIK_AI_PROXY_URL);
        }
        res.writeHead(upstream.statusCode || 502, headers);
        upstream.pipe(res);
      });
      req.pipe(pReq);
      pReq.on("error", (e) => {
        if (!res.headersSent) {
          res.status(502).json({
            error: "ATIK AI API'ye ulaşılamadı",
            detail: e.message,
            hint:
              "uvicorn çalışıyor mu? Örn: python -m uvicorn atik_ai.api.routes:app --port 8000",
          });
        }
      });
    } catch (e) {
      if (!res.headersSent) res.status(500).json({ error: e.message });
    }
  });
}

app.use(express.json({ limit: "2mb" }));

// ------------------------------------------------------------
// Contact (Canlı Pazar) mini backend
// Amaç: localStorage yerine server üzerinden mesajlaşmayı
// farklı cihazlarda da mümkün kılmak.
// Not: Demo amaçlı JSON dosya persistence.
// ------------------------------------------------------------
const CONTACT_DB_PATH = process.env.CONTACT_DB_PATH
  ? path.resolve(process.env.CONTACT_DB_PATH)
  : path.join(__dirname, "contact_threads.json");

function readContactThreads() {
  try {
    if (!fs.existsSync(CONTACT_DB_PATH)) return {};
    const raw = fs.readFileSync(CONTACT_DB_PATH, "utf-8");
    const parsed = JSON.parse(raw || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_e) {
    return {};
  }
}

function writeContactThreads(threads) {
  try {
    fs.writeFileSync(CONTACT_DB_PATH, JSON.stringify(threads, null, 2), "utf-8");
  } catch (_e) {
    // ignore
  }
}

function getThreadLastMessage(t) {
  const msgs = Array.isArray(t?.messages) ? t.messages : [];
  if (!msgs.length) return { lastAt: null, lastText: null };
  let last = msgs[0];
  for (let i = 1; i < msgs.length; i++) {
    const at0 = Number(last?.at || 0);
    const at1 = Number(msgs[i?.at] || msgs[i]?.at || 0);
    if (at1 >= at0) last = msgs[i];
  }
  return {
    lastAt: last?.at != null ? last.at : null,
    lastText: last?.text != null ? String(last.text).slice(0, 120) : null,
  };
}

function ensureRecordList(list) {
  return Array.isArray(list) ? list : [];
}

app.get("/health", async (_req, res) => {
  try {
    if (USE_FABRIC) {
      const list = ensureRecordList(await fabric.fabricListRecords());
      return res.json({
        ok: true,
        mode: "hyperledger-fabric",
        chaincode: fabric.chaincodeName,
        channel: fabric.channelName,
        cryptoPath: fabric.cryptoPath,
        records: list.length,
        atikAiProxy: ATIK_AI_PROXY_URL || null,
        chat: CHAT_ENABLED,
        chatModel: CHAT_ENABLED ? CHAT_MODEL : null,
        chatModels: CHAT_ENABLED && useOllama ? OLLAMA_ALLOWED_MODELS : null,
        chatProvider: CHAT_ENABLED ? (useOllama ? "ollama" : "openai") : null,
        chatStream: CHAT_ENABLED,
        chatMaxTokens: CHAT_ENABLED ? CHAT_MAX_TOKENS : null,
        chatTemperature: CHAT_ENABLED ? CHAT_TEMPERATURE : null,
        webSocketHub: WS_HUB_ENABLED ? "/ws/hub" : null,
      });
    }
    res.json({
      ok: true,
      mode: "file-ledger",
      blocks: ledger.chain.length,
      records: Object.keys(ledger.state).length,
      atikAiProxy: ATIK_AI_PROXY_URL || null,
      chat: CHAT_ENABLED,
      chatModel: CHAT_ENABLED ? CHAT_MODEL : null,
      chatModels: CHAT_ENABLED && useOllama ? OLLAMA_ALLOWED_MODELS : null,
      chatProvider: CHAT_ENABLED ? (useOllama ? "ollama" : "openai") : null,
      chatStream: CHAT_ENABLED,
      chatMaxTokens: CHAT_ENABLED ? CHAT_MAX_TOKENS : null,
      chatTemperature: CHAT_ENABLED ? CHAT_TEMPERATURE : null,
      webSocketHub: WS_HUB_ENABLED ? "/ws/hub" : null,
    });
  } catch (e) {
    res.status(503).json({ ok: false, error: e.message, mode: USE_FABRIC ? "fabric" : "file" });
  }
});

app.get("/api/waste", async (_req, res) => {
  try {
    if (USE_FABRIC) {
      const list = ensureRecordList(await fabric.fabricListRecords());
      return res.json(list);
    }
    res.json(ledger.listRecords());
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/api/waste/:id", async (req, res) => {
  try {
    if (USE_FABRIC) {
      const r = await fabric.fabricGetRecord(req.params.id);
      return res.json(r);
    }
    const r = ledger.getRecord(req.params.id);
    if (!r) return res.status(404).json({ error: "Kayıt bulunamadı" });
    res.json(r);
  } catch (e) {
    if (USE_FABRIC && (e.message || "").indexOf("Kayıt yok") !== -1) {
      return res.status(404).json({ error: "Kayıt bulunamadı" });
    }
    res.status(404).json({ error: e.message || "Kayıt bulunamadı" });
  }
});

app.get("/api/blocks", (_req, res) => {
  if (USE_FABRIC) {
    return res.json({
      mode: "fabric",
      note: "Bloklar Fabric orderer/peer düğümlerinde. Bu uç örnek dosya zincirini listelemez.",
      explorerHint: "docker ps | findstr peer  —  peer logları: docker logs peer0.org1.example.com",
    });
  }
  res.json({ length: ledger.chain.length, blocks: ledger.getChain() });
});

app.get("/api/blocks/:index", (req, res) => {
  if (USE_FABRIC) {
    return res.status(400).json({ error: "Fabric modunda /api/blocks/:index kullanılmaz." });
  }
  const idx = parseInt(req.params.index, 10);
  const b = ledger.getBlockDetail(idx);
  if (!b) return res.status(404).json({ error: "Blok yok" });
  res.json(b);
});

function genId() {
  const y = new Date().getFullYear();
  const n = Math.floor(Math.random() * 90000) + 10000;
  return "ATK-" + y + "-" + n;
}

function upgradeRecordShape(r) {
  if (r.disposalAmountKg == null) r.disposalAmountKg = 0;
  return r;
}

const STAGE_ORDER = ["kayit", "tasimada", "gd_merkezi", "ayristirildi", "kapandi"];

app.post("/api/waste", async (req, res) => {
  try {
    const body = req.body || {};
    const t = nowIso();
    const rec = Object.assign({}, defaultsChainFields(), body, {
      id: body.id || genId(),
      stageId: "kayit",
      updatedAt: t,
      reusableKg: body.reusableKg != null ? body.reusableKg : null,
      events: body.events || [
        {
          stageId: "kayit",
          at: t,
          actor: body.collector || "Toplama",
          note: body.note || "Yeni kayıt (API / zincir).",
        },
      ],
    });
    upgradeRecordShape(rec);
    if (USE_FABRIC) {
      await fabric.fabricCreateWaste(rec);
      const saved = await fabric.fabricGetRecord(rec.id);
      hubBroadcast("ledger", { event: "waste-created", id: rec.id, mode: "fabric" });
      return res.status(201).json(saved);
    }
    ledger.appendTx({ type: "CREATE_WASTE", payload: { record: rec } });
    hubBroadcast("ledger", { event: "waste-created", id: rec.id, mode: "file-ledger" });
    res.status(201).json(ledger.getRecord(rec.id));
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

app.post("/api/waste/:id/advance", async (req, res) => {
  try {
    const id = req.params.id;
    let r;
    if (USE_FABRIC) {
      r = await fabric.fabricGetRecord(id);
    } else {
      r = ledger.getRecord(id);
    }
    if (!r) return res.status(404).json({ error: "Kayıt yok" });
    const i = STAGE_ORDER.indexOf(r.stageId);
    if (i < 0 || i >= STAGE_ORDER.length - 1) {
      return res.status(400).json({ error: "İlerletilemez (kapalı veya bilinmeyen aşama)" });
    }
    const nextId = STAGE_ORDER[i + 1];
    let reusableKg = req.body && req.body.reusableKg;
    if (nextId === "ayristirildi" && (reusableKg === undefined || reusableKg === null)) {
      return res.status(400).json({ error: "Bu aşama için reusableKg (geri kazanım kg) gerekli" });
    }
    const tx = {
      type: "ADVANCE_STAGE",
      payload: {
        id,
        reusableKg: reusableKg != null ? Number(reusableKg) : undefined,
        at: nowIso(),
      },
    };
    if (USE_FABRIC) {
      const state = { [id]: JSON.parse(JSON.stringify(r)) };
      applyTransaction(state, tx);
      await fabric.fabricSaveWaste(state[id]);
      hubBroadcast("ledger", {
        event: "stage-advanced",
        id,
        stageId: state[id].stageId,
        mode: "fabric",
      });
      return res.json(state[id]);
    }
    ledger.appendTx(tx);
    const afterAdv = ledger.getRecord(id);
    hubBroadcast("ledger", {
      event: "stage-advanced",
      id,
      stageId: afterAdv && afterAdv.stageId,
      mode: "file-ledger",
    });
    res.json(afterAdv);
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

app.patch("/api/waste/:id", async (req, res) => {
  try {
    const id = req.params.id;
    let exists;
    if (USE_FABRIC) {
      try {
        exists = await fabric.fabricGetRecord(id);
      } catch (_e) {
        exists = null;
      }
    } else {
      exists = ledger.getRecord(id);
    }
    if (!exists) return res.status(404).json({ error: "Kayıt yok" });

    const b = req.body || {};
    const patch = {};
    const allowed = [
      "logisticsLocality",
      "logisticsLat",
      "logisticsLon",
      "logisticsApiValidated",
      "logisticsApiCheckedAt",
      "intermediateProcessRequired",
      "facilityCapacityKg",
      "disposalAmountKg",
      "futureWasteKg",
      "futureDisposalKg",
      "supplyChainRef",
      "reusableKg",
      "weightKg",
      "wasteType",
      "collector",
      "owner",
    ];
    for (const k of allowed) {
      if (b[k] !== undefined) patch[k] = b[k];
    }
    if (patch.logisticsApiValidated === true) patch.logisticsApiCheckedAt = nowIso();
    if (patch.logisticsApiValidated === false) patch.logisticsApiCheckedAt = null;

    const tx = {
      type: "PATCH_RECORD",
      payload: {
        id,
        patch,
        actor: b.actor || "Zincir yöneticisi",
        eventNote: b.eventNote || "Kayıt alanları güncellendi (PATCH).",
      },
    };
    if (USE_FABRIC) {
      const state = { [id]: JSON.parse(JSON.stringify(exists)) };
      applyTransaction(state, tx);
      await fabric.fabricSaveWaste(state[id]);
      return res.json(state[id]);
    }
    ledger.appendTx(tx);
    res.json(ledger.getRecord(id));
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

app.post("/api/waste/:id/logistics-attest", async (req, res) => {
  try {
    const id = req.params.id;
    let r;
    if (USE_FABRIC) {
      r = await fabric.fabricGetRecord(id);
    } else {
      r = ledger.getRecord(id);
    }
    if (!r) return res.status(404).json({ error: "Kayıt yok" });
    const tx = { type: "LOGISTICS_ATTEST", payload: { id } };
    if (USE_FABRIC) {
      const state = { [id]: JSON.parse(JSON.stringify(r)) };
      applyTransaction(state, tx);
      await fabric.fabricSaveWaste(state[id]);
      return res.json(state[id]);
    }
    ledger.appendTx(tx);
    res.json(ledger.getRecord(id));
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

app.post("/api/seed", async (_req, res) => {
  try {
    if (USE_FABRIC) {
      let list = [];
      try {
        list = ensureRecordList(await fabric.fabricListRecords());
      } catch (_e) {}
      for (const rec of list) {
        try {
          await fabric.fabricDeleteWaste(rec.id);
        } catch (_e2) {}
      }
      for (const rec of seedSamples()) {
        await fabric.fabricCreateWaste(rec);
      }
      const n = ensureRecordList(await fabric.fabricListRecords()).length;
      return res.json({ ok: true, records: n, mode: "fabric" });
    }
    ledger.resetChain();
    for (const rec of seedSamples()) {
      ledger.appendTx({ type: "CREATE_WASTE", payload: { record: rec } });
    }
    res.json({ ok: true, records: ledger.listRecords().length, blocks: ledger.chain.length });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

/** Sık görülen uydurma / hatalı resmi URL kalıplarını yanıtta yumuşatır (LLM halüsinasyonu). */
function sanitizeChatReplyText(text) {
  if (text == null || typeof text !== "string") return text;
  return text
    .replace(/https?:\/\/www\.csiky\.gov\.tr[^\s)\]">]*/gi, "mevzuat.gov.tr ve ilgili kurumun güncel resmi sitesi (adresi doğrulayın)")
    .replace(/\bwww\.csiky\.gov\.tr[^\s)\]">]*/gi, "ilgili kurumun güncel resmi sitesi")
    .replace(/\[([^\]]*)\]\(https?:\/\/www\.csiky\.gov\.tr[^)]*\)/gi, "$1 — adresi ilgili kurumun güncel resmi sitesinden doğrulayın");
}

const CHAT_SYSTEM_PROMPT = [
  "ZORUNLU DİL: Yanıtın tamamını Türkçe yaz. Çince, Japonca, Korece veya başka dilde kelime/cümle ekleme; kullanıcı Türkçe yazıyor.",
  "Sen Atık AI platformunun Türkçe sohbet asistanısın (atık yönetimi, geri dönüşüm, sürdürülebilirlik). Kendini 'Ben Atık AI asistanıyım' gibi tanıt; kullanıcıya 'Sen Atık AI...' deme.",
  "Üslup: kısa, net, profesyonel; gereksiz uzun giriş ve tekrar yok. Gerekirse madde işareti; en fazla birkaç madde.",
  "Türkiye mevzuatı veya hukuki sonuç için kesin iddia verme; mevzuat.gov.tr ve ilgili kurumun güncel sitesinden doğrulama iste.",
  "Uydurma URL/telefon verme. csiky.gov.tr ve benzeri sahte alan adları YASAK; tam Bakanlık linki uydurma.",
  "Yanıtı tam ve anlamlı bir cümleyle bitir; yarım bırakma.",
  "Elektronik atık ve veri silme: kısa genel hatırlatma; kesin prosedür için kurum/IT uzmanı. SSD ile HDD farkını abartmadan belirt.",
  "Tehlikeli atık/ADR için yalnızca genel uyarı; etiket metni için mevzuat.",
  "Arayüz tanıtım amaçlıdır; hukuki tavsiye yerine geçmediğini gerektiğinde belirt.",
].join(" ");

app.post("/api/chat", async (req, res) => {
  if (!CHAT_ENABLED) {
    return res.status(503).json({
      error:
        "Sohbet kapalı. Yerel model için .env içinde USE_OLLAMA=1 (Ollama çalışıyor olmalı) veya bulut için OPENAI_API_KEY tanımlayıp sunucuyu yeniden başlatın.",
    });
  }
  const body = req.body || {};
  const messages = body.messages;
  if (!Array.isArray(messages) || messages.length === 0) {
    return res.status(400).json({ error: "Geçerli bir messages dizisi gerekli (OpenAI formatında role + content)." });
  }
  const safe = messages
    .filter((m) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string")
    .map((m) => ({ role: m.role, content: m.content.slice(0, 12000) }))
    .slice(-24);
  if (safe.length === 0) {
    return res.status(400).json({ error: "En az bir kullanıcı veya asistan mesajı gerekli." });
  }
  const useStream = Boolean(body.stream);
  const modelForRequest = resolveRequestChatModel(body.model);
  try {
    const headers = { "Content-Type": "application/json" };
    if (!useOllama && OPENAI_API_KEY) {
      headers.Authorization = "Bearer " + OPENAI_API_KEY;
    }
    const payload = {
      model: modelForRequest,
      messages: [{ role: "system", content: CHAT_SYSTEM_PROMPT }].concat(safe),
      temperature: CHAT_TEMPERATURE,
      max_tokens: CHAT_MAX_TOKENS,
      ...(useStream ? { stream: true } : {}),
    };
    const r = await fetch(CHAT_URL, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    const upstreamCt = (r.headers.get("content-type") || "").toLowerCase();
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      const msg = (data.error && data.error.message) || data.message || JSON.stringify(data).slice(0, 200);
      return res.status(r.status >= 400 && r.status < 600 ? r.status : 502).json({ error: msg });
    }
    if (useStream && upstreamCt.includes("text/event-stream") && r.body) {
      res.status(200);
      res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
      res.setHeader("Cache-Control", "no-cache, no-transform");
      res.setHeader("Connection", "keep-alive");
      res.setHeader("X-Accel-Buffering", "no");
      if (typeof res.flushHeaders === "function") res.flushHeaders();
      const reader = r.body.getReader();
      const onClose = () => {
        reader.cancel().catch(() => {});
      };
      req.on("close", onClose);
      req.on("aborted", onClose);
      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          if (value && value.length) res.write(Buffer.from(value));
        }
      } catch (_pipeErr) {
        try {
          res.end();
        } catch (_e2) {}
        return;
      }
      try {
        res.end();
      } catch (_e3) {}
      return;
    }
    const data = await r.json().catch(() => ({}));
    const text = (data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) || "";
    const cleaned = sanitizeChatReplyText(String(text).trim()) || "(Boş yanıt)";
    res.json({ reply: cleaned });
  } catch (e) {
    res.status(502).json({ error: e.message || "LLM isteği başarısız" });
  }
});

// ---------------------------
// Contact threads API
// ---------------------------
// GET /api/contact/thread/:threadId
app.get("/api/contact/thread/:threadId", async (req, res) => {
  const threadId = String(req.params.threadId || "");
  if (!threadId) return res.status(400).json({ error: "threadId gerekli" });

  try {
    const threads = readContactThreads();
    const t = threads[threadId];
    if (!t) {
      return res.json({
        threadId,
        listingId: null,
        recipientEmail: null,
        recipientName: null,
        wasteType: null,
        region: null,
        messages: [],
        updatedAt: null,
        readBy: {},
        lastMessageAt: null,
        lastMessagePreview: null,
      });
    }
    const { lastAt, lastText } = getThreadLastMessage(t);
    return res.json({
      ...t,
      readBy: t.readBy || {},
      lastMessageAt: lastAt,
      lastMessagePreview: lastText,
    });
  } catch (e) {
    return res.status(500).json({ error: e.message || "thread okunamadı" });
  }
});

// POST /api/contact/thread/:threadId/meta
app.post("/api/contact/thread/:threadId/meta", async (req, res) => {
  const threadId = String(req.params.threadId || "");
  if (!threadId) return res.status(400).json({ error: "threadId gerekli" });

  const body = req.body || {};
  const listingId = body.listingId != null ? String(body.listingId) : null;
  const recipientEmail = body.recipientEmail != null ? String(body.recipientEmail) : null;
  const recipientName = body.recipientName != null ? String(body.recipientName) : null;
  const wasteType = body.wasteType != null ? String(body.wasteType) : null;
  const region = body.region != null ? String(body.region) : null;

  try {
    const threads = readContactThreads();
    const existing = threads[threadId];
    const t = existing || {
      threadId,
      listingId: null,
      recipientEmail: null,
      recipientName: "",
      wasteType: "",
      region: "",
      messages: [],
      readBy: {},
      updatedAt: Date.now(),
    };

    // Only set if missing (avoid overriding already-written data)
    t.listingId = t.listingId || listingId;
    t.recipientEmail = t.recipientEmail || recipientEmail;
    t.recipientName = t.recipientName || recipientName || "";
    t.wasteType = t.wasteType || wasteType || "";
    t.region = t.region || region || "";
    t.readBy = t.readBy || {};
    t.updatedAt = Date.now();

    threads[threadId] = t;
    writeContactThreads(threads);
    return res.json({ ok: true, thread: t });
  } catch (e) {
    return res.status(500).json({ error: e.message || "thread meta kaydedilemedi" });
  }
});

// POST /api/contact/thread/:threadId/message
app.post("/api/contact/thread/:threadId/message", async (req, res) => {
  const threadId = String(req.params.threadId || "");
  if (!threadId) return res.status(400).json({ error: "threadId gerekli" });

  const body = req.body || {};
  const fromEmail = body.fromEmail != null ? String(body.fromEmail) : "";
  const fromName = body.fromName != null ? String(body.fromName) : "";
  const text = body.text != null ? String(body.text) : "";

  if (!fromEmail) return res.status(400).json({ error: "fromEmail gerekli" });
  if (!text || !text.trim()) return res.status(400).json({ error: "text boş olamaz" });

  const cleanText = text.trim().slice(0, 1200);

  try {
    const threads = readContactThreads();
    const existing = threads[threadId];
    const t = existing || {
      threadId,
      listingId: null,
      recipientEmail: null,
      recipientName: "",
      wasteType: "",
      region: "",
      messages: [],
      readBy: {},
      updatedAt: Date.now(),
    };

    t.messages = Array.isArray(t.messages) ? t.messages : [];
    t.readBy = t.readBy || {};

    // Meta is best-effort; işaretleme tutmazsa bile recipientEmail'ı threadId'den çıkar.
    // threadId formatı: pair:emailA|emailB (iki e-posta sortlu)
    if (!t.recipientEmail) {
      const m = String(threadId || "").match(/^pair:(.+)\|(.+)$/);
      if (m) {
        const e1 = String(m[1] || "");
        const e2 = String(m[2] || "");
        const from = String(fromEmail || "");
        if (from && from === e1) t.recipientEmail = e2;
        else if (from && from === e2) t.recipientEmail = e1;
      }
    }

    t.messages.push({
      id: `m_${Date.now()}_${Math.random().toString(16).slice(2)}`,
      fromEmail,
      fromName: fromName || "",
      text: cleanText,
      at: Date.now(),
    });
    t.updatedAt = Date.now();

    // Basic pruning
    if (t.messages.length > 200) t.messages = t.messages.slice(-200);

    threads[threadId] = t;
    writeContactThreads(threads);

    return res.json({ ok: true, thread: t });
  } catch (e) {
    return res.status(500).json({ error: e.message || "message gönderilemedi" });
  }
});

// POST /api/contact/thread/:threadId/read
app.post("/api/contact/thread/:threadId/read", async (req, res) => {
  const threadId = String(req.params.threadId || "");
  if (!threadId) return res.status(400).json({ error: "threadId gerekli" });

  const body = req.body || {};
  const readerEmail = body.readerEmail != null ? String(body.readerEmail) : "";
  if (!readerEmail) return res.status(400).json({ error: "readerEmail gerekli" });

  try {
    const threads = readContactThreads();
    const existing = threads[threadId];
    if (!existing) return res.status(404).json({ error: "thread yok" });

    const t = existing;
    t.readBy = t.readBy || {};

    const { lastAt } = getThreadLastMessage(t);
    if (lastAt != null) t.readBy[readerEmail] = lastAt;
    t.updatedAt = Date.now();

    threads[threadId] = t;
    writeContactThreads(threads);

    return res.json({ ok: true, threadId, readAt: t.readBy[readerEmail] || null });
  } catch (e) {
    return res.status(500).json({ error: e.message || "okuma işareti başarısız" });
  }
});

// GET /api/contact/threads?viewerEmail=...
app.get("/api/contact/threads", async (req, res) => {
  const viewerEmail = String(req.query.viewerEmail || "");
  if (!viewerEmail) return res.status(400).json({ error: "viewerEmail gerekli" });

  try {
    const threads = readContactThreads();
    const viewer = viewerEmail;
    const out = [];

    for (const [threadId, t] of Object.entries(threads || {})) {
      const msgs = Array.isArray(t?.messages) ? t.messages : [];
      const hasViewer =
        String(t?.recipientEmail || "") === String(viewer) || msgs.some((m) => String(m?.fromEmail || "") === String(viewer));
      if (!hasViewer) continue;

      // Last message
      const { lastAt, lastText } = getThreadLastMessage(t);

      // Unread count: viewer'ın son okumasından sonra gelen ve viewer'dan olmayan mesajlar
      const readBy = t.readBy || {};
      const lastReadAt = readBy[viewer] != null ? Number(readBy[viewer]) : null;
      const unread = msgs.filter((m) => {
        const at = Number(m?.at || 0);
        const from = String(m?.fromEmail || "");
        if (from === viewer) return false;
        if (lastReadAt == null) return true;
        return at > lastReadAt;
      }).length;

      out.push({
        threadId,
        listingId: t.listingId || null,
        recipientEmail: t.recipientEmail || null,
        recipientName: t.recipientName || "",
        wasteType: t.wasteType || "",
        region: t.region || "",
        lastMessageAt: lastAt,
        lastMessagePreview: lastText || "",
        unreadCount: unread,
      });
    }

    out.sort((a, b) => Number(b.lastMessageAt || 0) - Number(a.lastMessageAt || 0));
    return res.json({ ok: true, threads: out.slice(0, 30) });
  } catch (e) {
    return res.status(500).json({ error: e.message || "thread listesi başarısız" });
  }
});

app.delete("/api/waste", async (_req, res) => {
  try {
    if (USE_FABRIC) {
      const list = ensureRecordList(await fabric.fabricListRecords());
      for (const rec of list) {
        try {
          await fabric.fabricDeleteWaste(rec.id);
        } catch (_e) {}
      }
      return res.json({ ok: true, message: "Fabric defterindeki tüm atık kayıtları silindi.", mode: "fabric" });
    }
    ledger.resetChain();
    res.json({ ok: true, message: "Zincir sıfırlandı (yalnızca genesis)." });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

if (fs.existsSync(WEB_STATIC)) {
  app.get("/", (_req, res) => {
    res.sendFile(path.join(WEB_STATIC, "Atik.html"));
  });
  app.use(express.static(WEB_STATIC, { extensions: ["html"], index: false }));
} else {
  console.warn("Statik site klasörü yok (atlanıyor):", WEB_STATIC);
}
if (fs.existsSync(DATA_STATIC)) {
  app.use("/data", express.static(DATA_STATIC, { index: false }));
}
if (fs.existsSync(RESULT_STATIC)) {
  app.use("/results", express.static(RESULT_STATIC, { index: false }));
}

app.use((err, _req, res, _next) => {
  console.error(err);
  res.status(500).json({ error: "Sunucu hatası" });
});

const server = app.listen(PORT, () => {
  if (WS_HUB_ENABLED) {
    attachWebSocketHub(server, { path: "/ws/hub" });
    console.log("WebSocket hub (konu yayını): ws://localhost:" + PORT + "/ws/hub  |  örnek topic: ledger");
  }
  console.log("Atık API http://localhost:" + PORT);
  if (ATIK_AI_PROXY_URL) {
    console.log("ATIK AI proxy: GET /api/atik-ai/health/ → " + ATIK_AI_PROXY_URL + "/api/v1/health/");
  }
  if (String(PORT) === "5040") {
    console.log(
      "Not: /health veya sohbet boş dönüyorsa Windows’ta 5040 başka bir hizmetle çakışıyor olabilir — .env içinde PORT=5055 deneyin."
    );
  }
  if (USE_FABRIC) {
    console.log("Mod: HYPERLEDGER FABRIC  |  chaincode:", process.env.CHAINCODE_NAME || "atikwaste");
    console.log("CRYPTO_PATH:", fabric.cryptoPath);
  } else {
    console.log("Mod: dosya tabanlı demo zincir (chain.json)");
    console.log("Bloklar: GET /api/blocks  |  Fabric için: USE_FABRIC=1 ve bootstrap-fabric.sh");
  }
  console.log("Arayüz (dosyadan): blokzincir.html?server=1");
  if (fs.existsSync(WEB_STATIC)) {
    console.log("Web + API aynı portta: http://localhost:" + PORT + "/chatbot.html");
  }
  if (useOllama) {
    console.log("Sohbet LLM: Ollama  |  base:", ollamaBase, " |  model:", CHAT_MODEL);
  } else if (OPENAI_API_KEY) {
    console.log("Sohbet LLM: OpenAI  |  model:", OPENAI_MODEL);
  } else {
    console.log("Sohbet LLM: kapalı — USE_OLLAMA=1 veya OPENAI_API_KEY= (.env) ile açın");
  }
});

server.on("error", (err) => {
  if (err.code === "EADDRINUSE") {
    console.error(
      "Port " + PORT + " dolu (başka bir npm start / node çalışıyor olabilir).\n" +
        "Çözüm: o süreci kapatın veya farklı port:  $env:PORT=5041; npm start\n" +
        "Windows: netstat -ano | findstr :" + PORT + "  → taskkill /PID <pid> /F"
    );
  } else {
    console.error(err);
  }
  process.exit(1);
});

process.on("SIGINT", () => {
  if (fabric && fabric.closeFabric) fabric.closeFabric();
  server.close(() => process.exit(0));
});
