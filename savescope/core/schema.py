import json
import keyword
from pathlib import Path
from typing import Optional, Union

from savescope.models.schema_models import SaveSchema, FieldDefinition, DataType, Endianness

VALID_CHECKSUMS = {"crc32", "adler32", "md5"}

class SchemaManager:
    """
    Manages loading, validating, exporting, and caching SaveSchema definitions.
    Strictly validates schemas before caching to prevent corrupted or malicious layouts.
    """
    def __init__(self, schemas_dir: Optional[Union[str, Path]] = None):
        self.schemas_dir = Path(schemas_dir) if schemas_dir else Path(__file__).parent.parent.parent / "schemas"
        self.schemas_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, SaveSchema] = {}
        self.reload_all()

    def reload_all(self) -> None:
        self._cache.clear()
        for f in self.schemas_dir.glob("*.json"):
            try:
                schema = self.load_schema_file(f)
                errs = self.validate_schema(schema)
                if not errs:
                    self._cache[schema.name] = schema
                else:
                    print(f"Skipping invalid schema {f.name}: {errs}")
            except Exception as e:
                print(f"Failed loading schema {f.name}: {e}")

    @property
    def schemas(self) -> list[SaveSchema]:
        return list(self._cache.values())

    def get_schema(self, name: str) -> Optional[SaveSchema]:
        return self._cache.get(name)

    def load_schema_file(self, path: Union[str, Path]) -> SaveSchema:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        schema = SaveSchema.from_dict(data)
        errs = self.validate_schema(schema)
        if errs:
            raise ValueError(f"Schema validation failed: {errs}")
        self._cache[schema.name] = schema
        return schema

    def save_schema_file(self, schema: SaveSchema, path: Optional[Union[str, Path]] = None) -> Path:
        errs = self.validate_schema(schema)
        if errs:
            raise ValueError(f"Cannot save invalid schema: {errs}")

        if path is None:
            clean_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in schema.name.lower())
            path = self.schemas_dir / f"{clean_name}.json"
        else:
            path = Path(path)

        path.write_text(json.dumps(schema.to_dict(), indent=2), encoding="utf-8")
        self._cache[schema.name] = schema
        return path

    def validate_schema(self, schema: SaveSchema) -> list[str]:
        """
        Thoroughly validates schema fields, offsets, boundary spans, identifier safety,
        checksum configurations, and overlap to prevent invalid reads or memory writes.
        """
        errors = []
        if not schema.name.strip():
            errors.append("Schema name cannot be empty.")

        if schema.expected_size is not None and schema.expected_size <= 0:
            errors.append(f"Expected size must be positive, got {schema.expected_size}.")

        if schema.checksum_type:
            if schema.checksum_type.lower() not in VALID_CHECKSUMS:
                errors.append(f"Invalid checksum type '{schema.checksum_type}'. Must be one of: {sorted(VALID_CHECKSUMS)}")
            if schema.checksum_offset is None or schema.checksum_offset < 0:
                errors.append("Checksum offset must be specified and non-negative when checksum_type is set.")
            elif schema.expected_size is not None and schema.checksum_offset + 4 > schema.expected_size:
                errors.append(f"Checksum offset {schema.checksum_offset} + 4 exceeds expected size {schema.expected_size}.")

        if schema.magic_bytes:
            if schema.magic_offset < 0:
                errors.append("Magic offset cannot be negative.")
            elif schema.expected_size is not None and schema.magic_offset + len(schema.magic_bytes) > schema.expected_size:
                errors.append("Magic header bytes exceed expected file size.")

        seen_keys = set()
        seen_spans: list[tuple[int, int, str]] = []

        for field in schema.fields:
            if not field.key.strip():
                errors.append(f"Field at offset {field.offset} has empty key.")
            elif not field.key.isidentifier() or keyword.iskeyword(field.key):
                errors.append(f"Field key '{field.key}' is not a valid Python identifier or is a reserved keyword.")
            elif field.key in seen_keys:
                errors.append(f"Duplicate field key '{field.key}'.")
            seen_keys.add(field.key)

            if field.offset < 0:
                errors.append(f"Field '{field.key}' has negative offset {field.offset}.")

            size = field.length if field.data_type in (DataType.STRING, DataType.BYTES) else field.data_type.byte_size
            if size <= 0:
                errors.append(f"Field '{field.key}' must have positive length/size.")

            span_end = field.offset + size
            if schema.expected_size is not None and span_end > schema.expected_size:
                errors.append(f"Field '{field.key}' ends at {span_end}, exceeding expected file size {schema.expected_size}.")

            # Overlap check
            for prev_start, prev_end, prev_key in seen_spans:
                if not (span_end <= prev_start or field.offset >= prev_end):
                    errors.append(f"Field '{field.key}' [0x{field.offset:X}..0x{span_end:X}] overlaps with '{prev_key}' [0x{prev_start:X}..0x{prev_end:X}].")

            seen_spans.append((field.offset, span_end, field.key))

        return errors
