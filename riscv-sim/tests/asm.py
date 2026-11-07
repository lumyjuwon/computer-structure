"""테스트 입력 생성용 미니 어셈블러(인코더).

시뮬레이터(rvsim)의 해독 코드와 독립적으로 작성했다. rvsim 을 import 하지 않는다.
(해독기와 인코더가 같은 코드를 공유하면 같은 실수가 양쪽에 숨어 검증이 되지 않기 때문)

지원 문법
  label:                       레이블 정의 (분기 목표)
  add  rd, rs1, rs2            sub / and / or 동일
  addi rd, rs1, imm            andi / ori 동일
  lui  rd, imm20               imm20 은 0 ~ 0xFFFFF (상위 20비트)
  lw   rd, imm(rs1)
  sw   rs2, imm(rs1)
  beq  rs1, rs2, label|offset  bne / blt / bge 동일 (offset 은 바이트 단위)
  nop                          addi x0, x0, 0
  .word value                  32비트 값을 그대로 배치 (invalid instruction 등)
  # 이후는 주석

invalid instruction 테스트용으로, 지원하지 않는 실제 RV32I/RV32M 명령어도 인코딩할 수 있다.
  R형: xor sll srl sra slt sltu mul       I형: slti sltiu xori slli srli srai
  load: lb lh lbu lhu   store: sb sh       branch: bltu bgeu
  jal rd, offset   jalr rd, imm(rs1)   auipc rd, imm20   ecall   ebreak
"""

import re
import struct

TEXT_BASE = 0x00040000

REGS = {"x%d" % i: i for i in range(32)}
REGS["zero"] = 0

# 지원 명령어 14개
R_OPS = {"add": (0b000, 0b0000000), "sub": (0b000, 0b0100000),
         "and": (0b111, 0b0000000), "or": (0b110, 0b0000000)}
I_OPS = {"addi": 0b000, "andi": 0b111, "ori": 0b110}
BRANCH_OPS = {"beq": 0b000, "bne": 0b001, "blt": 0b100, "bge": 0b101}

# invalid instruction 테스트용(시뮬레이터는 지원하지 않음)
R_OPS_UNSUPPORTED = {"sll": (0b001, 0), "slt": (0b010, 0), "sltu": (0b011, 0),
                     "xor": (0b100, 0), "srl": (0b101, 0), "sra": (0b101, 0b0100000),
                     "mul": (0b000, 0b0000001)}
I_OPS_UNSUPPORTED = {"slti": 0b010, "sltiu": 0b011, "xori": 0b100}
SHIFT_OPS_UNSUPPORTED = {"slli": (0b001, 0), "srli": (0b101, 0), "srai": (0b101, 0b0100000)}
LOAD_OPS_UNSUPPORTED = {"lb": 0b000, "lh": 0b001, "lbu": 0b100, "lhu": 0b101}
STORE_OPS_UNSUPPORTED = {"sb": 0b000, "sh": 0b001}
BRANCH_OPS_UNSUPPORTED = {"bltu": 0b110, "bgeu": 0b111}

OP, OP_IMM, LOAD, STORE, BRANCH, LUI = 0x33, 0x13, 0x03, 0x23, 0x63, 0x37
AUIPC, JAL, JALR, SYSTEM = 0x17, 0x6F, 0x67, 0x73


class AsmError(Exception):
    pass


def _check_range(value, lo, hi, what):
    if not lo <= value <= hi:
        raise AsmError("%s %d out of range [%d, %d]" % (what, value, lo, hi))


def enc_r(funct7, rs2, rs1, funct3, rd, opcode):
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def enc_i(imm, rs1, funct3, rd, opcode):
    _check_range(imm, -2048, 2047, "I-type imm")
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def enc_s(imm, rs2, rs1, funct3, opcode):
    _check_range(imm, -2048, 2047, "S-type imm")
    imm &= 0xFFF
    return (((imm >> 5) & 0x7F) << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) \
        | ((imm & 0x1F) << 7) | opcode


def enc_b(offset, rs2, rs1, funct3, opcode):
    _check_range(offset, -4096, 4094, "B-type offset")
    if offset % 2:
        raise AsmError("B-type offset must be even: %d" % offset)
    imm = offset & 0x1FFF
    return (((imm >> 12) & 1) << 31) | (((imm >> 5) & 0x3F) << 25) | (rs2 << 20) \
        | (rs1 << 15) | (funct3 << 12) | (((imm >> 1) & 0xF) << 8) \
        | (((imm >> 11) & 1) << 7) | opcode


def enc_u(imm20, rd, opcode):
    _check_range(imm20, 0, 0xFFFFF, "U-type imm20")
    return (imm20 << 12) | (rd << 7) | opcode


def enc_j(offset, rd, opcode):
    _check_range(offset, -(1 << 20), (1 << 20) - 2, "J-type offset")
    imm = offset & 0x1FFFFF
    return (((imm >> 20) & 1) << 31) | (((imm >> 1) & 0x3FF) << 21) \
        | (((imm >> 11) & 1) << 20) | (((imm >> 12) & 0xFF) << 12) | (rd << 7) | opcode


def _reg(tok):
    tok = tok.strip()
    if tok not in REGS:
        raise AsmError("bad register: %r" % tok)
    return REGS[tok]


