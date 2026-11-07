# 22_invalid_mul
# 목적: add 와 opcode·funct3 가 같고 funct7 만 0000001 (RV32M mul). funct7 검사 필수.
#
# 주소        기계어      어셈블리
0x00040000  0x100000b7  lui  x1, 0x10000
0x00040004  0x00300113  addi x2, x0, 3
0x00040008  0x00400193  addi x3, x0, 4
0x0004000c  0x00310233  add  x4, x2, x3       # 7
0x00040010  0x0040a023  sw   x4, 0(x1)        # [0] = 7 (0xaaaaaaaa 를 덮어씀)
0x00040014  0x023102b3  mul x5, x2, x3             # 0x00040014: invalid -> 실행하지 않고 종료
0x00040018  0x0020a223  sw   x2, 4(x1)        # 실행되면 안 됨 ([4] 는 0xcafebabe 그대로)
0x0004001c  0x00000000  .word 0
