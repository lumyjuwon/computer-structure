"""자체 테스트 케이스 정의: 프로그램(어셈블리), data.bin, 손으로 도출한 기대 결과.

기대 결과는 시뮬레이터 실행 결과를 복사한 것이 아니라, 각 명령어의 의미에 따라
직접 계산한 값이다. 계산 근거를 각 줄의 주석에 적었다.

필드
  name          : 케이스 이름 (tests/cases/<name>/ 디렉터리)
  purpose       : 테스트 목적
  source        : 어셈블리 소스 (tests/asm.py 문법). 0x00040000 부터 배치
  data          : data.bin 내용 (bytes)
  stdout        : 기대 표준 출력 한 줄 (비정상 종료면 "")
  expect_words  : {data 오프셋: 32비트 값} - 실행 후 바뀌는 워드 (나머지는 data.bin 그대로)
  expect_bytes  : {data 오프셋: "16진 바이트열"} - 바이트 단위로 확인할 위치
  exit_code     : 기대 종료 코드 (0 정상, 2 실행 한도 초과, 3 범위·정렬 위반)
  check_text    : (선택) text.bin 이 이 바이트열과 같아야 함 (명세 예시 대조)
"""

import struct

DATA_SIZE = 1024


def words(*values):
    """32비트 값들을 little-endian data.bin 바이트열로 만든다."""
    return b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in values)


def line(pc, word):
    return "PC 0x%08x invalid instruction 0x%08x\n" % (pc, word)


CASES = []


def case(name, purpose, source, data=b"", stdout="", expect_words=None,
         expect_bytes=None, exit_code=0, check_text=None):
    CASES.append(dict(name=name, purpose=purpose, source=source, data=data,
                      stdout=stdout, expect_words=expect_words or {},
                      expect_bytes=expect_bytes or {}, exit_code=exit_code,
                      check_text=check_text))


# ---------------------------------------------------------------------------
# 1. 명세 예시와 기본 입출력
# ---------------------------------------------------------------------------
case("01_spec_example",
     "명세 7절 예시를 그대로 재현한다. text.bin 바이트열까지 명세와 대조한다.",
     """
     lui  x1, 0x10000      # x1 = 0x10000 << 12 = 0x10000000
     addi x2, x0, 7        # x2 = 7
     addi x3, x0, 5        # x3 = 5
     add  x4, x2, x3       # x4 = 12 = 0x0000000c
     sw   x4, 0(x1)        # [0x10000000] = 0x0000000c -> 바이트 0c 00 00 00
     .word 0x00000000      # 0x00040014: invalid -> 종료
     """,
     data=bytes(DATA_SIZE),
     stdout=line(0x00040014, 0x00000000),
     expect_bytes={0: "0c000000"},
     check_text=bytes.fromhex("b7000010 13017000 93015000 33023100 23a04000 00000000"))

case("02_immediate_invalid",
     "첫 명령어가 invalid. 아무것도 실행하지 않고 PC 0x00040000 을 출력하며, "
     "data.out 은 data.bin 1,024 바이트와 완전히 같아야 한다(0x0a, 0x0d, 0x1a 바이트 포함).",
     """
     .word 0x00000000      # 0x00040000: 첫 fetch 부터 invalid
     """,
     data=bytes((i * 7 + 3) & 0xFF for i in range(DATA_SIZE)),
     stdout=line(0x00040000, 0x00000000))

# ---------------------------------------------------------------------------
# 2. 레지스터·산술·논리·즉시값
# ---------------------------------------------------------------------------
case("03_x0_hardwired",
     "x0 에 대한 쓰기(addi, lui, add, sub, lw)가 모두 무시되고 x0 를 읽으면 항상 0 인지 확인.",
     """
     lui  x1, 0x10000      # x1 = 0x10000000
     addi x0, x0, 5        # 무시
     lui  x0, 0xfffff      # 무시
     addi x2, x0, 7        # x2 = 0 + 7 = 7
     add  x0, x2, x2       # 무시
     sub  x0, x0, x2       # 무시
     lw   x0, 0(x1)        # 메모리 값 0x11223344 를 읽지만 무시
     sw   x0, 4(x1)        # [+4] = 0 (0xdeadbeef 를 덮어씀)
     add  x3, x0, x2       # x3 = 0 + 7 = 7
     sw   x3, 8(x1)        # [+8] = 7 (0xffffffff 를 덮어씀)
     .word 0               # 0x00040028
     """,
     data=words(0x11223344, 0xDEADBEEF, 0xFFFFFFFF),
     stdout=line(0x00040028, 0),
     expect_words={4: 0x00000000, 8: 0x00000007})

