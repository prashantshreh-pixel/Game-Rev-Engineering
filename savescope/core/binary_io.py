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
        return struct.unpack_from("B", self._data, offset)[0]

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
    """
    Safe binary memory writer. Enforces strict bounds and disallows resizing buffer.
    """
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
        if not (0 <= val <= 255):
            raise ValueError(f"Value {val} out of uint8 range [0, 255]")
        struct.pack_into("B", self._data, offset, val)

    def write_i8(self, offset: int, val: int) -> None:
        if not (-128 <= val <= 127):
            raise ValueError(f"Value {val} out of int8 range [-128, 127]")
        struct.pack_into("b", self._data, offset, val)

    def write_u16(self, offset: int, val: int, endian: str = "little") -> None:
        if not (0 <= val <= 65535):
            raise ValueError(f"Value {val} out of uint16 range [0, 65535]")
        fmt = "<H" if endian == "little" else ">H"
        struct.pack_into(fmt, self._data, offset, val)

    def write_i16(self, offset: int, val: int, endian: str = "little") -> None:
        if not (-32768 <= val <= 32767):
            raise ValueError(f"Value {val} out of int16 range [-32768, 32767]")
        fmt = "<h" if endian == "little" else ">h"
        struct.pack_into(fmt, self._data, offset, val)

    def write_u32(self, offset: int, val: int, endian: str = "little") -> None:
        if not (0 <= val <= 4294967295):
            raise ValueError(f"Value {val} out of uint32 range [0, 4294967295]")
        fmt = "<I" if endian == "little" else ">I"
        struct.pack_into(fmt, self._data, offset, val)

    def write_i32(self, offset: int, val: int, endian: str = "little") -> None:
        if not (-2147483648 <= val <= 2147483647):
            raise ValueError(f"Value {val} out of int32 range [-2147483648, 2147483647]")
        fmt = "<i" if endian == "little" else ">i"
        struct.pack_into(fmt, self._data, offset, val)

    def write_u64(self, offset: int, val: int, endian: str = "little") -> None:
        if not (0 <= val <= 18446744073709551615):
            raise ValueError(f"Value {val} out of uint64 range [0, 18446744073709551615]")
        fmt = "<Q" if endian == "little" else ">Q"
        struct.pack_into(fmt, self._data, offset, val)

    def write_i64(self, offset: int, val: int, endian: str = "little") -> None:
        if not (-9223372036854775808 <= val <= 9223372036854775807):
            raise ValueError(f"Value {val} out of int64 range [-9223372036854775808, 9223372036854775807]")
        fmt = "<q" if endian == "little" else ">q"
        struct.pack_into(fmt, self._data, offset, val)

    def write_f32(self, offset: int, val: float, endian: str = "little") -> None:
        fmt = "<f" if endian == "little" else ">f"
        struct.pack_into(fmt, self._data, offset, float(val))

    def write_f64(self, offset: int, val: float, endian: str = "little") -> None:
        fmt = "<d" if endian == "little" else ">d"
        struct.pack_into(fmt, self._data, offset, float(val))

    def write_string(self, offset: int, text: str, length: int, encoding: str = "ascii") -> None:
        if offset + length > len(self._data):
            raise ValueError(f"String write at 0x{offset:X} (len {length}) exceeds buffer size {len(self._data)}")
        raw = text.encode(encoding, errors="replace")[:length]
        padded = raw.ljust(length, b"\x00")
        self._data[offset : offset + length] = padded

    def write_bytes(self, offset: int, chunk: bytes, expected_len: int = None) -> None:
        if expected_len is not None and len(chunk) != expected_len:
            raise ValueError(f"Expected exact byte length {expected_len}, got {len(chunk)}")
        if offset + len(chunk) > len(self._data):
            raise ValueError(f"Bytes write at 0x{offset:X} (len {len(chunk)}) exceeds buffer size {len(self._data)}")
        self._data[offset : offset + len(chunk)] = chunk

    def save_to_file(self, path: Union[str, Path]) -> None:
        Path(path).write_bytes(self._data)
