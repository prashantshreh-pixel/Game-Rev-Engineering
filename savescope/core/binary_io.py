import struct
from pathlib import Path
from typing import Union

class BinaryReader:
    def __init__(self, data: bytes):
        self._data = bytearray(data)
        self._offset = 0

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "BinaryReader":
        return cls(Path(path).read_bytes())

    @property
    def data(self) -> bytes:
        return bytes(self._data)

    @property
    def size(self) -> int:
        return len(self._data)

    @property
    def offset(self) -> int:
        return self._offset

    def seek(self, offset: int) -> None:
        if 0 <= offset <= len(self._data):
            self._offset = offset
        else:
            raise ValueError(f"Offset {offset} out of bounds (0..{len(self._data)})")

    def read_bytes(self, count: int) -> bytes:
        chunk = self._data[self._offset : self._offset + count]
        self._offset += len(chunk)
        return bytes(chunk)

    def peek_bytes(self, offset: int, count: int) -> bytes:
        return bytes(self._data[offset : offset + count])

    def read_u8(self, offset: int) -> int:
        return self._data[offset]

    def read_i8(self, offset: int) -> int:
        return struct.unpack_from("b", self._data, offset)[0]

    def read_u16(self, offset: int, endian: str = "little") -> int:
        fmt = "<H" if endian == "little" else ">H"
        return struct.unpack_from(fmt, self._data, offset)[0]

    def read_i16(self, offset: int, endian: str = "little") -> int:
        fmt = "<h" if endian == "little" else ">h"
        return struct.unpack_from(fmt, self._data, offset)[0]

    def read_u32(self, offset: int, endian: str = "little") -> int:
        fmt = "<I" if endian == "little" else ">I"
        return struct.unpack_from(fmt, self._data, offset)[0]

    def read_i32(self, offset: int, endian: str = "little") -> int:
        fmt = "<i" if endian == "little" else ">i"
        return struct.unpack_from(fmt, self._data, offset)[0]

    def read_u64(self, offset: int, endian: str = "little") -> int:
        fmt = "<Q" if endian == "little" else ">Q"
        return struct.unpack_from(fmt, self._data, offset)[0]

    def read_i64(self, offset: int, endian: str = "little") -> int:
        fmt = "<q" if endian == "little" else ">q"
        return struct.unpack_from(fmt, self._data, offset)[0]

    def read_f32(self, offset: int, endian: str = "little") -> float:
        fmt = "<f" if endian == "little" else ">f"
        return struct.unpack_from(fmt, self._data, offset)[0]

    def read_f64(self, offset: int, endian: str = "little") -> float:
        fmt = "<d" if endian == "little" else ">d"
        return struct.unpack_from(fmt, self._data, offset)[0]

    def read_string(self, offset: int, length: int, encoding: str = "ascii") -> str:
        raw = bytes(self._data[offset : offset + length])
        null_idx = raw.find(b"\x00")
        if null_idx != -1:
            raw = raw[:null_idx]
        return raw.decode(encoding, errors="replace")


class BinaryWriter:
    def __init__(self, data: Union[bytes, bytearray]):
        if isinstance(data, bytearray):
            self._data = data
        else:
            self._data = bytearray(data)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "BinaryWriter":
        return cls(Path(path).read_bytes())

    @property
    def buffer(self) -> bytearray:
        return self._data

    def to_bytes(self) -> bytes:
        return bytes(self._data)

    def write_u8(self, offset: int, val: int) -> None:
        self._data[offset] = val & 0xFF

    def write_i8(self, offset: int, val: int) -> None:
        struct.pack_into("b", self._data, offset, val)

    def write_u16(self, offset: int, val: int, endian: str = "little") -> None:
        fmt = "<H" if endian == "little" else ">H"
        struct.pack_into(fmt, self._data, offset, val)

    def write_i16(self, offset: int, val: int, endian: str = "little") -> None:
        fmt = "<h" if endian == "little" else ">h"
        struct.pack_into(fmt, self._data, offset, val)

    def write_u32(self, offset: int, val: int, endian: str = "little") -> None:
        fmt = "<I" if endian == "little" else ">I"
        struct.pack_into(fmt, self._data, offset, val)

    def write_i32(self, offset: int, val: int, endian: str = "little") -> None:
        fmt = "<i" if endian == "little" else ">i"
        struct.pack_into(fmt, self._data, offset, val)

    def write_u64(self, offset: int, val: int, endian: str = "little") -> None:
        fmt = "<Q" if endian == "little" else ">Q"
        struct.pack_into(fmt, self._data, offset, val)

    def write_i64(self, offset: int, val: int, endian: str = "little") -> None:
        fmt = "<q" if endian == "little" else ">q"
        struct.pack_into(fmt, self._data, offset, val)

    def write_f32(self, offset: int, val: float, endian: str = "little") -> None:
        fmt = "<f" if endian == "little" else ">f"
        struct.pack_into(fmt, self._data, offset, val)

    def write_f64(self, offset: int, val: float, endian: str = "little") -> None:
        fmt = "<d" if endian == "little" else ">d"
        struct.pack_into(fmt, self._data, offset, val)

    def write_string(self, offset: int, text: str, length: int, encoding: str = "ascii") -> None:
        raw = text.encode(encoding, errors="replace")[:length]
        padded = raw.ljust(length, b"\x00")
        self._data[offset : offset + length] = padded

    def write_bytes(self, offset: int, chunk: bytes) -> None:
        self._data[offset : offset + len(chunk)] = chunk

    def save_to_file(self, path: Union[str, Path]) -> None:
        Path(path).write_bytes(self._data)
