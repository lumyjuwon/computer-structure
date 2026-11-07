#!/usr/bin/env python3
"""변이 테스트(mutation test): 테스트 모음이 흔한 구현 실수를 실제로 잡아내는지 확인한다.

시뮬레이터 소스를 임시 디렉터리에 복사한 뒤 '일부러 버그를 하나 넣은 버전(변이)'을 만들고,
tests/cases 의 종단 간 테스트를 돌린다. 하나 이상 실패하면 그 변이는 '검출됨(killed)'.
검출되지 않은 변이가 있으면 테스트가 그 실수를 놓친다는 뜻이므로 테스트를 보강해야 한다.

사용법:  python tests/mutation_test.py [--markdown 결과.md]
"""

import argparse
import os
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from run_tests import CASES_DIR, run_case  # noqa: E402

# (설명, 파일, 원래 코드, 바꾼 코드)  - 원래 코드는 파일에 정확히 존재해야 한다(전부 교체)
MUTANTS = [
    ("blt 를 부호 없는 비교로 구현", "rvsim/cpu.py",
     "if to_signed32(rs1) < to_signed32(rs2):", "if rs1 < rs2:"),
    ("bge 를 부호 없는 비교로 구현", "rvsim/cpu.py",
     "if to_signed32(rs1) >= to_signed32(rs2):", "if rs1 >= rs2:"),
    ("bne 조건 반전", "rvsim/cpu.py",
     "if rs1 != rs2:", "if rs1 == rs2:"),
    ("분기 목표를 PC+4 기준으로 계산", "rvsim/cpu.py",
     "next_pc = pc + imm", "next_pc = pc + 4 + imm"),
    ("x0 쓰기 보호 누락", "rvsim/cpu.py",
     "if index != 0:", "if True:"),
    ("레지스터 값을 32비트로 자르지 않음", "rvsim/cpu.py",
     "self.regs[index] = to_u32(value)", "self.regs[index] = value"),
    ("andi/ori 즉시값을 부호 확장하지 않음(하위 12비트만)", "rvsim/cpu.py",
     "to_u32(imm)", "(imm & 0xFFF)"),
    ("lui 값을 한 번 더 12비트 시프트", "rvsim/cpu.py",
     "self.write_reg(inst.rd, imm)                # imm", "self.write_reg(inst.rd, imm << 12)  # imm"),
    ("lw 에서 오프셋 무시", "rvsim/cpu.py",
     "addr = to_u32(rs1 + imm)\n            self.write_reg",
     "addr = to_u32(rs1)\n            self.write_reg"),
    ("sw 가 rs2 대신 rs1 을 저장", "rvsim/cpu.py",
     "self.memory.store_word(addr, rs2)", "self.memory.store_word(addr, rs1)"),
    ("종료 시 fetch PC 대신 PC+4 출력", "rvsim/cpu.py",
     "return fetch_pc, word", "return fetch_pc + 4, word"),
    ("실행 한도 비교를 > 로 (1,000,001 개 허용)", "rvsim/cpu.py",
     "if self.executed >= limit:", "if self.executed > limit:"),
    ("실행 한도 검사를 invalid 판별보다 먼저 수행", "rvsim/cpu.py",
     "            if inst is None:                        # 지원하지 않는 명령어 -> 실행 없이 종료\n"
     "                return fetch_pc, word\n"
     "            if self.executed >= limit:              # 이미 한도만큼 실행했는데 또 정상 명령어\n"
     "                raise ExecutionLimitExceeded(fetch_pc, word)\n",
     "            if self.executed >= limit:\n"
     "                raise ExecutionLimitExceeded(fetch_pc, word)\n"
     "            if inst is None:\n"
     "                return fetch_pc, word\n"),
    ("I형 즉시값 부호 확장 누락", "rvsim/decoder.py",
     "return sign_extend(get_bits(word, 31, 20), 12)", "return get_bits(word, 31, 20)"),
    ("S형 즉시값 imm[4:0] 누락", "rvsim/decoder.py",
     "imm = (get_bits(word, 31, 25) << 5) | get_bits(word, 11, 7)",
     "imm = (get_bits(word, 31, 25) << 5)"),
    ("B형 즉시값 imm[11](bit 7) 누락", "rvsim/decoder.py",
     "| (get_bits(word, 7, 7) << 11)", "| (0 << 11)"),
    ("B형 즉시값을 12비트로 부호 확장", "rvsim/decoder.py",
     "return sign_extend(imm, 13)", "return sign_extend(imm, 12)"),
    ("R형 funct7 검사 누락 (sub 외에는 add 로 간주)", "rvsim/decoder.py",
     "R_TYPE_TABLE.get((funct3, funct7))",
     "R_TYPE_TABLE.get((funct3, funct7 if funct7 == 0b0100000 else 0))"),
    ("sub 를 add 로 해독", "rvsim/decoder.py",
     '(0b000, 0b0100000): "sub"', '(0b000, 0b0100000): "add"'),
    ("lw 의 funct3 검사 누락", "rvsim/decoder.py",
     "name = LOAD_TABLE.get(funct3)", 'name = "lw"'),
    ("sw 의 funct3 검사 누락", "rvsim/decoder.py",
     "name = STORE_TABLE.get(funct3)", 'name = "sw"'),
    ("I형 연산 funct3 검사 누락 (모르는 funct3 를 addi 로)", "rvsim/decoder.py",
     "name = OP_IMM_TABLE.get(funct3)", 'name = OP_IMM_TABLE.get(funct3, "addi")'),
    ("bltu/bgeu 를 blt/bge 로 해독", "rvsim/decoder.py",
     "name = BRANCH_TABLE.get(funct3)", "name = BRANCH_TABLE.get(funct3 & 0b101)"),
    ("little-endian 대신 big-endian 으로 읽기", "rvsim/memory.py",
     "return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)",
     "return b3 | (b2 << 8) | (b1 << 16) | (b0 << 24)"),
    ("data.out 을 텍스트 모드로 저장", "rvsim/memory.py",
     'with open(path, "wb") as f:\n        f.write(bytes(memory.data[0:DATA_SIZE]))',
     'with open(path, "w", encoding="latin-1") as f:\n'
     '        f.write(bytes(memory.data[0:DATA_SIZE]).decode("latin-1"))'),
    ("data.out 을 1,020 바이트만 저장", "rvsim/memory.py",
     "bytes(memory.data[0:DATA_SIZE])", "bytes(memory.data[0:DATA_SIZE - 4])"),
    ("표준 출력을 텍스트 모드 print 로 출력", "sim.py",
     'sys.stdout.buffer.write(format_termination_line(pc, word).encode("ascii"))',
     'sys.stdout.write(format_termination_line(pc, word)); sys.stdout.flush()'),
    ("16진수를 대문자로 출력", "sim.py",
     '"PC 0x%08x invalid instruction 0x%08x\\n"', '"PC 0x%08X invalid instruction 0x%08X\\n"'),
    ("16진수 선행 0 생략", "sim.py",
     '"PC 0x%08x invalid instruction 0x%08x\\n"', '"PC 0x%x invalid instruction 0x%x\\n"'),
]