case("04_add_sub_wrap",
     "add/sub 결과를 하위 32비트로 유지(오버플로 무시, 음수는 2의 보수)하는지 확인.",
     """
     lui  x1, 0x10000      # x1 = 0x10000000
     lui  x2, 0x80000      # x2 = 0x80000000
     addi x2, x2, -1       # x2 = 0x7fffffff (INT_MAX)
     addi x3, x0, 1        # x3 = 1
     add  x4, x2, x3       # 0x7fffffff + 1 = 0x80000000 (부호 오버플로, 예외 없음)
     sw   x4, 0(x1)
     sub  x5, x0, x3       # 0 - 1 = -1 = 0xffffffff
     sw   x5, 4(x1)
     add  x6, x4, x4       # 0x80000000 * 2 = 0x1_00000000 -> 하위 32비트 0x00000000
     sw   x6, 8(x1)
     add  x7, x5, x5       # 0xffffffff * 2 = 0x1_fffffffe -> 0xfffffffe
     sw   x7, 12(x1)
     sub  x8, x4, x3       # 0x80000000 - 1 = 0x7fffffff
     sw   x8, 16(x1)
     sub  x9, x3, x4       # 1 - 0x80000000 = -2147483647 -> 0x80000001
     sw   x9, 20(x1)
     .word 0               # 0x00040040
     """,
     data=b"\xaa" * 24,
     stdout=line(0x00040040, 0),
     expect_words={0: 0x80000000, 4: 0xFFFFFFFF, 8: 0x00000000,
                   12: 0xFFFFFFFE, 16: 0x7FFFFFFF, 20: 0x80000001})

case("05_addi_imm",
     "I형 12비트 즉시값의 부호 확장과 경계값(-2048, 2047), addi 자리올림 버림 확인.",
     """
     lui  x1, 0x10000
     addi x2, x0, -1       # imm 0xfff -> -1 -> x2 = 0xffffffff
     addi x3, x0, -2048    # imm 0x800 -> -2048 -> 0xfffff800
     addi x4, x0, 2047     # imm 0x7ff -> 0x000007ff
     addi x5, x4, 1        # 0x7ff + 1 = 0x00000800
     addi x6, x2, 1        # 0xffffffff + 1 = 0x1_00000000 -> 0x00000000
     addi x7, x3, -2048    # 0xfffff800 - 0x800 = 0xfffff000
     addi x8, x8, 0x123    # 초기 레지스터 0 -> 0x00000123
     sw   x2, 0(x1)
     sw   x3, 4(x1)
     sw   x4, 8(x1)
     sw   x5, 12(x1)
     sw   x6, 16(x1)
     sw   x7, 20(x1)
     sw   x8, 24(x1)
     .word 0               # 0x0004003c
     """,
     data=b"\xaa" * 28,
     stdout=line(0x0004003C, 0),
     expect_words={0: 0xFFFFFFFF, 4: 0xFFFFF800, 8: 0x000007FF, 12: 0x00000800,
                   16: 0x00000000, 20: 0xFFFFF000, 24: 0x00000123})

case("06_logic",
     "and/or/andi/ori. andi/ori 의 즉시값도 부호 확장됨(-1 -> 0xffffffff, -2048 -> 0xfffff800).",
     """
     lui  x1, 0x10000
     lui  x2, 0x12345
     addi x2, x2, 0x678    # x2 = 0x12345678
     lui  x3, 0xff00f
     addi x3, x3, 0x0f0    # x3 = 0xff00f0f0
     and  x4, x2, x3       # 12&ff 34&00 56&f0 78&f0 = 0x12005070
     or   x5, x2, x3       # 12|ff 34|00 56|f0 78|f0 = 0xff34f6f8
     andi x6, x2, -1       # & 0xffffffff = 0x12345678 (그대로)
     andi x7, x2, 0x7ff    # & 0x000007ff = 0x00000678
     ori  x8, x2, -2048    # | 0xfffff800 = 0xfffffe78
     andi x9, x2, -256     # & 0xffffff00 = 0x12345600
     ori  x10, x0, 0x555   # 0 | 0x555 = 0x00000555
     sw   x4, 0(x1)
     sw   x5, 4(x1)
     sw   x6, 8(x1)
     sw   x7, 12(x1)
     sw   x8, 16(x1)
     sw   x9, 20(x1)
     sw   x10, 24(x1)
     .word 0               # 0x0004004c
     """,
     data=b"\xaa" * 28,
     stdout=line(0x0004004C, 0),
     expect_words={0: 0x12005070, 4: 0xFF34F6F8, 8: 0x12345678, 12: 0x00000678,
                   16: 0xFFFFFE78, 20: 0x12345600, 24: 0x00000555})

