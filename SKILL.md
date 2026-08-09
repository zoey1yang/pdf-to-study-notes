---
name: pdf-to-study-notes
description: Convert courseware PDFs (digital or scanned, Chinese or English) into clean, hierarchical Markdown study notes. Use when users ask to convert PDF/PPT lecture slides, scanned documents, or course materials into structured notes; when OCR output is flat and needs heading levels, watermark cleanup, or logical reorganization; or when existing flat Markdown from PDFs needs semantic cleanup into readable notes. Handles scanned Chinese PDFs via OCR, detects headings from real font sizes / text heights, filters watermarks, and provides a semantic cleanup workflow (OCR error fixing, hierarchy normalization, gap-filling marked with 【补充】, logical connectors).
---

# PDF to Study Notes

## Overview

This skill turns courseware PDFs into study-ready Markdown notes with real heading
hierarchy. Pipeline: mechanical conversion (font-size / OCR-height heading detection)
to mechanical pre-clean (watermarks, junk) to LLM semantic cleanup (OCR fixes,
hierarchy normalization, gap-filling, logical connectors).

## Dependencies

- Python 3.10+
- Core (digital/text-layer PDFs only): `pip install pymupdf` (~54 MB)
- With OCR (scanned PDFs): `pip install pymupdf rapidocr_onnxruntime pillow` (~148 MB)
- The OCR stack is loaded lazily: runs that never hit a scanned page skip it entirely.
- CPU-only is fine; scanned pages are slow (~5-20 s/page depending on DPI and machine).

## Workflow

1. **Convert** — for each PDF:

   ```bash
   python scripts/convert.py <input.pdf|dir>... -o <outdir>
   ```

   The script auto-detects: text-layer pages get real font-size headings; weak-text
   pages and pages whose text layer is mostly repeated watermark lines are OCR'd with
   height-based heading inference. OCR initializes only on the first scanned page.
   Output keeps `<!-- 第 N 页 -->` markers.

2. **Pre-clean mechanically** (saves LLM tokens):

   ```bash
   python scripts/mech_clean.py <raw.md> <mech.md>
   ```

   Removes watermark/logo lines, collapses blank runs, demotes fragment headings.

3. **Semantic cleanup (LLM)** — follow [references/cleanup-guide.md](references/cleanup-guide.md):
   - Process one file at a time; back up the raw conversion first (e.g. `原始转换版/`).
   - Keep page markers; normalize hierarchy (`##` chapter / `###` section / `####` point).
   - Fix only confident OCR errors; mark all additions with `【补充：…】`.
   - Merge fragmented lines with logical connectors; put grouped facts into tables.
   - Keep output tighter than input; no padding.

4. **Verify** each file:
   - No watermark fragments left (`客服微信`, `Exoplanet`, `TONGJI`, etc.);
   - Heading list has no fragment junk (`grep '^#'`);
   - Every page marker has content or is intentionally empty.

## Guidance

- For large batches, convert and pre-clean all files first, then run the semantic pass
  file by file. Never load more than one source file into context at a time.
- Scanned-deck hierarchy is inferred (OCR box heights); flag it in the file header and
  recommend cross-checking key pages against the PDF.
- If a page is unreadable after OCR (dense classical Chinese, tables), keep the best
  partial text and mark `（原课件此处 OCR 质量差）` instead of inventing content.

## Example output

See [assets/example.md](assets/example.md) for the exact formatting conventions
(headers, tables, page markers, 【补充】 markers, 真题 markers).
