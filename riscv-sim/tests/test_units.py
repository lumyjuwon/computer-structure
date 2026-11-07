#!/usr/bin/env python3
"""단위 테스트: 비트 처리, 즉시값, 해독/invalid 판별, 메모리, CPU 실행 규칙.

사용법:  python tests/test_units.py      (표준 라이브러리 unittest 만 사용)
"""

import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # rvsim 패키지
sys.path.insert(0, HERE)                    # asm.py

from rvsim.bits import get_bits, sign_extend, to_signed32, to_u32  # noqa: E402
from rvsim.cpu import CPU, ExecutionLimitExceeded  # noqa: E402
from rvsim.decoder import decode, imm_b, imm_i, imm_s, imm_u  # noqa: E402
from rvsim.memory import (DATA_BASE, TEXT_BASE, Memory, SimError,  # noqa: E402
                          read_word_le, write_word_le)
import asm  # noqa: E402
from sim import format_termination_line  # noqa: E402


def make_cpu(source, data=b""):
    return CPU(Memory(asm.words_to_bytes(asm.assemble(source)), data))


class BitsTest(unittest.TestCase):
    def test_to_u32(self):
        self.assertEqual(to_u32(0xFFFFFFFF + 1), 0)
        self.assertEqual(to_u32(-1), 0xFFFFFFFF)
        self.assertEqual(to_u32(-2048), 0xFFFFF800)
        self.assertEqual(to_u32(0x1_2345_6789), 0x23456789)

    def test_to_signed32(self):
        self.assertEqual(to_signed32(0xFFFFFFFF), -1)
        self.assertEqual(to_signed32(0x80000000), -2147483648)
        self.assertEqual(to_signed32(0x7FFFFFFF), 2147483647)
        self.assertEqual(to_signed32(1), 1)
        self.assertEqual(to_signed32(0), 0)

    def test_sign_extend(self):
        self.assertEqual(sign_extend(0xFFF, 12), -1)
        self.assertEqual(sign_extend(0x800, 12), -2048)
        self.assertEqual(sign_extend(0x7FF, 12), 2047)
        self.assertEqual(sign_extend(0x000, 12), 0)
        self.assertEqual(sign_extend(0x1000, 13), -4096)
        self.assertEqual(sign_extend(0x0FFE, 13), 4094)

    def test_get_bits(self):
        self.assertEqual(get_bits(0x00700113, 6, 0), 0x13)
        self.assertEqual(get_bits(0x00700113, 31, 20), 7)
        self.assertEqual(get_bits(0x80000000, 31, 31), 1)


class ImmediateTest(unittest.TestCase):
    def test_i_boundaries(self):
        for imm in (-2048, -1, 0, 1, 2047):
            self.assertEqual(imm_i(asm.enc_i(imm, 1, 0, 2, 0x13)), imm)

    def test_s_boundaries(self):
        for imm in (-2048, -516, -1, 0, 1, 31, 32, 2044, 2047):
            self.assertEqual(imm_s(asm.enc_s(imm, 3, 1, 0b010, 0x23)), imm)

    def test_b_boundaries(self):
        for off in (-4096, -2048, -16, -4, -2, 0, 2, 4, 2032, 2048, 4094):
            self.assertEqual(imm_b(asm.enc_b(off, 2, 1, 0, 0x63)), off)

    def test_u(self):
        self.assertEqual(imm_u(asm.enc_u(0xFFFFF, 1, 0x37)), 0xFFFFF000)
        self.assertEqual(imm_u(0x100000B7), 0x10000000)

    def test_random_roundtrip(self):
        rng = random.Random(1234)
        for _ in range(2000):
            i = rng.randint(-2048, 2047)
            b = rng.randrange(-4096, 4095, 2)
            self.assertEqual(imm_i(asm.enc_i(i, rng.randrange(32), 0, rng.randrange(32), 0x13)), i)
            self.assertEqual(imm_s(asm.enc_s(i, rng.randrange(32), rng.randrange(32), 2, 0x23)), i)
            self.assertEqual(imm_b(asm.enc_b(b, rng.randrange(32), rng.randrange(32), 0, 0x63)), b)


