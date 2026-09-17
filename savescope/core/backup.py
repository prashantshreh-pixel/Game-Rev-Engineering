import os
import shutil
import time
import tempfile
from pathlib import Path
from typing import Optional, Union
from savescope.utils.checksum import compute_sha256

class BackupManager:
    """
    Phase 7: Rolling Backup & Rollback Manager.
    Automatically snapshots save files before modifications, maintaining
    timestamped versions, SHA-256 integrity verification on restore, and atomic rollbacks.
    """

    def __init__(self, backup_root: Optional[Union[str, Path]] = None):
        if backup_root is None:
            self.backup_root = Path.home() / ".savescope" / "backups"
        else:
            self.backup_root = Path(backup_root)
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def create_backup(self, file_path: Union[str, Path], tag: str = "auto") -> Path:
        source = Path(file_path).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Cannot backup non-existent file: {source}")

        game_folder = source.parent.name
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target_dir = self.backup_root / game_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        backup_name = f"{source.stem}_{timestamp}_{tag}{source.suffix}"
        target_path = target_dir / backup_name

        data = source.read_bytes()
        target_path.write_bytes(data)

        # Write metadata sidecar (.meta)
        meta_path = target_path.with_suffix(".meta")
        meta_content = (
            f"original_path: {source}\n"
            f"created_at: {time.time()}\n"
            f"sha256: {compute_sha256(data)}\n"
            f"size: {len(data)}\n"
            f"tag: {tag}\n"
        )
        meta_path.write_text(meta_content, encoding="utf-8")

        return target_path

    def list_backups(self, file_path: Optional[Union[str, Path]] = None) -> list[dict]:
        backups = []
        pattern = "**/*.meta"
        for meta_file in self.backup_root.glob(pattern):
            try:
                lines = dict(
                    line.split(": ", 1)
                    for line in meta_file.read_text(encoding="utf-8").splitlines()
                    if ": " in line
                )
                backup_bin = meta_file.with_suffix("")
                matches = list(meta_file.parent.glob(f"{meta_file.stem}.*"))
                actual_backup = [m for m in matches if m.suffix != ".meta"]
                backup_bin = actual_backup[0] if actual_backup else None

                if backup_bin and backup_bin.exists():
                    orig = lines.get("original_path", "")
                    if file_path is None or str(Path(file_path).resolve()) == str(Path(orig).resolve()):
                        backups.append({
                            "backup_path": backup_bin,
                            "original_path": Path(orig),
                            "timestamp": float(lines.get("created_at", 0)),
                            "sha256": lines.get("sha256", ""),
                            "size": int(lines.get("size", 0)),
                            "tag": lines.get("tag", "auto"),
                        })
            except Exception:
                continue

        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return backups

    def restore_backup(
        self, backup_path: Union[str, Path], destination: Optional[Union[str, Path]] = None, verify_sha256: bool = True
    ) -> Path:
        """
        Restores a backup to its original path or destination.
        Strictly verifies SHA-256 checksum from .meta sidecar before restoring
        and writes destination atomically using temporary file replacement.
        """
        b_path = Path(backup_path).resolve()
        if not b_path.exists():
            raise FileNotFoundError(f"Backup file not found: {b_path}")

        meta_path = b_path.with_suffix(".meta")
        target_path = None
        expected_hash = None

        if meta_path.exists():
            for line in meta_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("original_path: "):
                    target_path = Path(line.split(": ", 1)[1])
                elif line.startswith("sha256: "):
                    expected_hash = line.split(": ", 1)[1].strip()

        if destination:
            target_path = Path(destination)

        if not target_path:
            raise ValueError("No destination specified and original_path not found in metadata.")

        # SHA-256 Integrity Verification
        actual_hash = compute_sha256(b_path.read_bytes())
        if verify_sha256 and expected_hash:
            if actual_hash.lower() != expected_hash.lower():
                raise ValueError(
                    f"Backup integrity verification failed! Expected SHA-256: {expected_hash}, Actual: {actual_hash}"
                )

        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic replacement: write to temp file on same volume then replace
        temp_file = target_path.with_name(f".tmp_{target_path.name}_{os.getpid()}")
        try:
            shutil.copy2(b_path, temp_file)
            temp_file.replace(target_path)
        finally:
            if temp_file.exists():
                temp_file.unlink()

        return target_path
