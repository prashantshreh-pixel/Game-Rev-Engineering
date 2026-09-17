import pytest
import tempfile
import shutil
from pathlib import Path

from savescope.models.schema_models import SaveSchema, FieldDefinition, DataType, Endianness
from savescope.core.schema import SchemaManager
from savescope.core.editor import SaveEditor
from savescope.core.codegen import ParserGenerator
from savescope.core.sl2 import SL2Container
from savescope.core.backup import BackupManager

def test_intrinsic_numeric_bounds_enforced():
    """Verify uint8 and int16 reject out-of-range values even without schema min/max."""
    schema = SaveSchema(
        name="Bounds Test",
        expected_size=16,
        fields=[
            FieldDefinition(key="level", offset=0, data_type=DataType.UINT8),
            FieldDefinition(key="score", offset=2, data_type=DataType.INT16),
        ]
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "test.bin"
        test_file.write_bytes(bytes(16))

        editor = SaveEditor(test_file, schema)

        # uint8 cannot exceed 255 or be negative
        errs = editor.set_value("level", 256)
        assert len(errs) == 1
        assert "out of intrinsic uint8 range" in errs[0]

        errs_neg = editor.set_value("level", -1)
        assert len(errs_neg) == 1

        # int16 out of range
        errs_i16 = editor.set_value("score", 32768)
        assert len(errs_i16) == 1
        assert "out of intrinsic int16 range" in errs_i16[0]

        # Valid values succeed
        assert editor.set_value("level", 255) == []
        assert editor.set_value("score", -32768) == []

def test_bytes_exact_length_enforced():
    """Verify bytes fields must match exact length to avoid shifting buffer offsets."""
    schema = SaveSchema(
        name="Bytes Test",
        expected_size=16,
        fields=[
            FieldDefinition(key="signature", offset=0, data_type=DataType.BYTES, length=4),
            FieldDefinition(key="gold", offset=4, data_type=DataType.UINT32),
        ]
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "test.bin"
        test_file.write_bytes(bytes(16))

        editor = SaveEditor(test_file, schema)

        # Wrong byte length rejected
        errs_short = editor.set_value("signature", b"\x01\x02")
        assert len(errs_short) == 1
        assert "bytes length must be exactly 4" in errs_short[0]

        errs_long = editor.set_value("signature", b"\x01\x02\x03\x04\x05")
        assert len(errs_long) == 1

        # Buffer size preserved
        assert editor.size == 16

def test_schema_overlap_and_keyword_validation():
    """Verify overlapping fields and reserved keywords fail schema validation."""
    mgr = SchemaManager()

    # Overlapping fields
    overlap_schema = SaveSchema(
        name="Overlap Test",
        expected_size=16,
        fields=[
            FieldDefinition(key="val_a", offset=0, data_type=DataType.UINT32),  # 0..4
            FieldDefinition(key="val_b", offset=2, data_type=DataType.UINT32),  # 2..6 (overlaps!)
        ]
    )
    errs = mgr.validate_schema(overlap_schema)
    assert any("overlaps with" in e for e in errs)

    # Keyword field name
    keyword_schema = SaveSchema(
        name="Keyword Test",
        expected_size=16,
        fields=[
            FieldDefinition(key="class", offset=0, data_type=DataType.UINT32),
        ]
    )
    errs_kw = mgr.validate_schema(keyword_schema)
    assert any("reserved keyword" in e for e in errs_kw)

def test_codegen_hostile_schema_rejected():
    """Verify parser generator rejects keyword or malicious field names."""
    bad_schema = SaveSchema(
        name="Bad Schema",
        fields=[FieldDefinition(key="def", offset=0, data_type=DataType.UINT32)]
    )
    with pytest.raises(ValueError, match="invalid identifier or keyword"):
        ParserGenerator.generate_code(bad_schema)

def test_unsafe_mode_forbids_direct_overwrite():
    """Verify opening file with failed validation enables read-only mode forbidding direct overwrite."""
    schema = SaveSchema(
        name="Size Guard Test",
        expected_size=100,  # File is only 16 bytes
        fields=[FieldDefinition(key="gold", offset=0, data_type=DataType.UINT32)]
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "test.bin"
        test_file.write_bytes(bytes(16))

        # Enforced guards raises ValueError
        with pytest.raises(ValueError, match="File size mismatch"):
            SaveEditor(test_file, schema, enforce_schema_guards=True)

        # Bypassed guards enters read-only mode
        editor = SaveEditor(test_file, schema, enforce_schema_guards=False)
        assert editor.read_only_mode is True

        # Direct overwrite forbidden
        with pytest.raises(PermissionError, match="Direct overwrite is forbidden"):
            editor.save(destination=test_file)

        # Save As Copy allowed
        copy_dest = Path(tmp_dir) / "copy.bin"
        saved = editor.save(destination=copy_dest)
        assert saved.exists()

def test_sl2_malformed_container_safety():
    """Verify malformed/truncated BND4 containers raise controlled ValueErrors."""
    # Truncated header
    with pytest.raises(ValueError, match="Invalid or truncated BND4"):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"BND4\x00\x00")
            f_path = f.name
        try:
            SL2Container(f_path)
        finally:
            Path(f_path).unlink(missing_ok=True)