class DecodeTest(unittest.TestCase):
    def check(self, word, name, rd=0, rs1=0, rs2=0, imm=0):
        inst = decode(word)
        self.assertIsNotNone(inst, "0x%08x should be valid" % word)
        self.assertEqual((inst.name, inst.rd, inst.rs1, inst.rs2, inst.imm),
                         (name, rd, rs1, rs2, imm), "0x%08x" % word)

    def test_spec_example_words(self):
        self.check(0x100000B7, "lui", rd=1, imm=0x10000000)
        self.check(0x00700113, "addi", rd=2, rs1=0, imm=7)
        self.check(0x00500193, "addi", rd=3, rs1=0, imm=5)
        self.check(0x00310233, "add", rd=4, rs1=2, rs2=3)
        self.check(0x0040A023, "sw", rs1=1, rs2=4, imm=0)
        self.assertIsNone(decode(0x00000000))

    def test_all_supported_mnemonics(self):
        cases = [
            ("add x5, x6, x7", ("add", 5, 6, 7, 0)),
            ("sub x31, x30, x29", ("sub", 31, 30, 29, 0)),
            ("and x1, x2, x3", ("and", 1, 2, 3, 0)),
            ("or x4, x5, x6", ("or", 4, 5, 6, 0)),
            ("addi x1, x2, -5", ("addi", 1, 2, 0, -5)),
            ("andi x3, x4, -1", ("andi", 3, 4, 0, -1)),
            ("ori x5, x6, 2047", ("ori", 5, 6, 0, 2047)),
            ("lui x7, 0xfffff", ("lui", 7, 0, 0, 0xFFFFF000)),
            ("lw x8, -4(x9)", ("lw", 8, 9, 0, -4)),
            ("sw x10, 2044(x11)", ("sw", 0, 11, 10, 2044)),
            ("beq x1, x2, -8", ("beq", 0, 1, 2, -8)),
            ("bne x3, x4, 12", ("bne", 0, 3, 4, 12)),
            ("blt x5, x6, -4096", ("blt", 0, 5, 6, -4096)),
            ("bge x7, x8, 4094", ("bge", 0, 7, 8, 4094)),
        ]
        for src, want in cases:
            word = asm.assemble(src)[0]
            inst = decode(word)
            self.assertIsNotNone(inst, src)
            self.assertEqual((inst.name, inst.rd, inst.rs1, inst.rs2, inst.imm), want, src)

    def test_unsupported_instructions_are_invalid(self):
        unsupported = [
            "xor x1, x2, x3", "sll x1, x2, x3", "srl x1, x2, x3", "sra x1, x2, x3",
            "slt x1, x2, x3", "sltu x1, x2, x3", "mul x1, x2, x3",
            "slti x1, x2, 5", "sltiu x1, x2, 5", "xori x1, x2, 5",
            "slli x1, x2, 3", "srli x1, x2, 3", "srai x1, x2, 3",
            "lb x1, 0(x2)", "lh x1, 0(x2)", "lbu x1, 0(x2)", "lhu x1, 0(x2)",
            "sb x1, 0(x2)", "sh x1, 0(x2)", "bltu x1, x2, 8", "bgeu x1, x2, 8",
            "jal x1, 8", "jalr x1, 0(x2)", "auipc x1, 0x10", "ecall", "ebreak",
        ]
        for src in unsupported:
            word = asm.assemble(src)[0]
            self.assertIsNone(decode(word), "%s (0x%08x) must be invalid" % (src, word))

    def test_wrong_funct7_is_invalid(self):
        add = asm.assemble("add x1, x2, x3")[0]
        for funct7 in range(128):
            word = (add & 0x01FFFFFF) | (funct7 << 25)
            expect_valid = funct7 in (0b0000000, 0b0100000)   # add / sub
            self.assertEqual(decode(word) is not None, expect_valid, "funct7=%d" % funct7)
        for src in ("and x1, x2, x3", "or x1, x2, x3"):
            base = asm.assemble(src)[0]
            for funct7 in range(1, 128):
                self.assertIsNone(decode((base & 0x01FFFFFF) | (funct7 << 25)))

    def test_every_funct3_per_opcode(self):
        valid = {0x13: {0, 6, 7}, 0x03: {2}, 0x23: {2}, 0x63: {0, 1, 4, 5}}
        for opcode, ok in valid.items():
            for funct3 in range(8):
                word = (funct3 << 12) | opcode
                self.assertEqual(decode(word) is not None, funct3 in ok,
                                 "opcode=0x%02x funct3=%d" % (opcode, funct3))

    def test_only_six_opcodes_are_valid(self):
        valid_opcodes = {0x33, 0x13, 0x03, 0x23, 0x63, 0x37}
        for opcode in range(128):
            # funct3/funct7 = 0 이면 add/addi/beq/lui 는 유효, lw/sw 는 funct3=2 필요
            word = opcode | (2 << 12 if opcode in (0x03, 0x23) else 0)
            self.assertEqual(decode(word) is not None, opcode in valid_opcodes,
                             "opcode=0x%02x" % opcode)

    def test_random_words_match_reference_rule(self):
        """무작위 32비트 값에 대해 decode 의 유효 판정이 명세 표와 일치하는지 (독립 규칙으로 검사)."""
        rng = random.Random(42)
        for _ in range(200000):
            w = rng.getrandbits(32)
            op, f3, f7 = w & 0x7F, (w >> 12) & 7, w >> 25
            ref = ((op == 0x33 and (f3, f7) in ((0, 0), (0, 0x20), (7, 0), (6, 0)))
                   or (op == 0x13 and f3 in (0, 6, 7))
                   or (op == 0x03 and f3 == 2)
                   or (op == 0x23 and f3 == 2)
                   or (op == 0x63 and f3 in (0, 1, 4, 5))
                   or op == 0x37)
            self.assertEqual(decode(w) is not None, ref, "0x%08x" % w)


