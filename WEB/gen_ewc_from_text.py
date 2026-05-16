import argparse
import json
import re
from pathlib import Path


# Matches lines like:
# "01 01 04* description..." or "01 04 09 Atık kum ve killer"
CODE_LINE_RE = re.compile(r"^\s*(\d{2})\s*(\d{2})\s*(\d{2})(\*)?\s*(.*?)\s*$")

EWC_CHAPTERS = {f"{i:02d}" for i in range(1, 21)} | {"99"}


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def parse_lines(lines):
    """
    Returns list of { code, code6, star, chapter, description }
    """
    found = {}
    current = None

    def flush():
        nonlocal current
        if not current:
            return
        key = (current["code6"], current["star"])
        prev = found.get(key)
        if not prev or len(current.get("description", "")) > len(prev.get("description", "")):
            found[key] = current
        current = None

    for raw in lines:
        line = normalize_spaces(raw)
        if not line:
            continue

        m = CODE_LINE_RE.match(line)
        if m:
            flush()
            ch, sec, code2, star_raw, tail = m.groups()
            if ch not in EWC_CHAPTERS:
                continue
            code6 = f"{ch}{sec}{code2}"
            star = bool(star_raw and "*" in star_raw)
            desc = normalize_spaces(tail)
            current = {
                "code": code6 + ("*" if star else ""),
                "code6": code6,
                "star": star,
                "chapter": ch,
                "description": desc,
            }
            continue

        # Skip standalone markers that appear in some PDF scans (e.g., "A" / "M")
        if line in {"A", "M", "A.", "M."}:
            continue

        if current:
            # Append continuation lines to the description.
            # Avoid polluting with other header blocks; keep it permissive.
            current["description"] = normalize_spaces(current.get("description", "") + " " + line)

    flush()
    # Convert to sorted list
    out = sorted(found.values(), key=lambda x: (x["code6"], x["star"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", default="ewc_raw.txt", help="Input text file path")
    ap.add_argument("--out", default="assets/ewc_codes_from_text.json", help="Output JSON file path")
    ap.add_argument("--max-lines", type=int, default=0, help="0 = all")
    args = ap.parse_args()

    in_path = Path(args.in)
    if not in_path.exists():
        raise SystemExit(f"Input file not found: {in_path}")

    lines = in_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if args.max_lines and args.max_lines > 0:
        lines = lines[: args.max_lines]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = parse_lines(lines)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done. Parsed codes: {len(data)}")


if __name__ == "__main__":
    main()

