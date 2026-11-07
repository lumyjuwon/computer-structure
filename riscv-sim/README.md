# RISC-V (RV32I 부분집합) 기능 시뮬레이터

명세서(`시뮬레이터_프로젝트_명세서.pdf`)에 정의된 RV32I 14개 명령어
(add, sub, and, or, addi, andi, ori, lui, lw, sw, beq, bne, blt, bge)를
실행하는 명령줄(CLI) 기능 시뮬레이터입니다.

## 팀원 (11조, 4명)

| 이름 | 학번 | 담당 |
|---|---|---|
| 성주원 | 【작성 필요】 | 【작성 필요】 |
| 김도윤 | 【작성 필요】 | 【작성 필요】 |
| 송윤재 | 【작성 필요】 | 【작성 필요】 |
| 정재운 | 【작성 필요】 | 【작성 필요】 |

## 언어·버전·의존성

| 항목 | 내용 |
|---|---|
| 언어 | Python 3 |
| 지원 버전 | Python 3.8 이상 |
| 확인한 환경 | Windows 11 + Python 3.10.0 / Linux(Docker `python:3.8-slim`, `python:3.13-slim`) |
| 시뮬레이터 의존성 | **없음** (표준 라이브러리만 사용, `pip install` 불필요) |
| 선택 의존성 (테스트·문서 전용) | `unicorn` - 참조 실행기 차등 테스트(`tests/diff_ref_unicorn.py`)에만 사용<br>`markdown` - 보고서 PDF 생성(`report/build_report.py`)에만 사용 |

## 빌드

인터프리터 언어이므로 **빌드 과정이 없습니다.** 소스 그대로 실행합니다.

## 실행

```sh
# Linux / macOS
python3 sim.py <text.bin 경로> <data.bin 경로>

# Windows (python3 명령이 없으면 python 또는 py 사용)
python sim.py <text.bin 경로> <data.bin 경로>
```

- 인수는 정확히 두 개(text 파일 경로, data 파일 경로 순서)입니다.
- `data.out`은 **현재 작업 디렉터리**에 만들어집니다(기존 파일은 덮어씀).
- `sim.py`는 다른 디렉터리에서 경로로 실행해도 됩니다.

```sh
cd tests/cases/01_spec_example
python3 ../../../sim.py text.bin data.bin
# 표준 출력: PC 0x00040014 invalid instruction 0x00000000
# data.out : 1,024 바이트, 첫 4 바이트 0c 00 00 00
```

### 출력

| 출력 | 내용 |
|---|---|
| 표준 출력 | 정상 종료 시 한 줄: `PC 0x%08x invalid instruction 0x%08x` + `\n` (소문자 8자리 16진수) |
| `data.out` | 정상 종료 시 0x10000000 ~ 0x100003FF 의 1,024 바이트 (헤더·줄바꿈 없는 바이너리) |
| 표준 오류 | 경고·오류 메시지 (표준 출력에는 위 한 줄 외에 아무것도 쓰지 않음) |

### 종료 코드

| 코드 | 의미 | 표준 출력 | data.out |
|---|---|---|---|
| 0 | 정상 종료 (invalid instruction fetch) | 한 줄 출력 | 생성 |
| 1 | 인수 개수 오류, 입력 파일 읽기 실패, data.out 쓰기 실패 | 없음 | 생성 안 함 |
| 2 | 실행 한도 초과 (정상 명령어 1,000,000 개 실행 후 다음 fetch 도 지원 명령어) | 없음 | 생성 안 함 |
| 3 | 명세 범위 밖 동작 (text 밖 fetch, lw/sw 의 데이터 영역 밖·비정렬 접근) | 없음 | 생성 안 함 |

## 테스트

