from dataclasses import dataclass, field
import pathlib
from typing import Optional

@dataclass
class SaveSlot:
    path: pathlib.Path
    name: str
    size_bytes: int
    modified_time: float
    sha256: str = ""
    backup_count: int = 0
    format_type: str = "binary"  # "json", "xml", "ini", "text", "binary"

    @property
    def is_tweakable_text(self) -> bool:
        return self.format_type in ("json", "xml", "ini", "text")

@dataclass
class DiscoveredGame:
    game_id: str
    name: str
    publisher: str = "Unknown"
    launcher: str = "Custom"
    install_dir: Optional[pathlib.Path] = None
    save_dir: Optional[pathlib.Path] = None
    save_files: list[SaveSlot] = field(default_factory=list)
    associated_schema: Optional[str] = None
    icon_path: Optional[pathlib.Path] = None

    @property
    def total_saves(self) -> int:
        return len(self.save_files)

    @property
    def tweakable_count(self) -> int:
        return sum(1 for s in self.save_files if s.is_tweakable_text)
