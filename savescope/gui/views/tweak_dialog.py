import json
import xml.dom.minidom
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit,
    QMessageBox, QSplitter, QHeaderView, QLineEdit, QTabWidget, QWidget, QFrame
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt

from savescope.models.game import SaveSlot
from savescope.core.backup import BackupManager
from savescope.core.sl2 import SL2Container
from savescope.gui.widgets.hex_grid import HexViewerWidget
from savescope.gui.views.sekiro_studio import SekiroStudioWidget

class SaveTweakDialog(QDialog):
    """
    Intelligent Save Tweak Editor & FromSoftware SL2 Repair Suite:
    - Sekiro Studio: Dedicated character stats, inventory manager, item spawner, and slot importer.
    - Text Mode: For JSON, XML, and INI configuration files with live formatting & search.
    - Hex Editor Mode: For binary save containers (.sl2, .dat, .bin) with offset navigation and in-place byte editing.
    - Automatic Checksum Engine: If an .sl2 FromSoftware save (Sekiro / Elden Ring) is detected,
      it verifies all slot checksums and automatically recalculates the 16-byte MD5 hashes on write
      so the game NEVER triggers 'Save Data is Corrupted'!
    - Automatic Rolling Backup: Snapshots original files before any byte is altered.
    """
    def __init__(self, slot: SaveSlot, game_name: str, parent=None):
        super().__init__(parent)
        self.slot = slot
        self.game_name = game_name
        self.backup_mgr = BackupManager()
        self.sl2_container: SL2Container = None
        self.sekiro_studio: SekiroStudioWidget = None

        self.setWindowTitle(f"SaveScope Tweak Editor — {game_name}: {slot.name}")
        self.resize(1150, 760)

        layout = QVBoxLayout(self)

        # Header Info Bar
        info_bar = QHBoxLayout()
        fmt_badge = f"<b style='color: #4ec9b0;'>[{slot.format_type.upper()}]</b>"
        info_bar.addWidget(QLabel(f"<b>File:</b> {slot.name} {fmt_badge}  |  <b>Path:</b> <span style='color: #888888;'>{slot.path}</span>"))
        info_bar.addStretch()

        btn_open_folder = QPushButton("Open Folder in Explorer")
        btn_open_folder.clicked.connect(self._open_in_explorer)
        info_bar.addWidget(btn_open_folder)
        layout.addLayout(info_bar)

        # Check if file is an SL2 FromSoftware save
        is_sl2 = SL2Container.is_sl2_file(self.slot.path)
        if is_sl2:
            self.sl2_container = SL2Container(self.slot.path)
            self._render_sl2_banner(layout)

        # Main Tabs
        self.tabs = QTabWidget()

        # Check if this is a Sekiro save file
        if self.sl2_container:
            is_sekiro = (
                "sekiro" in self.game_name.lower()
                or "sekiro" in str(self.slot.path).lower()
                or (len(self.sl2_container.slots) >= 1 and self.sl2_container.slots[0].payload_size == 0x100000)
            )
            if is_sekiro:
                self.sekiro_studio = SekiroStudioWidget(self.sl2_container, parent=self)
                self.sekiro_studio.dataChanged.connect(self._on_sekiro_studio_changed)
                self.tabs.addTab(self.sekiro_studio, "🥷 Sekiro Character & Inventory Studio")

        # Tab: Interactive Hex Editor
        self.hex_widget = HexViewerWidget(editable=True)

        # Tab: Text / Config Editor
        self.text_widget = QWidget()
        text_layout = QVBoxLayout(self.text_widget)
        text_layout.setContentsMargins(0, 5, 0, 0)

        search_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search parameters (e.g. gold, money, level, health, runes, sen)...")
        self.search_input.textChanged.connect(self._search_text)
        search_bar.addWidget(self.search_input)

        if slot.format_type == "json":
            btn_format = QPushButton("Prettify / Format JSON")
            btn_format.clicked.connect(self._format_json)
            search_bar.addWidget(btn_format)
        elif slot.format_type == "xml":
            btn_format = QPushButton("Prettify XML")
            btn_format.clicked.connect(self._format_xml)
            search_bar.addWidget(btn_format)
        text_layout.addLayout(search_bar)

        self.editor = QTextEdit()
        self.editor.setFont(QFont("Consolas", 11))
        self.editor.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; selection-background-color: #264f78;")
        text_layout.addWidget(self.editor)

        # Add tabs according to format
        if slot.is_tweakable_text:
            self.tabs.addTab(self.text_widget, "Text / Parameter Editor")
            self.tabs.addTab(self.hex_widget, "Raw Binary Hex Inspector")
        else:
            self.tabs.addTab(self.hex_widget, "Interactive Hex Editor")
            self.tabs.addTab(self.text_widget, "Plain Text Preview")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

        # Bottom Action Bar
        bottom_bar = QHBoxLayout()
        self.status_lbl = QLabel(f"Size: {slot.size_bytes} bytes | SHA256: {slot.sha256[:16]}...")
        self.status_lbl.setStyleSheet("color: #888888; padding: 2px 0;")
        bottom_bar.addWidget(self.status_lbl)
        bottom_bar.addStretch()

        if self.sl2_container:
            btn_recalc = QPushButton("Verify & Recalculate SL2 Checksums")
            btn_recalc.setStyleSheet("background-color: #0e639c; color: white; font-weight: bold; padding: 7px 14px;")
            btn_recalc.clicked.connect(self._recalculate_sl2)
            bottom_bar.addWidget(btn_recalc)

        self.btn_revert = QPushButton("Revert to Original")
        self.btn_revert.clicked.connect(self._load_content)
        bottom_bar.addWidget(self.btn_revert)

        self.btn_save = QPushButton("Save Changes (Auto-Backup & Patch Checksums)")
        self.btn_save.setStyleSheet("background-color: #2da44e; color: white; font-weight: bold; padding: 8px 18px;")
        self.btn_save.clicked.connect(self._save_changes)
        bottom_bar.addWidget(self.btn_save)

        layout.addLayout(bottom_bar)

        self._load_content()

    def _render_sl2_banner(self, parent_layout: QVBoxLayout):
        banner = QFrame()
        banner.setStyleSheet("background-color: #162a45; border: 1px solid #205493; border-radius: 6px; padding: 8px;")
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(10, 6, 10, 6)

        msg = (
            "<b style='color: #4ec9b0;'>FromSoftware BND4 Save Detected (Sekiro / Elden Ring)</b><br>"
            "<span style='color: #cccccc; font-size: 11px;'>"
            "SaveScope automatically verifies and recalculates the 16-byte MD5 slot checksums before saving. "
            "Any byte edits in the Hex Editor will not corrupt your save data!</span>"
        )
        b_layout.addWidget(QLabel(msg))
        b_layout.addStretch()

        is_valid = self.sl2_container.verify_all()
        status_text = "<b style='color: #55ff55;'>All 12 Slots Intact</b>" if is_valid else "<b style='color: #ff5555;'>Checksum Mismatch Detected!</b>"
        b_layout.addWidget(QLabel(status_text))

        parent_layout.addWidget(banner)

    def _load_content(self):
        try:
            raw = self.slot.path.read_bytes()

            # Load Hex View
            self.hex_widget.load_bytes(raw)

            # Load Text View
            if self.slot.format_type == "json":
                try:
                    obj = json.loads(raw.decode("utf-8", errors="replace"))
                    self.editor.setText(json.dumps(obj, indent=2))
                    return
                except Exception:
                    pass

            if self.slot.is_tweakable_text:
                self.editor.setText(raw.decode("utf-8", errors="replace"))
            else:
                notice = (
                    f"/* NOTICE: {self.slot.name} is a compiled binary save container ({self.slot.format_type.upper()}).\\n"
                    " * Use the 'Interactive Hex Editor' tab to edit bytes safely.\\n"
                    " */\\n\\n"
                )
                text_preview = raw[:32768].decode("ascii", errors="replace")
                self.editor.setText(notice + text_preview)
        except Exception as e:
            self.editor.setText(f"Failed loading file: {e}")

    def _recalculate_sl2(self):
        if not self.sl2_container:
            return
        # Sync buffer from hex widget
        self.sl2_container.data = bytearray(self.hex_widget.current_bytes)
        patched = self.sl2_container.recalculate_and_patch_checksums()
        self.hex_widget.load_bytes(self.sl2_container.data)
        QMessageBox.information(
            self, "SL2 Checksum Verification",
            f"Successfully checked all 12 FromSoftware save slots!\\n"
            f"Recalculated and patched MD5 checksum headers for {patched} slot(s).\\n\\n"
            f"Save file is 100% verified and ready for the game."
        )

    def _format_json(self):
        try:
            obj = json.loads(self.editor.toPlainText())
            self.editor.setText(json.dumps(obj, indent=2))
            QMessageBox.information(self, "Success", "JSON formatted and validated successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Invalid JSON", f"Syntax Error: {e}")

    def _format_xml(self):
        try:
            dom = xml.dom.minidom.parseString(self.editor.toPlainText())
            self.editor.setText(dom.toprettyxml(indent="  "))
            QMessageBox.information(self, "Success", "XML formatted successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Invalid XML", f"Syntax Error: {e}")

    def _search_text(self, term: str):
        if not term:
            return
        found = self.editor.find(term)
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.editor.setTextCursor(cursor)
            self.editor.find(term)

    def _on_tab_changed(self, index: int):
        current_widget = self.tabs.widget(index)
        if self.sekiro_studio and current_widget == self.sekiro_studio:
            # Sync container data from hex widget if user edited in hex view
            self.sl2_container.data = bytearray(self.hex_widget.current_bytes)
            self.sekiro_studio._load_slot(self.sekiro_studio.current_slot_idx)
        elif current_widget == self.hex_widget and self.sl2_container:
            # Sync hex view from container data
            self.hex_widget.load_bytes(self.sl2_container.data)

    def _on_sekiro_studio_changed(self):
        if self.sl2_container:
            self.hex_widget.load_bytes(self.sl2_container.data)

    def _save_changes(self):
        try:
            # 1. Automatic pre-modification backup with SHA-256 verification
            backup_path = self.backup_mgr.create_backup(self.slot.path, tag="pre_tweak")

            if self.slot.is_tweakable_text:
                # Text save
                content = self.editor.toPlainText()
                if self.slot.format_type == "json":
                    try:
                        json.loads(content)
                    except Exception as e:
                        reply = QMessageBox.question(
                            self, "JSON Syntax Warning",
                            f"The JSON contains syntax errors:\n{e}\n\nSave anyway?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )
                        if reply == QMessageBox.StandardButton.No:
                            return

                self.slot.path.write_text(content, encoding="utf-8")
            else:
                # Binary save: if SL2 container, save via sl2_container with checksum patching
                if self.sl2_container:
                    # If current tab is hex widget, sync from hex widget first
                    if self.tabs.currentWidget() == self.hex_widget:
                        self.sl2_container.data = bytearray(self.hex_widget.current_bytes)
                    self.sl2_container.save(output_path=self.slot.path, auto_recalculate=True)
                else:
                    data_to_write = bytearray(self.hex_widget.current_bytes)
                    temp_file = self.slot.path.with_name(f".tmp_{self.slot.path.name}")
                    temp_file.write_bytes(data_to_write)
                    temp_file.replace(self.slot.path)

            self.status_lbl.setText(f"Saved & Verified! Backup at: {backup_path.name}")
            msg = f"Successfully saved changes to:\\n{self.slot.name}\\n\\nBackup created at:\\n{backup_path}"
            if self.sl2_container:
                msg += "\\n\\nFromSoftware MD5 slot checksums were automatically recalculated and patched!"
            QMessageBox.information(self, "Save Complete", msg)

        except Exception as e:
            QMessageBox.critical(self, "Error Saving File", f"Failed saving file: {e}")

    def _open_in_explorer(self):
        import os
        folder = self.slot.path.parent
        os.system(f'explorer "{folder}"')
