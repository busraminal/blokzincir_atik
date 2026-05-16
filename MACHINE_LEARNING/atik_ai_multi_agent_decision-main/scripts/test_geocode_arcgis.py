from geopy.geocoders import ArcGIS

g = ArcGIS(timeout=10)
queries = [
    "ALCI OSB MAH 2033. Cad. No:23 SİNCAN/ANKARA",
    "Açıkel Dağıtım Alcı OSB Mah 2033 Cad No 3/1 Sincan Ankara",
    "ASO 2. Organize Sanayi Bolgesi Sincan Ankara",
]
for q in queries:
    r = g.geocode(q)
    print(q)
    print((r.latitude, r.longitude, r.address) if r else None)
    print('-'*60)