case("07_lui",
     "lui 는 imm20<<12 를 쓰고 하위 12비트를 0 으로 만든다. lui+addi 로 32비트 상수 만들기"
     "(하위 12비트가 0x800 이상이면 상위를 +1 하고 음수 addi).",
     """
     lui  x1, 0x10000
     lui  x2, 0xfffff      # 0xfffff000
     lui  x3, 0x1          # 0x00001000
     lui  x4, 0x12346
     addi x4, x4, -1       # 0x12346000 - 1 = 0x12345fff
     lui  x5, 0x80000      # 0x80000000
     lui  x6, 0xdeadc
     addi x6, x6, -0x111   # 0xdeadc000 - 0x111 = 0xdeadbeef
     addi x7, x0, 0x7ff    # x7 = 0x000007ff
     lui  x7, 0x54321      # 하위 비트까지 덮어씀 -> 0x54321000 (0x543217ff 아님)
     sw   x2, 0(x1)
     sw   x3, 4(x1)
     sw   x4, 8(x1)
     sw   x5, 12(x1)
     sw   x6, 16(x1)
     sw   x7, 20(x1)
     .word 0               # 0x00040040
     """,
     data=b"\xaa" * 24,
     stdout=line(0x00040040, 0),
     expect_words={0: 0xFFFFF000, 4: 0x00001000, 8: 0x12345FFF, 12: 0x80000000,
                   16: 0xDEADBEEF, 20: 0x54321000})

case("08_wrap_compare",
     "레지스터 값이 항상 32비트 비트 패턴인지 확인. addi 로 만든 -1 과 lw 로 읽은 0xffffffff 는 "
     "같은 값이어야 하고(beq 분기), 0xffffffff + 1 은 0 이어야 한다. "
     "(32비트로 자르지 않으면 sw 결과는 우연히 맞아도 beq/bne 비교가 틀어진다. 버그 시 x10 = 3)",
     """
     lui  x1, 0x10000
     lw   x2, 0(x1)        # 0xffffffff (메모리에서 읽음)
     addi x3, x0, -1       # 0 + (-1) -> 0xffffffff (연산 결과)
     addi x10, x0, 0
     beq  x2, x3, A        # 같은 비트 패턴 -> 분기 (bit0 안 켜짐)
     ori  x10, x10, 1
A:   addi x4, x2, 1        # 0xffffffff + 1 = 0x1_00000000 -> 0x00000000
     beq  x4, x0, B        # 0 == 0 -> 분기 (bit1 안 켜짐)
     ori  x10, x10, 2
B:   add  x5, x2, x2       # 0x1_fffffffe -> 0xfffffffe
     lui  x6, 0xfffff      # 0xfffff000
     ori  x6, x6, -2       # 0xfffff000 | 0xfffffffe = 0xfffffffe
     bne  x5, x6, C        # 같음 -> 진행 (bit2 켜짐)
     ori  x10, x10, 4
C:   sw   x10, 4(x1)       # x10 = 4
     .word 0               # 0x0004003c
     """,
     data=words(0xFFFFFFFF),
     stdout=line(0x0004003C, 0),
     expect_words={4: 0x00000004})

# ---------------------------------------------------------------------------
# 3. 메모리·바이트 순서
# ---------------------------------------------------------------------------
_endian_data = bytearray(DATA_SIZE)
_endian_data[0:4] = bytes.fromhex("78563412")
_endian_data[4:8] = bytes.fromhex("efbeadde")
_endian_data[8:12] = bytes.fromhex("00000080")
_endian_data[1020:1024] = bytes.fromhex("01020304")

