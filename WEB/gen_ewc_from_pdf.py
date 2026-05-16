import argparse
import json
import re
from pathlib import Path

import fitz
import numpy as np
from easyocr import Reader


EWC_CHAPTERS = {f"{i:02d}" for i in range(1, 21)} | {"99"}

# OCR bazen "01 01 01" (arada boşluk) bazen de "010101" (bitişik) döndürebiliyor.
CODE_RE_SPACED = re.compile(r"(\d{2})\s*(\d{2})\s*(\d{2})(\s*\*)?")
CODE_RE_CONTIG = re.compile(r"(\d{6})(\s*\*)?")


def clean_text(s: str) -> str:
    if s is None:
        return ""
    # Normalize whitespace; keep Turkish characters as-is.
    s = str(s).replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_codes_and_desc(ocr_lines):
    """
    ocr_lines: list of strings (readable chunks in top-to-bottom order).
    Returns dict: code -> {code, description, star, chapter}
    """
    found = {}
    # OCR bazen "01 01 01" kodunun parçalarını farklı satırlara bölebiliyor.
    # Bu yüzden sayfa bazında birleştirip regex'i tüm metin üzerinde çalıştırıyoruz.
    page_text = clean_text(" ".join(ocr_lines))
    if not page_text:
        return found

    # Yardimci: match sonrasindan kisa bir segment al.
    # Not: Açıklama her zaman "koddan hemen sonra" gelmeyebilir; yine de kodu yakalamak ilk hedef.
    def desc_after(m_end: int) -> str:
        snippet = page_text[m_end : m_end + 220].strip()
        return snippet

    # 1) Spaced format: "01 01 01" or "01 03 04*"
    for m in CODE_RE_SPACED.finditer(page_text):
        ch, sec, code2, star_raw = m.groups()
        if ch not in EWC_CHAPTERS:
            continue
        code6 = f"{ch}{sec}{code2}"
        star = bool(star_raw and "*" in star_raw)
        desc = desc_after(m.end())

        key = (code6, star)
        prev = found.get(key)
        if not prev or len(desc) > len(prev.get("description", "")):
            found[key] = {
                "code": code6 + ("*" if star else ""),
                "code6": code6,
                "star": star,
                "chapter": ch,
                "description": desc,
            }

    # 2) Contiguous format: "010104" or "010104*"
    for m in CODE_RE_CONTIG.finditer(page_text):
        code6_raw, star_raw = m.groups()
        if not code6_raw or len(code6_raw) != 6:
            continue
        ch = code6_raw[:2]
        if ch not in EWC_CHAPTERS:
            continue
        code6 = code6_raw
        star = bool(star_raw and "*" in star_raw)
        desc = desc_after(m.end())

        key = (code6, star)
        prev = found.get(key)
        if not prev or len(desc) > len(prev.get("description", "")):
            found[key] = {
                "code": code6 + ("*" if star else ""),
                "code6": code6,
                "star": star,
                "chapter": ch,
                "description": desc,
            }

    return found


def ocr_page(reader: Reader, page, scale: float):
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)

    # Depending on easyocr version, readtext(detail=1) may return either:
    #  - (bbox, text, conf)
    #  - (bbox, text)
    res = reader.readtext(img, detail=1, paragraph=True)
    # Sort by top y coordinate to reduce out-of-order text.
    lines = []
    for item in res:
        # item: (bbox, text, conf?) or (bbox, text)
        if not isinstance(item, (list, tuple)):
            continue
        if len(item) == 3:
            bbox, text, _conf = item
        elif len(item) == 2:
            bbox, text = item
        else:
            continue
        try:
            y0 = bbox[0][1]
        except Exception:
            y0 = 0
        lines.append((y0, str(text)))
    lines.sort(key=lambda x: x[0])
    return [t for _y, t in lines]


def main():
    repo_root = Path(__file__).resolve().parent.parent
    default_pdf = repo_root / "DATA" / "ewc_kodlari.pdf"
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--pdf",
        default=str(default_pdf),
        help="PDF path (varsayılan: DATA/ewc_kodlari.pdf)",
    )
    ap.add_argument("--out", default="assets/ewc_codes_from_pdf.json", help="Output JSON path")
    ap.add_argument("--start-page", type=int, default=0, help="Starting page index (0-based)")
    ap.add_argument("--max-pages", type=int, default=0, help="0 = all pages")
    ap.add_argument("--scale", type=float, default=1.8, help="Render scale for OCR")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    page_count = doc.page_count
    start_page = max(0, args.start_page)
    if args.max_pages <= 0:
        max_pages = page_count - start_page
    else:
        max_pages = min(page_count - start_page, args.max_pages)

    # Turkish OCR improves recognition of Turkish headers; using tr only keeps downloads minimal.
    reader = Reader(["tr", "en"], gpu=False, verbose=False)

    found = {}
    for i in range(max_pages):
        page_index = start_page + i
        print(f"OCR page {page_index+1}/{page_count}...")
        page = doc.load_page(page_index)
        ocr_lines = ocr_page(reader, page, scale=args.scale)
        page_found = extract_codes_and_desc(ocr_lines)
        # merge
        for key, val in page_found.items():
            if key not in found:
                found[key] = val
            else:
                # Prefer longer description
                if len(val.get("description", "")) > len(found[key].get("description", "")):
                    found[key] = val

    out = sorted(found.values(), key=lambda x: (x["code6"], x["star"]))
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done. Total codes: {len(out)}")


if __name__ == "__main__":
    main()

