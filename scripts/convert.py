# -*- coding: utf-8 -*-
"""Convert courseware PDFs into hierarchical Markdown.

Strategy:
- Pages with a usable text layer: extract text with real font sizes and map
  size ratios to heading levels (## / ### / ####).
- Pages without a text layer, or where watermark/repeated lines dominate the
  text layer (image-based slides), are OCR'd and headings are inferred from
  OCR text height.
- Watermark / logo fragments (frequent short lines, all-caps fragments) are
  filtered out.

Usage:
    python convert.py <pdf-or-dir>... -o <outdir> [--dpi 200] [--min-chars 40]
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image
from rapidocr_onnxruntime import RapidOCR


# font-size / OCR-height ratio to heading level
LEVELS = (
    (1.60, 2),  # page/slide title
    (1.35, 3),  # section title
    (1.22, 4),  # emphasized / sub-point
)
MAX_HEADING_CHARS = 45
LIST_MARK_RE = re.compile(r"^\s*(?:[-•·*▪◦●○◆◇►▶]|\d+[.、)）]|[①②③④⑤⑥⑦⑧⑨⑩])\s*")


def looks_like_junk(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if len(t) <= 3 and not any("\u4e00" <= ch <= "\u9fff" for ch in t):
        return True
    return False


def heading_level(text: str, ratio: float) -> int | None:
    t = text.strip()
    if not t or len(t) > MAX_HEADING_CHARS:
        return None
    if LIST_MARK_RE.match(t):
        return None
    for threshold, level in LEVELS:
        if ratio >= threshold:
            return level
    return None


def collect_noise(pages_data: list, page_count: int) -> set[str]:
    """Frequent short text (watermarks/logos) seen on many pages."""
    counter: Counter = Counter()
    for kind, data in pages_data:
        seen = set()
        if kind == "text":
            entries = ((t, 12) for _, _, t, _ in data)
        else:
            entries = ((t, 16) for _, _, _, t in data)
        for t, max_len in entries:
            t = t.strip()
            if not t or looks_like_junk(t) or len(t) > max_len:
                continue
            if t.isascii() and not any(ch.islower() for ch in t) and " " not in t:
                continue  # handled by the uppercase rule below
            seen.add(t)
        counter.update(seen)

    upper_counter: Counter = Counter()
    for kind, data in pages_data:
        seen = set()
        for item in data:
            t = (item[2] if kind == "text" else item[3]).strip()
            if (
                t
                and t.isascii()
                and not any(ch.islower() for ch in t)
                and len(t) <= 20
            ):
                seen.add(t)
        upper_counter.update(seen)

    threshold = max(3, int(page_count * 0.20))
    noise = {t for t, c in counter.items() if c >= threshold}
    noise |= {t for t, c in upper_counter.items() if c >= 2}
    return noise


def extract_text_lines(page) -> list[tuple[float, float, str, float]]:
    """Return (y0, x0, text, max_font_size) per text line."""
    out: list[tuple[float, float, str, float]] = []
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans") or []
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            size = max(s.get("size", 0) for s in spans)
            bbox = line.get("bbox") or (0, 0, 0, 0)
            out.append((bbox[1], bbox[0], text, size))
    return out


def render_text_page(lines: list[tuple[float, float, str, float]], body_size: float) -> str:
    parts: list[str] = []
    for y0, x0, text, size in sorted(lines):
        t = text.strip()
        if LIST_MARK_RE.match(t) and len(t) <= 2:
            continue
        ratio = size / body_size if body_size else 1.0
        lvl = heading_level(t, ratio)
        parts.append(f"{'#' * lvl} {t}" if lvl else t)
    return "\n\n".join(parts)


def ocr_page_items(page, ocr: RapidOCR, dpi: int) -> list[tuple[float, float, float, str]]:
    """OCR a page, returning (y0, x0, text_height, text)."""
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    result, _ = ocr(img)
    items: list[tuple[float, float, float, str]] = []
    for box, text, _conf in result or []:
        text = text.strip()
        if not text:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append((min(ys), min(xs), max(ys) - min(ys), text))
    return items


def render_ocr_page(items: list[tuple[float, float, float, str]], noise: set[str]) -> str:
    heights = [h for _, _, h, t in items if h > 0 and t.strip() not in noise and not looks_like_junk(t)]
    body_h = sorted(heights)[len(heights) // 2] if heights else 12.0
    parts: list[str] = []
    for y0, x0, h, text in sorted(items):
        t = text.strip()
        if LIST_MARK_RE.match(t) and len(t) <= 2:
            continue
        if looks_like_junk(t) or t in noise:
            continue
        ratio = h / body_h if body_h else 1.0
        lvl = heading_level(t, ratio)
        parts.append(f"{'#' * lvl} {t}" if lvl else t)
    return "\n\n".join(parts)


def convert_one(pdf: Path, ocr: RapidOCR, out_dir: Path, dpi: int, min_chars: int, wm_ratio: float) -> dict:
    doc = fitz.open(str(pdf))
    page_count = doc.page_count

    # Pass 1: classify pages from the text layer only (fast, no OCR yet).
    text_lines: list[list[tuple[float, float, str, float]]] = []
    freq_counter: Counter = Counter()
    for page in doc:
        text = page.get_text() or ""
        if len(text.strip()) >= min_chars:
            lines = extract_text_lines(page)
        else:
            lines = []
        text_lines.append(lines)
        seen = set()
        for _, _, t, _ in lines:
            t = t.strip()
            if 6 <= len(t) <= 60:
                seen.add(t)
        freq_counter.update(seen)
    # Lines appearing on >=25% of pages are watermarks/headers/footers.
    frequent = {t for t, c in freq_counter.items() if c >= max(4, int(page_count * 0.25))}

    # Pass 2: pages whose text layer is mostly frequent lines are image slides -> OCR.
    pages_data: list = []
    for idx, lines in enumerate(text_lines, start=1):
        if lines:
            total_chars = sum(len(t) for _, _, t, _ in lines)
            wm_chars = sum(len(t) for _, _, t, _ in lines if t.strip() in frequent)
            if total_chars and wm_chars / total_chars >= wm_ratio:
                lines = []
        if not lines:
            try:
                pages_data.append(("ocr", ocr_page_items(doc[idx - 1], ocr, dpi)))
            except Exception as exc:
                pages_data.append(("ocr_error", f"（第 {idx} 页 OCR 失败：{exc}）"))
        else:
            pages_data.append(("text", lines))

    noise = collect_noise(pages_data, page_count) | frequent

    # Body font size: most frequent font size (weighted by char count) in text pages.
    size_counter: Counter = Counter()
    for kind, lines in pages_data:
        if kind != "text":
            continue
        for _, _, text, size in lines:
            if text.strip() in noise or looks_like_junk(text):
                continue
            size_counter[round(size * 2) / 2] += len(text)
    body_size = size_counter.most_common(1)[0][0] if size_counter else 14.0

    parts: list[str] = []
    ocr_pages = 0
    for idx, (kind, data) in enumerate(pages_data, start=1):
        if kind == "ocr_error":
            parts.append(f"<!-- 第 {idx} 页 -->\n\n{data}")
            continue
        if kind == "ocr":
            body = render_ocr_page(data, noise)
            if body:
                ocr_pages += 1
        else:
            kept = [(y, x, t, s) for y, x, t, s in data if t.strip() not in noise]
            body = render_text_page(kept, body_size)
        if body:
            parts.append(f"<!-- 第 {idx} 页 -->\n\n{body}")
        if idx % 20 == 0:
            print(f"  {pdf.name}: {idx}/{page_count} 页", flush=True)
    doc.close()

    note = (
        "> 由 pdf-to-study-notes 转换器生成：文字页按真实字号识别标题层级，"
        f"扫描页按 OCR 字高推断层级。来源：{pdf.name}（扫描页数：{ocr_pages}）"
    )
    target = out_dir / (pdf.stem + ".md")
    target.write_text(f"# {pdf.stem}\n\n{note}\n\n" + "\n\n".join(parts) + "\n", encoding="utf-8")
    return {"source": pdf.name, "target": target.name, "ocr_pages": ocr_pages, "status": "ok"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert courseware PDFs to hierarchical Markdown.")
    ap.add_argument("inputs", nargs="+", help="PDF files or directories containing PDFs")
    ap.add_argument("-o", "--out", default="out", help="Output directory (default: out)")
    ap.add_argument("--dpi", type=int, default=200, help="OCR render DPI (default: 200)")
    ap.add_argument("--min-chars", type=int, default=40, help="Min text-layer chars to skip OCR (default: 40)")
    ap.add_argument("--watermark-ratio", type=float, default=0.5,
                    help="Reclassify page to OCR when frequent-line chars exceed this ratio (default: 0.5)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs: list[Path] = []
    for inp in args.inputs:
        p = Path(inp)
        if p.is_dir():
            pdfs.extend(sorted(p.glob("*.pdf")))
        elif p.suffix.lower() == ".pdf":
            pdfs.append(p)
    if not pdfs:
        print("没有找到 PDF 文件")
        sys.exit(1)

    ocr = RapidOCR()
    for pdf in pdfs:
        try:
            item = convert_one(pdf, ocr, out_dir, args.dpi, args.min_chars, args.watermark_ratio)
            print(f"完成 {pdf.name}: {item['status']}（OCR {item['ocr_pages']} 页）", flush=True)
        except Exception as exc:
            print(f"失败 {pdf.name}: {str(exc)[:300]}", flush=True)


if __name__ == "__main__":
    main()
