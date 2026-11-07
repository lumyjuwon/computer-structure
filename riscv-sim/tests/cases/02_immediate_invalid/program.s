# 02_immediate_invalid
# 목적: 첫 명령어가 invalid. 아무것도 실행하지 않고 PC 0x00040000 을 출력하며, data.out 은 data.bin 1,024 바이트와 완전히 같아야 한다(0x0a, 0x0d, 0x1a 바이트 포함).
#
# 주소        기계어      어셈블리
0x00040000  0x00000000  .word 0x00000000      # 0x00040000: 첫 fetch 부터 invalid
