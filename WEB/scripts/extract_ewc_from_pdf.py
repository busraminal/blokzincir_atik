"""ewc_kodlari.pdf içinden EasyOCR ile 6 haneli EWC kodlarını çıkarır → ewc_kodlari_extracted.json"""
import argparse
import io
import json
import re
import sys
from pathlib import Path
from typing import Dict

import fitz
import numpy as np
from PIL import Image

import easyocr


def extract_from_pdf(pdf_path: Path, dpi: int = 130) -> Dict[str, str]:
    reader = easyocr.Reader(["tr", "en"], gpu=False, verbose=False)
    doc = fitz.open(pdf_path)
    codes: dict[str, str] = {}
    n = len(doc)
    for pi in range(n):
        page = doc[pi]
        pix = page.get_pixmap(dpi=dpi)
        img = np.array(Image.open(io.BytesIO(pix.tobytes("png"))))
        res = reader.readtext(img)
        for _bbox, text, _conf in res:
            t = text or ""
            # 15 01 06 veya 150106
            for m in re.finditer(r"(\d{2})\s*(\d{2})\s*(\d{2})", t):
                c = m.group(1) + m.group(2) + m.group(3)
                if c not in codes:
                    codes[c] = t.strip()[:200]
            for m in re.finditer(r"\b(\d{6})\b", t):
                c = m.group(1)
                if c not in codes:
                    codes[c] = t.strip()[:200]
        print(f"Sayfa {pi + 1}/{n} — toplam kod: {len(codes)}", file=sys.stderr, flush=True)
    doc.close()
    return codes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("ewc_kodlari_extracted.json"))
    ap.add_argument("--dpi", type=int, default=130)
    args = ap.parse_args()
    if not args.pdf.is_file():
        print("PDF bulunamadı:", args.pdf, file=sys.stderr)
        sys.exit(1)
    codes = extract_from_pdf(args.pdf, dpi=args.dpi)
    lst = [{"code": k, "label": v} for k, v in sorted(codes.items(), key=lambda x: x[0])]
    args.out.write_text(json.dumps(lst, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(lst), "out": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
