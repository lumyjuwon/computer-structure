#!/usr/bin/env python3
"""tests/cases.py 의 정의로 tests/cases/<이름>/ 테스트 입출력 파일을 생성한다.

생성 파일 (케이스마다)
  program.s             주소·기계어·어셈블리 목록과 테스트 목적
  text.bin, data.bin    시뮬레이터 입력 (헤더 없는 바이너리)
  expected_stdout.txt   기대 표준 출력 (비정상 종료 케이스는 빈 파일)
  expected_data.out     기대 data.out 1,024 바이트 (정상 종료 케이스만)
  expected_exit_code.txt 기대 종료 코드
그리고 tests/cases/INDEX.md (전체 목록)

사용법:  python tests/gen_tests.py
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from asm import TEXT_BASE, assemble, listing, words_to_bytes  # noqa: E402
from cases import CASES, expected_data_out  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "cases")


def write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


def write_text_lf(path, text):
    """줄바꿈 변환 없이 LF 그대로 저장 (Windows 에서도 \\r\\n 이 되지 않도록 바이너리로 기록)."""
    write_bytes(path, text.encode("utf-8"))


def check_case(c, words):
    """생성 전 자기 점검: 손으로 계산한 값과 어셈블러 결과를 교차 확인."""
    text = words_to_bytes(words)
    if c["check_text"] is not None and text != c["check_text"]:
        raise SystemExit("%s: text.bin differs from spec bytes\n  got  %s\n  want %s"
                         % (c["name"], text.hex(), c["check_text"].hex()))
    if words[-1] != 0:
        raise SystemExit("%s: text.bin must end with 0x00000000 (spec 6)" % c["name"])
    if len(c["data"]) > 1024:
        raise SystemExit("%s: data.bin larger than 1024 bytes" % c["name"])
    if c["exit_code"] == 0:
        # 기대 출력의 명령어 값 == 그 주소에 어셈블된 값 (손 계산 vs 인코더)
        parts = c["stdout"].split()
        pc, word = int(parts[1], 16), int(parts[4], 16)
        index = (pc - TEXT_BASE) // 4
        if words[index] != word:
            raise SystemExit("%s: expected word 0x%08x but assembled 0x%08x at 0x%08x"
                             % (c["name"], word, words[index], pc))
        if not c["stdout"].endswith("\n") or "\r" in c["stdout"]:
            raise SystemExit("%s: stdout must end with a single LF" % c["name"])


def program_listing(c):
    lines = ["# %s" % c["name"], "# 목적: %s" % c["purpose"], "#",
             "# 주소        기계어      어셈블리"]
    for pc, word, raw in listing(c["source"]):
        lines.append("0x%08x  0x%08x  %s" % (pc, word, raw))
    return "\n".join(lines) + "\n"


def main():
    # cases.py 에 정의된 케이스 디렉터리만 다시 만든다.
    # 팀원이 손으로 추가한 tests/cases/<다른 이름>/ 은 지우지 않는다 (run_tests.py 는 그것도 실행한다).
    os.makedirs(OUT_DIR, exist_ok=True)
    defined = {c["name"] for c in CASES}
    for extra in sorted(os.listdir(OUT_DIR)):
        if os.path.isdir(os.path.join(OUT_DIR, extra)) and extra not in defined:
            print("keeping manually added case (not in cases.py): " + extra)

    index = ["# 자체 테스트 목록", "",
             "`python tests/gen_tests.py` 가 `tests/cases.py` 로부터 생성한 파일이다. "
             "기대 결과는 `tests/cases.py` 의 주석에 도출 근거가 있다.", "",
             "| 케이스 | 목적 | 기대 표준 출력 / 종료 코드 |",
             "|---|---|---|"]
    names = set()
    for c in CASES:
        if c["name"] in names:
            raise SystemExit("duplicate case name: " + c["name"])
        names.add(c["name"])

        words = assemble(c["source"])
        check_case(c, words)

        d = os.path.join(OUT_DIR, c["name"])
        if os.path.isdir(d):
            shutil.rmtree(d)        # 이전 생성물(예: 정상 -> 비정상으로 바뀐 케이스의 expected_data.out) 제거
        os.makedirs(d)
        write_bytes(os.path.join(d, "text.bin"), words_to_bytes(words))
        write_bytes(os.path.join(d, "data.bin"), c["data"])
        write_text_lf(os.path.join(d, "expected_stdout.txt"), c["stdout"])
        write_text_lf(os.path.join(d, "expected_exit_code.txt"), "%d\n" % c["exit_code"])
        write_text_lf(os.path.join(d, "program.s"), program_listing(c))
        if c["exit_code"] == 0:
            image = expected_data_out(c)
            assert len(image) == 1024
            write_bytes(os.path.join(d, "expected_data.out"), image)

        expect = ("`%s`" % c["stdout"].strip()) if c["exit_code"] == 0 else \
            "표준 출력 없음, 종료 코드 %d" % c["exit_code"]
        index.append("| %s | %s | %s |" % (c["name"], c["purpose"].replace("|", "\\|"), expect))

    write_text_lf(os.path.join(OUT_DIR, "INDEX.md"), "\n".join(index) + "\n")
    print("generated %d test cases in %s" % (len(CASES), OUT_DIR))


if __name__ == "__main__":
    main()
