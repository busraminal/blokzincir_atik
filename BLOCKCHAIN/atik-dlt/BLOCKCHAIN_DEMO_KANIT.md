## Blockchain Demo Kanit Plani

Bu dokuman, bitirme projesi sunumunda Hyperledger Fabric tarafinin calistigini hizlica gostermek icin hazirlandi.

## 1) Beklenen Sistem Durumu

- Fabric agi calisiyor: `orderer.example.com`, `peer0.org1.example.com`, `peer0.org2.example.com`
- Kanal: `mychannel`
- Chaincode: `atikwaste`
- Son aktif chaincode tanimi: `Version 1.1`, `Sequence 2`
- API Fabric modda aciliyor: `npm run start:fabric`

## 2) Sunum Oncesi Hizli Kontrol

WSL terminal:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Burada peer/orderer konteynerleri `Up` gorulmeli.

PowerShell:

```powershell
cd "c:\Users\busra\Desktop\projeler\atık\BLOCKCHAIN\atik-dlt"
$env:USE_FABRIC="1"
$env:CRYPTO_PATH = (wsl -e bash -lc 'wslpath -w $HOME/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com').Trim()
npm run start:fabric
```

## 3) Canli Demo Akisi (2-3 dk)

1. Tarayicida ac:
   - `http://localhost:5055/health`
   - Beklenen: `mode` degeri `hyperledger-fabric`
2. Liste endpointini ac:
   - `http://localhost:5055/api/waste`
   - Bos ise `[]` gelmesi normaldir.
3. Uygulama ekranindan yeni bir atik kaydi olustur:
   - `http://localhost:5055/blokzincir.html?server=1`
4. `http://localhost:5055/api/waste` sayfasini yenile:
   - Yeni kaydin listede gorunmesi gerekir.

## 4) Sorun Cikarsa Hemen Kurtarma

WSL terminal:

```bash
cd ~/fabric-samples/test-network
./network.sh down
./network.sh up createChannel -c mychannel
```

Sonra API'yi tekrar Fabric modda acip demo adimlarini tekrarla.

## 5) Hocaya Tek Cumlelik Ozet

"Sistem Hyperledger Fabric test-network uzerinde (2 peer + 1 orderer) calisiyor; `atikwaste` chaincode'u kanalda commit edildi ve uygulamadan olusturulan kayitlar `/api/waste` uzerinden zincir verisi olarak okunuyor."