case("09_lw_sw_endian",
     "little-endian lw/sw. 78 56 34 12 -> 0x12345678, 저장 시 하위 바이트부터. "
     "데이터 영역 첫 워드(0x10000000)와 마지막 워드(0x100003fc), 음수 오프셋.",
     """
     lui  x1, 0x10000      # x1 = 0x10000000
     lw   x2, 0(x1)        # 78 56 34 12 -> 0x12345678
     lw   x3, 4(x1)        # ef be ad de -> 0xdeadbeef
     lw   x4, 1020(x1)     # 01 02 03 04 -> 0x04030201 (마지막 워드)
     sw   x2, 16(x1)       # [+16] = 78 56 34 12
     addi x5, x1, 1024     # x5 = 0x10000400 (데이터 영역 끝 다음 주소)
     sw   x3, -4(x5)       # [0x100003fc] = ef be ad de
     sw   x4, -1024(x5)    # [0x10000000] = 01 02 03 04
     lw   x6, 8(x1)        # 00 00 00 80 -> 0x80000000
     addi x7, x6, -1       # 0x7fffffff
     sw   x7, 20(x1)       # [+20] = ff ff ff 7f
     .word 0               # 0x0004002c
     """,
     data=bytes(_endian_data),
     stdout=line(0x0004002C, 0),
     expect_bytes={0: "01020304", 4: "efbeadde", 8: "00000080", 16: "78563412",
                   20: "ffffff7f", 1020: "efbeadde"})

case("10_sw_lw_imm_split",
     "S형 즉시값은 imm[11:5]=bit31:25, imm[4:0]=bit11:7 로 나뉜다. 큰 양수(2044)·음수(-516, -1024) "
     "오프셋으로 sw/lw 주소 계산 확인.",
     """
     lui  x1, 0x10000      # 0x10000000
     addi x3, x1, -1024    # x3 = 0x0ffffc00 (데이터 영역 밖이지만 기준 주소로만 사용)
     addi x4, x1, 1024     # x4 = 0x10000400
     lui  x2, 0xa1b2c
     addi x2, x2, 0x3d4    # x2 = 0xa1b2c3d4
     sw   x2, 2044(x3)     # 0x0ffffc00 + 0x7fc = 0x100003fc
     sw   x2, -516(x4)     # 0x10000400 - 0x204 = 0x100001fc
     addi x5, x0, 0x11
     sw   x5, -1024(x4)    # 0x10000400 - 0x400 = 0x10000000
     lw   x6, -4(x4)       # [0x100003fc] = 0xa1b2c3d4
     addi x6, x6, 1        # 0xa1b2c3d5
     sw   x6, 2040(x3)     # 0x0ffffc00 + 0x7f8 = 0x100003f8
     lw   x7, 2044(x3)     # [0x100003fc] = 0xa1b2c3d4
     sw   x7, 4(x1)        # [0x10000004] = 0xa1b2c3d4
     .word 0               # 0x00040038
     """,
     stdout=line(0x00040038, 0),
     expect_words={0x000: 0x00000011, 0x004: 0xA1B2C3D4, 0x1FC: 0xA1B2C3D4,
                   0x3F8: 0xA1B2C3D5, 0x3FC: 0xA1B2C3D4})

case("11_data_empty",
     "data.bin 이 0 바이트여도 데이터 영역 1,024 바이트는 0 으로 초기화되고 data.out 은 1,024 바이트. "
     "0x0a/0x0d 바이트를 바이너리로 정확히 기록하는지(텍스트 모드 줄바꿈 변환 금지) 확인.",
     """
     lui  x1, 0x10000
     lw   x2, 512(x1)      # 초기화된 0
     addi x2, x2, 0x0d     # 0x0000000d
     sw   x2, 0(x1)        # 0d 00 00 00
     addi x3, x0, 0x0a
     sw   x3, 1020(x1)     # 0a 00 00 00 (마지막 워드)
     lui  x4, 0x0a0d1      # 하위 12비트 0xa0d >= 0x800 이므로 상위 +1
     addi x4, x4, -0x5f3   # 0x0a0d1000 - 0x5f3 = 0x0a0d0a0d
     sw   x4, 4(x1)        # 0d 0a 0d 0a
     .word 0               # 0x00040024
     """,
     data=b"",
     stdout=line(0x00040024, 0),
     expect_bytes={0: "0d000000", 4: "0d0a0d0a", 1020: "0a000000"})

case("12_data_partial",
     "data.bin 이 6 바이트(4의 배수 아님)일 때 나머지는 0. 01 02 03 04 05 06 00 00 ...",
     """
     lui  x1, 0x10000
     lw   x2, 4(x1)        # 05 06 00 00 -> 0x00000605
     sw   x2, 8(x1)
     lw   x3, 0(x1)        # 01 02 03 04 -> 0x04030201
     sw   x3, 12(x1)
     .word 0               # 0x00040014
     """,
     data=bytes.fromhex("010203040506"),
     stdout=line(0x00040014, 0),
     expect_bytes={0: "0102030405060000", 8: "0506000001020304"})

