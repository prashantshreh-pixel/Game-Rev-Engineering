import json
from pathlib import Path
from typing import Optional, Union, Any

from savescope.models.schema_models import SaveSchema, FieldDefinition, DataType, Endianness

class SchemaManager:
    """
    Manages loading, validating, exporting, and searching SaveSchema definitions.
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
                self._cache[schema.name] = schema
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
        self._cache[schema.name] = schema
        return schema

    def save_schema_file(self, schema: SaveSchema, path: Optional[Union[str, Path]] = None) -> Path:
        if path is None:
            clean_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in schema.name.lower())
            path = self.schemas_dir / f"{clean_name}.json"
        else:
            path = Path(path)
        
        path.write_text(json.dumps(schema.to_dict(), indent=2), encoding="utf-8")
        self._cache[schema.name] = schema
        return path

    def validate_schema(self, schema: SaveSchema) -> list[str]:
        """Returns a list of validation errors (empty if valid)."""
        errors = []
        if not schema.name.strip():
            errors.append("Schema name cannot be empty.")
        
        seen_keys = set()
        for field in schema.fields:
            if not field.key.strip():
                errors.append(f"Field at offset {field.offset} has empty key.")
            elif field.key in seen_keys:
                errors.append(f"Duplicate field key '{field.key}'.")
            seen_keys.add(field.key)

            if field.offset < 0:
                errors.append(f"Field '{field.key}' has negative offset {field.offset}.")

            if field.data_type == DataType.STRING and (field.length is None or field.length <= 0):
                errors.append(f"String field '{field.key}' must have positive length.")

            if schema.expected_size is not None:
                field_end = field.offset + (field.length if field.data_type in (DataType.STRING, DataType.BYTES) else field.data_type.byte_size)
                if field_end > schema.expected_size:
                    errors.append(f"Field '{field.key}' ends at {field_end}, exceeding expected size {schema.expected_size}.")
        return errors
