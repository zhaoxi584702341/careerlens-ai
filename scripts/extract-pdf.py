#!/usr/bin/env python3
"""从脱敏 PDF 简历中抽取文本，生成 samples/ 下的演示样本。

依赖：pypdf（见 python-service/requirements.txt）。
用法：
    python scripts/extract-pdf.py --src "../脱敏资料" --out "samples"
    python scripts/extract-pdf.py --list          # 仅列出各 PDF 页数与字符数

说明：脱敏 PDF 已确认含完整文本层（images_remaining=0），无需 OCR。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    sys.exit("缺少依赖 pypdf，请先执行：pip install pypdf")


def extract_text(pdf_path: Path) -> str:
    """抽取单个 PDF 的全部文本，按页拼接。"""
    reader = PdfReader(str(pdf_path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in pages if p)


def main() -> None:
    parser = argparse.ArgumentParser(description="脱敏 PDF 简历文本抽取")
    parser.add_argument("--src", default="../脱敏资料", help="PDF 所在目录")
    parser.add_argument("--out", default="samples", help="文本输出目录")
    parser.add_argument("--list", action="store_true", help="仅列出 PDF 页数与字符数")
    args = parser.parse_args()

    src_dir = Path(args.src).resolve()
    if not src_dir.is_dir():
        sys.exit(f"源目录不存在：{src_dir}")

    pdfs = sorted(src_dir.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"源目录下未找到 PDF：{src_dir}")

    if args.list:
        print(f"{'文件':<20}{'页数':>6}{'字符数':>10}")
        for pdf in pdfs:
            reader = PdfReader(str(pdf))
            text = extract_text(pdf)
            print(f"{pdf.name:<20}{len(reader.pages):>6}{len(text):>10}")
        return

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 按需求抽取 3 份代表性简历：短（1-2页）/ 中（3-4页）/ 长（5-6页）
    targets = {
        "resume_short.txt": ("resume_20.pdf", 1),
        "resume_mid.txt": ("resume_05.pdf", 2),
        "resume_long.txt": ("resume_18.pdf", 6),
    }

    for out_name, (pdf_name, _pages) in targets.items():
        pdf_path = src_dir / pdf_name
        if not pdf_path.exists():
            print(f"[跳过] 未找到 {pdf_name}")
            continue
        text = extract_text(pdf_path)
        (out_dir / out_name).write_text(text, encoding="utf-8")
        print(f"[生成] {out_name}  <- {pdf_name}  ({len(text)} 字符)")


if __name__ == "__main__":
    main()
