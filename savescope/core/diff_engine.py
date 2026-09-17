import struct
import math
from typing import Optional, Union
from pathlib import Path

from savescope.models.schema_models import DataType, Endianness
from savescope.models.diff_models import DiffCandidate, DiffResult

class DiffEngine:
    """
    Phase 1 & 2: Differential Analysis Engine with Strict Region Alignment.
    Compares binary save files, identifies contiguous changed regions,
    applies alignment heuristics, and penalizes unaligned arbitrary multibyte overlaps.
    """

    @classmethod
    def compare_files(cls, path_a: Union[str, Path], path_b: Union[str, Path]) -> DiffResult:
        data_a = Path(path_a).read_bytes()
        data_b = Path(path_b).read_bytes()
        return cls.compare_bytes(data_a, data_b)

    @classmethod
    def compare_bytes(cls, data_a: bytes, data_b: bytes) -> DiffResult:
        size_a = len(data_a)
        size_b = len(data_b)
        min_size = min(size_a, size_b)

        changed_offsets: list[int] = []
        for i in range(min_size):
            if data_a[i] != data_b[i]:
                changed_offsets.append(i)

        if size_a != size_b:
            changed_offsets.extend(range(min_size, max(size_a, size_b)))

        identical = len(changed_offsets) == 0

        # Calculate contiguous regions
        regions: list[tuple[int, int]] = []
        if changed_offsets:
            start = changed_offsets[0]
            prev = start
            for off in changed_offsets[1:]:
                if off == prev + 1:
                    prev = off
                else:
                    regions.append((start, prev))
                    start = off
                    prev = off
            regions.append((start, prev))

        candidates = cls._infer_candidates(data_a, data_b, changed_offsets, regions)
        return DiffResult(
            size_a=size_a,
            size_b=size_b,
            identical=identical,
            changed_offsets=changed_offsets,
            candidates=candidates,
            contiguous_regions=regions,
        )

    @classmethod
    def _infer_candidates(
        cls,
        data_a: bytes,
        data_b: bytes,
        changed_offsets: list[int],
        regions: list[tuple[int, int]]
    ) -> list[DiffCandidate]:
        candidates: list[DiffCandidate] = []
        changed_set = set(changed_offsets)
        min_len = min(len(data_a), len(data_b))
        visited_checks: set[tuple[int, DataType, Endianness]] = set()

        # Build map of which changed region an offset belongs to
        # (region_start, region_end, region_length)
        region_map = {}
        for r_start, r_end in regions:
            r_len = r_end - r_start + 1
            for o in range(r_start, r_end + 1):
                region_map[o] = (r_start, r_end, r_len)

        for off in changed_offsets:
            if off >= min_len:
                continue

            r_info = region_map.get(off, (off, off, 1))
            r_start, r_end, r_len = r_info

            # Candidate evaluation start positions:
            candidate_starts = {off, r_start}
            candidate_starts.add(off - (off % 2))
            candidate_starts.add(off - (off % 4))
            if off >= 4:
                candidate_starts.add(off - 4)

            for c_off in sorted(candidate_starts):
                if c_off < 0 or c_off >= min_len:
                    continue

                # -------------------------------------------------------------
                # 1 BYTE TYPES (uint8, int8)
                # -------------------------------------------------------------
                if c_off in changed_set:
                    u8_a, u8_b = data_a[c_off], data_b[c_off]
                    cand_key = (c_off, DataType.UINT8, Endianness.LITTLE)
                    if cand_key not in visited_checks:
                        visited_checks.add(cand_key)

                        delta = u8_b - u8_a
                        # Isolated single byte change (e.g. Level 1 -> 2) scores very high!
                        if r_len == 1:
                            conf = 0.94
                            if 0 < abs(delta) <= 10:
                                conf += 0.04  # Extra bonus for level/stat progression
                        else:
                            conf = 0.65

                        candidates.append(
                            DiffCandidate(
                                offset=c_off,
                                data_type=DataType.UINT8,
                                endianness=Endianness.LITTLE,
                                val_a=u8_a,
                                val_b=u8_b,
                                delta=delta,
                                confidence=min(conf, 0.98),
                                reason=f"UInt8 changed {u8_a} -> {u8_b} (delta: {delta:+d})",
                            )
                        )

                    # Signed int8
                    i8_a = struct.unpack_from("b", data_a, c_off)[0]
                    i8_b = struct.unpack_from("b", data_b, c_off)[0]
                    if (i8_a < 0 or i8_b < 0) and (c_off, DataType.INT8, Endianness.LITTLE) not in visited_checks:
                        visited_checks.add((c_off, DataType.INT8, Endianness.LITTLE))
                        candidates.append(
                            DiffCandidate(
                                offset=c_off,
                                data_type=DataType.INT8,
                                endianness=Endianness.LITTLE,
                                val_a=i8_a,
                                val_b=i8_b,
                                delta=i8_b - i8_a,
                                confidence=0.72,
                                reason=f"Signed Int8 changed {i8_a} -> {i8_b}",
                            )
                        )

                # -------------------------------------------------------------
                # 2 BYTE TYPES (uint16, int16)
                # -------------------------------------------------------------
                if c_off + 2 <= min_len and any((c_off + i) in changed_set for i in range(2)):
                    is_aligned_2 = (c_off % 2 == 0)
                    # How many bytes in [c_off, c_off + 2] changed?
                    changed_in_window = sum(1 for i in range(2) if (c_off + i) in changed_set)

                    for endian in (Endianness.LITTLE, Endianness.BIG):
                        fmt_u = "<H" if endian == Endianness.LITTLE else ">H"
                        u16_a = struct.unpack_from(fmt_u, data_a, c_off)[0]
                        u16_b = struct.unpack_from(fmt_u, data_b, c_off)[0]

                        if u16_a != u16_b:
                            cand_key = (c_off, DataType.UINT16, endian)
                            if cand_key not in visited_checks:
                                visited_checks.add(cand_key)

                                conf = 0.70
                                if is_aligned_2:
                                    conf += 0.15
                                else:
                                    conf -= 0.25

                                if endian == Endianness.LITTLE:
                                    conf += 0.05

                                # Perfect region fit: changed region begins at c_off and is <= 2 bytes
                                if c_off == r_start and r_len <= 2:
                                    conf += 0.08

                                delta = u16_b - u16_a
                                if 0 < abs(delta) <= 1000:
                                    conf += 0.05

                                candidates.append(
                                    DiffCandidate(
                                        offset=c_off,
                                        data_type=DataType.UINT16,
                                        endianness=endian,
                                        val_a=u16_a,
                                        val_b=u16_b,
                                        delta=delta,
                                        confidence=max(0.20, min(conf, 0.96)),
                                        reason=f"UInt16 ({endian.value}) delta: {delta:+d}",
                                    )
                                )

                # -------------------------------------------------------------
                # 4 BYTE TYPES (uint32, int32, float32)
                # -------------------------------------------------------------
                if c_off + 4 <= min_len and any((c_off + i) in changed_set for i in range(4)):
                    is_aligned_4 = (c_off % 4 == 0)

                    # Inspect how many independent regions intersect this 4-byte window
                    intersected_regions = {region_map[c_off + i] for i in range(4) if (c_off + i) in region_map}
                    # If this 4-byte window straddles multiple separate changed regions, it's noise!
                    multiple_regions = len(intersected_regions) > 1

                    for endian in (Endianness.LITTLE, Endianness.BIG):
                        fmt_u = "<I" if endian == Endianness.LITTLE else ">I"
                        fmt_f = "<f" if endian == Endianness.LITTLE else ">f"

                        u32_a = struct.unpack_from(fmt_u, data_a, c_off)[0]
                        u32_b = struct.unpack_from(fmt_u, data_b, c_off)[0]

                        # Float candidate (checked first so legitimate floats aren't masked by int32)
                        f32_a = struct.unpack_from(fmt_f, data_a, c_off)[0]
                        f32_b = struct.unpack_from(fmt_f, data_b, c_off)[0]
                        if f32_a != f32_b and not (math.isnan(f32_a) or math.isnan(f32_b)):
                            # Check plausible game floats (between 0.001 and 1,000,000)
                            if (abs(f32_a) < 1e7 and abs(f32_b) < 1e7 and
                                (f32_a == 0.0 or 1e-3 <= abs(f32_a)) and
                                (f32_b == 0.0 or 1e-3 <= abs(f32_b))):
                                cand_key = (c_off, DataType.FLOAT32, endian)
                                if cand_key not in visited_checks:
                                    visited_checks.add(cand_key)

                                    f_conf = 0.80
                                    if is_aligned_4:
                                        f_conf += 0.12
                                    else:
                                        f_conf -= 0.30
                                    if endian == Endianness.LITTLE:
                                        f_conf += 0.05
                                    if c_off == r_start:
                                        f_conf += 0.05
                                    if multiple_regions:
                                        f_conf -= 0.35

                                    f_delta = round(f32_b - f32_a, 4)
                                    candidates.append(
                                        DiffCandidate(
                                            offset=c_off,
                                            data_type=DataType.FLOAT32,
                                            endianness=endian,
                                            val_a=round(f32_a, 4),
                                            val_b=round(f32_b, 4),
                                            delta=f_delta,
                                            confidence=max(0.15, min(f_conf, 0.98)),
                                            reason=f"Float32 ({endian.value}) changed {f32_a:.2f} -> {f32_b:.2f}",
                                        )
                                    )

                        # UInt32 candidate
                        if u32_a != u32_b:
                            cand_key = (c_off, DataType.UINT32, endian)
                            if cand_key not in visited_checks:
                                visited_checks.add(cand_key)

                                conf = 0.70
                                if is_aligned_4:
                                    conf += 0.15
                                else:
                                    conf -= 0.35

                                if endian == Endianness.LITTLE:
                                    conf += 0.05

                                # Penalize multi-region straddling (e.g. byte 20 and byte 22 straddled together)
                                if multiple_regions:
                                    conf -= 0.30

                                delta = u32_b - u32_a
                                # Reasonable game economy range
                                if 0 <= u32_a <= 50_000_000 and 0 <= u32_b <= 50_000_000:
                                    conf += 0.05
                                    if 0 < abs(delta) <= 100_000:
                                        conf += 0.04
                                else:
                                    # Very high astronomical numbers without float plausibility penalized
                                    conf -= 0.15

                                candidates.append(
                                    DiffCandidate(
                                        offset=c_off,
                                        data_type=DataType.UINT32,
                                        endianness=endian,
                                        val_a=u32_a,
                                        val_b=u32_b,
                                        delta=delta,
                                        confidence=max(0.15, min(conf, 0.99)),
                                        reason=f"UInt32 ({endian.value}) delta: {delta:+d}",
                                    )
                                )

        # Sort candidates: confidence descending, priority to higher confidence & naturally aligned offsets
        candidates.sort(key=lambda c: (round(c.confidence, 2), -c.offset), reverse=True)
        return candidates
