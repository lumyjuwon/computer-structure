"""명령어 해독(decode)과 invalid instruction 판별.

RV32I 32비트 명령어 형식 (비트 번호 31 ~ 0)

        31       25 24   20 19   15 14  12 11         7 6      0
  R형  | funct7    |  rs2  |  rs1  |funct3|     rd     | opcode |
  I형  |     imm[11:0]     |  rs1  |funct3|     rd     | opcode |
  S형  | imm[11:5] |  rs2  |  rs1  |funct3|  imm[4:0]  | opcode |
  B형  |imm[12|10:5]| rs2  |  rs1  |funct3| imm[4:1|11]| opcode |
  U형  |            imm[31:12]            |     rd     | opcode |

지원 명령어 14개와 판별 조건 (이 표에 없는 조합은 모두 invalid instruction)

  명령어 형식  opcode    funct3  funct7
  add    R    0110011   000     0000000
  sub    R    0110011   000     0100000
  and    R    0110011   111     0000000
  or     R    0110011   110     0000000
  addi   I    0010011   000     -
  andi   I    0010011   111     -
  ori    I    0010011   110     -
  lw     I    0000011   010     -
  sw     S    0100011   010     -
  beq    B    1100011   000     -
  bne    B    1100011   001     -
  blt    B    1100011   100     -
  bge    B    1100011   101     -
  lui    U    0110111   -       -
"""

from .bits import get_bits, sign_extend

# opcode (명령어 비트 [6:0])
OPCODE_OP = 0b0110011      # 0x33  R형 연산: add, sub, and, or
OPCODE_OP_IMM = 0b0010011  # 0x13  I형 연산: addi, andi, ori
OPCODE_LOAD = 0b0000011    # 0x03  lw
OPCODE_STORE = 0b0100011   # 0x23  sw
OPCODE_BRANCH = 0b1100011  # 0x63  beq, bne, blt, bge
OPCODE_LUI = 0b0110111     # 0x37  lui

# opcode 별로 funct3(와 funct7) 조합 -> 명령어 이름
R_TYPE_TABLE = {           # (funct3, funct7) -> 이름
    (0b000, 0b0000000): "add",
    (0b000, 0b0100000): "sub",
    (0b111, 0b0000000): "and",
    (0b110, 0b0000000): "or",
}
OP_IMM_TABLE = {0b000: "addi", 0b111: "andi", 0b110: "ori"}
LOAD_TABLE = {0b010: "lw"}
STORE_TABLE = {0b010: "sw"}
BRANCH_TABLE = {0b000: "beq", 0b001: "bne", 0b100: "blt", 0b101: "bge"}


class Instruction:
    """해독된 명령어. 사용하지 않는 필드는 0 이다. imm 은 부호 확장된 Python 정수."""

    __slots__ = ("name", "rd", "rs1", "rs2", "imm")

    def __init__(self, name, rd=0, rs1=0, rs2=0, imm=0):
        self.name = name
        self.rd = rd
        self.rs1 = rs1
        self.rs2 = rs2
        self.imm = imm

    def __repr__(self):
        return "Instruction(%s, rd=%d, rs1=%d, rs2=%d, imm=%d)" % (
            self.name, self.rd, self.rs1, self.rs2, self.imm)


def imm_i(word):
    """I형 즉시값: imm[11:0] = word[31:20], 12비트 부호 확장."""
    return sign_extend(get_bits(word, 31, 20), 12)


def imm_s(word):
    """S형 즉시값: imm[11:5] = word[31:25], imm[4:0] = word[11:7], 12비트 부호 확장."""
    imm = (get_bits(word, 31, 25) << 5) | get_bits(word, 11, 7)
    return sign_extend(imm, 12)


def imm_b(word):
    """B형 즉시값(분기 오프셋, 바이트 단위). 13비트 부호 확장, imm[0] 은 항상 0.

    imm[12]   = word[31]
    imm[11]   = word[7]
    imm[10:5] = word[30:25]
    imm[4:1]  = word[11:8]
    """
    imm = ((get_bits(word, 31, 31) << 12)
           | (get_bits(word, 7, 7) << 11)
           | (get_bits(word, 30, 25) << 5)
           | (get_bits(word, 11, 8) << 1))
    return sign_extend(imm, 13)


def imm_u(word):
    """U형 즉시값: word[31:12] 를 상위 20비트에 그대로 두고 하위 12비트는 0."""
    return word & 0xFFFFF000


def decode(word):
    """32비트 명령어 값을 해독한다.

    지원하는 14개 명령어이면 Instruction 을, 아니면 None(invalid instruction)을 반환한다.
    opcode 뿐 아니라 funct3, (R형은) funct7 까지 모두 일치해야 지원 명령어로 인정한다.
    """
    opcode = get_bits(word, 6, 0)
    rd = get_bits(word, 11, 7)
    funct3 = get_bits(word, 14, 12)
    rs1 = get_bits(word, 19, 15)
    rs2 = get_bits(word, 24, 20)
    funct7 = get_bits(word, 31, 25)

    if opcode == OPCODE_OP:                                   # R형
        name = R_TYPE_TABLE.get((funct3, funct7))
        if name is None:
            return None
        return Instruction(name, rd=rd, rs1=rs1, rs2=rs2)

    if opcode == OPCODE_OP_IMM:                               # I형 연산
        name = OP_IMM_TABLE.get(funct3)
        if name is None:
            return None
        return Instruction(name, rd=rd, rs1=rs1, imm=imm_i(word))

    if opcode == OPCODE_LOAD:                                 # I형 lw
        name = LOAD_TABLE.get(funct3)
        if name is None:
            return None
        return Instruction(name, rd=rd, rs1=rs1, imm=imm_i(word))

    if opcode == OPCODE_STORE:                                # S형 sw
        name = STORE_TABLE.get(funct3)
        if name is None:
            return None
        return Instruction(name, rs1=rs1, rs2=rs2, imm=imm_s(word))

    if opcode == OPCODE_BRANCH:                               # B형 분기
        name = BRANCH_TABLE.get(funct3)
        if name is None:
            return None
        return Instruction(name, rs1=rs1, rs2=rs2, imm=imm_b(word))

    if opcode == OPCODE_LUI:                                  # U형 lui
        return Instruction("lui", rd=rd, imm=imm_u(word))

    return None                                               # 지원하지 않는 opcode