class MemoryTest(unittest.TestCase):
    def test_little_endian_read(self):
        self.assertEqual(read_word_le(bytes([0x78, 0x56, 0x34, 0x12]), 0), 0x12345678)
        self.assertEqual(read_word_le(bytes.fromhex("b7000010"), 0), 0x100000B7)

    def test_little_endian_write(self):
        buf = bytearray(4)
        write_word_le(buf, 0, 0x12345678)
        self.assertEqual(bytes(buf), bytes([0x78, 0x56, 0x34, 0x12]))

    def test_data_zero_init_and_load(self):
        m = Memory(b"\x00" * 4, b"\x01\x02\x03")
        self.assertEqual(len(m.data), 1024)
        self.assertEqual(m.load_word(DATA_BASE), 0x00030201)
        self.assertEqual(m.load_word(DATA_BASE + 1020), 0)

    def test_data_bounds_and_alignment(self):
        m = Memory(b"\x00" * 4, b"")
        m.store_word(DATA_BASE + 1020, 0xA1B2C3D4)                # 마지막 워드 OK
        self.assertEqual(m.data[1020:1024], bytes.fromhex("d4c3b2a1"))
        for bad in (DATA_BASE - 4, DATA_BASE + 1024, DATA_BASE + 2, DATA_BASE + 1021,
                    TEXT_BASE, 0, 0xFFFFFFFC):
            with self.assertRaises(SimError):
                m.load_word(bad)
            with self.assertRaises(SimError):
                m.store_word(bad, 0)

    def test_fetch_bounds(self):
        m = Memory(bytes.fromhex("13000000 00000000"), b"")
        self.assertEqual(m.fetch(TEXT_BASE), 0x00000013)
        self.assertEqual(m.fetch(TEXT_BASE + 4), 0)
        for bad in (TEXT_BASE + 8, TEXT_BASE - 4, TEXT_BASE + 2, DATA_BASE):
            with self.assertRaises(SimError):
                m.fetch(bad)


