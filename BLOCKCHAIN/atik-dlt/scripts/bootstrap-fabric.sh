#!/usr/bin/env bash
# WSL veya Linux'ta çalıştırın. Docker Desktop açık olmalı.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATIK_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Go chaincode: Node+WSL ortaminda UTF-8 hatalari gorulurse varsayilan olarak Go kullan
CC_DIR="${ATIK_CC_DIR:-$ATIK_ROOT/chaincode/atik-waste-go}"
FAB_HOME="${FAB_HOME:-$HOME/fabric-samples}"

echo ">> fabric-samples: $FAB_HOME"
echo ">> Chaincode: $CC_DIR"

if [ ! -d "$FAB_HOME/test-network" ]; then
  echo ">> fabric-samples yok — klonlanıyor..."
  mkdir -p "$(dirname "$FAB_HOME")"
  git clone --depth 1 https://github.com/hyperledger/fabric-samples.git "$FAB_HOME"
  cd "$FAB_HOME"
  echo ">> Fabric Docker + binary kurulumu (birkaç dakika sürebilir)..."
  curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/install-fabric.sh -o /tmp/install-fabric.sh
  chmod +x /tmp/install-fabric.sh
  /tmp/install-fabric.sh docker binary samples
else
  echo ">> fabric-samples zaten var."
fi

cd "$FAB_HOME"
if ! command -v peer >/dev/null 2>&1 && [[ ! -x "$FAB_HOME/bin/peer" ]]; then
  echo ">> peer binary yok — install-fabric.sh çalıştırılıyor..."
  curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/install-fabric.sh -o /tmp/install-fabric.sh
  chmod +x /tmp/install-fabric.sh
  /tmp/install-fabric.sh docker binary samples
fi
export PATH="$FAB_HOME/bin:${FAB_HOME}/../bin:${PATH}"

# (Node chaincode) fabric-nodeenv — sadece CC javascript ise gerekir
if [[ "$CC_DIR" == *"javascript"* ]] && command -v docker >/dev/null 2>&1; then
  echo ">> Docker: fabric-nodeenv (Node chaincode)..."
  if ! docker pull hyperledger/fabric-nodeenv:2.5 2>/dev/null; then
    docker pull ghcr.io/hyperledger/fabric-nodeenv:2.5.15
    docker tag ghcr.io/hyperledger/fabric-nodeenv:2.5.15 hyperledger/fabric-nodeenv:2.5 2>/dev/null || true
  fi
fi

cd "$FAB_HOME/test-network"

echo ">> Ağ: down + up + kanal..."
./network.sh down 2>/dev/null || true
./network.sh up createChannel -c mychannel

if [[ "$CC_DIR" == *"chaincode/atik-waste-go"* ]] || [[ "$CC_DIR" == *"atik-waste-go" ]]; then
  echo ">> Go chaincode: go mod vendor (apt install golang-go gerekir)..."
  if ! command -v go >/dev/null 2>&1; then
    echo "HATA: 'go' yok. WSL: sudo apt update && sudo apt install -y golang-go"
    exit 1
  fi
  (cd "$CC_DIR" && go mod tidy && go mod vendor)
  echo ">> Chaincode deploy (atikwaste, Go)..."
  ./network.sh deployCC -ccn atikwaste -ccp "$CC_DIR" -ccl go -c mychannel
else
  echo ">> Chaincode bağımlılıkları (Node)..."
  npm install --prefix "$CC_DIR"
  echo ">> Chaincode deploy (atikwaste, Node)..."
  ./network.sh deployCC -ccn atikwaste -ccp "$CC_DIR" -ccl javascript -c mychannel
fi

echo ""
echo "=============================================="
echo "FABRIC HAZIR"
echo "=============================================="
echo ""
echo "A) API'yi WSL içinden (önerilen):"
echo "   cd \"$ATIK_ROOT\""
echo "   npm install"
echo "   export USE_FABRIC=1"
echo "   npm run start:fabric"
echo ""
echo "B) API'yi Windows PowerShell'den:"
echo "   \$env:USE_FABRIC='1'"
echo "   \$env:CRYPTO_PATH = (wsl wslpath -w \$HOME/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com).Trim()"
echo "   cd \"$ATIK_ROOT\""
echo "   npm run start:fabric"
echo ""
echo "Sonra tarayıcı: blokzincir.html?server=1"
echo ""
