"""32비트 정수·부호 처리 도우미.

Python 의 int 는 크기 제한이 없고(임의 정밀도) 음수를 그대로 표현한다.
하드웨어의 32비트 레지스터처럼 동작하게 하려면 결과를 하위 32비트로 잘라야 한다.

이 시뮬레이터의 값 표현 규칙
  - 레지스터·메모리에 저장되는 값은 항상 0 ~ 0xFFFFFFFF 범위의
    '부호 없는 32비트 비트 패턴'으로 보관한다.
  - 즉시값(immediate)은 해독 단계에서 부호 확장하여 Python 의 음수/양수 정수로 둔다.
  - 부호 있는 해석이 필요한 곳(blt, bge 비교)에서만 to_signed32() 를 사용한다.
"""

MASK32 = 0xFFFFFFFF


def to_u32(value):
    """임의의 Python 정수를 하위 32비트 비트 패턴(0 ~ 0xFFFFFFFF)으로 자른다.

    예) to_u32(0xFFFFFFFF + 1) -> 0x00000000   (덧셈 결과의 자리올림 버림)
        to_u32(0 - 1)          -> 0xFFFFFFFF   (음수 -> 2의 보수 비트 패턴)
    """
    return value & MASK32


def to_signed32(value):
    """32비트 비트 패턴을 2의 보수 부호 있는 정수(-2^31 ~ 2^31-1)로 해석한다.

    예) 0xFFFFFFFF -> -1, 0x80000000 -> -2147483648, 0x7FFFFFFF -> 2147483647
    """
    value &= MASK32
    if value & 0x80000000:          # bit 31(부호 비트)이 1 이면 음수
        return value - 0x100000000  # 2^32 를 빼서 음수 값으로 바꾼다
    return value


def sign_extend(value, bit_count):
    """bit_count 비트 폭의 값을 부호 확장한다(최상위 비트가 1 이면 음수).

    예) sign_extend(0xFFF, 12) -> -1      sign_extend(0x800, 12) -> -2048
        sign_extend(0x7FF, 12) -> 2047    sign_extend(0x1000, 13) -> -4096
    """
    value &= (1 << bit_count) - 1
    if value & (1 << (bit_count - 1)):
        return value - (1 << bit_count)
    return value


def get_bits(value, hi, lo):
    """value 의 비트 [hi:lo] (양 끝 포함) 필드를 꺼낸다.

    예) get_bits(0x00700113, 6, 0) -> 0x13 (opcode)
    """
    return (value >> lo) & ((1 << (hi - lo + 1)) - 1)
