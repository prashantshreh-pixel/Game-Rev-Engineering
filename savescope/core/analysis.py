import math
from collections import Counter
from typing import Optional

class BinaryAnalysisEngine:
    """
    Phase 9: Advanced Analysis.
    Calculates Shannon entropy, detects compression/encryption blocks,
    computes byte frequency histograms, and discovers structural boundaries.
    """

    @staticmethod
    def calculate_shannon_entropy(data: bytes) -> float:
        """Returns Shannon entropy between 0.0 (uniform/constant) and 8.0 (pure random/compressed)."""
        if not data:
            return 0.0
        counts = Counter(data)
        total = len(data)
        entropy = 0.0
        for count in counts.values():
            p = count / total
            entropy -= p * math.log2(p)
        return round(entropy, 4)

    @classmethod
    def sliding_window_entropy(cls, data: bytes, window_size: int = 64, step: int = 16) -> list[tuple[int, float]]:
        """Returns a list of (offset, entropy) points across the binary file."""
        if len(data) < window_size:
            return [(0, cls.calculate_shannon_entropy(data))]

        points = []
        for offset in range(0, len(data) - window_size + 1, step):
            window = data[offset : offset + window_size]
            points.append((offset, cls.calculate_shannon_entropy(window)))
        return points

    @staticmethod
    def byte_distribution(data: bytes) -> dict[int, int]:
        """Returns byte values (0..255) mapped to their frequency counts."""
        counts = Counter(data)
        return {b: counts.get(b, 0) for b in range(256)}

    @classmethod
    def identify_blocks(cls, data: bytes, chunk_size: int = 32) -> list[dict]:
        """
        Categorizes blocks into structural types:
        - ZERO_PADDING: All zero bytes
        - ASCII_TEXT: Mostly printable characters
        - STRUCTURED_DATA: Low-to-moderate entropy (structs, counters)
        - COMPRESSED_OR_ENCRYPTED: High entropy (> 7.2)
        """
        blocks = []
        for offset in range(0, len(data), chunk_size):
            chunk = data[offset : offset + chunk_size]
            if not chunk:
                continue

            entropy = cls.calculate_shannon_entropy(chunk)
            zero_ratio = chunk.count(b"\x00") / len(chunk)
            printable_ratio = sum(1 for b in chunk if 32 <= b <= 126 or b in (9, 10, 13)) / len(chunk)

            max_possible = math.log2(len(chunk)) if len(chunk) > 1 else 1.0
            entropy_ratio = entropy / max_possible if max_possible > 0 else 0.0

            if zero_ratio > 0.90:
                block_type = "ZERO_PADDING"
                desc = "Null byte padding region"
            elif printable_ratio > 0.80:
                block_type = "ASCII_TEXT"
                desc = f"Text string data ('{chunk.decode('ascii', errors='replace')[:16]}...')"
            elif entropy_ratio > 0.88 or entropy > 7.0:
                block_type = "COMPRESSED_OR_ENCRYPTED"
                desc = f"High entropy ({entropy:.2f}, likely compressed or encrypted)"
            else:
                block_type = "STRUCTURED_DATA"
                desc = "Standard binary integers, floats, or structs"

            blocks.append({
                "offset": offset,
                "size": len(chunk),
                "entropy": entropy,
                "type": block_type,
                "description": desc,
            })
        return blocks