def make_mutant(workdir, rel_path, old, new):
    shutil.copy(os.path.join(ROOT, "sim.py"), workdir)
    shutil.copytree(os.path.join(ROOT, "rvsim"), os.path.join(workdir, "rvsim"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    path = os.path.join(workdir, rel_path)
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if old not in src:
        raise SystemExit("mutation pattern not found in %s:\n%s" % (rel_path, old))
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(src.replace(old, new))
    return os.path.join(workdir, "sim.py")


def run_suite(sim_cmd, names):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda n: (n, run_case(sim_cmd, os.path.join(CASES_DIR, n))),
                                names))
    return [n for n, problems in results if problems]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", help="write result table to this markdown file")
    args = parser.parse_args()

    names = sorted(n for n in os.listdir(CASES_DIR) if os.path.isdir(os.path.join(CASES_DIR, n)))

    # 원본은 모든 테스트를 통과해야 의미가 있다.
    original_failures = run_suite([sys.executable, os.path.join(ROOT, "sim.py")], names)
    if original_failures:
        sys.exit("original simulator fails: %s" % original_failures)

    rows, survived = [], 0
    for desc, rel_path, old, new in MUTANTS:
        with tempfile.TemporaryDirectory() as work:
            sim_path = make_mutant(work, rel_path, old, new)
            failing = run_suite([sys.executable, sim_path], names)
        status = "검출" if failing else "미검출"
        survived += not failing
        shown = ", ".join(failing[:4]) + (" 외 %d개" % (len(failing) - 4) if len(failing) > 4 else "")
        print("[%s] %-40s %s" % (status, desc, shown))
        rows.append((desc, rel_path, len(failing), shown))

    print("\n%d/%d mutants killed" % (len(MUTANTS) - survived, len(MUTANTS)))
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8", newline="\n") as f:
            f.write("| 심은 버그 | 파일 | 실패한 테스트 수 | 실패한 테스트(일부) |\n|---|---|---|---|\n")
            for desc, rel_path, n, shown in rows:
                f.write("| %s | %s | %d | %s |\n" % (desc, rel_path, n, shown or "**없음**"))
    sys.exit(1 if survived else 0)


if __name__ == "__main__":
    main()
