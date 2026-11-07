# CLAUDE.md - 11조 RISC-V 시뮬레이터 프로젝트

컴퓨터 구조 과목 팀 프로젝트. `시뮬레이터_프로젝트_명세서.pdf`(7쪽)가 요구하는 RV32I 14개 명령어 기능 시뮬레이터를 구현한다.
팀은 **11조**, 4명: 성주원, 김도윤, 송윤재, 정재운 (학번·역할 미기입). 2026-11-08에 Claude Code(Claude Opus 5.5)로 대부분 생성했다.

## 폴더 구조

```
computer-structure/
├── 시뮬레이터_프로젝트_명세서.pdf   명세서 원본 (기준 문서)
├── CLAUDE.md                      이 파일
├── 직접_해야_할_일.md               팀이 해야 할 일 + 명세서 충족 점검표 (제출 X)
├── riscv-sim/                     ★ 제출 폴더 (이 폴더 전체를 제출)
│   ├── sim.py                     진입점: 인수, 파일 읽기, 종료 출력 (채점 대상)
│   ├── rvsim/                     본체 (채점 대상): bits.py, memory.py, decoder.py, cpu.py
│   ├── README.md                  팀원·언어·의존성·실행·파일 배치·팀 결정
│   ├── tests/                     asm.py, cases.py, gen_tests.py, run_tests.py, test_units.py,
│   │                              mutation_test.py, diff_ref_unicorn.py, cases/<40개>/
│   ├── tools/trace.py             디버깅용 실행 추적 (채점 출력과 무관)
│   └── report/                    report.md → build_report.py → report.pdf, mutation_results.md
└── study/                         시험 대비 (제출 X, 시험장 반입 X)
    ├── 시험대비_정리.md / .pdf
    ├── source_listing_core.pdf / source_listing_all.pdf   줄 번호 인쇄본
    └── build_pdfs.py
```

**study/와 직접_해야_할_일.md는 절대 제출 폴더에 넣지 않는다.** 명세 9절: 시험장에는 소스 인쇄본만 가져갈 수 있고 예상 답안·메모는 금지다.

## 명세 핵심 (외울 것)

| 항목 | 값 |
|---|---|
| 명령어 | add, sub, and, or, addi, andi, ori, lui, lw, sw, beq, bne, blt, bge (14개만) |
| 초기 PC = text 시작 | `0x00040000` |
| data | `0x10000000` ~ `0x100003FF` (1,024 B), 실행 전 전체 0 초기화 후 data.bin(0~1,024 B) 적재 |
| 레지스터 | x0~x31 32비트, 모두 0으로 시작, x0은 항상 0 |
| 바이트 순서 | little-endian (명령어·데이터). `78 56 34 12` → `0x12345678` |
| 종료 | 지원하지 않는 명령어를 fetch하면 **실행하지 않고** 종료 |
| 표준 출력 | `PC 0x%08x invalid instruction 0x%08x\n` 한 줄만 (fetch 당시 PC, 소문자 8자리) |
| data.out | 현재 작업 디렉터리, 정확히 1,024 B 바이너리, 덮어쓰기 |
| 실행 한도 | 정상 명령어 최대 1,000,000개. 다음 fetch가 invalid면 정상 종료, 지원 명령어면 실행 없이 비정상 종료 |
| 실행 | `<명령> text.bin data.bin` (인수 정확히 2개). 네트워크·AI·대화형 입력 금지 |
| GUI | **불필요.** 10절: GUI·언어·속도는 가산점 없음 |
| 평가 | 팀 60점(공통·비공개 테스트, 출력 바이트 비교) + 개인 40점(기말고사, AI 없이, 인쇄 소스만 열람) |
| 제출물 | 소스, README, 보고서 PDF(필수 구성 ①~⑪ + 구현 위치표 + 9.2절 AI 활용 양식), 자체 테스트, 팀 전원 사진 |