# ---------------------------------------------------------------------------
# 4. 분기·PC 갱신
# ---------------------------------------------------------------------------
case("13_beq_bne",
     "beq/bne 의 분기/비분기. 분기하면 다음 ori 를 건너뛴다. x10 비트가 1 = 그 ori 가 실행됨.",
     """
     lui  x1, 0x10000
     addi x2, x0, 5
     addi x3, x0, 5
     addi x4, x0, 7
     addi x10, x0, 0
     beq  x2, x3, L1       # 5 == 5 -> 분기 (bit0 안 켜짐)
     ori  x10, x10, 1
L1:  beq  x2, x4, L2       # 5 == 7 거짓 -> 진행 (bit1 켜짐)
     ori  x10, x10, 2
L2:  bne  x2, x4, L3       # 5 != 7 -> 분기 (bit2 안 켜짐)
     ori  x10, x10, 4
L3:  bne  x2, x3, L4       # 5 != 5 거짓 -> 진행 (bit3 켜짐)
     ori  x10, x10, 8
L4:  sw   x10, 0(x1)       # x10 = 2 | 8 = 0x0a
     .word 0               # 0x00040038
     """,
     stdout=line(0x00040038, 0),
     expect_words={0: 0x0000000A})

case("14_blt_bge_signed",
     "blt/bge 는 부호 있는 비교. 0xffffffff(-1) < 1 이므로 blt 분기. INT_MIN/INT_MAX, 같은 값. "
     "(부호 없는 비교로 잘못 구현하면 결과가 0x99 가 된다.)",
     """
     lui  x1, 0x10000
     addi x2, x0, -1       # 0xffffffff = -1
     addi x3, x0, 1        # 1
     lui  x4, 0x80000      # 0x80000000 = INT_MIN
     addi x5, x4, -1       # 0x7fffffff = INT_MAX
     addi x10, x0, 0
     blt  x2, x3, A        # -1 < 1 참 -> 분기
     ori  x10, x10, 1
A:   bge  x2, x3, B        # -1 >= 1 거짓 -> 진행: bit1
     ori  x10, x10, 2
B:   blt  x3, x2, C        # 1 < -1 거짓 -> 진행: bit2
     ori  x10, x10, 4
C:   bge  x3, x2, D        # 1 >= -1 참 -> 분기
     ori  x10, x10, 8
D:   blt  x4, x5, E        # INT_MIN < INT_MAX 참 -> 분기
     ori  x10, x10, 16
E:   bge  x4, x5, F        # INT_MIN >= INT_MAX 거짓 -> 진행: bit5
     ori  x10, x10, 32
F:   bge  x3, x3, G        # 1 >= 1 참(같음) -> 분기
     ori  x10, x10, 64
G:   blt  x3, x3, H        # 1 < 1 거짓 -> 진행: bit7
     ori  x10, x10, 128
H:   sw   x10, 0(x1)       # 2 + 4 + 32 + 128 = 166 = 0xa6
     .word 0               # 0x0004005c
     """,
     stdout=line(0x0004005C, 0),
     expect_words={0: 0x000000A6})

# 14: B형 즉시값의 모든 비트 위치 확인 (+2048: imm[11]=bit7, +2032: imm[10:4], -4096: imm[12]만)
_far = ["lui  x1, 0x10000",
        "addi x10, x0, 0",
        "beq  x0, x0, 16          # 0x00040008 -> 0x00040018 (start)",
        "ori  x10, x10, 4         # 0x0004000c: -4096 분기의 도착점",
        "sw   x10, 0(x1)          # 0x00040010",
        ".word 0                  # 0x00040014: 종료 지점",
        "beq  x0, x0, 2048        # 0x00040018 -> 0x00040818 (imm[11] 이 bit 7 로 감)"]
_far += ["ori  x10, x10, 1         # 건너뛰어야 하는 영역"] * 511       # 0x0004001c ~ 0x00040814
_far += ["ori  x10, x10, 2         # 0x00040818",
         "beq  x0, x0, 2032        # 0x0004081c -> 0x0004100c"]
_far += ["ori  x10, x10, 1         # 건너뛰어야 하는 영역"] * 507       # 0x00040820 ~ 0x00041008
_far += ["beq  x0, x0, -4096       # 0x0004100c -> 0x0004000c (imm[12] 만 1)",
         ".word 0                  # 0x00041010: text 마지막 워드 (도달하지 않음)"]
