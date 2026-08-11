# -*- coding: utf-8 -*-
"""Question-continuity audit for converted Markdown notes.

Detects and lists "suspicious" spots that a plain read can miss:
- missing question numbers (non-contiguous sequence, e.g. 8.5 -> 8.17);
- merged questions (two or more question anchors on the same line/paragraph);
- short non-CJK fragments that look like dropped content (informational).

It never fixes anything: it prints/写出一份「可疑清单」for the user to
cross-check against the source PDF. Same philosophy as the 【补充】 marker:
never silently repair, surface uncertainty instead.

Usage:
    python scripts/audit_questions.py <note.md>... [-o report.md]

Output: one section per input file; each finding is labelled "疑似" (suspected).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# 题号样式（覆盖数字+点/顿号/括号、8.5 这类段号）
DECIMAL_ID_RE = re.compile(r"(?<![\d.])-?(\d{1,3})\.(\d{1,3})(?![\d.])")
PLAIN_ID_RE = re.compile(r"^\s*(\d{1,3})[.、)）]")
# 行内独立题号：数字+点（后不跟数字，避免把 8.4 里的 "8." 当独立题号）或数字+顿号/右括号
PLAIN_DOT_RE = re.compile(r"(?<!\d)(\d{1,3})\.(?!\d)")
PLAIN_OTHER_RE = re.compile(r"(?<!\d)(\d{1,3})[、)）]")

# 选项字母（OCR 短字符低置信时不得静默丢弃）
OPTION_MARKER_RE = re.compile(r"^[A-Ha-h][.、)）:：]?$")

# 同段并题的判据：两个题号靠得足够近（字符数间隔）
MERGE_PROXIMITY_CHARS = 80
MAX_GAP_TO_FLAG = 25


def _collect_decimal_ids(lines: list[str]) -> list[tuple[int, int, int]]:
    """返回 [(行号, 整数部分, 小数部分)]，只收“题号式”段号（整数部分 ≤ 99）。"""
    found: list[tuple[int, int, int]] = []
    for idx, line in enumerate(lines, start=1):
        for match in DECIMAL_ID_RE.finditer(line):
            whole, frac = int(match.group(1)), int(match.group(2))
            if whole > 99 or frac > 99:
                continue
            found.append((idx, whole, frac))
    return found


def _collect_plain_ids(lines: list[str]) -> list[tuple[int, int]]:
    """返回 [(行号, 数字)]，只收行首题号（避免把正文里的数字当题号）。"""
    found: list[tuple[int, int]] = []
    for idx, line in enumerate(lines, start=1):
        if re.match(r"^\s*\d{1,3}\.\d", line):
            continue  # 8.4 这类段号交给小数题号检查，不当作独立编号
        match = PLAIN_ID_RE.match(line)
        if match:
            found.append((idx, int(match.group(1))))
    return found


def audit_decimal_gaps(lines: list[str]) -> list[str]:
    """同一整数部分内的小数题号不连续 -> 疑似漏题。"""
    items = _collect_decimal_ids(lines)
    findings: list[str] = []
    by_whole: dict[int, list[tuple[int, int]]] = {}
    for line_no, whole, frac in items:
        by_whole.setdefault(whole, []).append((line_no, frac))
    for whole, pairs in by_whole.items():
        pairs.sort(key=lambda item: item[1])
        # 去掉重复的小数部分
        unique: list[tuple[int, int]] = []
        for pair in pairs:
            if not unique or unique[-1][1] != pair[1]:
                unique.append(pair)
        for prev, curr in zip(unique, unique[1:]):
            gap = curr[1] - prev[1]
            if 1 < gap <= MAX_GAP_TO_FLAG:
                missing = f"{whole}.{prev[1] + 1}–{whole}.{curr[1] - 1}" if gap > 2 else f"{whole}.{prev[1] + 1}"
                findings.append(
                    f"第 {prev[0]} 行的 {whole}.{prev[1]} → 第 {curr[0]} 行的 {whole}.{curr[1]}：疑似缺 {missing}"
                )
    return findings


def audit_plain_gaps(lines: list[str]) -> list[str]:
    """行首连续编号跳号（9、11、…）-> 疑似漏题。"""
    items = _collect_plain_ids(lines)
    findings: list[str] = []
    # 编号列表会分节重新从 1 开始：只在“同一连续增长段”内判跳号。
    run: list[tuple[int, int]] = []
    for line_no, number in items:
        if run and number > run[-1][1]:
            gap = number - run[-1][1]
            if 1 < gap <= MAX_GAP_TO_FLAG:
                missing = f"{run[-1][1] + 1}–{number - 1}" if gap > 2 else f"{run[-1][1] + 1}"
                findings.append(
                    f"第 {run[-1][0]} 行的 {run[-1][1]} → 第 {line_no} 行的 {number}：疑似缺 {missing}"
                )
            run.append((line_no, number))
        elif run and number <= run[-1][1]:
            run = [(line_no, number)]  # 新一轮编号
        else:
            run.append((line_no, number))
    return findings


def audit_merged(lines: list[str]) -> list[str]:
    """同一行/段出现两个及以上靠得很近的题号 -> 疑似并题。"""
    findings: list[str] = []
    for idx, line in enumerate(lines, start=1):
        text = line.strip()
        if len(text) < 8:
            continue
        decimal_hits = [
            (int(m.group(1)), int(m.group(2)))
            for m in DECIMAL_ID_RE.finditer(text)
            if int(m.group(1)) <= 99 and int(m.group(2)) <= 99
        ]
        plain_hits = (
            [int(m.group(1)) for m in PLAIN_DOT_RE.finditer(text)]
            + [int(m.group(1)) for m in PLAIN_OTHER_RE.finditer(text)]
        )
        anchors: list[str] = [f"{a}.{b}" for a, b in decimal_hits] + [str(n) for n in plain_hits]
        if len(anchors) < 2:
            continue
        # 只报“靠得近”的双题号，避免把整行引用题号误报
        positions: list[int] = []
        for match in (
            list(DECIMAL_ID_RE.finditer(text))
            + list(PLAIN_DOT_RE.finditer(text))
            + list(PLAIN_OTHER_RE.finditer(text))
        ):
            positions.append(match.start())
        if max(positions) - min(positions) <= MERGE_PROXIMITY_CHARS:
            findings.append(f"第 {idx} 行疑似并题，同一段含多个题号：{'、'.join(sorted(set(anchors)))}")
    return findings


def audit_dropped_fragments(lines: list[str]) -> list[str]:
    """列出长度 ≤3 的非中文短字符（选项字母保留，其余列为人工核对候选）。"""
    findings: list[str] = []
    for idx, line in enumerate(lines, start=1):
        t = line.strip()
        if not t or len(t) > 3 or any("\u4e00" <= ch <= "\u9fff" for ch in t):
            continue
        if OPTION_MARKER_RE.match(t):
            continue  # 选项字母，保留
        findings.append(f"第 {idx} 行有孤立短字符「{t}」，请对照原 PDF 确认是否有内容被丢。")
    return findings[:30]  # 只列前 30 条，避免刷屏


def audit_file(path: Path) -> dict[str, list[str]]:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    return {
        "漏题（题号不连续）": audit_decimal_gaps(lines) + audit_plain_gaps(lines),
        "并题（同一段含多个题号）": audit_merged(lines),
        "短字符核对候选": audit_dropped_fragments(lines),
    }


def render_report(path: Path, findings: dict[str, list[str]]) -> str:
    lines = [f"## {path.name}", ""]
    has_any = False
    for category, items in findings.items():
        lines.append(f"### {category}")
        if items:
            has_any = True
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- （未发现）")
        lines.append("")
    if not has_any:
        lines.append("> 机器自检未发现明显异常；仍建议关键题号抽查对照原 PDF。")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="题号连续性自检：漏题 / 并题 / 短字符核对候选")
    parser.add_argument("inputs", nargs="+", help="转换后的 Markdown 笔记")
    parser.add_argument("-o", "--out", default="", help="输出报告路径（不填则打印到标准输出）")
    args = parser.parse_args()

    sections: list[str] = ["# 可疑清单（机器自检，未经人工核对）", "",
                           "> 以下均为“疑似”，请对照原 PDF 确认后再处理；本清单不做任何修改。", ""]
    for raw in args.inputs:
        path = Path(raw)
        if not path.exists():
            print(f"跳过不存在的文件：{raw}", file=sys.stderr)
            continue
        sections.append(render_report(path, audit_file(path)))

    report = "\n".join(sections).rstrip() + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"可疑清单已写入：{out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
