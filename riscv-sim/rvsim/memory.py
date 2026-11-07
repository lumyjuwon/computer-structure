"""메모리 모델과 바이너리 입출력.

주소 공간 (명세 2절, 6절)
  text segment : 0x00040000 부터 text.bin 크기만큼. 명령어 fetch 전용, 쓰기 불가.
  data segment : 0x10000000 ~ 0x100003FF (1,024 바이트). lw/sw 전용.

바이트 순서: little-endian (명령어·데이터 모두)
  주소 a 부터 네 바이트가 b0 b1 b2 b3 이면
  32비트 값 = b0 + (b1 << 8) + (b2 << 16) + (b3 << 24)
  예) 파일 바이트 78 56 34 12  ->  값 0x12345678
"""

TEXT_BASE = 0x00040000
DATA_BASE = 0x10000000
DATA_SIZE = 1024  # 0x400 바이트: 0x10000000 ~ 0x100003FF


class SimError(Exception):
    """명세의 유효 범위를 벗어난 동작(주소 범위·정렬 위반 등)."""


def read_word_le(buf, offset):
    """buf[offset] 부터 4 바이트를 little-endian 32비트 값으로 읽는다."""
    b0 = buf[offset]
    b1 = buf[offset + 1]
    b2 = buf[offset + 2]
    b3 = buf[offset + 3]
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)


def write_word_le(buf, offset, value):
    """32비트 값을 little-endian 순서(하위 바이트 먼저)로 buf[offset] 부터 4 바이트에 쓴다."""
    buf[offset] = value & 0xFF
    buf[offset + 1] = (value >> 8) & 0xFF
    buf[offset + 2] = (value >> 16) & 0xFF
    buf[offset + 3] = (value >> 24) & 0xFF


class Memory:
    """text segment(읽기 전용)와 data segment(1,024 바이트)를 분리해 관리한다."""

    def __init__(self, text_bytes, data_bytes):
        # text: 수정할 수 없는 bytes 로 보관 -> text segment 쓰기 불가
        self.text = bytes(text_bytes)
        # data: 먼저 1,024 바이트 전체를 0 으로 초기화한 뒤 data.bin 내용을 앞에서부터 복사
        self.data = bytearray(DATA_SIZE)
        n = min(len(data_bytes), DATA_SIZE)
        self.data[0:n] = data_bytes[0:n]

    def fetch(self, addr):
        """명령어 인출: text segment 의 addr 에서 32비트 명령어 값을 읽는다."""
        offset = addr - TEXT_BASE
        if addr % 4 != 0 or offset < 0 or offset + 4 > len(self.text):
            raise SimError("instruction fetch outside text segment or misaligned: "
                           "pc=0x%08x" % addr)
        return read_word_le(self.text, offset)

    def _data_offset(self, addr):
        """data 주소를 self.data 배열의 인덱스로 바꾼다. 4바이트 정렬·범위를 검사한다."""
        offset = addr - DATA_BASE
        if addr % 4 != 0 or offset < 0 or offset + 4 > DATA_SIZE:
            raise SimError("data access outside data segment or misaligned: "
                           "addr=0x%08x" % addr)
        return offset

    def load_word(self, addr):
        """lw: data segment 에서 32비트 값을 little-endian 으로 읽는다."""
        return read_word_le(self.data, self._data_offset(addr))

    def store_word(self, addr, value):
        """sw: data segment 에 32비트 값을 little-endian 으로 쓴다."""
        write_word_le(self.data, self._data_offset(addr), value)


def read_binary_file(path):
    """입력 파일을 바이너리 모드로 읽는다(ASCII/16진수 텍스트로 해석하지 않음)."""
    with open(path, "rb") as f:
        return f.read()


def write_data_out(path, memory):
    """data segment 0x10000000 ~ 0x100003FF 의 1,024 바이트를 주소 증가 순서로 저장한다.

    "wb" 모드: 기존 파일을 덮어쓰고, 줄바꿈 변환 없이 바이트를 그대로 기록한다.
    (텍스트 모드로 쓰면 Windows 에서 0x0A 바이트가 0x0D 0x0A 로 바뀌어 크기가 달라진다.)
    """
    with open(path, "wb") as f:
        f.write(bytes(memory.data[0:DATA_SIZE]))
