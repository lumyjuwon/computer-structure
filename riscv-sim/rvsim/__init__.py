"""RV32I 부분집합(14개 명령어) 기능 시뮬레이터 패키지.

  bits.py    : 32비트 자르기, 부호 해석, 부호 확장, 비트 필드 추출
  memory.py  : text/data segment, little-endian 읽기·쓰기, 바이너리 파일 입출력
  decoder.py : 명령어 해독, 즉시값 생성, invalid instruction 판별
  cpu.py     : 레지스터·PC, fetch -> decode -> execute 루프, 명령어 실행
"""
