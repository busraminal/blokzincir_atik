"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const DATA_FILE = path.join(__dirname, "..", "data", "chain.json");

const STAGES = ["kayit", "tasimada", "gd_merkezi", "ayristirildi", "kapandi"];

function defaultsChainFields() {
  return {
    schemaVersion: 3,
    logisticsLocality: "",
    logisticsLat: null,
    logisticsLon: null,
    logisticsApiValidated: false,
    logisticsApiCheckedAt: null,
    intermediateProcessRequired: false,
    facilityCapacityKg: null,
    disposalAmountKg: 0,
    futureWasteKg: null,
    futureDisposalKg: null,
    supplyChainRef: "",
  };
}

function upgradeRecord(r) {
  const d = defaultsChainFields();
  for (const k of Object.keys(d)) {
    if (r[k] === undefined) r[k] = d[k];
  }
  r.schemaVersion = 3;
  return r;
}

function stageIndex(id) {
  const i = STAGES.indexOf(id);
  return i < 0 ? 0 : i;
}

function nowIso() {
  return new Date().toISOString();
}

function applyTransaction(state, tx) {
  switch (tx.type) {
    case "GENESIS":
      return;
    case "CREATE_WASTE": {
      const rec = upgradeRecord(JSON.parse(JSON.stringify(tx.payload.record)));
      if (!rec.id) throw new Error("Kayıt id eksik");
      if (state[rec.id]) throw new Error("Bu id zaten var: " + rec.id);
      state[rec.id] = rec;
      return;
    }
    case "ADVANCE_STAGE": {
      const { id, reusableKg } = tx.payload;
      const r = state[id];
      if (!r) throw new Error("Kayıt yok: " + id);
      if (r.stageId === "kapandi") throw new Error("Akış kapalı");
      const i = stageIndex(r.stageId);
      if (i >= STAGES.length - 1) throw new Error("İlerlenecek aşama yok");
      const nextId = STAGES[i + 1];
      if (nextId === "ayristirildi") {
        const kg = reusableKg != null ? Number(reusableKg) : NaN;
        if (Number.isNaN(kg) || kg < 0) throw new Error("ayristirildi için reusableKg gerekli");
        r.reusableKg = kg;
      }
      r.stageId = nextId;
      r.updatedAt = tx.payload.at || nowIso();
      r.events = r.events || [];
      let actor = "Sistem";
      if (nextId === "tasimada") actor = "Nakliye operatörü";
      if (nextId === "gd_merkezi") actor = "G.D. merkezi kabul";
      if (nextId === "ayristirildi") actor = "G.D. merkezi ayrıştırma";
      if (nextId === "kapandi") actor = "Yönetici";
      const hints = {
        kayit: "Kayıt / depo",
        tasimada: "Nakliyede",
        gd_merkezi: "G.D. merkezinde",
        ayristirildi: "Ayrıştırıldı",
        kapandi: "Süreç kapandı",
      };
      r.events.push({
        stageId: nextId,
        at: r.updatedAt,
        actor,
        note: hints[nextId] || nextId,
      });
      return;
    }
    case "PATCH_RECORD": {
      const { id, patch, eventNote, actor } = tx.payload;
      const r = state[id];
      if (!r) throw new Error("Kayıt yok: " + id);
      Object.assign(r, patch);
      r.updatedAt = nowIso();
      r.events = r.events || [];
      r.events.push({
        stageId: r.stageId,
        at: r.updatedAt,
        actor: actor || "API",
        note: eventNote || "Kayıt güncellendi",
      });
      upgradeRecord(r);
      return;
    }
    case "LOGISTICS_ATTEST": {
      const { id } = tx.payload;
      const r = state[id];
      if (!r) throw new Error("Kayıt yok: " + id);
      const t = nowIso();
      r.logisticsApiValidated = true;
      r.logisticsApiCheckedAt = t;
      r.updatedAt = t;
      r.events = r.events || [];
      r.events.push({
        stageId: r.stageId,
        at: t,
        actor: "Lojistik API (oracle)",
        note: "Yerellik / lojistik verisi doğrulandı (hash zincirine işlendi).",
      });
      return;
    }
    default:
      throw new Error("Bilinmeyen işlem: " + tx.type);
  }
}

function hashBlock(prevHash, tx, index) {
  return crypto
    .createHash("sha256")
    .update(prevHash + JSON.stringify(tx) + String(index))
    .digest("hex");
}

class Ledger {
  constructor() {
    this.chain = [];
    this.state = {};
  }

  rebuildState() {
    this.state = {};
    for (let i = 0; i < this.chain.length; i++) {
      applyTransaction(this.state, this.chain[i].tx);
    }
  }