case("15_branch_far_offsets",
     "B형 즉시값 비트 배치 확인: +2048(imm[11] 이 명령어 bit7), +2032, -4096(최소값). "
     "건너뛴 영역이 하나라도 실행되면 bit0 이 켜진다. 기대 x10 = 2 | 4 = 6.",
     "\n".join(_far),
     stdout=line(0x00040014, 0),
     expect_words={0: 0x00000006})

case("16_branch_over_invalid",
     "invalid 판정은 적재 시점이 아니라 fetch 시점에 한다. 분기로 건너뛴 invalid 워드는 종료를 일으키지 않는다.",
     """
     lui  x1, 0x10000
     addi x2, x0, 1
     beq  x0, x0, skip     # 항상 분기 -> 0x00040014
     .word 0x00000000      # fetch 되지 않음
     .word 0xffffffff      # fetch 되지 않음
skip: sw  x2, 0(x1)        # [0] = 1
     jal  x0, 0            # 0x00040018: 0x0000006f (jal 은 미지원 -> 종료, 실행되면 무한 루프)
     .word 0               # text 마지막 워드
     """,
     stdout=line(0x00040018, 0x0000006F),
     expect_words={0: 0x00000001})

case("17_loop_sum",
     "뒤로 가는 분기(음수 오프셋 -16)로 반복. data 의 1~10 합 = 55 (0x37). 실행 명령어 수 3+5*10+2 = 55.",
     """
     lui  x1, 0x10000      # 포인터
     addi x2, x0, 10       # 반복 횟수
     addi x3, x0, 0        # 합
loop: lw  x4, 0(x1)        # 0x0004000c
     add  x3, x3, x4
     addi x1, x1, 4
     addi x2, x2, -1
     bne  x2, x0, loop     # 0x0004001c -> 0x0004000c (오프셋 -16)
     lui  x5, 0x10000
     sw   x3, 64(x5)       # [0x10000040] = 55
     .word 0               # 0x00040028
     """,
     data=words(*range(1, 11)),
     stdout=line(0x00040028, 0),
     expect_words={64: 55})

case("18_fibonacci",
     "피보나치 F(0)~F(19) 를 데이터 영역에 저장. 레지스터 복사(addi rd, rs, 0)와 반복.",
     """
     lui  x1, 0x10000
     addi x2, x0, 0        # a = F(0)
     addi x3, x0, 1        # b = F(1)
     addi x4, x0, 20       # 20 개
loop: sw  x2, 0(x1)
     add  x5, x2, x3       # a + b
     addi x2, x3, 0        # a = b
     addi x3, x5, 0        # b = a + b
     addi x1, x1, 4
     addi x4, x4, -1
     bne  x4, x0, loop
     .word 0               # 0x0004002c
     """,
     stdout=line(0x0004002C, 0),
     expect_words={4 * i: v for i, v in enumerate(
         [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597,
          2584, 4181])})

case("19_multiply_signed",
     "반복 덧셈 곱셈 (-3) * 7 = -21 = 0xffffffeb. blt x0, x3 (0 < count, 부호 비교) 루프.",
     """
     lui  x1, 0x10000
     lw   x2, 0(x1)        # -3 = 0xfffffffd
     lw   x3, 4(x1)        # 7
     addi x4, x0, 0
loop: add x4, x4, x2       # 0x00040010
     addi x3, x3, -1
     blt  x0, x3, loop     # 0 < x3 이면 반복
     sw   x4, 8(x1)        # -21 = 0xffffffeb
     .word 0               # 0x00040020
     """,
     data=words(0xFFFFFFFD, 7),
     stdout=line(0x00040020, 0),
     expect_words={8: 0xFFFFFFEB})

case("20_bubble_sort",
     "부호 있는 정수 8개 버블 정렬(bge 부호 비교, lw/sw, 이중 루프). "
     "[5,-3,12,0,-7,8,1,-1] -> [-7,-3,-1,0,1,5,8,12].",
     """
     lui  x1, 0x10000      # 배열 시작
     addi x2, x0, 7        # 바깥 루프: 남은 비교 횟수 i = n-1
outer: addi x3, x1, 0      # p = &a[0]
     addi x4, x2, 0        # j = i
inner: lw  x5, 0(x3)       # a[k]
     lw   x6, 4(x3)        # a[k+1]
     bge  x6, x5, noswap   # a[k+1] >= a[k] 이면 교환 안 함 (부호 비교)
     sw   x6, 0(x3)
     sw   x5, 4(x3)
noswap: addi x3, x3, 4
     addi x4, x4, -1
     bne  x4, x0, inner
     addi x2, x2, -1
     bne  x2, x0, outer
     .word 0               # 0x00040038
     """,
     data=words(5, -3, 12, 0, -7, 8, 1, -1),
     stdout=line(0x00040038, 0),
     expect_words={4 * i: v & 0xFFFFFFFF for i, v in enumerate([-7, -3, -1, 0, 1, 5, 8, 12])})

