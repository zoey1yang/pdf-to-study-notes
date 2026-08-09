# -*- coding: utf-8 -*-
"""Mechanical pre-clean of converted Markdown before the LLM semantic pass.

Removes watermark / customer-service / obvious OCR-noise lines, collapses
blank runs, keeps `<!-- 第 N 页 -->` markers, and demotes fragment-like
headings (pure-ASCII single words, all-caps, or <=2 CJK chars) to body text
so the LLM pass can decide whether they are real headings.

Usage:
    python mech_clean.py <input.md> <output.md>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


WATERMARK_SUBSTR = (
    "客服微信",
    "waixingren",
    "ixingren",
    "Exoplanet",
    "exoplanet",
    "aupidox",
    "aupdox",
    "TONGJI",
    "COLLEGEOF",
    "INNOVATI",
    "TONGJ I",
)
JUNK_WORDS = {
    "外星人设计",
    "设计Stduio",
    "Stduio",
    "Studio（客服",
}
BULLET_ONLY = re.compile(r"^\s*(?:[-•·*▪◦●○◆◇►▶□■]|\d+[.、)）])\s*$")
HEADING = re.compile(r"^(#{1,4})\s+(.*)$")


def is_noise_line(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if BULLET_ONLY.match(t):
        return True
    low = t.lower()
    if any(s.lower() in low for s in WATERMARK_SUBSTR):
        return True
    if any(w in t for w in JUNK_WORDS):
        return True
    if len(t) <= 3 and not re.search(r"[\u4e00-\u9fff]", t):
        return True
    return False


def demote_junk_heading(text: str) -> str | None:
    """Demote fragment/decorative headings to body text; None keeps the line."""
    m = HEADING.match(text)
    if not m:
        return None
    t = m.group(2).strip()
    cjk = sum(1 for ch in t if "\u4e00" <= ch <= "\u9fff")
    if cjk == 0 and t.isascii():
        if " " not in t or t.isupper() or len(t) <= 4:
            return t
    if cjk <= 2 and len(t) <= 4:
        return t
    return None


def clean(text: str) -> str:
    out: list[str] = []
    blank = 0
    prev = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if is_noise_line(line):
            continue
        demoted = demote_junk_heading(line)
        if demoted is not None:
            line = demoted
        if not line.strip():
            blank += 1
            if blank <= 1:
                out.append("")
            continue
        blank = 0
        if line == prev:
            continue
        out.append(line)
        prev = line
    return "\n".join(out).strip() + "\n"


def main() -> None:
    if len(sys.argv) != 3:
        print("用法: python mech_clean.py <输入> <输出>")
        sys.exit(1)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(clean(src.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"{src.name}: {src.stat().st_size} -> {dst.stat().st_size} bytes")


if __name__ == "__main__":
    main()
