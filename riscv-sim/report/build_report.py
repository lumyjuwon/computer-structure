#!/usr/bin/env python3
"""report.md -> report.html -> report.pdf 변환 (보고서 작성용 보조 도구, 시뮬레이터와 무관).

필요한 것: pip install markdown, 그리고 Microsoft Edge 또는 Google Chrome/Chromium (PDF 인쇄용)

  python report/build_report.py                 # report.pdf 생성
  python report/build_report.py --html-only     # report.html 만 생성 (브라우저에서 열어 인쇄해도 됨)
  python report/build_report.py --browser "C:/경로/chrome.exe"

삽입 규칙
  <!-- MUTATION_TABLE --> : report/mutation_results.md 내용
                           (python tests/mutation_test.py --markdown report/mutation_results.md 로 갱신)
  <!-- TEAM_PHOTO -->     : report/team_photo.jpg (또는 .jpeg/.png) 가 있으면 사진, 없으면 안내 상자
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

try:
    import markdown
except ImportError:
    sys.exit("python-markdown is required: pip install markdown")

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm;
        @bottom-center { content: counter(page) " / " counter(pages); font-size: 9pt; color: #666; } }
body { font-family: "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
       font-size: 10pt; line-height: 1.55; color: #111; }
h1 { font-size: 19pt; border-bottom: 2px solid #2b4a6f; padding-bottom: 4px; color: #1d3557; }
h2 { font-size: 14pt; color: #1d3557; border-bottom: 1px solid #c8d3e0; padding-bottom: 2px;
     margin-top: 22px; break-after: avoid; }
h3 { font-size: 11.5pt; color: #2b4a6f; margin-top: 14px; break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 8.8pt;
        break-inside: auto; }
tr { break-inside: avoid; }
th, td { border: 1px solid #9aa8b8; padding: 3px 6px; vertical-align: top; }
th { background: #e8eef6; }
code { font-family: Consolas, "D2Coding", monospace; font-size: 8.8pt; background: #f3f5f8;
       padding: 0 2px; border-radius: 2px; }
pre { background: #f6f8fa; border: 1px solid #d5dbe3; padding: 7px 9px; font-size: 8.6pt;
      line-height: 1.4; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; }
blockquote { border-left: 4px solid #e0a800; background: #fff8e1; margin: 8px 0; padding: 4px 10px; }
svg { display: block; margin: 8px auto; break-inside: avoid; }
.photo { width: 100%; max-height: 120mm; object-fit: contain; border: 1px solid #ccc; }
.placeholder { border: 2px dashed #b55; color: #b55; padding: 40px; text-align: center; }
"""

BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_browser(explicit):
    if explicit:
        return explicit
    for path in BROWSER_CANDIDATES:
        if os.path.exists(path):
            return path
    for name in ("msedge", "google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def normalize_lists(text):
    """Python-Markdown 은 목록 앞에 빈 줄이 있어야 하고 중첩 목록은 4칸 들여쓰기를 요구한다.
    GitHub 식으로 쓴 report.md 를 그대로 변환할 수 있게 맞춰 준다(코드 블록은 건드리지 않음)."""
    out, in_code, prev = [], False, ""
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_code = not in_code
        elif not in_code:
            m = re.match(r"^( *)([-*]|\d+\.) ", line)
            if m:
                if len(m.group(1)) in (2, 3):
                    line = "    " + line.lstrip()
                prev_in_list = re.match(r"^ *([-*]|\d+\.) ", prev) or prev.startswith("  ")
                if prev.strip() and not prev_in_list:
                    out.append("")
        out.append(line)
        prev = line
    return "\n".join(out)


def build_html():
    with open(os.path.join(HERE, "report.md"), encoding="utf-8") as f:
        text = normalize_lists(f.read())

    mutation_path = os.path.join(HERE, "mutation_results.md")
    if os.path.exists(mutation_path):
        with open(mutation_path, encoding="utf-8") as f:
            text = text.replace("<!-- MUTATION_TABLE -->", f.read())
    else:
        text = text.replace("<!-- MUTATION_TABLE -->",
                            "(python tests/mutation_test.py --markdown report/mutation_results.md 실행 필요)")

    photo = next((p for p in ("team_photo.jpg", "team_photo.jpeg", "team_photo.png")
                  if os.path.exists(os.path.join(HERE, p))), None)
    if photo:
        text = text.replace("<!-- TEAM_PHOTO -->",
                            '<img class="photo" src="%s" alt="팀 사진">' % photo)
    else:
        text = text.replace("<!-- TEAM_PHOTO -->",
                            '<div class="placeholder">【프로젝트 실행 중 팀원 전원이 함께 찍은 사진을 '
                            'report/team_photo.jpg 로 저장한 뒤 다시 빌드】</div>')

    md = markdown.Markdown(extensions=["tables", "fenced_code"])
    md.block_level_elements.append("svg")
    body = md.convert(text)
    html = ('<!DOCTYPE html>\n<html lang="ko"><head><meta charset="utf-8">'
            "<title>RISC-V 시뮬레이터 보고서</title><style>%s</style></head><body>%s</body></html>"
            % (CSS, body))
    html_path = os.path.join(HERE, "report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html-only", action="store_true")
    parser.add_argument("--browser")
    args = parser.parse_args()

    html_path = build_html()
    print("wrote", html_path)
    if args.html_only:
        return

    browser = find_browser(args.browser)
    if not browser:
        sys.exit("Edge/Chrome not found. open report.html in a browser and print to PDF, "
                 "or pass --browser PATH")
    pdf_path = os.path.join(HERE, "report.pdf")
    url = "file:///" + html_path.replace("\\", "/").lstrip("/")
    subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    "--print-to-pdf-no-header", "--print-to-pdf=" + pdf_path, url],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    print("wrote", pdf_path)


if __name__ == "__main__":
    main()
