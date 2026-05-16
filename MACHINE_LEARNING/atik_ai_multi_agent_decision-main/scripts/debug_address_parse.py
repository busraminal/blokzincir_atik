import re
import requests
from bs4 import BeautifulSoup

url = "https://aso2osb.org.tr/firmalar"
headers = {"User-Agent": "Mozilla/5.0"}

response = requests.get(url, headers=headers, timeout=30)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")
rows = soup.find("table").find_all("tr")[1:6]

for i, row in enumerate(rows, 1):
    cols = row.find_all("td")
    if not cols:
        continue

    raw = cols[0].get_text(" ", strip=True)
    m = re.search(r"(.+?)(?=ALCI OSB MAH|ALCI OSB|SINCAN/ANKARA|SINCAN ANKARA|$)", raw, re.IGNORECASE | re.DOTALL)
    if m:
        firma = m.group(1).strip()
        adres = raw[len(firma):].strip()
    else:
        firma = raw
        adres = ""

    print(f"[{i}] RAW: {raw}")
    print(f"    FIRMA: {firma}")
    print(f"    ADRES: {adres}")
