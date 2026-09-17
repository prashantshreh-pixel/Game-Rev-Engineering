import os
import uuid
import struct
import hashlib
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass

@dataclass
class SL2Slot:
    index: int
    name: str
    container_offset: int
    total_size: int
    checksum_offset: int
    payload_offset: int
    payload_size: int
    stored_checksum: str
    calculated_checksum: str
    is_valid: bool

class SL2Container:
    """
    Reverse-Engineered FromSoftware BND4 Save Container Engine.
    Hardened with strict bounds validation on all untrusted header values:
    - BND4 magic check
    - File count upper and lower bounds (1..64)
    - Record table bounds check
    - Slot payload bounds validation
    """

    MAGIC = b"BND4"
    MAX_SLOTS = 64

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path).resolve()
        self.data = bytearray(self.file_path.read_bytes())
        self.slots: list[SL2Slot] = []
        self._parse()

    @classmethod
    def is_sl2_file(cls, path_or_bytes: Union[str, Path, bytes]) -> bool:
        if isinstance(path_or_bytes, (str, Path)):
            p = Path(path_or_bytes)
            if not p.exists() or p.stat().st_size < 0x40:
                return False
            with open(p, "rb") as f:
                return f.read(4) == cls.MAGIC
        return bytes(path_or_bytes[:4]) == cls.MAGIC

    def _parse(self) -> None:
        file_len = len(self.data)
        if file_len < 0x40 or self.data[:4] != self.MAGIC:
            raise ValueError(f"Invalid or truncated BND4 header in {self.file_path.name}")

        file_count = struct.unpack_from("<I", self.data, 0x0C)[0]
        if file_count <= 0 or file_count > self.MAX_SLOTS:
            raise ValueError(f"Corrupted BND4 header: invalid slot count {file_count} (expected 1..{self.MAX_SLOTS})")

        header_table_size = file_count * 0x20
        if 0x40 + header_table_size > file_len:
            raise ValueError(f"Malformed BND4 container: record table exceeds file size ({0x40 + header_table_size} > {file_len})")

        self.slots.clear()

        offset = 0x40
        for i in range(file_count):
            flags = struct.unpack_from("<I", self.data, offset)[0]
            size = struct.unpack_from("<Q", self.data, offset + 8)[0]
            data_off = struct.unpack_from("<I", self.data, offset + 16)[0]
            name_off = struct.unpack_from("<I", self.data, offset + 20)[0]

            if data_off < 0 or data_off + size > file_len:
                raise ValueError(f"Slot {i} data span [0x{data_off:X}..0x{data_off + size:X}] exceeds file size {file_len}")
            if size < 16:
                raise ValueError(f"Slot {i} size {size} is too small to contain 16-byte checksum header.")
            if name_off < 0 or name_off + 32 > file_len:
                name = f"SLOT_{i:02d}"
            else:
                name = self.data[name_off : name_off + 32].decode("utf-16le", errors="ignore").split("\x00")[0]

            chk_offset = data_off
            payload_off = data_off + 16
            payload_size = size - 16

            stored_chk = bytes(self.data[chk_offset : chk_offset + 16]).hex()
            calc_chk = hashlib.md5(self.data[payload_off : payload_off + payload_size]).hexdigest()

            self.slots.append(
                SL2Slot(
                    index=i,
                    name=name,
                    container_offset=data_off,
                    total_size=size,
                    checksum_offset=chk_offset,
                    payload_offset=payload_off,
                    payload_size=payload_size,
                    stored_checksum=stored_chk,
                    calculated_checksum=calc_chk,
                    is_valid=(stored_chk.lower() == calc_chk.lower()),
                )
            )
            offset += 0x20

    def verify_all(self) -> bool:
        self._parse()
        return all(s.is_valid for s in self.slots)

    def recalculate_and_patch_checksums(self) -> int:
        patched_count = 0
        for slot in self.slots:
            new_hash = hashlib.md5(self.data[slot.payload_offset : slot.payload_offset + slot.payload_size]).digest()
            curr_hash = bytes(self.data[slot.checksum_offset : slot.checksum_offset + 16])
            if curr_hash != new_hash:
                self.data[slot.checksum_offset : slot.checksum_offset + 16] = new_hash
                patched_count += 1

        self._parse()
        return patched_count

    def save(self, output_path: Optional[Union[str, Path]] = None, auto_recalculate: bool = True) -> Path:
        if auto_recalculate:
            self.recalculate_and_patch_checksums()

        target = Path(output_path).resolve() if output_path else self.file_path
        target.parent.mkdir(parents=True, exist_ok=True)

        unique_id = uuid.uuid4().hex
        temp_file = target.with_name(f".tmp_{unique_id}_{target.name}")
        try:
            with open(temp_file, "wb") as f:
                f.write(self.data)
                f.flush()
                os.fsync(f.fileno())
            temp_file.replace(target)
        finally:
            if temp_file.exists():
                temp_file.unlink()

        return target
