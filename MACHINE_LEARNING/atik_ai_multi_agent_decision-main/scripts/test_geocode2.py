from geopy.geocoders import Nominatim

g = Nominatim(user_agent="atik_ai_geocoder_test")
queries = [
    "2033 cadde no 23 sincan ankara",
    "2033. Cadde, Sincan, Ankara",
    "Ahi Evran OSB Mahallesi 2033 Cadde No 23 Sincan Ankara",
    "Ahi Evran OSB Mahallesi 2033 Cadde Sincan Ankara",
    "Ankara Sanayi Odasi 2 Organize Sanayi Bolgesi 2033 Cadde 23",
    "Ahi Evran Mh 2033 Cd No 23 Sincan",
]
for q in queries:
    r = g.geocode(q)
    print(q)
    print((r.latitude, r.longitude, r.address) if r else None)
    print('-'*60)
