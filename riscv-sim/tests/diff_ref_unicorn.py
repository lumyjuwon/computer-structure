#!/usr/bin/env python3
"""(선택) 참조 실행기 Unicorn Engine 과의 차등 테스트 - 테스트 전용, 시뮬레이터 실행에는 쓰지 않는다.

Unicorn Engine(https://www.unicorn-engine.org, QEMU 기반 CPU 에뮬레이터)은 우리 팀이 작성하지 않은
독립 구현이다. 명세 8절에 따라 '참조 실행기를 별도 테스트용으로' 사용하며 보고서에 밝힌다.
시뮬레이터(sim.py, rvsim/)는 Unicorn 을 전혀 사용하지 않는다.

  1) tests/cases 의 정상 종료 케이스: 손으로 도출한 기대 data.out 을 Unicorn 실행 결과와 대조
     (기대 결과 자체가 맞는지 독립적으로 재확인)
  2) 무작위 프로그램 N 개: 우리 CPU 와 Unicorn 의 최종 레지스터 32개·데이터 1,024 바이트·종료 PC 비교

Unicorn 은 RV32 전체를 실행하므로 invalid instruction 에서 스스로 멈추지 않는다.
그래서 종료 지점(기대 출력의 PC)을 until 주소로 주어 그 직전에서 멈추게 한다.

사용법:  pip install unicorn
         python tests/diff_ref_unicorn.py [--programs 3000] [--seed 1]
"""

import argparse
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

try:
    from unicorn import UC_ARCH_RISCV, UC_MODE_RISCV32, Uc, UcError
    from unicorn.riscv_const import UC_RISCV_REG_PC, UC_RISCV_REG_X0
except ImportError:
    sys.exit("unicorn is not installed. run: pip install unicorn")

import asm  # noqa: E402
from rvsim.cpu import CPU  # noqa: E402
from rvsim.memory import Memory  # noqa: E402

TEXT_BASE, DATA_BASE = 0x00040000, 0x10000000
CASES_DIR = os.path.join(HERE, "cases")


def run_unicorn(text, data, stop_pc, max_count=2000000):
    """Unicorn 으로 stop_pc 에 도달할 때까지 실행. (레지스터 목록, 데이터 1,024 바이트) 반환.
    stop_pc 에 도달하지 못하면(다른 곳에서 멈추거나 예외) None 을 반환한다."""
    uc = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
    text_size = (len(text) + 0xFFF) & ~0xFFF
    uc.mem_map(TEXT_BASE, max(text_size, 0x1000))
    uc.mem_map(DATA_BASE, 0x1000)
    uc.mem_write(TEXT_BASE, text)
    uc.mem_write(DATA_BASE, (data + bytes(1024))[:1024])
    try:
        uc.emu_start(TEXT_BASE, stop_pc, count=max_count)
    except UcError:
        return None
    if uc.reg_read(UC_RISCV_REG_PC) & 0xFFFFFFFF != stop_pc:
        return None
    regs = [uc.reg_read(UC_RISCV_REG_X0 + i) & 0xFFFFFFFF for i in range(32)]
    return regs, bytes(uc.mem_read(DATA_BASE, 1024))


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def check_hand_expectations():
    """정상 종료 케이스의 손 계산 기대값 == Unicorn 결과 인지 확인."""
    checked, bad = 0, 0
    for name in sorted(os.listdir(CASES_DIR)):
        d = os.path.join(CASES_DIR, name)
        if not os.path.isdir(d):
            continue
        if int(read_bytes(os.path.join(d, "expected_exit_code.txt"))) != 0:
            continue
        read = lambda fn: read_bytes(os.path.join(d, fn))  # noqa: E731
        stop_pc = int(read("expected_stdout.txt").split()[1], 16)
        result = run_unicorn(read("text.bin"), read("data.bin"), stop_pc)
        ok = result is not None and result[1] == read("expected_data.out")
        checked += 1
        bad += not ok
        print("%s  %s" % ("OK  " if ok else "DIFF", name))
    return checked, bad


# ---------------------------------------------------------------------------
# 무작위 프로그램 생성
#   x31 = 0x10000000, x30 = 0x10000400 : lw/sw 기준 주소 (변경 금지)
#   x29 = 루프 카운터 (루프 블록 전용)
#   분기는 앞으로만(같은 블록 안 또는 블록 끝) -> 반드시 종료
# ---------------------------------------------------------------------------
SPECIAL = [0, 1, 0xFFFFFFFF, 0x80000000, 0x7FFFFFFF, 0xFFFFF800, 0x800, 0x7FF]