```sh
python3 tests/run_tests.py        # 자체 테스트 40개 + CLI 오류 처리 4개 (바이트 단위 비교)
python3 tests/test_units.py       # 단위 테스트 (해독, 즉시값, 메모리, 실행 규칙)
python3 tests/mutation_test.py    # 변이 테스트: 일부러 넣은 버그 29종을 테스트가 잡는지 확인 (약 2분)
python3 tests/gen_tests.py        # tests/cases.py 로부터 테스트 입출력 파일 재생성

# (선택) 참조 실행기 Unicorn 과의 차등 테스트 - 테스트 전용
pip install unicorn
python3 tests/diff_ref_unicorn.py --programs 3000
```

다른 실행 명령을 테스트하려면: `python3 tests/run_tests.py --sim "python3 /경로/sim.py"`

## 디버깅 도구 (채점 출력과 무관)

```sh
python3 tools/trace.py text.bin data.bin      # 명령어별 PC·기계어·디스어셈블·변경값 + 레지스터 덤프
python3 tools/trace.py text.bin --disasm      # text.bin 디스어셈블
```

## 파일 배치

```
riscv-sim/
├── README.md               이 파일
├── sim.py                  실행 진입점: 인수 처리, 파일 읽기, 종료 출력(표준 출력 한 줄, data.out)
├── rvsim/                  시뮬레이터 본체
│   ├── bits.py             32비트 자르기, 부호 해석, 부호 확장, 비트 필드 추출
│   ├── memory.py           text/data 영역, little-endian 읽기·쓰기, 바이너리 파일 입출력
│   ├── decoder.py          명령어 해독, 즉시값(I/S/B/U), invalid instruction 판별
│   └── cpu.py              레지스터·PC, fetch -> decode -> execute 루프, 14개 명령어 실행
├── tests/
│   ├── asm.py              테스트 입력 생성용 미니 어셈블러 (rvsim 과 독립된 인코더)
│   ├── cases.py            테스트 케이스 정의 (프로그램, data.bin, 손으로 도출한 기대 결과와 근거)
│   ├── gen_tests.py        cases.py -> tests/cases/<이름>/ 파일 생성
│   ├── run_tests.py        별도 프로세스로 sim.py 실행, 표준 출력·data.out 바이트 비교
│   ├── test_units.py       단위 테스트
│   ├── mutation_test.py    변이 테스트
│   ├── diff_ref_unicorn.py (선택) 참조 실행기 차등 테스트
│   └── cases/              생성된 테스트 입출력 (INDEX.md 에 목록)
│       └── <이름>/         program.s, text.bin, data.bin, expected_stdout.txt,
│                           expected_data.out, expected_exit_code.txt
├── tools/
│   └── trace.py            디버깅용 실행 추적·레지스터 덤프
└── report/
    ├── report.md           보고서 원본
    ├── build_report.py     report.md -> report.pdf 변환
    ├── report.pdf          제출용 보고서
    ├── mutation_results.md 변이 테스트 결과표 (보고서 부록 B 에 삽입)
    └── team_photo.jpg      팀 사진 【추가 필요】
```

## 명세에 정의되지 않은 동작에 대한 팀 결정

| 상황 | 동작 |
|---|---|
| 실행 한도 초과 | 표준 출력 없음, 표준 오류에 PC·명령어 값, 종료 코드 2, data.out 생성 안 함 |
| 비정상 종료(코드 1~3) 시 이미 있던 data.out | 건드리지 않음 → **이전 실행의 data.out 이 남아 있을 수 있으므로** 종료 코드 0 일 때만 data.out 을 결과로 본다 |
| text 영역 밖 fetch, 비정렬 PC | 표준 오류 메시지, 종료 코드 3 |
| lw/sw 주소가 데이터 영역 밖이거나 4의 배수가 아님 (text 영역 쓰기 포함) | 표준 오류 메시지, 종료 코드 3 |
| text.bin 크기가 0 이거나 4의 배수가 아님 | 표준 오류에 경고 후 계속 실행 (마지막 불완전 워드는 fetch 불가) |
| data.bin 이 1,024 바이트 초과 | 표준 오류에 경고, 앞 1,024 바이트만 적재 |