## 확정된 결정

- **언어: Python 3 (3.8 이상), 표준 라이브러리만. CLI만, GUI 없음.** 사용자가 직접 선택했다.
  - 이유: 빌드가 필요 없고, 인쇄본이 짧고, 32비트 처리가 코드에 명시적으로 드러난다.
- **값 표현:**
  - 레지스터는 항상 0 ~ 0xFFFFFFFF 비트 패턴이다. 모든 쓰기는 `CPU.write_reg`에서 `to_u32`로 자르고, x0 쓰기는 무시한다.
  - 즉시값은 해독할 때 부호 확장한 Python 정수다.
  - blt/bge에서만 `to_signed32`로 부호를 해석한다.
  - andi/ori는 `to_u32(imm)`을 쓴다.
- **바이너리 입출력:** 입력은 `"rb"`, data.out은 `"wb"`, 표준 출력은 `sys.stdout.buffer`로 쓴다. Windows의 CRLF 변환을 막기 위해서다.
- **루프 순서 (cpu.py `CPU.run`):** fetch_pc 보존 → fetch → decode → **invalid 확인 → 한도 확인** → execute. 순서를 바꾸면 "정확히 1,000,000개 + invalid = 정상"이 깨진다.
- **명세에 없는 동작 (AI 제안, 팀 채택):**

| 상황 | 동작 |
|---|---|
| 실행 한도 초과 | 종료 코드 2, 표준 출력 없음, data.out 생성 안 함 |
| text 밖 fetch, lw/sw 범위·정렬 위반, text에 쓰기 | 종료 코드 3 |
| 인수·파일 입출력 오류 | 종료 코드 1 |
| text.bin 크기가 4의 배수가 아님, data.bin > 1,024 B | 경고 후 진행 |
| 비정상 종료 시 이전 data.out | 지우지 않음 → 남을 수 있음 (문서화만 함, 채점 입력에는 영향 없음) |

- **속도 최적화(해독 캐시)는 하지 않음:** fetch/decode/execute 흐름을 코드에 그대로 보이기 위해서다. 100만 개 실행에 약 2.5~4초.

## 명령어

```powershell
cd riscv-sim
python sim.py text.bin data.bin              # 실행 (Linux/macOS는 python3)
python tests\run_tests.py                    # 종단 간 40 + CLI 4 → 44/44 passed
python tests\test_units.py                   # 단위 30개 → OK
python tests\mutation_test.py --markdown report\mutation_results.md   # 변이 29/29 (약 2분)
python tests\gen_tests.py                    # cases.py → tests/cases/ 재생성 (손으로 추가한 폴더는 보존)
python tools\trace.py text.bin data.bin [--limit N] [--disasm]
pip install unicorn; python tests\diff_ref_unicorn.py --programs 3000  # 참조 실행기 대조 (테스트 전용)
pip install markdown; python report\build_report.py                    # report.pdf (Edge/Chrome 필요)
cd ..; python study\build_pdfs.py            # 인쇄본·시험 정리 PDF
```

- 콘솔 한글이 깨지면 `PYTHONIOENCODING=utf-8`을 설정한다.
- 이전 세션의 unicorn/markdown 가상환경은 임시 폴더에 있었으므로 새 세션에서는 다시 설치해야 한다.

## 검증 결과 (2026-11-08, 본체 최종 수정 04:23 이후 기준)

| 검증 | 결과 |
|---|---|
| 종단 간 테스트 (손으로 기대값 도출, 별도 프로세스, 바이트 비교) | 44/44 |
| 단위 테스트 (무작위 해독 200,000개 포함) | 30/30 |
| 변이 테스트 | 29/29 검출 |
| Unicorn 참조 대조 | 손 계산 33/33, 무작위 프로그램 23,000+ 일치 |
| Docker Linux Python 3.8.20 / 3.13.18 | 전부 통과 |
| 독립 검토 에이전트 | BUG 0건. 해독 262,144개 전수, 즉시값 전 범위, 무작위 20,000개 불일치 0, 테스트 기대값 40개 재확인 |

