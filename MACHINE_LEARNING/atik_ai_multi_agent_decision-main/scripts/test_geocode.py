from geopy.geocoders import Nominatim

queries = [
    "ALCI OSB MAH 2033. Cad. No:23 SİNCAN/ANKARA",
    "Alci OSB Mah 2033 Cad No 23 Sincan Ankara Turkiye",
    "Alcı OSB Mahallesi 2033 Caddesi No 23 Sincan Ankara Turkey",
    "ASO 2. Organize Sanayi Bolgesi Sincan Ankara"
]

g = Nominatim(user_agent="atik_ai_geocoder_test")
for q in queries:
    r = g.geocode(q)
    print("Q:", q)
    print("R:", (r.latitude, r.longitude, r.address) if r else None)
    print()
