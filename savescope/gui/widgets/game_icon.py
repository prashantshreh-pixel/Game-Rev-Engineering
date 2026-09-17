import os
import winreg
from pathlib import Path
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont
from PyQt6.QtCore import Qt

class GameIconManager:
    """
    Manages loading and rendering game icons and badges.
    Extracts icons from Windows registry / Steam / exe, or generates stylish
    colored badges matching modern game launchers (NVIDIA App / Steam style).
    """
    _cache: dict[str, QIcon] = {}

    @classmethod
    def get_icon(cls, game_name: str, file_path: str = "") -> QIcon:
        clean_name = game_name.lower().strip()
        if clean_name in cls._cache:
            return cls._cache[clean_name]

        # 1. Check if an icon file exists in the registry
        reg_icon = cls._lookup_registry_icon(game_name)
        if reg_icon and Path(reg_icon).exists():
            try:
                icon = QIcon(reg_icon)
                if not icon.isNull():
                    cls._cache[clean_name] = icon
                    return icon
            except Exception:
                pass

        # 2. Generate a modern gaming badge
        icon = cls._generate_badge_icon(game_name)
        cls._cache[clean_name] = icon
        return icon

    @classmethod
    def _generate_badge_icon(cls, name: str) -> QIcon:
        pix = QPixmap(64, 64)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Palette selection based on hash
        colors = [
            ("#ff4655", "#b31b26"),  # Red / Valorant style
            ("#e5a93b", "#a86c0c"),  # Gold / RPG style
            ("#0078d7", "#004578"),  # Blue / Sci-fi style
            ("#2da44e", "#1b632e"),  # Green / Forest
            ("#8957e5", "#5a2ca6"),  # Purple / Magic
            ("#d73a49", "#cb2431"),  # Crimson / Dark Souls style
        ]
        h = sum(ord(c) for c in name) % len(colors)
        bg_col, border_col = colors[h]

        painter.setBrush(QColor(bg_col))
        painter.setPen(QColor(border_col))
        painter.drawRoundedRect(4, 4, 56, 56, 12, 12)

        # Initials text (max 3 letters)
        parts = [p[0].upper() for p in name.replace(":", " ").replace("-", " ").split() if p]
        initials = "".join(parts[:3]) or "G"

        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(0, 0, 64, 64, Qt.AlignmentFlag.AlignCenter, initials)
        painter.end()

        return QIcon(pix)

    @classmethod
    def _lookup_registry_icon(cls, game_name: str) -> str:
        uninstall_keys = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
        ]
        target = game_name.lower().replace(" ", "").replace(":", "")
        for ukey in uninstall_keys:
            for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    k = winreg.OpenKey(root, ukey)
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        try:
                            sub = winreg.EnumKey(k, i)
                            sk = winreg.OpenKey(k, sub)
                            try:
                                d_name, _ = winreg.QueryValueEx(sk, "DisplayName")
                                if target in d_name.lower().replace(" ", ""):
                                    icon, _ = winreg.QueryValueEx(sk, "DisplayIcon")
                                    # Strip possible ",0" index
                                    icon = icon.split(",")[0].strip('"')
                                    if icon.lower().endswith(".ico") or icon.lower().endswith(".exe"):
                                        return icon
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass
        return ""
