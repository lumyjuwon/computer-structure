#!/usr/bin/env python3
"""디버깅 보조 도구: 명령어 단위 실행 추적과 레지스터 덤프 (채점 대상 출력이 아님).

sim.py 와 같은 rvsim 코드로 실행하면서, 명령어마다
  실행 순번, PC, 기계어, 디스어셈블 결과, 바뀐 레지스터/메모리
를 출력하고, 마지막에 레지스터 32개를 덤프한다. data.out 은 만들지 않는다.

사용법
  python tools/trace.py text.bin data.bin              # 전체 추적
  python tools/trace.py text.bin data.bin --limit 50   # 처음 50개만 추적 출력
  python tools/trace.py text.bin --disasm              # text.bin 디스어셈블만
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rvsim.cpu import CPU, ExecutionLimitExceeded  # noqa: E402
from rvsim.decoder import decode  # noqa: E402
from rvsim.memory import TEXT_BASE, Memory, SimError, read_binary_file  # noqa: E402


def disassemble(inst, pc):
    n = inst.name
    if n in ("add", "sub", "and", "or"):
        return "%-4s x%d, x%d, x%d" % (n, inst.rd, inst.rs1, inst.rs2)
    if n in ("addi", "andi", "ori"):
        return "%-4s x%d, x%d, %d" % (n, inst.rd, inst.rs1, inst.imm)
    if n == "lui":
        return "lui  x%d, 0x%x" % (inst.rd, inst.imm >> 12)
    if n == "lw":
        return "lw   x%d, %d(x%d)" % (inst.rd, inst.imm, inst.rs1)
    if n == "sw":
        return "sw   x%d, %d(x%d)" % (inst.rs2, inst.imm, inst.rs1)
    return "%-4s x%d, x%d, %d   # -> 0x%08x" % (n, inst.rs1, inst.rs2, inst.imm,
                                                (pc + inst.imm) & 0xFFFFFFFF)


class TracingCPU(CPU):
    def __init__(self, memory, show_limit):
        super().__init__(memory)
        self.show_limit = show_limit

    def execute(self, inst, pc):
        if self.executed >= self.show_limit:      # 출력하지 않는 구간은 스냅샷 없이 실행만
            return super().execute(inst, pc)
        before_regs = list(self.regs)
        before_data = bytes(self.memory.data)
        next_pc = super().execute(inst, pc)
        changes = ["x%d = 0x%08x" % (i, self.regs[i]) for i in range(32)
                   if self.regs[i] != before_regs[i]]
        for off in range(0, len(before_data), 4):
            if self.memory.data[off:off + 4] != before_data[off:off + 4]:
                value = int.from_bytes(self.memory.data[off:off + 4], "little")
                changes.append("[0x%08x] = 0x%08x" % (0x10000000 + off, value))
        if inst.name in ("beq", "bne", "blt", "bge"):
            changes.append("taken" if next_pc != pc + 4 else "not taken")
        word = self.memory.fetch(pc)
        print("#%-7d 0x%08x  0x%08x  %-34s %s" % (self.executed + 1, pc, word,
                                                 disassemble(inst, pc), "  ".join(changes)))
        return next_pc


def dump_registers(regs):
    for row in range(8):
        print("  ".join("x%-2d = 0x%08x" % (i, regs[i]) for i in range(row, 32, 8)))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text")
    parser.add_argument("data", nargs="?")
    parser.add_argument("--limit", type=int, default=10 ** 9, help="trace only first N")
    parser.add_argument("--disasm", action="store_true", help="only disassemble text.bin")
    args = parser.parse_args()

    text = read_binary_file(args.text)
    if args.disasm:
        mem = Memory(text, b"")
        for off in range(0, len(text) - len(text) % 4, 4):
            pc = TEXT_BASE + off
            word = mem.fetch(pc)
            inst = decode(word)
            print("0x%08x  0x%08x  %s" % (pc, word,
                                          disassemble(inst, pc) if inst else "(invalid)"))
        return

    data = read_binary_file(args.data) if args.data else b""
    cpu = TracingCPU(Memory(text, data), args.limit)
    try:
        pc, word = cpu.run()
        print("STOP    0x%08x  0x%08x  invalid instruction (executed %d)" % (pc, word, cpu.executed))
    except (ExecutionLimitExceeded, SimError) as e:
        print("ERROR   %s (executed %d)" % (e, cpu.executed))
    print("\nregisters:")
    dump_registers(cpu.regs)


if __name__ == "__main__":
    main()