def _int(tok):
    return int(tok.strip(), 0)


_MEM_RE = re.compile(r"^\s*(-?(?:0x[0-9a-fA-F]+|\d+))\s*\(\s*(\w+)\s*\)\s*$")


def _mem(tok):
    m = _MEM_RE.match(tok)
    if not m:
        raise AsmError("bad memory operand: %r" % tok)
    return int(m.group(1), 0), _reg(m.group(2))


def _parse(source):
    """소스를 (주소, 명령어 이름, 피연산자 목록, 원본 줄) 목록과 레이블 표로 바꾼다."""
    items, labels = [], {}
    addr = TEXT_BASE
    for raw in source.splitlines():
        line = raw.split("#", 1)[0].strip()
        while line:
            m = re.match(r"^(\w+)\s*:\s*(.*)$", line)
            if not m:
                break
            if m.group(1) in labels:
                raise AsmError("duplicate label: " + m.group(1))
            labels[m.group(1)] = addr
            line = m.group(2).strip()
        if not line:
            continue
        parts = line.split(None, 1)
        mnemonic = parts[0].lower()
        operands = [p.strip() for p in parts[1].split(",")] if len(parts) > 1 else []
        items.append((addr, mnemonic, operands, raw.strip()))
        addr += 4
    return items, labels


def _target(tok, labels, pc):
    tok = tok.strip()
    if tok in labels:
        return labels[tok] - pc
    return _int(tok)


def _encode(mn, ops, labels, pc):
    if mn in R_OPS or mn in R_OPS_UNSUPPORTED:
        funct3, funct7 = R_OPS.get(mn) or R_OPS_UNSUPPORTED[mn]
        return enc_r(funct7, _reg(ops[2]), _reg(ops[1]), funct3, _reg(ops[0]), OP)
    if mn in I_OPS or mn in I_OPS_UNSUPPORTED:
        funct3 = I_OPS[mn] if mn in I_OPS else I_OPS_UNSUPPORTED[mn]
        return enc_i(_int(ops[2]), _reg(ops[1]), funct3, _reg(ops[0]), OP_IMM)
    if mn in SHIFT_OPS_UNSUPPORTED:
        funct3, funct7 = SHIFT_OPS_UNSUPPORTED[mn]
        shamt = _int(ops[2])
        _check_range(shamt, 0, 31, "shamt")
        return enc_r(funct7, shamt, _reg(ops[1]), funct3, _reg(ops[0]), OP_IMM)
    if mn == "nop":
        return enc_i(0, 0, 0b000, 0, OP_IMM)
    if mn == "lui" or mn == "auipc":
        return enc_u(_int(ops[1]), _reg(ops[0]), LUI if mn == "lui" else AUIPC)
    if mn == "lw" or mn in LOAD_OPS_UNSUPPORTED:
        imm, rs1 = _mem(ops[1])
        funct3 = 0b010 if mn == "lw" else LOAD_OPS_UNSUPPORTED[mn]
        return enc_i(imm, rs1, funct3, _reg(ops[0]), LOAD)
    if mn == "sw" or mn in STORE_OPS_UNSUPPORTED:
        imm, rs1 = _mem(ops[1])
        funct3 = 0b010 if mn == "sw" else STORE_OPS_UNSUPPORTED[mn]
        return enc_s(imm, _reg(ops[0]), rs1, funct3, STORE)
    if mn in BRANCH_OPS or mn in BRANCH_OPS_UNSUPPORTED:
        funct3 = BRANCH_OPS[mn] if mn in BRANCH_OPS else BRANCH_OPS_UNSUPPORTED[mn]
        return enc_b(_target(ops[2], labels, pc), _reg(ops[1]), _reg(ops[0]), funct3, BRANCH)
    if mn == "jal":
        return enc_j(_target(ops[1], labels, pc), _reg(ops[0]), JAL)
    if mn == "jalr":
        imm, rs1 = _mem(ops[1])
        return enc_i(imm, rs1, 0b000, _reg(ops[0]), JALR)
    if mn == "ecall":
        return SYSTEM
    if mn == "ebreak":
        return (1 << 20) | SYSTEM
    if mn == ".word":
        value = _int(ops[0])
        _check_range(value, 0, 0xFFFFFFFF, ".word value")
        return value
    raise AsmError("unknown mnemonic: " + mn)


def assemble(source):
    """어셈블리 소스 -> 32비트 명령어 값 목록 (주소 0x00040000 부터 4바이트 간격)."""
    items, labels = _parse(source)
    words = []
    for pc, mn, ops, raw in items:
        try:
            words.append(_encode(mn, ops, labels, pc))
        except (AsmError, IndexError, ValueError) as e:
            raise AsmError("0x%08x: %s  <- %s" % (pc, e, raw))
    return words


def listing(source):
    """(주소, 명령어 값, 원본 줄) 목록. 테스트 문서화용."""
    items, _ = _parse(source)
    return [(pc, w, raw) for (pc, _, _, raw), w in zip(items, assemble(source))]


def words_to_bytes(words):
    """32비트 값 목록 -> little-endian 바이트열 (struct '<I' 사용)."""
    return b"".join(struct.pack("<I", w) for w in words)
