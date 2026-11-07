# 28_invalid_sh
# 목적: store opcode 이지만 funct3=001 (sh). sw 는 funct3=010 만.
#
# 주소        기계어      어셈블리
0x00040000  0x100000b7  lui  x1, 0x10000
0x00040004  0x00300113  addi x2, x0, 3
0x00040008  0x00400193  addi x3, x0, 4
0x0004000c  0x00310233  add  x4, x2, x3       # 7
0x00040010  0x0040a023  sw   x4, 0(x1)        # [0] = 7 (0xaaaaaaaa 를 덮어씀)
0x00040014  0x00209223  sh x2, 4(x1)             # 0x00040014: invalid -> 실행하지 않고 종료
0x00040018  0x0020a223  sw   x2, 4(x1)        # 실행되면 안 됨 ([4] 는 0xcafebabe 그대로)
0x0004001c  0x00000000  .word 0
