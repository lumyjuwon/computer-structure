#!/usr/bin/env python3
"""시험 준비용 PDF 생성 (제출물 아님).

  1) source_listing_core.pdf : 시뮬레이터 본체(sim.py, rvsim/*) 줄 번호 인쇄본
  2) source_listing_all.pdf  : 제출 소스 전체(본체 + tests + tools + report 스크립트) 줄 번호 인쇄본
  3) 시험대비_정리.pdf       : 이 폴더의 시험대비_정리.md (공부용, 시험장 반입 불가)

인쇄본(1, 2)은 소스 내용 + 줄 번호 + 파일 이름만 담는다. 명세 9절에 따라 해설·메모를 넣지 않는다.
반드시 '제출 마감 시 고정된 최종 소스'로 다시 실행한 뒤 인쇄한다.

필요한 것: pip install markdown, Edge 또는 Chrome
사용법:    python study/build_pdfs.py
"""

import html
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(os.path.dirname(HERE), "riscv-sim")
sys.path.insert(0, os.path.join(ROOT, "report"))

import build_report  # noqa: E402  (CSS, normalize_lists, find_browser 재사용)

CORE = ["sim.py", "rvsim/__init__.py", "rvsim/bits.py", "rvsim/memory.py",
        "rvsim/decoder.py", "rvsim/cpu.py"]
REST = ["tests/asm.py", "tests/cases.py", "tests/gen_tests.py", "tests/run_tests.py",
        "tests/test_units.py", "tests/mutation_test.py", "tests/diff_ref_unicorn.py",
        "tools/trace.py", "report/build_report.py"]

LISTING_CSS = """
@page { size: A4; margin: 12mm 10mm 14mm 10mm;
        @bottom-center { content: counter(page) " / " counter(pages); font-size: 8pt; color: #555; } }
body { font-family: Consolas, "D2Coding", "Malgun Gothic", monospace; font-size: 7.6pt; color: #000; }
h2 { font-family: "Malgun Gothic", sans-serif; font-size: 11pt; margin: 0 0 4px;
     border-bottom: 1.5px solid #000; }
section { break-before: page; }
section:first-of-type { break-before: auto; }
pre { margin: 0; white-space: pre-wrap; line-height: 1.32; }
.n { color: #666; user-select: none; }
"""


def listing_html(files, title):
    parts = []
    for rel in files:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            lines = f.read().split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        body = "\n".join('<span class="n">%4d</span>  %s' % (i, html.escape(line))
                         for i, line in enumerate(lines, 1))
        parts.append("<section><h2>%s  (%d줄)</h2><pre>%s</pre></section>"
                     % (html.escape(rel), len(lines), body))
    return ('<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>%s</title>'
            "<style>%s</style></head><body>%s</body></html>" % (title, LISTING_CSS, "".join(parts)))


def guide_html():
    import markdown
    with open(os.path.join(HERE, "시험대비_정리.md"), encoding="utf-8") as f:
        text = build_report.normalize_lists(f.read())
    md = markdown.Markdown(extensions=["tables", "fenced_code"])
    return ('<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>시험 대비 정리</title>'
            "<style>%s</style></head><body>%s</body></html>" % (build_report.CSS, md.convert(text)))


def to_pdf(browser, html_text, name):
    html_path = os.path.join(HERE, name + ".html")
    pdf_path = os.path.join(HERE, name + ".pdf")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    url = "file:///" + html_path.replace("\\", "/").lstrip("/")
    subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    "--print-to-pdf-no-header", "--print-to-pdf=" + pdf_path, url],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    os.remove(html_path)
    print("wrote", pdf_path)


def main():
    browser = build_report.find_browser(None)
    if not browser:
        sys.exit("Edge/Chrome not found")
    to_pdf(browser, listing_html(CORE, "시뮬레이터 본체 소스"), "source_listing_core")
    to_pdf(browser, listing_html(CORE + REST, "제출 소스 전체"), "source_listing_all")
    to_pdf(browser, guide_html(), "시험대비_정리")


if __name__ == "__main__":
    main()
