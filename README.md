# SaveScope — Game Save Reverse Engineering Toolkit

SaveScope is a professional educational toolkit designed for binary file analysis, single-player save file reverse engineering, and safe save editing in **Python 3.11+** with a modern **PyQt6** desktop interface.

---

## Safety & Reverse Engineering Notice

* **Always Work on Copies**: Never modify live save files in active game directories without creating manual or automated backups.
* **Game Updates Invalidate Schemas**: Official game updates frequently alter memory alignments, struct sizes, and field ordering. Schemas authored for a previous game patch may become invalid.
* **Single-Player Only**: SaveScope is strictly built for offline, single-player educational analysis. Modifying files for online games or bypassing multiplayer anti-cheat violates platform Terms of Service.
* **SL2 MD5 Compatibility vs. Security**: The MD5 recalculation performed on FromSoftware `.sl2` saves (Sekiro, Elden Ring) is purely a container format integrity check to avoid the in-game "Save Data is Corrupted" screen. It is not cryptographic tamper protection.

---

## Supported Formats vs. Reverse-Engineered Containers

| Format Category | Supported Extensions | Editing & Inspection Features |
|---|---|---|
| **Text & Config Files** | `.json`, `.xml`, `.ini`, `.cfg`, `.yaml` | Full in-app syntax prettification, live parameter search, and direct modification. |
| **Custom Binary Structures** | `.dat`, `.sav`, `.bin` | Declarative JSON schemas, struct unpacking, field bounds enforcement, and CRC32/Adler32 recalculation. |
| **FromSoftware Containers** | `.sl2` (Sekiro, Dark Souls, Elden Ring) | Multi-slot BND4 container parsing, in-place hex editing, and automated 16-byte MD5 slot checksum recalculation. |

---

## Installation & Testing

```bash
# Clone the repository and install with development dependencies
python -m pip install -e ".[dev]"

# Run the complete test suite
python -m pytest -v
```

---

## Quickstart Commands

```bash
# 1. Compare two saves to pinpoint modified variables
python -m savescope diff samples/retro_rpg/save_slot1_level1.dat samples/retro_rpg/save_slot1_level2.dat

# 2. Compute Shannon Entropy & detect compression/encryption blocks
python -m savescope analyze samples/retro_rpg/save_slot1_level1.dat --chunk-size 32

# 3. Generate standalone typed Python parser from schema
python -m savescope codegen "Chronicles of Aeloria" -o aeloria_parser.py

# 4. Educational Academy guides
python -m savescope edu --topic endianness

# 5. Launch the Desktop GUI
python -m savescope gui
```

---

## Schema Authoring Guide

SaveScope schemas map binary byte offsets into strongly-typed fields:

```json
{
  "name": "Chronicles of Aeloria",
  "version": "1.0",
  "endianness": "little",
  "expected_size": 256,
  "magic_hex": "53534350",
  "magic_offset": 0,
  "checksum_type": "crc32",
  "checksum_offset": 252,
  "fields": [
    {
      "key": "gold",
      "offset": 16,
      "type": "uint32",
      "category": "Economy",
      "description": "Total party gold coins",
      "min": 0,
      "max": 999999
    },
    {
      "key": "hero_name",
      "offset": 32,
      "type": "string",
      "length": 16,
      "encoding": "ascii",
      "category": "Character"
    }
  ]
}
```

### Schema Rules & Validation:
1. `key`: Must be a valid Python identifier and cannot be a Python keyword (`def`, `class`, `import`, etc.).
2. `offset`: Must be non-negative.
3. `fields`: Cannot overlap in byte spans.
4. `expected_size`: Total file length must encompass all field offsets and checksums.
