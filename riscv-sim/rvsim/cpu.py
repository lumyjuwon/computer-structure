"""CPU 상태(PC, 레지스터 x0~x31)와 fetch -> decode -> execute 실행 루프."""

from .bits import to_signed32, to_u32
from .decoder import decode
from .memory import TEXT_BASE

MAX_INSTRUCTIONS = 1000000  # 정상 명령어 최대 실행 개수 (명세 6절)


class ExecutionLimitExceeded(Exception):
    """정상 명령어를 한도만큼 실행한 뒤 다음 fetch 도 지원 명령어인 경우(비정상 종료)."""

    def __init__(self, pc, word):
        super().__init__("execution limit exceeded: pc=0x%08x instruction=0x%08x"
                         % (pc, word))
        self.pc = pc
        self.word = word


class CPU:
    def __init__(self, memory):
        self.memory = memory
        self.regs = [0] * 32   # x0 ~ x31 모두 0 으로 시작 (스택 포인터 초기화 없음)
        self.pc = TEXT_BASE    # 초기 PC = 0x00040000
        self.executed = 0      # 지금까지 실행을 마친 정상 명령어 수

    def write_reg(self, index, value):
        """레지스터 쓰기. x0 는 항상 0 이므로 쓰기를 무시하고, 값은 하위 32비트만 저장한다."""
        if index != 0:
            self.regs[index] = to_u32(value)

    def run(self, limit=MAX_INSTRUCTIONS):
        """invalid instruction 을 fetch 할 때까지 실행한다.

        반환값: (invalid instruction 을 fetch 한 주소, 그 32비트 명령어 값)
        invalid instruction 자체는 실행하지 않는다.
        """
        while True:
            fetch_pc = self.pc                      # fetch 당시 주소를 따로 보존
            word = self.memory.fetch(fetch_pc)      # 1) fetch
            inst = decode(word)                     # 2) decode
            if inst is None:                        # 지원하지 않는 명령어 -> 실행 없이 종료
                return fetch_pc, word
            if self.executed >= limit:              # 이미 한도만큼 실행했는데 또 정상 명령어
                raise ExecutionLimitExceeded(fetch_pc, word)
            self.pc = self.execute(inst, fetch_pc)  # 3) execute + PC 갱신
            self.executed += 1

    def execute(self, inst, pc):
        """명령어 하나를 실행하고 다음 PC 를 반환한다. pc 는 이 명령어의 주소."""
        name = inst.name
        rs1 = self.regs[inst.rs1]   # x0 은 쓰기가 무시되므로 항상 0 이 읽힌다
        rs2 = self.regs[inst.rs2]
        imm = inst.imm              # 부호 확장된 즉시값 (Python 정수, 음수 가능)
        next_pc = pc + 4            # 분기하지 않으면 다음 명령어

        # ---- R형 산술·논리 ----
        if name == "add":
            self.write_reg(inst.rd, rs1 + rs2)          # write_reg 에서 하위 32비트만 저장
        elif name == "sub":
            self.write_reg(inst.rd, rs1 - rs2)          # 음수 결과도 2의 보수 비트 패턴으로
        elif name == "and":
            self.write_reg(inst.rd, rs1 & rs2)
        elif name == "or":
            self.write_reg(inst.rd, rs1 | rs2)

        # ---- I형 산술·논리 (즉시값은 부호 확장된 값) ----
        elif name == "addi":
            self.write_reg(inst.rd, rs1 + imm)
        elif name == "andi":
            self.write_reg(inst.rd, rs1 & to_u32(imm))  # 예) imm=-1 -> 0xFFFFFFFF
        elif name == "ori":
            self.write_reg(inst.rd, rs1 | to_u32(imm))

        # ---- U형 ----
        elif name == "lui":
            self.write_reg(inst.rd, imm)                # imm = 상위 20비트 << 12

        # ---- 메모리 (유효 주소 = rs1 + 부호 확장 오프셋, 32비트로 자름) ----
        elif name == "lw":
            addr = to_u32(rs1 + imm)
            self.write_reg(inst.rd, self.memory.load_word(addr))
        elif name == "sw":
            addr = to_u32(rs1 + imm)
            self.memory.store_word(addr, rs2)

        # ---- B형 분기 (분기 목표 = 분기 명령어 자신의 주소 + 오프셋) ----
        elif name == "beq":
            if rs1 == rs2:
                next_pc = pc + imm
        elif name == "bne":
            if rs1 != rs2:
                next_pc = pc + imm
        elif name == "blt":                             # 부호 있는 비교
            if to_signed32(rs1) < to_signed32(rs2):
                next_pc = pc + imm
        elif name == "bge":                             # 부호 있는 비교
            if to_signed32(rs1) >= to_signed32(rs2):
                next_pc = pc + imm

        else:
            raise AssertionError("decode() returned unknown instruction: " + name)

        return to_u32(next_pc)
