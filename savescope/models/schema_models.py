from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

class Endianness(str, Enum):
    LITTLE = "little"
    BIG = "big"

class DataType(str, Enum):
    INT8 = "int8"
    UINT8 = "uint8"
    INT16 = "int16"
    UINT16 = "uint16"
    INT32 = "int32"
    UINT32 = "uint32"
    INT64 = "int64"
    UINT64 = "uint64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    STRING = "string"
    BOOLEAN = "boolean"
    BYTES = "bytes"

    @property
    def byte_size(self) -> int:
        sizes = {
            DataType.INT8: 1,
            DataType.UINT8: 1,
            DataType.BOOLEAN: 1,
            DataType.INT16: 2,
            DataType.UINT16: 2,
            DataType.INT32: 4,
            DataType.UINT32: 4,
            DataType.FLOAT32: 4,
            DataType.INT64: 8,
            DataType.UINT64: 8,
            DataType.FLOAT64: 8,
        }
        return sizes.get(self, 0)

@dataclass
class FieldDefinition:
    key: str
    offset: int
    data_type: DataType
    description: str = ""
    length: Optional[int] = None
    endianness: Optional[Endianness] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    category: str = "General"
    encoding: str = "ascii"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "key": self.key,
            "offset": self.offset,
            "type": self.data_type.value,
            "category": self.category,
        }
        if self.description:
            d["description"] = self.description
        if self.length is not None:
            d["length"] = self.length
        if self.endianness:
            d["endianness"] = self.endianness.value
        if self.min_value is not None:
            d["min"] = self.min_value
        if self.max_value is not None:
            d["max"] = self.max_value
        if self.data_type == DataType.STRING:
            d["encoding"] = self.encoding
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldDefinition":
        raw_type = data.get("type", "uint32")
        dtype = DataType(raw_type)
        endian_str = data.get("endianness")
        endianness = Endianness(endian_str) if endian_str else None
        return cls(
            key=data["key"],
            offset=data["offset"],
            data_type=dtype,
            description=data.get("description", ""),
            length=data.get("length"),
            endianness=endianness,
            min_value=data.get("min"),
            max_value=data.get("max"),
            category=data.get("category", "General"),
            encoding=data.get("encoding", "ascii"),
        )

@dataclass
class SaveSchema:
    name: str
    version: str = "1.0"
    game_name: str = ""
    endianness: Endianness = Endianness.LITTLE
    expected_size: Optional[int] = None
    fields: list[FieldDefinition] = field(default_factory=list)
    magic_bytes: Optional[bytes] = None
    magic_offset: int = 0
    checksum_type: Optional[str] = None
    checksum_offset: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "game_name": self.game_name,
            "endianness": self.endianness.value,
            "expected_size": self.expected_size,
            "magic_hex": self.magic_bytes.hex() if self.magic_bytes else None,
            "magic_offset": self.magic_offset,
            "checksum_type": self.checksum_type,
            "checksum_offset": self.checksum_offset,
            "fields": [f.to_dict() for f in self.fields],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SaveSchema":
        magic_hex = data.get("magic_hex")
        magic_bytes = bytes.fromhex(magic_hex) if magic_hex else None
        fields_data = data.get("fields", [])
        fields = [FieldDefinition.from_dict(f) for f in fields_data]
        return cls(
            name=data.get("name", "Unnamed Schema"),
            version=data.get("version", "1.0"),
            game_name=data.get("game_name", ""),
            endianness=Endianness(data.get("endianness", "little")),
            expected_size=data.get("expected_size"),
            fields=fields,
            magic_bytes=magic_bytes,
            magic_offset=data.get("magic_offset", 0),
            checksum_type=data.get("checksum_type"),
            checksum_offset=data.get("checksum_offset"),
        )
