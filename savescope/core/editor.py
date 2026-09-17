import os
import struct
from pathlib import Path
from typing import Any, Optional, Union

from savescope.models.schema_models import SaveSchema, FieldDefinition, DataType, Endianness
from savescope.core.binary_io import BinaryReader, BinaryWriter
from savescope.core.backup import BackupManager
from savescope.core.presets import SavePreset
from savescope.utils.checksum import compute_crc32, compute_adler32

class SaveEditor:
    """
    Phase 5: Production-Hardened Save Editor Engine.
    Enforces schema safeguards:
    - Expected file size verification
    - Magic bytes header checking
    - CRC32/Adler32 checksum verification and auto-recalculation
    - Coercive type casting from UI strings to typed numerics/booleans/strings
    - Automatic rolling backup before modification
    - Atomic file saving via temporary file rename
    """

    def __init__(
        self,
        file_path: Union[str, Path],
        schema: SaveSchema,
        backup_mgr: Optional[BackupManager] = None,
        enforce_schema_guards: bool = True
    ):
        self.file_path = Path(file_path).resolve()
        self.schema = schema
        self.backup_mgr = backup_mgr or BackupManager()
        self._raw_data = bytearray(self.file_path.read_bytes())
        self._undo_stack: list[bytearray] = []
        self._redo_stack: list[bytearray] = []

        if enforce_schema_guards:
            self._validate_file_integrity()

    def _validate_file_integrity(self) -> None:
        """Enforces schema expected_size, magic_bytes, and checksum."""
        # 1. Expected size check
        if self.schema.expected_size is not None and len(self._raw_data) != self.schema.expected_size:
            raise ValueError(
                f"File size mismatch for {self.file_path.name}: expected {self.schema.expected_size} bytes, got {len(self._raw_data)} bytes."
            )

        # 2. Magic bytes check
        if self.schema.magic_bytes:
            magic_len = len(self.schema.magic_bytes)
            start = self.schema.magic_offset
            actual_magic = bytes(self._raw_data[start : start + magic_len])
            if actual_magic != self.schema.magic_bytes:
                raise ValueError(
                    f"Magic header mismatch at offset {start}: expected {self.schema.magic_bytes.hex()}, got {actual_magic.hex()}."
                )

        # 3. Checksum verification
        if self.schema.checksum_type and self.schema.checksum_offset is not None:
            self.verify_checksum()

    def verify_checksum(self) -> bool:
        """Verifies embedded checksum matches buffer content."""
        if not self.schema.checksum_type or self.schema.checksum_offset is None:
            return True

        endian = self.schema.endianness.value
        reader = BinaryReader(self._raw_data)
        stored_cs = reader.read_u32(self.schema.checksum_offset, endian)

        # Exclude checksum bytes from calculation
        data_to_hash = bytearray(self._raw_data)
        data_to_hash[self.schema.checksum_offset : self.schema.checksum_offset + 4] = b"\x00\x00\x00\x00"

        if self.schema.checksum_type.lower() == "crc32":
            actual_cs = compute_crc32(bytes(data_to_hash))
        elif self.schema.checksum_type.lower() == "adler32":
            actual_cs = compute_adler32(bytes(data_to_hash))
        else:
            return True

        if stored_cs != actual_cs:
            raise ValueError(f"Checksum mismatch ({self.schema.checksum_type}): stored 0x{stored_cs:08X} != actual 0x{actual_cs:08X}")
        return True

    def recalculate_checksum(self) -> None:
        """Recalculates and embeds updated checksum in buffer."""
        if not self.schema.checksum_type or self.schema.checksum_offset is None:
            return

        endian = self.schema.endianness.value
        writer = BinaryWriter(self._raw_data)

        data_to_hash = bytearray(self._raw_data)
        data_to_hash[self.schema.checksum_offset : self.schema.checksum_offset + 4] = b"\x00\x00\x00\x00"

        if self.schema.checksum_type.lower() == "crc32":
            new_cs = compute_crc32(bytes(data_to_hash))
        elif self.schema.checksum_type.lower() == "adler32":
            new_cs = compute_adler32(bytes(data_to_hash))
        else:
            return

        writer.write_u32(self.schema.checksum_offset, new_cs, endian)

    @property
    def raw_data(self) -> bytes:
        return bytes(self._raw_data)

    @property
    def size(self) -> int:
        return len(self._raw_data)

    def get_all_values(self) -> dict[str, Any]:
        values = {}
        for f in self.schema.fields:
            values[f.key] = self.get_value(f.key)
        return values

    def get_value(self, field_key: str) -> Any:
        field = self._find_field(field_key)
        if not field:
            raise KeyError(f"Field '{field_key}' not in schema.")

        endian = field.endianness.value if field.endianness else self.schema.endianness.value
        reader = BinaryReader(self._raw_data)

        if field.data_type == DataType.UINT8:
            return reader.read_u8(field.offset)
        elif field.data_type == DataType.INT8:
            return reader.read_i8(field.offset)
        elif field.data_type == DataType.BOOLEAN:
            return bool(reader.read_u8(field.offset))
        elif field.data_type == DataType.UINT16:
            return reader.read_u16(field.offset, endian)
        elif field.data_type == DataType.INT16:
            return reader.read_i16(field.offset, endian)
        elif field.data_type == DataType.UINT32:
            return reader.read_u32(field.offset, endian)
        elif field.data_type == DataType.INT32:
            return reader.read_i32(field.offset, endian)
        elif field.data_type == DataType.UINT64:
            return reader.read_u64(field.offset, endian)
        elif field.data_type == DataType.INT64:
            return reader.read_i64(field.offset, endian)
        elif field.data_type == DataType.FLOAT32:
            return round(reader.read_f32(field.offset, endian), 4)
        elif field.data_type == DataType.FLOAT64:
            return round(reader.read_f64(field.offset, endian), 6)
        elif field.data_type == DataType.STRING:
            return reader.read_string(field.offset, field.length or 16, field.encoding)
        elif field.data_type == DataType.BYTES:
            return reader.peek_bytes(field.offset, field.length or 1)
        return None

    def set_value(self, field_key: str, raw_val: Any) -> list[str]:
        """
        Safely casts, validates, and sets a field value.
        Converts text input (e.g. from GUI) into typed numerics/booleans.
        """
        field = self._find_field(field_key)
        if not field:
            raise KeyError(f"Field '{field_key}' not found in schema.")

        # Robust Type Coercion
        typed_val, cast_err = self._coerce_type(field, raw_val)
        if cast_err:
            return [cast_err]

        # Bounds validation
        val_errors = self._validate_field_val(field, typed_val)
        if val_errors:
            return val_errors

        # Save snapshot for undo
        self._undo_stack.append(bytearray(self._raw_data))
        self._redo_stack.clear()

        endian = field.endianness.value if field.endianness else self.schema.endianness.value
        writer = BinaryWriter(self._raw_data)

        if field.data_type == DataType.UINT8:
            writer.write_u8(field.offset, typed_val)
        elif field.data_type == DataType.INT8:
            writer.write_i8(field.offset, typed_val)
        elif field.data_type == DataType.BOOLEAN:
            writer.write_u8(field.offset, 1 if typed_val else 0)
        elif field.data_type == DataType.UINT16:
            writer.write_u16(field.offset, typed_val, endian)
        elif field.data_type == DataType.INT16:
            writer.write_i16(field.offset, typed_val, endian)
        elif field.data_type == DataType.UINT32:
            writer.write_u32(field.offset, typed_val, endian)
        elif field.data_type == DataType.INT32:
            writer.write_i32(field.offset, typed_val, endian)
        elif field.data_type == DataType.UINT64:
            writer.write_u64(field.offset, typed_val, endian)
        elif field.data_type == DataType.INT64:
            writer.write_i64(field.offset, typed_val, endian)
        elif field.data_type == DataType.FLOAT32:
            writer.write_f32(field.offset, typed_val, endian)
        elif field.data_type == DataType.FLOAT64:
            writer.write_f64(field.offset, typed_val, endian)
        elif field.data_type == DataType.STRING:
            writer.write_string(field.offset, typed_val, field.length or 16, field.encoding)
        elif field.data_type == DataType.BYTES:
            writer.write_bytes(field.offset, typed_val)

        # Recalculate checksum if enabled
        if self.schema.checksum_type:
            self.recalculate_checksum()

        return []

    def _coerce_type(self, field: FieldDefinition, val: Any) -> tuple[Any, Optional[str]]:
        """Converts user or UI inputs (e.g. string) to the target schema type."""
        try:
            if field.data_type in (
                DataType.INT8, DataType.UINT8, DataType.INT16, DataType.UINT16,
                DataType.INT32, DataType.UINT32, DataType.INT64, DataType.UINT64
            ):
                if isinstance(val, str):
                    val = val.strip()
                    coerced = int(val, 16) if val.lower().startswith("0x") else int(val)
                else:
                    coerced = int(val)
                return coerced, None

            elif field.data_type in (DataType.FLOAT32, DataType.FLOAT64):
                return float(val), None

            elif field.data_type == DataType.BOOLEAN:
                if isinstance(val, str):
                    val = val.strip().lower()
                    if val in ("true", "1", "yes"):
                        return True, None
                    elif val in ("false", "0", "no"):
                        return False, None
                    return bool(int(val)), None
                return bool(val), None

            elif field.data_type == DataType.STRING:
                return str(val), None

            elif field.data_type == DataType.BYTES:
                if isinstance(val, str):
                    return bytes.fromhex(val.replace(" ", "")), None
                return bytes(val), None

            return val, None
        except Exception as e:
            return None, f"Invalid value '{val}' for {field.data_type.value}: {e}"

    def apply_preset(self, preset: SavePreset) -> list[str]:
        errors = []
        for action in preset.actions:
            field = self._find_field(action.field_key)
            if not field:
                continue
            curr = self.get_value(action.field_key)
            if action.operation == "set":
                target = action.target_value
            elif action.operation == "add":
                target = curr + action.target_value
            elif action.operation == "multiply":
                target = curr * action.target_value
            else:
                target = action.target_value

            errs = self.set_value(action.field_key, target)
            errors.extend(errs)
        return errors

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(bytearray(self._raw_data))
        self._raw_data = self._undo_stack.pop()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(bytearray(self._raw_data))
        self._raw_data = self._redo_stack.pop()
        return True

    def save(self, auto_backup: bool = True) -> Path:
        """Creates a rolling backup and atomically writes changes to disk."""
        if auto_backup and self.file_path.exists():
            self.backup_mgr.create_backup(self.file_path, tag="pre_edit")

        # Atomic File Write using temporary file on same directory
        temp_file = self.file_path.with_name(f".tmp_{self.file_path.name}_{os.getpid()}")
        try:
            temp_file.write_bytes(self._raw_data)
            temp_file.replace(self.file_path)
        finally:
            if temp_file.exists():
                temp_file.unlink()

        return self.file_path

    def _find_field(self, key: str) -> Optional[FieldDefinition]:
        for f in self.schema.fields:
            if f.key == key:
                return f
        return None

    def _validate_field_val(self, field: FieldDefinition, val: Any) -> list[str]:
        errors = []
        if field.min_value is not None and val < field.min_value:
            errors.append(f"{field.key}: value {val} is below minimum {field.min_value}")
        if field.max_value is not None and val > field.max_value:
            errors.append(f"{field.key}: value {val} exceeds maximum {field.max_value}")
        return errors
