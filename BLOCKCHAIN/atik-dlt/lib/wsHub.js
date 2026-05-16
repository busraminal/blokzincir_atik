"use strict";

/**
 * SignalR tarzı merkezi hub: tek HTTP sunucusuna bağlı WebSocket uç noktası.
 * İstemciler konuya (topic) abone olur; sunucu hubBroadcast(topic, payload) ile yayınlar.
 *
 * Protokol (JSON metin):
 *   { "op": "sub",   "topic": "ledger" }   — abone ol
 *   { "op": "unsub", "topic": "ledger" }   — çık
 *   { "op": "ping" }                       — { "op": "pong", "t": ... }
 *
 * Sunucudan:
 *   { "op": "event", "topic": "ledger", "payload": {...}, "ts": number }
 */

const WebSocket = require("ws");

const topicClients = new Map();

function subscribe(topic, ws) {
  if (!topic || typeof topic !== "string") return;
  let set = topicClients.get(topic);
  if (!set) {
    set = new Set();
    topicClients.set(topic, set);
  }
  set.add(ws);
  if (!ws._atikHubTopics) ws._atikHubTopics = new Set();
  ws._atikHubTopics.add(topic);
}

function unsubscribe(topic, ws) {
  const set = topicClients.get(topic);
  if (set) {
    set.delete(ws);
    if (set.size === 0) topicClients.delete(topic);
  }
  if (ws._atikHubTopics) ws._atikHubTopics.delete(topic);
}

function detachClient(ws) {
  if (!ws._atikHubTopics) return;
  for (const t of ws._atikHubTopics) {
    const set = topicClients.get(t);
    if (set) {
      set.delete(ws);
      if (set.size === 0) topicClients.delete(t);
    }
  }
  ws._atikHubTopics.clear();
}

function attachWebSocketHub(httpServer, options) {
  const path = (options && options.path) || "/ws/hub";
  const wss = new WebSocket.Server({ server: httpServer, path });

  wss.on("connection", (ws) => {
    ws.send(
      JSON.stringify({
        op: "hello",
        path,
        hint: 'Örnek: {"op":"sub","topic":"ledger"}',
      })
    );

    ws.on("message", (raw) => {
      let msg;
      try {
        msg = JSON.parse(String(raw));
      } catch {
        return;
      }
      if (!msg || typeof msg !== "object") return;

      if (msg.op === "ping") {
        ws.send(JSON.stringify({ op: "pong", t: Date.now() }));
        return;
      }
      if (msg.op === "sub" && typeof msg.topic === "string") {
        subscribe(msg.topic, ws);
        ws.send(JSON.stringify({ op: "subscribed", topic: msg.topic }));
        return;
      }
      if (msg.op === "unsub" && typeof msg.topic === "string") {
        unsubscribe(msg.topic, ws);
        ws.send(JSON.stringify({ op: "unsubscribed", topic: msg.topic }));
        return;
      }
    });

    ws.on("close", () => detachClient(ws));
  });

  return { wss, path };
}

function hubBroadcast(topic, payload) {
  const set = topicClients.get(topic);
  if (!set || set.size === 0) return;
  const data = JSON.stringify({
    op: "event",
    topic,
    payload,
    ts: Date.now(),
  });
  for (const client of set) {
    if (client.readyState === WebSocket.OPEN) client.send(data);
  }
}

module.exports = { attachWebSocketHub, hubBroadcast };
