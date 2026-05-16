"use strict";

/**
 * Hyperledger Fabric Gateway (gerçek peer) — test-network + User1@org1.example.com
 * Ortam değişkenleri: CRYPTO_PATH, PEER_ENDPOINT, CHANNEL_NAME, CHAINCODE_NAME
 */

const fs = require("fs");
const path = require("path");
const os = require("os");
const crypto = require("crypto");
const grpc = require("@grpc/grpc-js");
const { connect, hash, signers } = require("@hyperledger/fabric-gateway");
const { TextDecoder } = require("util");

const utf8 = new TextDecoder();

const channelName = process.env.CHANNEL_NAME || "mychannel";
const chaincodeName = process.env.CHAINCODE_NAME || "atikwaste";
const mspId = process.env.MSP_ID || "Org1MSP";
const peerEndpoint = process.env.PEER_ENDPOINT || "localhost:7051";
const peerHostAlias = process.env.PEER_HOST_ALIAS || "peer0.org1.example.com";

const defaultCrypto = path.join(
  os.homedir(),
  "fabric-samples",
  "test-network",
  "organizations",
  "peerOrganizations",
  "org1.example.com"
);
const cryptoPath = process.env.CRYPTO_PATH
  ? path.resolve(process.env.CRYPTO_PATH)
  : defaultCrypto;

let gateway = null;
let grpcClient = null;

function firstFile(dir) {
  if (!fs.existsSync(dir)) throw new Error("Klasör yok: " + dir);
  const files = fs.readdirSync(dir).filter((f) => !f.startsWith("."));
  if (!files.length) throw new Error("Boş klasör: " + dir);
  return path.join(dir, files[0]);
}

function getContract() {
  const tlsCertPath = path.join(cryptoPath, "peers", "peer0.org1.example.com", "tls", "ca.crt");
  const keyDir = path.join(cryptoPath, "users", "User1@org1.example.com", "msp", "keystore");
  const certDir = path.join(cryptoPath, "users", "User1@org1.example.com", "msp", "signcerts");

  if (!fs.existsSync(tlsCertPath)) {
    throw new Error(
      "Fabric TLS sertifikası bulunamadı: " +
        tlsCertPath +
        "\nÖnce WSL'de scripts/bootstrap-fabric.sh çalıştırın veya CRYPTO_PATH ayarlayın."
    );
  }

  if (!grpcClient) {
    const tlsRootCert = fs.readFileSync(tlsCertPath);
    const credentials = grpc.credentials.createSsl(tlsRootCert);
    grpcClient = new grpc.Client(peerEndpoint, credentials, {
      "grpc.ssl_target_name_override": peerHostAlias,
    });

    const certPath = firstFile(certDir);
    const identity = { mspId, credentials: fs.readFileSync(certPath) };
    const keyPath = firstFile(keyDir);
    const privateKey = crypto.createPrivateKey(fs.readFileSync(keyPath));
    const signer = signers.newPrivateKeySigner(privateKey);

    gateway = connect({
      client: grpcClient,
      identity,
      signer,
      hash: hash.sha256,
      evaluateOptions: () => ({ deadline: Date.now() + 25000 }),
      endorseOptions: () => ({ deadline: Date.now() + 60000 }),
      submitOptions: () => ({ deadline: Date.now() + 25000 }),
      commitStatusOptions: () => ({ deadline: Date.now() + 120000 }),
    });
  }

  return gateway.getNetwork(channelName).getContract(chaincodeName);
}

function closeFabric() {
  try {
    if (gateway) gateway.close();
  } catch (_e) {}
  try {
    if (grpcClient) grpcClient.close();
  } catch (_e) {}
  gateway = null;
  grpcClient = null;
}

async function fabricListRecords() {
  const c = getContract();
  const bytes = await c.evaluateTransaction("QueryAllWastes");
  const s = utf8.decode(bytes);
  return JSON.parse(s || "[]");
}

async function fabricGetRecord(id) {
  const c = getContract();
  const bytes = await c.evaluateTransaction("ReadWaste", id);
  return JSON.parse(utf8.decode(bytes));
}

async function fabricCreateWaste(rec) {
  const c = getContract();
  const jsonStr = JSON.stringify(rec);
  await c.submitTransaction("CreateWaste", rec.id, jsonStr);
  return rec;
}

async function fabricSaveWaste(rec) {
  const c = getContract();
  await c.submitTransaction("SaveWaste", rec.id, JSON.stringify(rec));
  return rec;
}

async function fabricDeleteWaste(id) {
  const c = getContract();
  await c.submitTransaction("DeleteWaste", id);
}

module.exports = {
  getContract,
  closeFabric,
  fabricListRecords,
  fabricGetRecord,
  fabricCreateWaste,
  fabricSaveWaste,
  fabricDeleteWaste,
  cryptoPath,
  chaincodeName,
  channelName,
};
