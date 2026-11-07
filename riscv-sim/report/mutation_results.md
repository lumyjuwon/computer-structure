| 심은 버그 | 파일 | 실패한 테스트 수 | 실패한 테스트(일부) |
|---|---|---|---|
| blt 를 부호 없는 비교로 구현 | rvsim/cpu.py | 1 | 14_blt_bge_signed |
| bge 를 부호 없는 비교로 구현 | rvsim/cpu.py | 2 | 14_blt_bge_signed, 20_bubble_sort |
| bne 조건 반전 | rvsim/cpu.py | 7 | 08_wrap_compare, 13_beq_bne, 17_loop_sum, 18_fibonacci 외 3개 |
| 분기 목표를 PC+4 기준으로 계산 | rvsim/cpu.py | 10 | 08_wrap_compare, 14_blt_bge_signed, 15_branch_far_offsets, 16_branch_over_invalid 외 6개 |
| x0 쓰기 보호 누락 | rvsim/cpu.py | 1 | 03_x0_hardwired |
| 레지스터 값을 32비트로 자르지 않음 | rvsim/cpu.py | 1 | 08_wrap_compare |
| andi/ori 즉시값을 부호 확장하지 않음(하위 12비트만) | rvsim/cpu.py | 1 | 06_logic |
| lui 값을 한 번 더 12비트 시프트 | rvsim/cpu.py | 32 | 01_spec_example, 03_x0_hardwired, 04_add_sub_wrap, 05_addi_imm 외 28개 |
| lw 에서 오프셋 무시 | rvsim/cpu.py | 6 | 09_lw_sw_endian, 10_sw_lw_imm_split, 12_data_partial, 19_multiply_signed 외 2개 |
| sw 가 rs2 대신 rs1 을 저장 | rvsim/cpu.py | 31 | 01_spec_example, 03_x0_hardwired, 04_add_sub_wrap, 05_addi_imm 외 27개 |
| 종료 시 fetch PC 대신 PC+4 출력 | rvsim/cpu.py | 33 | 01_spec_example, 02_immediate_invalid, 03_x0_hardwired, 04_add_sub_wrap 외 29개 |
| 실행 한도 비교를 > 로 (1,000,001 개 허용) | rvsim/cpu.py | 1 | 34_limit_plus_one |
| 실행 한도 검사를 invalid 판별보다 먼저 수행 | rvsim/cpu.py | 1 | 33_limit_exact |
| I형 즉시값 부호 확장 누락 | rvsim/decoder.py | 14 | 04_add_sub_wrap, 05_addi_imm, 06_logic, 07_lui 외 10개 |
| S형 즉시값 imm[4:0] 누락 | rvsim/decoder.py | 14 | 03_x0_hardwired, 04_add_sub_wrap, 05_addi_imm, 06_logic 외 10개 |
| B형 즉시값 imm[11](bit 7) 누락 | rvsim/decoder.py | 8 | 15_branch_far_offsets, 17_loop_sum, 18_fibonacci, 19_multiply_signed 외 4개 |
| B형 즉시값을 12비트로 부호 확장 | rvsim/decoder.py | 1 | 15_branch_far_offsets |
| R형 funct7 검사 누락 (sub 외에는 add 로 간주) | rvsim/decoder.py | 1 | 22_invalid_mul |
| sub 를 add 로 해독 | rvsim/decoder.py | 1 | 04_add_sub_wrap |
| lw 의 funct3 검사 누락 | rvsim/decoder.py | 1 | 27_invalid_lb |
| sw 의 funct3 검사 누락 | rvsim/decoder.py | 1 | 28_invalid_sh |
| I형 연산 funct3 검사 누락 (모르는 funct3 를 addi 로) | rvsim/decoder.py | 1 | 26_invalid_slli |
| bltu/bgeu 를 blt/bge 로 해독 | rvsim/decoder.py | 1 | 29_invalid_bltu |
| little-endian 대신 big-endian 으로 읽기 | rvsim/memory.py | 39 | 01_spec_example, 03_x0_hardwired, 04_add_sub_wrap, 05_addi_imm 외 35개 |
| data.out 을 텍스트 모드로 저장 | rvsim/memory.py | 6 | 02_immediate_invalid, 11_data_empty, 13_beq_bne, 17_loop_sum 외 2개 |
| data.out 을 1,020 바이트만 저장 | rvsim/memory.py | 33 | 01_spec_example, 02_immediate_invalid, 03_x0_hardwired, 04_add_sub_wrap 외 29개 |
| 표준 출력을 텍스트 모드 print 로 출력 | sim.py | 33 | 01_spec_example, 02_immediate_invalid, 03_x0_hardwired, 04_add_sub_wrap 외 29개 |
| 16진수를 대문자로 출력 | sim.py | 14 | 05_addi_imm, 06_logic, 08_wrap_compare, 09_lw_sw_endian 외 10개 |
| 16진수 선행 0 생략 | sim.py | 33 | 01_spec_example, 02_immediate_invalid, 03_x0_hardwired, 04_add_sub_wrap 외 29개 |
