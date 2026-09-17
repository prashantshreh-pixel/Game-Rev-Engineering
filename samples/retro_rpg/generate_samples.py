import struct
from pathlib import Path

def generate_saves():
    """
    Generates deterministic sample save files for testing SaveScope.
    Magic header: 'SSCP' (0x50435353)
    Offset 0x00: Magic (4 bytes)
    Offset 0x04: Version (uint32 = 1)
    Offset 0x10: Gold (uint32) -> Save 1: 500, Save 2: 750 (diff: +250)
    Offset 0x14: Level (uint8) -> Save 1: 1, Save 2: 2
    Offset 0x15: Padding (uint8 = 0)
    Offset 0x16: HP (uint16) -> Save 1: 100, Save 2: 120
    Offset 0x18: Max HP (uint16) -> 120
    Offset 0x20: Hero Name (16 bytes ascii) -> 'Aeloria'
    Offset 0x30: Playtime (float32) -> Save 1: 125.5s, Save 2: 250.0s
    """
    buf1 = bytearray(256)
    buf2 = bytearray(256)

    # Magic & Version
    buf1[0:4] = b"SSCP"
    buf2[0:4] = b"SSCP"
    struct.pack_into("<I", buf1, 4, 1)
    struct.pack_into("<I", buf2, 4, 1)

    # Hero Name
    name = b"Aeloria".ljust(16, b"\x00")
    buf1[0x20:0x30] = name
    buf2[0x20:0x30] = name

    # Max HP
    struct.pack_into("<H", buf1, 0x18, 120)
    struct.pack_into("<H", buf2, 0x18, 120)

    # Save 1 values
    struct.pack_into("<I", buf1, 0x10, 500)      # Gold
    struct.pack_into("<B", buf1, 0x14, 1)        # Level
    struct.pack_into("<H", buf1, 0x16, 100)      # HP
    struct.pack_into("<f", buf1, 0x30, 125.5)    # Playtime

    # Save 2 values (differing)
    struct.pack_into("<I", buf2, 0x10, 750)      # Gold (+250)
    struct.pack_into("<B", buf2, 0x14, 2)        # Level (+1)
    struct.pack_into("<H", buf2, 0x16, 120)      # HP (+20)
    struct.pack_into("<f", buf2, 0x30, 250.0)    # Playtime

    out_dir = Path(__file__).parent
    (out_dir / "save_slot1_level1.dat").write_bytes(buf1)
    (out_dir / "save_slot1_level2.dat").write_bytes(buf2)
    print(f"Generated sample saves in {out_dir}")

if __name__ == "__main__":
    generate_saves()
