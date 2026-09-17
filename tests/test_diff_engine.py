from pathlib import Path
from savescope.core.diff_engine import DiffEngine
from savescope.models.schema_models import DataType

def test_diff_retro_rpg_samples():
    sample_dir = Path(__file__).parent.parent / "samples" / "retro_rpg"
    save_1 = sample_dir / "save_slot1_level1.dat"
    save_2 = sample_dir / "save_slot1_level2.dat"

    result = DiffEngine.compare_files(save_1, save_2)

    assert not result.identical
    assert result.size_a == 256
    assert result.size_b == 256
    assert result.total_changed_bytes > 0

    # Gold offset 0x10 (16) should be candidate
    gold_cands = [c for c in result.candidates if c.offset == 16 and c.data_type == DataType.UINT32]
    assert len(gold_cands) >= 1
    gold = gold_cands[0]
    assert gold.val_a == 500
    assert gold.val_b == 750
    assert gold.delta == 250
    assert gold.confidence > 0.80

    # Level offset 0x14 (20) should be candidate
    level_cands = [c for c in result.candidates if c.offset == 20 and c.data_type == DataType.UINT8]
    assert len(level_cands) >= 1
    assert level_cands[0].val_a == 1
    assert level_cands[0].val_b == 2
