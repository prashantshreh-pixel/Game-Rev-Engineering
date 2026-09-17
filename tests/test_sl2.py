import os
import struct
import hashlib
import tempfile
import shutil
from pathlib import Path

from savescope.core.sl2 import SL2Container

def test_sl2_container_checksum_repair():
    user_profile = Path(os.environ.get("USERPROFILE", ""))
    sl2_candidates = list(user_profile.glob("AppData/Roaming/Sekiro/**/S0000.sl2"))
    if not sl2_candidates:
        return

    real_sl2 = sl2_candidates[0]

    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_sl2 = Path(tmp_dir) / "S0000.sl2"
        shutil.copy2(real_sl2, temp_sl2)

        container = SL2Container(temp_sl2)
        assert container.verify_all() is True
        assert len(container.slots) == 12

        # Corrupt a byte in Slot 0 payload
        slot0_payload_offset = container.slots[0].payload_offset
        orig_val = container.data[slot0_payload_offset + 0x100]
        container.data[slot0_payload_offset + 0x100] = (orig_val + 1) & 0xFF

        container._parse()
        assert container.slots[0].is_valid is False
        assert container.verify_all() is False

        # Recalculate and patch
        patched = container.recalculate_and_patch_checksums()
        assert patched == 1
        assert container.verify_all() is True

        # Save and re-read from disk
        container.save(temp_sl2)
        re_container = SL2Container(temp_sl2)
        assert re_container.verify_all() is True
