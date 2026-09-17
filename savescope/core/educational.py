class EducationalContentEngine:
    """
    Phase 10: Educational Content Engine.
    Generates rich, beginner-friendly explanations and interactive tutorials
    covering hexadecimal representations, endianness, IEEE-754 floats,
    data alignment, and reverse engineering methodology.
    """

    TOPICS = {
        "endianness": {
            "title": "Understanding Endianness: Little vs. Big Endian",
            "content": """# Understanding Endianness

Endianness refers to the **order in which bytes of a multibyte word are stored in computer memory or file storage**.

### Little-Endian (Intel x86, AMD64, ARM default)
* The **least significant byte (LSB)** is stored at the lowest memory address.
* Example: Value `1,000` (`0x000003E8` in hexadecimal, 4 bytes):
  - Offset +0: `E8` (least significant)
  - Offset +1: `03`
  - Offset +2: `00`
  - Offset +3: `00` (most significant)
  - In a hex editor, you will read: `E8 03 00 00`

### Big-Endian (Network Byte Order, PowerPC, Sega Genesis)
* The **most significant byte (MSB)** is stored at the lowest address.
* Example: Value `1,000` (`0x000003E8`):
  - In a hex editor, you will read: `00 00 03 E8`

### Why Does This Matter for Game Save Hacking?
Almost all modern PC games (Windows, x64) store numeric values in **Little-Endian**.
If you search for `500` Gold (`0x01F4`), do not search for `01 F4`; search for `F4 01`!
"""
        },
        "diff_methodology": {
            "title": "The Differential Analysis Methodology",
            "content": """# The Differential Analysis Methodology

How do reverse engineers pinpoint variables in unknown binary files without source code?

### The 4-Step Differential Workflow:
1. **Initial Baseline (Save A)**:
   - Create a fresh save. Note the exact in-game state: `Gold = 500`, `Level = 1`.
2. **Deterministic Mutation**:
   - Perform **one single in-game action**. For example, defeat a goblin and collect 50 gold (`Gold = 550`).
   - Leave all other variables untouched if possible.
3. **Delta Save (Save B)**:
   - Save into a second slot.
4. **Byte-for-Byte Comparison**:
   - SaveScope computes `Save B - Save A`.
   - Any offset where `Val_B - Val_A == +50` (or `0x32` in hex) is immediately flagged as a high-probability Gold candidate!
"""
        },
        "shannon_entropy": {
            "title": "Shannon Entropy in Binary Reverse Engineering",
            "content": """# Shannon Entropy

Entropy is a mathematical measure of randomness or unpredictability in a dataset.

* **Score 0.0**: Completely uniform data (e.g. repeated `0x00` padding).
* **Score 2.0 - 4.5**: Standard binary struct formats, integer counters, strings.
* **Score 7.5 - 8.0**: High randomness. This indicates either:
  1. **Compression** (e.g., Zlib / Deflate, GZip, LZ4, Zstandard)
  2. **Encryption** (e.g., AES, Blowfish, XOR pads)

### Practical Application
If your save file has an entropy of `7.95` throughout its entire length, the file is compressed!
Editing raw bytes directly will corrupt the stream or fail decompression. You must first decompress, edit, and re-compress.
"""
        },
        "integers_and_floats": {
            "title": "Data Types: Two's Complement & IEEE-754 Floats",
            "content": """# Primitive Data Types in Save Files

### 1. Unsigned vs Signed Integers
* `uint8` (0 to 255): 1 byte. Used for item counts, levels, flags.
* `int32` (-2,147,483,648 to 2,147,483,647): 4 bytes. Used for currency, experience, quest IDs.
  - Negative values use **Two's Complement**.

### 2. Floating-Point Numbers (IEEE-754)
* `float32` (4 bytes): Used for player coordinates (X, Y, Z), stamina percentages, time-played counters.
  - 1 bit Sign, 8 bits Exponent, 23 bits Fraction.
  - Value `1.0` is `0x3F800000` in hex (or `00 00 80 3F` in little-endian).
"""
        }
    }

    @classmethod
    def get_topics(cls) -> list[dict]:
        return [{"id": k, "title": v["title"]} for k, v in cls.TOPICS.items()]

    @classmethod
    def get_topic_content(cls, topic_id: str) -> str:
        return cls.TOPICS.get(topic_id, {}).get("content", "Topic not found.")