_regs = ["lui  x31, 0x10000       # 기준 주소 레지스터 x31 (rs1 = 31)"]
_regs += ["addi x%d, x0, %d" % (i, i) for i in range(1, 31)]          # rd = 1 ~ 30
_regs += ["sw   x%d, %d(x31)" % (i, 4 * i) for i in range(1, 31)]      # rs2 = 1 ~ 30
_regs += ["sw   x31, 124(x31)       # [124] = 0x10000000 (rs2 = 31)",
          ".word 0                  # 0x000400f8"]
case("21_all_registers",
     "rd/rs1/rs2 필드 5비트 해독: x1~x31 을 모두 쓰고 저장. 기대 [4*i] = i, [124] = 0x10000000.",
     "\n".join(_regs),
     stdout=line(0x000400F8, 0),
     expect_words=dict([(4 * i, i) for i in range(1, 31)] + [(124, 0x10000000)]))

# ---------------------------------------------------------------------------
# 5. invalid instruction 판별: opcode, funct3, funct7 까지 확인
#    공통 구조: 유효 명령어 실행 -> 0x00040014 의 invalid 에서 종료 -> 뒤의 sw 는 실행되지 않음
# ---------------------------------------------------------------------------
_INVALID_TEMPLATE = """
     lui  x1, 0x10000
     addi x2, x0, 3
     addi x3, x0, 4
     add  x4, x2, x3       # 7
     sw   x4, 0(x1)        # [0] = 7 (0xaaaaaaaa 를 덮어씀)
     {invalid}             # 0x00040014: invalid -> 실행하지 않고 종료
     sw   x2, 4(x1)        # 실행되면 안 됨 ([4] 는 0xcafebabe 그대로)
     .word 0
"""

# (이름, 어셈블리, 손으로 계산한 명령어 값, 목적)
_INVALID_CASES = [
    ("22_invalid_mul", "mul x5, x2, x3", 0x023102B3,
     "add 와 opcode·funct3 가 같고 funct7 만 0000001 (RV32M mul). funct7 검사 필수."),
    ("23_invalid_sra", "sra x5, x2, x3", 0x403152B3,
     "funct7=0100000(sub 와 같음) + funct3=101. funct7 만 보고 sub 로 판단하면 안 됨."),
    ("24_invalid_and_funct7", ".word 0x403172b3", 0x403172B3,
     "and(funct3=111) 에 funct7=0100000 을 붙인 값. and/or 도 funct7=0 확인 필요."),
    ("25_invalid_xor", "xor x5, x2, x3", 0x003142B3,
     "R형 opcode 이지만 funct3=100 (지원하지 않는 xor)."),
    ("26_invalid_slli", "slli x5, x2, 3", 0x00311293,
     "I형 연산 opcode(0010011)이지만 funct3=001 (slli)."),
    ("27_invalid_lb", "lb x5, 0(x1)", 0x00008283,
     "load opcode 이지만 funct3=000 (lb). lw 는 funct3=010 만."),
    ("28_invalid_sh", "sh x2, 4(x1)", 0x00209223,
     "store opcode 이지만 funct3=001 (sh). sw 는 funct3=010 만."),
    ("29_invalid_bltu", "bltu x2, x3, 8", 0x00316463,
     "branch opcode 이지만 funct3=110 (bltu, 부호 없는 비교). blt 로 처리하면 안 됨."),
    ("30_invalid_jal", "jal x0, 0", 0x0000006F,
     "지원하지 않는 opcode 1101111 (jal). 실행되면 무한 루프."),
    ("31_invalid_ecall", "ecall", 0x00000073,
     "시스템 호출은 지원 제외 (opcode 1110011)."),
    ("32_invalid_all_ones", ".word 0xffffffff", 0xFFFFFFFF,
     "opcode 1111111 은 어떤 지원 명령어도 아님."),
]
for _name, _asm, _word, _purpose in _INVALID_CASES:
    case(_name, _purpose, _INVALID_TEMPLATE.format(invalid=_asm),
         data=words(0xAAAAAAAA, 0xCAFEBABE),
         stdout=line(0x00040014, _word),
         expect_words={0: 7})

