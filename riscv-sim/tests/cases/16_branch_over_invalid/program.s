# 16_branch_over_invalid
# 목적: invalid 판정은 적재 시점이 아니라 fetch 시점에 한다. 분기로 건너뛴 invalid 워드는 종료를 일으키지 않는다.
#
# 주소        기계어      어셈블리
0x00040000  0x100000b7  lui  x1, 0x10000
0x00040004  0x00100113  addi x2, x0, 1
0x00040008  0x00000663  beq  x0, x0, skip     # 항상 분기 -> 0x00040014
0x0004000c  0x00000000  .word 0x00000000      # fetch 되지 않음
0x00040010  0xffffffff  .word 0xffffffff      # fetch 되지 않음
0x00040014  0x0020a023  skip: sw  x2, 0(x1)        # [0] = 1
0x00040018  0x0000006f  jal  x0, 0            # 0x00040018: 0x0000006f (jal 은 미지원 -> 종료, 실행되면 무한 루프)
0x0004001c  0x00000000  .word 0               # text 마지막 워드