class CpuTest(unittest.TestCase):
    def test_x0_is_always_zero(self):
        cpu = make_cpu("addi x0, x0, 1\nlui x0, 0xfffff\nadd x0, x0, x0\n.word 0")
        cpu.run()
        self.assertEqual(cpu.regs[0], 0)

    def test_initial_state(self):
        cpu = make_cpu(".word 0")
        self.assertEqual(cpu.pc, 0x00040000)
        self.assertEqual(cpu.regs, [0] * 32)
        self.assertEqual(cpu.run(), (0x00040000, 0))
        self.assertEqual(cpu.executed, 0)

    def test_registers_hold_unsigned_32bit(self):
        cpu = make_cpu("addi x1, x0, -1\nsub x2, x0, x1\nadd x3, x1, x1\n.word 0")
        cpu.run()
        self.assertEqual(cpu.regs[1], 0xFFFFFFFF)
        self.assertEqual(cpu.regs[2], 1)
        self.assertEqual(cpu.regs[3], 0xFFFFFFFE)
        self.assertTrue(all(0 <= r <= 0xFFFFFFFF for r in cpu.regs))

    def test_blt_spec_question(self):
        """명세 9.1: 0xffffffff 와 1 비교 -> blt 는 분기한다 (-1 < 1)."""
        cpu = make_cpu("addi x1, x0, -1\naddi x2, x0, 1\nblt x1, x2, 8\n"
                       "addi x3, x0, 1\naddi x4, x0, 1\n.word 0")
        cpu.run()
        self.assertEqual(cpu.regs[1], 0xFFFFFFFF)
        self.assertEqual((cpu.regs[3], cpu.regs[4]), (0, 1))   # x3 건너뜀

    def test_branch_target_is_relative_to_branch_pc(self):
        cpu = make_cpu("nop\nbeq x0, x0, 8\n.word 0\n.word 0")
        self.assertEqual(cpu.run(), (0x0004000C, 0))   # 0x40004 + 8, PC+4 기준이 아님

    def test_termination_pc_is_fetch_pc(self):
        cpu = make_cpu("nop\nnop\n.word 0xffffffff\n.word 0")
        self.assertEqual(cpu.run(), (0x00040008, 0xFFFFFFFF))
        self.assertEqual(cpu.executed, 2)

    def test_limit_boundary(self):
        # 정상 명령어 3개 후 invalid: 한도 3 -> 정상 종료
        cpu = make_cpu("nop\nnop\nnop\n.word 0")
        self.assertEqual(cpu.run(limit=3), (0x0004000C, 0))
        # 정상 명령어 4개 후 invalid: 한도 3 -> 4번째(0x4000c) 실행 전 비정상 종료
        cpu = make_cpu("nop\nnop\nnop\nnop\n.word 0")
        with self.assertRaises(ExecutionLimitExceeded) as ctx:
            cpu.run(limit=3)
        self.assertEqual(ctx.exception.pc, 0x0004000C)
        self.assertEqual(cpu.executed, 3)

    def test_lw_rd_equals_rs1(self):
        cpu = make_cpu("lui x1, 0x10000\nlw x1, 0(x1)\n.word 0", data=bytes.fromhex("efbeadde"))
        cpu.run()
        self.assertEqual(cpu.regs[1], 0xDEADBEEF)


class OutputFormatTest(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_termination_line(0x00040014, 0),
                         "PC 0x00040014 invalid instruction 0x00000000\n")
        self.assertEqual(format_termination_line(0x00040000, 0xFFFFFFFF),
                         "PC 0x00040000 invalid instruction 0xffffffff\n")
        self.assertEqual(format_termination_line(0x0004ABC0, 0x0000006F),
                         "PC 0x0004abc0 invalid instruction 0x0000006f\n")


if __name__ == "__main__":
    unittest.main(verbosity=1)
