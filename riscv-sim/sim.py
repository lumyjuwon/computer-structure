#!/usr/bin/env python3
"""RISC-V(RV32I 부분집합) 기능 시뮬레이터 실행 진입점.

사용법:  python sim.py <text.bin 경로> <data.bin 경로>

정상 종료(invalid instruction 을 fetch)
  - 현재 작업 디렉터리에 data.out (0x10000000 부터 정확히 1,024 바이트) 생성
  - 표준 출력에 한 줄:  PC 0x%08x invalid instruction 0x%08x
종료 코드
  0 정상 종료 / 1 인수·파일 입출력 오류 / 2 실행 한도 초과 / 3 메모리 범위·정렬 위반
진단 메시지는 모두 표준 오류(stderr)로만 출력한다.
"""

import sys

from rvsim.cpu import CPU, ExecutionLimitExceeded
from rvsim.memory import DATA_SIZE, Memory, SimError, read_binary_file, write_data_out

EXIT_OK = 0
EXIT_IO_ERROR = 1
EXIT_LIMIT_EXCEEDED = 2
EXIT_RUNTIME_ERROR = 3

DATA_OUT_PATH = "data.out"  # 상대 경로 -> 현재 작업 디렉터리에 생성


def format_termination_line(pc, word):
    """종료 출력 한 줄. 두 숫자 모두 0x 접두사 + 선행 0 포함 소문자 8자리 16진수."""
    return "PC 0x%08x invalid instruction 0x%08x\n" % (pc, word)


def error(message):
    sys.stderr.write(message + "\n")


def main(argv):
    if len(argv) != 3:
        error("usage: python sim.py <text.bin> <data.bin>")
        return EXIT_IO_ERROR
    text_path, data_path = argv[1], argv[2]

    try:
        text = read_binary_file(text_path)
        data = read_binary_file(data_path)
    except OSError as e:
        error("error: cannot read input file: %s" % e)
        return EXIT_IO_ERROR

    # 명세의 유효 입력 범위를 벗어난 크기는 경고만 하고 계속 진행한다.
    if len(text) == 0 or len(text) % 4 != 0:
        error("warning: text.bin size %d is not a positive multiple of 4" % len(text))
    if len(data) > DATA_SIZE:
        error("warning: data.bin size %d exceeds %d bytes; extra bytes are ignored"
              % (len(data), DATA_SIZE))

    memory = Memory(text, data)
    cpu = CPU(memory)
    try:
        pc, word = cpu.run()
    except ExecutionLimitExceeded as e:
        error("error: %s (executed %d instructions)" % (e, cpu.executed))
        return EXIT_LIMIT_EXCEEDED
    except SimError as e:
        error("error: %s (executed %d instructions)" % (e, cpu.executed))
        return EXIT_RUNTIME_ERROR

    # 종료 처리: data.out 저장 -> 표준 출력 한 줄
    try:
        write_data_out(DATA_OUT_PATH, memory)
    except OSError as e:
        error("error: cannot write %s: %s" % (DATA_OUT_PATH, e))
        return EXIT_IO_ERROR

    # 텍스트 모드 stdout 은 Windows 에서 "\n" 을 "\r\n" 으로 바꾸므로 바이트로 직접 쓴다.
    sys.stdout.buffer.write(format_termination_line(pc, word).encode("ascii"))
    sys.stdout.buffer.flush()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
