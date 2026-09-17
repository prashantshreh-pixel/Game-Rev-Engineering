from pathlib import Path
import tempfile
import shutil
from savescope.core.backup import BackupManager
from savescope.core.editor import SaveEditor
from savescope.core.schema import SchemaManager
from savescope.core.presets import PresetLibrary

def test_backup_and_editor_workflow():
    sample_dir = Path(__file__).parent.parent / "samples" / "retro_rpg"
    orig_save = sample_dir / "save_slot1_level1.dat"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        test_save = tmp_path / "save.dat"
        shutil.copy2(orig_save, test_save)

        backup_mgr = BackupManager(backup_root=tmp_path / "backups")
        schema_mgr = SchemaManager(Path(__file__).parent.parent / "schemas")
        schema = schema_mgr.get_schema("Chronicles of Aeloria")

        editor = SaveEditor(test_save, schema, backup_mgr)
        assert editor.get_value("gold") == 500

        # Change value and save with auto backup
        errs = editor.set_value("gold", 77777)
        assert len(errs) == 0
        editor.save(auto_backup=True)

        # Check backup created
        backups = backup_mgr.list_backups(test_save)
        assert len(backups) == 1
        assert backups[0]["original_path"] == test_save

        # Check test_save updated
        editor_re = SaveEditor(test_save, schema, backup_mgr)
        assert editor_re.get_value("gold") == 77777

        # Restore backup
        backup_mgr.restore_backup(backups[0]["backup_path"])
        editor_restored = SaveEditor(test_save, schema, backup_mgr)
        assert editor_restored.get_value("gold") == 500
