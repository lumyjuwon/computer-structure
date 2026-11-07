# 19_multiply_signed
# 목적: 반복 덧셈 곱셈 (-3) * 7 = -21 = 0xffffffeb. blt x0, x3 (0 < count, 부호 비교) 루프.
#
# 주소        기계어      어셈블리
0x00040000  0x100000b7  lui  x1, 0x10000
0x00040004  0x0000a103  lw   x2, 0(x1)        # -3 = 0xfffffffd
0x00040008  0x0040a183  lw   x3, 4(x1)        # 7
0x0004000c  0x00000213  addi x4, x0, 0
0x00040010  0x00220233  loop: add x4, x4, x2       # 0x00040010
0x00040014  0xfff18193  addi x3, x3, -1
0x00040018  0xfe304ce3  blt  x0, x3, loop     # 0 < x3 이면 반복
0x0004001c  0x0040a423  sw   x4, 8(x1)        # -21 = 0xffffffeb
0x00040020  0x00000000  .word 0               # 0x00040020
