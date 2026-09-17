from pathlib import Path
from savescope.core.schema import SchemaManager
from savescope.models.schema_models import SaveSchema, FieldDefinition, DataType

def test_load_and_validate_schema():
    schemas_dir = Path(__file__).parent.parent / "schemas"
    mgr = SchemaManager(schemas_dir)
    assert len(mgr.schemas) >= 1

    schema = mgr.get_schema("Chronicles of Aeloria")
    assert schema is not None
    assert schema.expected_size == 256
    assert len(schema.fields) >= 5

    errors = mgr.validate_schema(schema)
    assert len(errors) == 0

    # Verify duplicate field detection
    dup_schema = SaveSchema(
        name="Invalid Test",
        fields=[
            FieldDefinition(key="gold", offset=0, data_type=DataType.UINT32),
            FieldDefinition(key="gold", offset=4, data_type=DataType.UINT32),
        ]
    )
    dup_errors = mgr.validate_schema(dup_schema)
    assert any("Duplicate field key" in e for e in dup_errors)
