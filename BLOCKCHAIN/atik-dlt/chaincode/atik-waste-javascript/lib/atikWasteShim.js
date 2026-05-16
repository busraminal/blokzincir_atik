"use strict";

const shim = require("fabric-shim");

function wasteKey(id) {
  return "WASTE_" + id;
}

class AtikWaste {
  async Init() {
    return shim.success();
  }

  async Invoke(stub) {
    const ret = stub.getFunctionAndParameters();
    const fcn = ret.fcn;
    const params = ret.params;
    if (fcn === "CreateWaste") {
      const id = params[0];
      const jsonStr = params[1] || "";
      const key = wasteKey(id);
      const exists = await stub.getState(key);
      if (exists && exists.length > 0) {
        throw new Error("id already exists: " + id);
      }
      await stub.putState(key, Buffer.from(jsonStr, "utf8"));
      return shim.success(Buffer.from(jsonStr, "utf8"));
    }
    if (fcn === "ReadWaste") {
      const id = params[0];
      const key = wasteKey(id);
      const b = await stub.getState(key);
      if (!b || b.length === 0) {
        throw new Error("not found: " + id);
      }
      return shim.success(Buffer.from(b.toString("utf8"), "utf8"));
    }
    if (fcn === "SaveWaste") {
      const id = params[0];
      const jsonStr = params[1] || "";
      const key = wasteKey(id);
      const cur = await stub.getState(key);
      if (!cur || cur.length === 0) {
        throw new Error("not found: " + id);
      }
      await stub.putState(key, Buffer.from(jsonStr, "utf8"));
      return shim.success(Buffer.from(jsonStr, "utf8"));
    }
    if (fcn === "DeleteWaste") {
      const id = params[0];
      await stub.deleteState(wasteKey(id));
      return shim.success();
    }
    if (fcn === "QueryAllWastes") {
      const iterator = await stub.getStateByRange("", "");
      const out = [];
      let r = await iterator.next();
      while (!r.done) {
        const k = r.value.key;
        if (k.indexOf("WASTE_") === 0) {
          const v = r.value.value.toString("utf8");
          try {
            out.push(JSON.parse(v));
          } catch (_e) {
            out.push({ id: k.replace(/^WASTE_/, ""), raw: v });
          }
        }
        r = await iterator.next();
      }
      await iterator.close();
      const s = JSON.stringify(out);
      return shim.success(Buffer.from(s, "utf8"));
    }
    throw new Error("unknown fcn: " + fcn);
  }
}

module.exports = { AtikWaste, start: () => shim.start(new AtikWaste()) };