def rand_imm12(rng):
    return rng.choice([-2048, -1, 0, 1, 2047, rng.randint(-2048, 2047), rng.randint(-16, 16)])


def rand_mem(rng):
    if rng.random() < 0.5:
        return "%d(x31)" % (4 * rng.randint(0, 255))
    return "%d(x30)" % (-4 * rng.randint(1, 256))


def rand_simple(rng):
    """분기가 아닌 명령어 하나 (rd 는 x0~x28)."""
    rd, rs1, rs2 = rng.randint(0, 28), rng.randint(0, 31), rng.randint(0, 31)
    kind = rng.random()
    if kind < 0.35:
        return "%s x%d, x%d, x%d" % (rng.choice(["add", "sub", "and", "or"]), rd, rs1, rs2)
    if kind < 0.65:
        return "%s x%d, x%d, %d" % (rng.choice(["addi", "andi", "ori"]), rd, rs1, rand_imm12(rng))
    if kind < 0.75:
        return "lui x%d, 0x%x" % (rd, rng.getrandbits(20))
    if kind < 0.87:
        return "lw x%d, %s" % (rd, rand_mem(rng))
    return "sw x%d, %s" % (rs2, rand_mem(rng))


def random_program(rng):
    lines = ["lui x31, 0x10000", "lui x30, 0x10000", "addi x30, x30, 1024"]
    for r in range(1, 29):                       # 레지스터 초기값 무작위
        v = rng.choice(SPECIAL) if rng.random() < 0.3 else rng.getrandbits(32)
        hi, lo = (v + 0x800) >> 12 & 0xFFFFF, ((v & 0xFFF) ^ 0x800) - 0x800
        lines += ["lui x%d, 0x%x" % (r, hi), "addi x%d, x%d, %d" % (r, r, lo)]

    label = [0]

    def new_label():
        label[0] += 1
        return "L%d" % label[0]

    for _ in range(rng.randint(2, 6)):
        if rng.random() < 0.3:                   # 루프 블록
            top = new_label()
            lines.append("addi x29, x0, %d" % rng.randint(1, 5))
            body = [rand_simple(rng) for _ in range(rng.randint(1, 8))]
            lines.append("%s: %s" % (top, body[0]))
            lines += body[1:]
            lines += ["addi x29, x29, -1", "bne x29, x0, %s" % top]
        else:                                    # 직선 블록 + 앞으로 가는 분기
            n = rng.randint(5, 30)
            labels = [new_label() for _ in range(n + 1)]   # labels[n] = 블록 끝
            block = []
            for i in range(n):
                if rng.random() < 0.25:
                    j = rng.randint(i + 1, n)
                    block.append("%s x%d, x%d, %s" % (rng.choice(["beq", "bne", "blt", "bge"]),
                                                       rng.randint(0, 31), rng.randint(0, 31),
                                                       labels[j]))
                else:
                    block.append(rand_simple(rng))
            for i in range(n):
                lines.append("%s: %s" % (labels[i], block[i]))
            lines.append("%s: addi x0, x0, 0" % labels[n])
    lines.append(".word 0")
    return "\n".join(lines)


def check_random(count, seed):
    rng = random.Random(seed)
    for k in range(count):
        src = random_program(rng)
        words = asm.assemble(src)
        text = asm.words_to_bytes(words)
        data = bytes(rng.getrandbits(8) for _ in range(rng.choice([0, 16, 1024])))
        end_pc = TEXT_BASE + 4 * (len(words) - 1)

        cpu = CPU(Memory(text, data))
        pc, word = cpu.run()
        result = run_unicorn(text, data, end_pc)
        uc_regs, uc_data = result if result is not None else ([None] * 32, None)

        if (pc, word) != (end_pc, 0) or cpu.regs != uc_regs or bytes(cpu.memory.data) != uc_data:
            print("MISMATCH in random program #%d (seed %d)" % (k, seed))
            if result is None:
                print("  unicorn did not reach end pc 0x%08x" % end_pc)
            for i in range(32):
                if result is not None and cpu.regs[i] != uc_regs[i]:
                    print("  x%d: ours 0x%08x, unicorn 0x%08x" % (i, cpu.regs[i], uc_regs[i]))
            print(src)
            return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--programs", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    checked, bad = check_hand_expectations()
    print("hand-derived expectations: %d/%d agree with unicorn" % (checked - bad, checked))
    ok = check_random(args.programs, args.seed)
    print("random differential test: %d programs %s" % (args.programs, "OK" if ok else "FAILED"))
    sys.exit(0 if ok and not bad else 1)


if __name__ == "__main__":
    main()
