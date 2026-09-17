from dataclasses import dataclass
from typing import Any, Optional
from savescope.models.schema_models import DataType, Endianness

@dataclass
class DiffCandidate:
    offset: int
    data_type: DataType
    endianness: Endianness
    val_a: Any
    val_b: Any
    delta: Optional[Any] = None
    confidence: float = 0.0
    reason: str = ""

@dataclass
class DiffResult:
    size_a: int
    size_b: int
    identical: bool
    changed_offsets: list[int]
    candidates: list[DiffCandidate]
    contiguous_regions: list[tuple[int, int]]

    @property
    def total_changed_bytes(self) -> int:
        return len(self.changed_offsets)