**발견하고 고친 것 (보고서 8장·11장에 기록):**
- 변이 테스트 1차에서 놓친 2종을 테스트 추가로 보강했다.
  - 레지스터 32비트 자르기 누락 → Python 음수 비트 연산 때문에 sw 결과는 우연히 맞음 → **08_wrap_compare** 추가
  - 한도 비교 `>` → **34_limit_plus_one** 추가
- 최종 검수에서 보조 도구 4건을 고쳤다.
  - run_tests `--sim`의 Windows 경로 처리
  - gen_tests가 손으로 추가한 케이스를 삭제하던 문제
  - diff_ref의 미도달 처리
  - trace 성능
- 명세 9·9.2절 대비 보고서 누락 2건을 보완했다(대표 사례 "검증 방법" 열, 등급 근거).
- 보고서에 확인되지 않은 팀 행동을 적은 문장 6곳을 빈칸으로 바꿨다.

## 작업 규칙 (이 저장소에서 작업할 때)

1. **본체(`sim.py`, `rvsim/`)를 고치면 함께 갱신할 것:**
   - `study/시험대비_정리.md`의 **파일:줄 참조** (2절 코드 지도, 8·11·12·14절)
   - 보고서 1.3 구현 위치표
   - `tests/mutation_test.py`의 `MUTANTS` 패턴 (원문 문자열이 정확히 있어야 함)
   - `report/mutation_results.md`
   - 그다음 `report.pdf`, `study/*.pdf`를 다시 빌드한다.
   - 제출이 가까우면 본체 수정은 최소화한다.
2. **테스트 기대값은 시뮬레이터 실행 결과를 복사하지 않는다.** 명령어 의미로 손 계산하고 근거를 `tests/cases.py` 주석에 적는다. 테스트 입력은 `tests/asm.py`(rvsim과 독립된 인코더)로 만든다.
3. **표준 출력에는 종료 한 줄 외에 아무것도 쓰지 않는다.** 진단은 stderr로, 추적은 `tools/trace.py`로 한다.
4. **AI 활용 기록은 사실대로.**
   - 현재 보고서는 전 영역 등급 3(주요 생성)이다.
   - 팀이 하지 않은 일을 했다고 쓰지 않는다. 확인 안 된 팀 행동은 `【】` 빈칸으로 둔다.
   - 모델·버전을 모르면 "확인 불가"라고 쓴다.
   - 허위 기재는 학업윤리 절차 대상이다(명세 9.2절).
5. **문서의 빈칸 표시는 `【】`.** 제출 전에 하나도 남지 않아야 한다(현재 README 5줄, report.md 26줄).
6. **Windows 환경:** Git Bash와 PowerShell을 쓴다. 테스트 바이너리 줄바꿈 보호를 위해 `riscv-sim/.gitattributes`가 있다.

## 남은 일 (팀) - 상세는 `직접_해야_할_일.md`

- [ ] README·보고서의 학번, 담당, 제출일, 10장 기여(현재 역할은 예시), 11장 AI 사용 팀원 이름·다른 AI 도구·팀 검증·팀 수정
- [ ] 보고서 맨 위 "작성 안내" 상자 삭제
- [ ] 실행 중 팀원 전원 사진 → `riscv-sim/report/team_photo.jpg` → `build_report.py` 다시 실행
- [ ] 각자 PC에서 README만으로 실행, 손 검산 분담 (01~08 / 09~16 / 17~24 / 25~36)
- [ ] 제출 정리(`__pycache__`, report.html 삭제), zip + SHA-256으로 버전 고정, 제출 후 코드 수정 금지
- [ ] 최종본으로 `study/build_pdfs.py` → `source_listing_core.pdf` 인쇄 (아무것도 적지 않기)
