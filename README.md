# SaveScope — Game Save Reverse Engineering Toolkit

SaveScope is an educational, production-grade reverse engineering and game save editing platform built with **Python 3.13+**, modern desktop GUI (`PyQt6`), and rich CLI tooling.

## Key Capabilities & Phases

- **Phase 0 — Game Discovery Engine**: Scans PC storage, Steam user libraries, AppData, and Documents for game saves.
- **Phase 1 & 2 — Diff Analysis & Heuristic Inference**: Sliding-window candidate type inference with confidence scoring.
- **Phase 3 — Save Structure Mapping**: Declarative JSON schema registry with range boundaries, categories, endianness, and validation.
- **Phase 4 — Standalone Python Parser Generator**: Generates typed `@dataclass` Python modules with `read_save()` and `write_save()`.
- **Phase 5 & 8 — Save Editor & Presets**: Structured table editing with safe bounds validation, undo/redo, and preset triggers.
- **Phase 6 — Desktop GUI**: PyQt6 user interface with Side-by-Side Hex Viewer, Field Color Highlighting, and Library Dashboard.
- **Phase 7 — Rolling Backup Engine**: Automated pre-modification snapshots with SHA-256 integrity hashes.
- **Phase 9 — Advanced Binary Analysis**: Sliding-window Shannon Entropy to identify zero padding, structs, and compression.
- **Phase 10 — Educational Academy**: Interactive curriculum explaining Endianness, Two's Complement, and Floats.

## Quickstart Commands

```bash
# Compare two saves and discover variables
python -m savescope diff samples/retro_rpg/save_slot1_level1.dat samples/retro_rpg/save_slot1_level2.dat

# Shannon Entropy & structural analysis
python -m savescope analyze samples/retro_rpg/save_slot1_level1.dat --chunk-size 32

# Generate Python parser
python -m savescope codegen "Chronicles of Aeloria" -o aeloria_parser.py

# Educational guides
python -m savescope edu --topic endianness

# Launch Desktop GUI
python -m savescope gui
```
