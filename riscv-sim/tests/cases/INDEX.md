# 자체 테스트 목록

`python tests/gen_tests.py` 가 `tests/cases.py` 로부터 생성한 파일이다. 기대 결과는 `tests/cases.py` 의 주석에 도출 근거가 있다.

| 케이스 | 목적 | 기대 표준 출력 / 종료 코드 |
|---|---|---|
| 01_spec_example | 명세 7절 예시를 그대로 재현한다. text.bin 바이트열까지 명세와 대조한다. | `PC 0x00040014 invalid instruction 0x00000000` |
| 02_immediate_invalid | 첫 명령어가 invalid. 아무것도 실행하지 않고 PC 0x00040000 을 출력하며, data.out 은 data.bin 1,024 바이트와 완전히 같아야 한다(0x0a, 0x0d, 0x1a 바이트 포함). | `PC 0x00040000 invalid instruction 0x00000000` |
| 03_x0_hardwired | x0 에 대한 쓰기(addi, lui, add, sub, lw)가 모두 무시되고 x0 를 읽으면 항상 0 인지 확인. | `PC 0x00040028 invalid instruction 0x00000000` |
| 04_add_sub_wrap | add/sub 결과를 하위 32비트로 유지(오버플로 무시, 음수는 2의 보수)하는지 확인. | `PC 0x00040040 invalid instruction 0x00000000` |
| 05_addi_imm | I형 12비트 즉시값의 부호 확장과 경계값(-2048, 2047), addi 자리올림 버림 확인. | `PC 0x0004003c invalid instruction 0x00000000` |
| 06_logic | and/or/andi/ori. andi/ori 의 즉시값도 부호 확장됨(-1 -> 0xffffffff, -2048 -> 0xfffff800). | `PC 0x0004004c invalid instruction 0x00000000` |
| 07_lui | lui 는 imm20<<12 를 쓰고 하위 12비트를 0 으로 만든다. lui+addi 로 32비트 상수 만들기(하위 12비트가 0x800 이상이면 상위를 +1 하고 음수 addi). | `PC 0x00040040 invalid instruction 0x00000000` |
| 08_wrap_compare | 레지스터 값이 항상 32비트 비트 패턴인지 확인. addi 로 만든 -1 과 lw 로 읽은 0xffffffff 는 같은 값이어야 하고(beq 분기), 0xffffffff + 1 은 0 이어야 한다. (32비트로 자르지 않으면 sw 결과는 우연히 맞아도 beq/bne 비교가 틀어진다. 버그 시 x10 = 3) | `PC 0x0004003c invalid instruction 0x00000000` |
| 09_lw_sw_endian | little-endian lw/sw. 78 56 34 12 -> 0x12345678, 저장 시 하위 바이트부터. 데이터 영역 첫 워드(0x10000000)와 마지막 워드(0x100003fc), 음수 오프셋. | `PC 0x0004002c invalid instruction 0x00000000` |
| 10_sw_lw_imm_split | S형 즉시값은 imm[11:5]=bit31:25, imm[4:0]=bit11:7 로 나뉜다. 큰 양수(2044)·음수(-516, -1024) 오프셋으로 sw/lw 주소 계산 확인. | `PC 0x00040038 invalid instruction 0x00000000` |
| 11_data_empty | data.bin 이 0 바이트여도 데이터 영역 1,024 바이트는 0 으로 초기화되고 data.out 은 1,024 바이트. 0x0a/0x0d 바이트를 바이너리로 정확히 기록하는지(텍스트 모드 줄바꿈 변환 금지) 확인. | `PC 0x00040024 invalid instruction 0x00000000` |
| 12_data_partial | data.bin 이 6 바이트(4의 배수 아님)일 때 나머지는 0. 01 02 03 04 05 06 00 00 ... | `PC 0x00040014 invalid instruction 0x00000000` |
| 13_beq_bne | beq/bne 의 분기/비분기. 분기하면 다음 ori 를 건너뛴다. x10 비트가 1 = 그 ori 가 실행됨. | `PC 0x00040038 invalid instruction 0x00000000` |
| 14_blt_bge_signed | blt/bge 는 부호 있는 비교. 0xffffffff(-1) < 1 이므로 blt 분기. INT_MIN/INT_MAX, 같은 값. (부호 없는 비교로 잘못 구현하면 결과가 0x99 가 된다.) | `PC 0x0004005c invalid instruction 0x00000000` |
| 15_branch_far_offsets | B형 즉시값 비트 배치 확인: +2048(imm[11] 이 명령어 bit7), +2032, -4096(최소값). 건너뛴 영역이 하나라도 실행되면 bit0 이 켜진다. 기대 x10 = 2 \| 4 = 6. | `PC 0x00040014 invalid instruction 0x00000000` |
| 16_branch_over_invalid | invalid 판정은 적재 시점이 아니라 fetch 시점에 한다. 분기로 건너뛴 invalid 워드는 종료를 일으키지 않는다. | `PC 0x00040018 invalid instruction 0x0000006f` |
| 17_loop_sum | 뒤로 가는 분기(음수 오프셋 -16)로 반복. data 의 1~10 합 = 55 (0x37). 실행 명령어 수 3+5*10+2 = 55. | `PC 0x00040028 invalid instruction 0x00000000` |
| 18_fibonacci | 피보나치 F(0)~F(19) 를 데이터 영역에 저장. 레지스터 복사(addi rd, rs, 0)와 반복. | `PC 0x0004002c invalid instruction 0x00000000` |
| 19_multiply_signed | 반복 덧셈 곱셈 (-3) * 7 = -21 = 0xffffffeb. blt x0, x3 (0 < count, 부호 비교) 루프. | `PC 0x00040020 invalid instruction 0x00000000` |
| 20_bubble_sort | 부호 있는 정수 8개 버블 정렬(bge 부호 비교, lw/sw, 이중 루프). [5,-3,12,0,-7,8,1,-1] -> [-7,-3,-1,0,1,5,8,12]. | `PC 0x00040038 invalid instruction 0x00000000` |
| 21_all_registers | rd/rs1/rs2 필드 5비트 해독: x1~x31 을 모두 쓰고 저장. 기대 [4*i] = i, [124] = 0x10000000. | `PC 0x000400f8 invalid instruction 0x00000000` |
| 22_invalid_mul | add 와 opcode·funct3 가 같고 funct7 만 0000001 (RV32M mul). funct7 검사 필수. | `PC 0x00040014 invalid instruction 0x023102b3` |
| 23_invalid_sra | funct7=0100000(sub 와 같음) + funct3=101. funct7 만 보고 sub 로 판단하면 안 됨. | `PC 0x00040014 invalid instruction 0x403152b3` |
| 24_invalid_and_funct7 | and(funct3=111) 에 funct7=0100000 을 붙인 값. and/or 도 funct7=0 확인 필요. | `PC 0x00040014 invalid instruction 0x403172b3` |
| 25_invalid_xor | R형 opcode 이지만 funct3=100 (지원하지 않는 xor). | `PC 0x00040014 invalid instruction 0x003142b3` |
| 26_invalid_slli | I형 연산 opcode(0010011)이지만 funct3=001 (slli). | `PC 0x00040014 invalid instruction 0x00311293` |
| 27_invalid_lb | load opcode 이지만 funct3=000 (lb). lw 는 funct3=010 만. | `PC 0x00040014 invalid instruction 0x00008283` |
| 28_invalid_sh | store opcode 이지만 funct3=001 (sh). sw 는 funct3=010 만. | `PC 0x00040014 invalid instruction 0x00209223` |
| 29_invalid_bltu | branch opcode 이지만 funct3=110 (bltu, 부호 없는 비교). blt 로 처리하면 안 됨. | `PC 0x00040014 invalid instruction 0x00316463` |
| 30_invalid_jal | 지원하지 않는 opcode 1101111 (jal). 실행되면 무한 루프. | `PC 0x00040014 invalid instruction 0x0000006f` |
| 31_invalid_ecall | 시스템 호출은 지원 제외 (opcode 1110011). | `PC 0x00040014 invalid instruction 0x00000073` |
| 32_invalid_all_ones | opcode 1111111 은 어떤 지원 명령어도 아님. | `PC 0x00040014 invalid instruction 0xffffffff` |
| 33_limit_exact | 정확히 1,000,000 개 실행 후 invalid 를 fetch -> 정상 종료. 실행 수 = 2 + 2 * 499999 = 1,000,000 (x1 = 0x7a11f = 499999). | `PC 0x00040010 invalid instruction 0x00000000` |
| 34_limit_plus_one | 필요한 실행 수가 정확히 1,000,001 개(= 3 + 2 * 499999). 1,000,000 번째로 addi 를 실행한 뒤 다음 fetch 는 지원 명령어 bne -> 실행하지 않고 비정상 종료(종료 코드 2). 한도 비교를 > 로 잘못 쓰면 bne 까지 실행되어 정상 종료가 되어 버린다. | 표준 출력 없음, 종료 코드 2 |
| 35_limit_exceeded | x1 = 500000 이면 필요한 실행 수가 1,000,002 개. 1,000,000 개 실행 뒤 다음 fetch(addi)가 지원 명령어이므로 실행하지 않고 비정상 종료(종료 코드 2, 표준 출력 없음). | 표준 출력 없음, 종료 코드 2 |
| 36_infinite_loop | 자기 자신으로 분기하는 무한 루프 -> 실행 한도 초과로 비정상 종료(종료 코드 2). | 표준 출력 없음, 종료 코드 2 |
| 37_err_lw_out_of_range | 데이터 영역 밖(0x10000400) lw -> 표준 오류 메시지, 종료 코드 3, 표준 출력 없음. | 표준 출력 없음, 종료 코드 3 |
| 38_err_sw_misaligned | 4바이트 정렬되지 않은 sw(0x10000002) -> 종료 코드 3. | 표준 출력 없음, 종료 코드 3 |
| 39_err_pc_out_of_text | 적재된 text 밖으로 분기(0x00040010) -> fetch 불가, 종료 코드 3. | 표준 출력 없음, 종료 코드 3 |
| 40_err_sw_to_text | text segment 쓰기 불가: sw 주소가 0x00040000 -> 종료 코드 3. | 표준 출력 없음, 종료 코드 3 |
