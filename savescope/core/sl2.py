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
    Reverse-Engineered FromSoftware BND4 Save Container Engine (Sekiro, Dark Souls, Elden Ring).
    
    Architecture:
    - BND4 Container Header with 12 packed save slots (USER_DATA000 .. USER_DATA011).
    - Each slot consists of:
      * 16-byte MD5 Checksum header (e.g. at offset 0x0300, 0x100310, etc.)
      * Slot Payload (e.g. 1,048,576 bytes / 1 MB of save state).
    - If any byte inside the payload is modified (by a hex editor or cheat),
      the game computes MD5(payload) and displays 'Save Data is Corrupted' unless
      the 16-byte checksum header is recalculated and patched.
    """

    MAGIC = b"BND4"

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path).resolve()
        self.data = bytearray(self.file_path.read_bytes())
        self.slots: list[SL2Slot] = []
        self._parse()

    @classmethod
    def is_sl2_file(cls, path_or_bytes: Union[str, Path, bytes]) -> bool:
        if isinstance(path_or_bytes, (str, Path)):
            p = Path(path_or_bytes)
            if not p.exists() or p.stat().st_size < 0x300:
                return False
            with open(p, "rb") as f:
                return f.read(4) == cls.MAGIC
        return bytes(path_or_bytes[:4]) == cls.MAGIC

    def _parse(self) -> None:
        if len(self.data) < 0x40 or self.data[:4] != self.MAGIC:
            raise ValueError(f"Invalid BND4 header in {self.file_path.name}")

        file_count = struct.unpack_from("<I", self.data, 0x0C)[0]
        self.slots.clear()

        offset = 0x40
        for i in range(file_count):
            flags = struct.unpack_from("<I", self.data, offset)[0]
            size = struct.unpack_from("<Q", self.data, offset + 8)[0]
            data_off = struct.unpack_from("<I", self.data, offset + 16)[0]
            name_off = struct.unpack_from("<I", self.data, offset + 20)[0]

            name = self.data[name_off : name_off + 32].decode("utf-16le", errors="ignore").split("\x00")[0]

            # 16-byte MD5 Checksum at start of slot
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
        """Returns True if all slots have valid MD5 checksums."""
        self._parse()
        return all(s.is_valid for s in self.slots)

    def recalculate_and_patch_checksums(self) -> int:
        """
        Calculates and updates the 16-byte MD5 checksum for every slot.
        Returns the number of slots patched.
        """
        patched_count = 0
        for slot in self.slots:
            new_hash = hashlib.md5(self.data[slot.payload_offset : slot.payload_offset + slot.payload_size]).digest()
            curr_hash = bytes(self.data[slot.checksum_offset : slot.checksum_offset + 16])
            if curr_hash != new_hash:
                self.data[slot.checksum_offset : slot.checksum_offset + 16] = new_hash
                patched_count += 1

        self._parse()
        return patched_count

    def patch_bytes(self, absolute_offset: int, new_bytes: bytes, auto_recalculate: bool = True) -> None:
        """Writes bytes at offset and automatically updates the affected slot's checksum."""
        self.data[absolute_offset : absolute_offset + len(new_bytes)] = new_bytes
        if auto_recalculate:
            self.recalculate_and_patch_checksums()

    def save(self, output_path: Optional[Union[str, Path]] = None, auto_recalculate: bool = True) -> Path:
        """Recalculates all MD5 slot checksums and atomically writes to file."""
        if auto_recalculate:
            self.recalculate_and_patch_checksums()

        target = Path(output_path).resolve() if output_path else self.file_path
        target.parent.mkdir(parents=True, exist_ok=True)

        temp_file = target.with_name(f".tmp_{target.name}")
        try:
            temp_file.write_bytes(self.data)
            temp_file.replace(target)
        finally:
            if temp_file.exists():
                temp_file.unlink()

        return target
