# 08_wrap_compare
# 목적: 레지스터 값이 항상 32비트 비트 패턴인지 확인. addi 로 만든 -1 과 lw 로 읽은 0xffffffff 는 같은 값이어야 하고(beq 분기), 0xffffffff + 1 은 0 이어야 한다. (32비트로 자르지 않으면 sw 결과는 우연히 맞아도 beq/bne 비교가 틀어진다. 버그 시 x10 = 3)
#
# 주소        기계어      어셈블리
0x00040000  0x100000b7  lui  x1, 0x10000
0x00040004  0x0000a103  lw   x2, 0(x1)        # 0xffffffff (메모리에서 읽음)
0x00040008  0xfff00193  addi x3, x0, -1       # 0 + (-1) -> 0xffffffff (연산 결과)
0x0004000c  0x00000513  addi x10, x0, 0
0x00040010  0x00310463  beq  x2, x3, A        # 같은 비트 패턴 -> 분기 (bit0 안 켜짐)
0x00040014  0x00156513  ori  x10, x10, 1
0x00040018  0x00110213  A:   addi x4, x2, 1        # 0xffffffff + 1 = 0x1_00000000 -> 0x00000000
0x0004001c  0x00020463  beq  x4, x0, B        # 0 == 0 -> 분기 (bit1 안 켜짐)
0x00040020  0x00256513  ori  x10, x10, 2
0x00040024  0x002102b3  B:   add  x5, x2, x2       # 0x1_fffffffe -> 0xfffffffe
0x00040028  0xfffff337  lui  x6, 0xfffff      # 0xfffff000
0x0004002c  0xffe36313  ori  x6, x6, -2       # 0xfffff000 | 0xfffffffe = 0xfffffffe
0x00040030  0x00629463  bne  x5, x6, C        # 같음 -> 진행 (bit2 켜짐)
0x00040034  0x00456513  ori  x10, x10, 4
0x00040038  0x00a0a223  C:   sw   x10, 4(x1)       # x10 = 4
0x0004003c  0x00000000  .word 0               # 0x0004003c