  loadOrInit() {
    try {
      if (fs.existsSync(DATA_FILE)) {
        const raw = fs.readFileSync(DATA_FILE, "utf8");
        const data = JSON.parse(raw);
        if (Array.isArray(data.chain)) {
          this.chain = data.chain;
          this.rebuildState();
          return;
        }
      }
    } catch (e) {
      console.error("Ledger yüklenemedi, sıfırlanıyor:", e.message);
    }
    this.resetChain();
  }

  resetChain() {
    this.chain = [];
    this.state = {};
    const genesisTx = { type: "GENESIS", payload: {} };
    const prevHash = "0".repeat(64);
    const hash = hashBlock(prevHash, genesisTx, 0);
    this.chain.push({
      index: 0,
      timestamp: Date.now(),
      prevHash,
      tx: genesisTx,
      hash,
    });
    this.rebuildState();
    this.save();
  }

  save() {
    fs.mkdirSync(path.dirname(DATA_FILE), { recursive: true });
    fs.writeFileSync(DATA_FILE, JSON.stringify({ chain: this.chain }, null, 2), "utf8");
  }

  appendTx(tx) {
    const prevHash = this.chain[this.chain.length - 1].hash;
    const index = this.chain.length;
    const hash = hashBlock(prevHash, tx, index);
    this.chain.push({
      index,
      timestamp: Date.now(),
      prevHash,
      tx,
      hash,
    });
    applyTransaction(this.state, tx);
    this.save();
  }

  listRecords() {
    return Object.values(this.state)
      .map(upgradeRecord)
      .sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));
  }

  getRecord(id) {
    const r = this.state[id];
    return r ? upgradeRecord(JSON.parse(JSON.stringify(r))) : null;
  }

  getChain() {
    return this.chain.map((b) => ({
      index: b.index,
      timestamp: b.timestamp,
      prevHash: b.prevHash,
      hash: b.hash,
      type: b.tx.type,
    }));
  }

  getBlockDetail(index) {
    const b = this.chain[index];
    if (!b) return null;
    return { ...b, tx: JSON.parse(JSON.stringify(b.tx)) };
  }
}

const ledger = new Ledger();

function seedSamples() {
  const t = nowIso();
  return [
    Object.assign({}, defaultsChainFields(), {
      id: "ATK-2025-10001",
      wasteType: "Plastik",
      weightKg: 820,
      collector: "Ekolojik Toplama Ltd.",
      owner: "Delta Ambalaj San.",
      reusableKg: null,
      stageId: "tasimada",
      updatedAt: t,
      logisticsLocality: "İzmir / Bornova",
      logisticsLat: 38.42,
      logisticsLon: 27.14,
      logisticsApiValidated: true,
      logisticsApiCheckedAt: t,
      intermediateProcessRequired: true,
      facilityCapacityKg: 5000,
      disposalAmountKg: 0,
      futureWasteKg: 900,
      futureDisposalKg: 120,
      supplyChainRef: "TZ-PLS-2025-0341",
      events: [
        { stageId: "kayit", at: t, actor: "Ekolojik Toplama Ltd.", note: "İlk kayıt." },
        { stageId: "tasimada", at: t, actor: "Lojistik: Anadolu Nakliyat", note: "Sevk başladı." },
      ],
    }),
    Object.assign({}, defaultsChainFields(), {
      id: "ATK-2025-10002",
      wasteType: "Kağıt / karton",
      weightKg: 2400,
      collector: "Yeşil Toplama A.Ş.",
      owner: "KutuMatbaa A.Ş.",
      reusableKg: 1980,
      stageId: "ayristirildi",
      updatedAt: t,
      logisticsLocality: "Ankara / Sincan",
      logisticsApiValidated: false,
      intermediateProcessRequired: false,
      facilityCapacityKg: 10000,
      disposalAmountKg: 320,
      futureWasteKg: 2600,
      futureDisposalKg: 400,
      supplyChainRef: "TZ-KGT-2025-0098",
      events: [
        { stageId: "kayit", at: t, actor: "Yeşil Toplama A.Ş.", note: "Balya kaydı." },
        { stageId: "tasimada", at: t, actor: "Nakliye", note: "Sevk." },
        { stageId: "gd_merkezi", at: t, actor: "İzmir Geri Dönüşüm", note: "Kabul." },
        { stageId: "ayristirildi", at: t, actor: "İzmir Geri Dönüşüm", note: "Ayrıştırma tamam." },
      ],
    }),
  ];
}

module.exports = {
  ledger,
  loadOrInit: () => ledger.loadOrInit(),
  STAGES,
  seedSamples,
  nowIso,
  defaultsChainFields,
  applyTransaction,
};