# ---------------------------------------------------------------------------
# 6. 실행 한도 (정상 명령어 최대 1,000,000 개)
# ---------------------------------------------------------------------------
case("33_limit_exact",
     "정확히 1,000,000 개 실행 후 invalid 를 fetch -> 정상 종료. "
     "실행 수 = 2 + 2 * 499999 = 1,000,000 (x1 = 0x7a11f = 499999).",
     """
     lui  x1, 0x7a         # 0x0007a000 = 499712
     addi x1, x1, 0x11f    # + 287 = 499999
loop: addi x1, x1, -1      # 0x00040008
     bne  x1, x0, loop     # 0x0004000c
     .word 0               # 0x00040010: 1,000,001 번째 fetch -> invalid -> 정상 종료
     """,
     stdout=line(0x00040010, 0))

case("34_limit_plus_one",
     "필요한 실행 수가 정확히 1,000,001 개(= 3 + 2 * 499999). 1,000,000 번째로 addi 를 실행한 뒤 "
     "다음 fetch 는 지원 명령어 bne -> 실행하지 않고 비정상 종료(종료 코드 2). "
     "한도 비교를 > 로 잘못 쓰면 bne 까지 실행되어 정상 종료가 되어 버린다.",
     """
     lui  x1, 0x7a
     addi x1, x1, 0x11f    # 499999
     nop                   # 실행 수 +1
loop: addi x1, x1, -1      # 1,000,000 번째 실행 = 마지막 반복의 addi
     bne  x1, x0, loop     # 1,000,001 번째 -> 실행하지 않고 비정상 종료
     .word 0
     """,
     exit_code=2)

case("35_limit_exceeded",
     "x1 = 500000 이면 필요한 실행 수가 1,000,002 개. 1,000,000 개 실행 뒤 다음 fetch(addi)가 "
     "지원 명령어이므로 실행하지 않고 비정상 종료(종료 코드 2, 표준 출력 없음).",
     """
     lui  x1, 0x7a         # 0x0007a000
     addi x1, x1, 0x120    # + 288 = 0x7a120 = 500000
loop: addi x1, x1, -1
     bne  x1, x0, loop
     .word 0
     """,
     exit_code=2)

case("36_infinite_loop",
     "자기 자신으로 분기하는 무한 루프 -> 실행 한도 초과로 비정상 종료(종료 코드 2).",
     """
loop: beq x0, x0, loop     # 오프셋 0
     .word 0
     """,
     exit_code=2)

# ---------------------------------------------------------------------------
# 7. 명세 범위 밖 입력에 대한 방어 동작 (채점 대상 아님, 우리 팀의 설계 결정)
# ---------------------------------------------------------------------------
case("37_err_lw_out_of_range",
     "데이터 영역 밖(0x10000400) lw -> 표준 오류 메시지, 종료 코드 3, 표준 출력 없음.",
     """
     lui  x1, 0x10000
     lw   x2, 1024(x1)     # 0x10000400: 범위 밖
     .word 0
     """,
     exit_code=3)

case("38_err_sw_misaligned",
     "4바이트 정렬되지 않은 sw(0x10000002) -> 종료 코드 3.",
     """
     lui  x1, 0x10000
     sw   x0, 2(x1)
     .word 0
     """,
     exit_code=3)

case("39_err_pc_out_of_text",
     "적재된 text 밖으로 분기(0x00040010) -> fetch 불가, 종료 코드 3.",
     """
     beq  x0, x0, 16       # 0x00040000 -> 0x00040010 (text 는 8 바이트뿐)
     .word 0
     """,
     exit_code=3)

case("40_err_sw_to_text",
     "text segment 쓰기 불가: sw 주소가 0x00040000 -> 종료 코드 3.",
     """
     lui  x1, 0x40         # 0x00040000
     sw   x0, 0(x1)
     .word 0
     """,
     exit_code=3)


def expected_data_out(c):
    """data.bin(1,024 바이트까지 0 으로 채움)에 기대 변경을 적용한 data.out 기대값."""
    image = bytearray(DATA_SIZE)
    image[0:min(len(c["data"]), DATA_SIZE)] = c["data"][0:DATA_SIZE]
    for offset, value in c["expect_words"].items():
        image[offset:offset + 4] = struct.pack("<I", value)
    for offset, hexstr in c["expect_bytes"].items():
        raw = bytes.fromhex(hexstr)
        image[offset:offset + len(raw)] = raw
    return bytes(image)
