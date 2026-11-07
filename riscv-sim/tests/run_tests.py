#!/usr/bin/env python3
"""tests/cases/*/ 의 모든 테스트를 실제 실행 방식 그대로(별도 프로세스) 돌려 바이트 단위로 비교한다.

각 테스트마다
  1) 새 임시 디렉터리를 현재 작업 디렉터리로 하여 시뮬레이터 실행
     (정상 종료 케이스는 쓰레기 값 data.out 2,048 바이트를 미리 만들어 덮어쓰기도 확인)
  2) 종료 코드 비교
  3) 표준 출력 바이트 비교 (줄바꿈 \\n 하나까지 정확히)
  4) 정상 종료면 data.out 크기 1,024 와 내용 바이트 비교,
     비정상 종료면 data.out 이 만들어지지 않았는지 확인

사용법
  python tests/run_tests.py                     # 기본: 현재 파이썬으로 sim.py 실행
  python tests/run_tests.py --sim "python3 /path/sim.py"   # 다른 실행 명령 지정
  python tests/run_tests.py 01_spec_example 13_blt_bge_signed  # 일부만
"""

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASES_DIR = os.path.join(HERE, "cases")


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def first_diff(a, b):
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return min(len(a), len(b))


def run_case(sim_cmd, case_dir):
    """실패 사유 목록을 반환한다 (빈 목록 = 통과)."""
    text_bin = os.path.join(case_dir, "text.bin")
    data_bin = os.path.join(case_dir, "data.bin")
    want_stdout = read_bytes(os.path.join(case_dir, "expected_stdout.txt"))
    want_exit = int(read_bytes(os.path.join(case_dir, "expected_exit_code.txt")))
    want_data_path = os.path.join(case_dir, "expected_data.out")

    problems = []
    with tempfile.TemporaryDirectory() as work:
        out_path = os.path.join(work, "data.out")
        if want_exit == 0:
            with open(out_path, "wb") as f:      # 기존 data.out 덮어쓰기 확인용
                f.write(b"\xee" * 2048)
        proc = subprocess.run(sim_cmd + [text_bin, data_bin], cwd=work,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)

        if proc.returncode != want_exit:
            problems.append("exit code %d, expected %d (stderr: %s)"
                            % (proc.returncode, want_exit,
                               proc.stderr.decode(errors="replace").strip()))
        if proc.stdout != want_stdout:
            problems.append("stdout %r, expected %r" % (proc.stdout, want_stdout))

        if want_exit == 0:
            if not os.path.exists(out_path):
                problems.append("data.out not created")
            else:
                got = read_bytes(out_path)
                want = read_bytes(want_data_path)
                if len(got) != 1024:
                    problems.append("data.out size %d, expected 1024" % len(got))
                if got != want:
                    i = first_diff(got, want)
                    problems.append("data.out differs at offset 0x%03x (addr 0x%08x): "
                                    "got %s expected %s"
                                    % (i, 0x10000000 + i, got[i:i + 4].hex(" "),
                                       want[i:i + 4].hex(" ")))
        elif os.path.exists(out_path):
            problems.append("data.out must not be created on abnormal termination")
    return problems


def run_cli_checks(sim_cmd):
    """인수 개수·파일 없음 오류 처리 확인 (종료 코드 1, 표준 출력 없음)."""
    results = []
    with tempfile.TemporaryDirectory() as work:
        for label, args in [("no arguments", []),
                            ("one argument", ["text.bin"]),
                            ("three arguments", ["a", "b", "c"]),
                            ("missing input file", ["no_such_text.bin", "no_such_data.bin"])]:
            proc = subprocess.run(sim_cmd + args, cwd=work, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=60)
            problems = []
            if proc.returncode != 1:
                problems.append("exit code %d, expected 1" % proc.returncode)
            if proc.stdout:
                problems.append("stdout must be empty, got %r" % proc.stdout)
            if not proc.stderr:
                problems.append("stderr should explain the error")
            results.append(("cli: " + label, problems))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sim", help="simulator command (default: current python + sim.py)")
    parser.add_argument("cases", nargs="*", help="case names to run (default: all)")
    args = parser.parse_args()

    if args.sim:
        # Windows 경로의 백슬래시가 사라지지 않도록 Windows 에서는 non-POSIX 규칙으로 나누고 따옴표만 벗긴다.
        sim_cmd = [t[1:-1] if len(t) > 1 and t[0] == t[-1] == '"' else t
                   for t in shlex.split(args.sim, posix=(os.name != "nt"))]
    else:
        sim_cmd = [sys.executable, os.path.join(ROOT, "sim.py")]

    if not os.path.isdir(CASES_DIR):
        sys.exit("tests/cases not found. run: python tests/gen_tests.py")
    names = args.cases or sorted(n for n in os.listdir(CASES_DIR)
                                 if os.path.isdir(os.path.join(CASES_DIR, n)))

    failed = 0
    total = 0
    for name in names:
        start = time.time()
        problems = run_case(sim_cmd, os.path.join(CASES_DIR, name))
        total += 1
        status = "PASS" if not problems else "FAIL"
        print("%s  %-28s %6.2fs" % (status, name, time.time() - start))
        for p in problems:
            print("      - " + p)
        failed += bool(problems)

    if not args.cases:
        for label, problems in run_cli_checks(sim_cmd):
            total += 1
            print("%s  %s" % ("PASS" if not problems else "FAIL", label))
            for p in problems:
                print("      - " + p)
            failed += bool(problems)

    print("\n%d/%d passed" % (total - failed, total))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
