import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt

from savescope.core.schema import SchemaManager
from savescope.core.editor import SaveEditor
from savescope.core.presets import PresetLibrary

MAX_GUI_OPEN_SIZE = 150 * 1024 * 1024  # 150 MB safety cap

class StructureView(QWidget):
    """
    Phase 5: Dynamic Structure & Value Editor.
    Hardened against unsafe schema bypass by forcing 'Save As Copy' when validation fails.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.schema_mgr = SchemaManager()
        self.editor: SaveEditor = None

        layout = QVBoxLayout(self)

        # Top Bar
        top_bar = QHBoxLayout()
        self.btn_load = QPushButton("Open Save File...")
        self.btn_load.clicked.connect(self._open_file)
        top_bar.addWidget(self.btn_load)

        self.schema_select = QComboBox()
        for s in self.schema_mgr.schemas:
            self.schema_select.addItem(s.name)
        top_bar.addWidget(QLabel("Schema:"))
        top_bar.addWidget(self.schema_select)

        self.preset_select = QComboBox()
        self.presets = PresetLibrary.get_standard_presets()
        for p in self.presets:
            self.preset_select.addItem(p.name)
        top_bar.addWidget(QLabel("Preset:"))
        top_bar.addWidget(self.preset_select)

        self.btn_apply_preset = QPushButton("Apply Preset")
        self.btn_apply_preset.clicked.connect(self._apply_preset)
        top_bar.addWidget(self.btn_apply_preset)

        self.btn_save = QPushButton("Save & Backup Changes")
        self.btn_save.setStyleSheet("background-color: #2da44e; color: white; font-weight: bold; padding: 6px 14px;")
        self.btn_save.clicked.connect(self._save_changes)
        top_bar.addWidget(self.btn_save)

        self.btn_save_as = QPushButton("Save As Copy...")
        self.btn_save_as.clicked.connect(self._save_as_copy)
        top_bar.addWidget(self.btn_save_as)

        layout.addLayout(top_bar)

        self.mode_banner = QLabel("Ready")
        self.mode_banner.setStyleSheet("color: #888888; font-size: 11px; padding: 2px 4px;")
        layout.addWidget(self.mode_banner)

        # Field table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Key", "Category", "Offset", "Type", "Current Value", "Description"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.cellChanged.connect(self._on_cell_edited)
        layout.addWidget(self.table)

        self._updating_ui = False

    def _open_file(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Open Save File", "", "All Files (*.*)")
        if not fpath:
            return

        p = Path(fpath)
        if p.stat().st_size > MAX_GUI_OPEN_SIZE:
            QMessageBox.critical(self, "File Too Large", f"Selected file ({p.stat().st_size / 1048576:.1f} MB) exceeds maximum allowed size (150 MB).")
            return

        schema_name = self.schema_select.currentText()
        schema = self.schema_mgr.get_schema(schema_name)
        if not schema:
            QMessageBox.warning(self, "Warning", "Please select a valid schema first.")
            return

        try:
            self.editor = SaveEditor(fpath, schema, enforce_schema_guards=True)
            self.mode_banner.setText(f"Loaded: {p.name} (Schema: {schema.name}) — Verified Integrity")
            self.mode_banner.setStyleSheet("color: #55ff55; font-weight: bold;")
            self.btn_save.setEnabled(True)
            self._refresh_table()
        except ValueError as e:
            reply = QMessageBox.question(
                self, "Schema Integrity Mismatch",
                f"File failed schema validation:\n{e}\n\n"
                "Would you like to open in UNSAFE COPY-ONLY mode?\n"
                "(Direct overwrites will be disabled to protect your original save. You may only 'Save As Copy'.)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.editor = SaveEditor(fpath, schema, enforce_schema_guards=False)
                self.mode_banner.setText(f"UNSAFE COPY-ONLY MODE: {p.name} (Direct overwrite forbidden)")
                self.mode_banner.setStyleSheet("color: #ff5555; font-weight: bold;")
                self.btn_save.setEnabled(False)  # Disable direct overwrite
                self._refresh_table()

    def _refresh_table(self):
        if not self.editor:
            return

        self._updating_ui = True
        self.table.setRowCount(len(self.editor.schema.fields))

        for row, f in enumerate(self.editor.schema.fields):
            val = self.editor.get_value(f.key)
            self.table.setItem(row, 0, QTableWidgetItem(f.key))
            self.table.setItem(row, 1, QTableWidgetItem(f.category))
            self.table.setItem(row, 2, QTableWidgetItem(f"0x{f.offset:04X} ({f.offset})"))
            self.table.setItem(row, 3, QTableWidgetItem(f.data_type.value))

            val_item = QTableWidgetItem(str(val))
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, val_item)
            self.table.setItem(row, 5, QTableWidgetItem(f.description))

        self._updating_ui = False

    def _on_cell_edited(self, row, col):
        if self._updating_ui or not self.editor or col != 4:
            return

        key_item = self.table.item(row, 0)
        val_item = self.table.item(row, 4)
        if not key_item or not val_item:
            return

        key = key_item.text()
        raw_val = val_item.text()

        errors = self.editor.set_value(key, raw_val)
        if errors:
            QMessageBox.critical(self, "Validation Error", "\n".join(errors))
            self._refresh_table()

    def _apply_preset(self):
        if not self.editor:
            return
        idx = self.preset_select.currentIndex()
        if 0 <= idx < len(self.presets):
            preset = self.presets[idx]
            self.editor.apply_preset(preset)
            self._refresh_table()
            QMessageBox.information(self, "Preset Applied", f"Preset '{preset.name}' applied to buffer!")

    def _save_changes(self):
        if not self.editor:
            return
        try:
            saved_path = self.editor.save(auto_backup=True)
            QMessageBox.information(self, "Success", f"Changes saved! Rolling backup verified at:\n{saved_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed saving file: {e}")

    def _save_as_copy(self):
        if not self.editor:
            return
        out_path, _ = QFileDialog.getSaveFileName(self, "Save As Copy", "", "Save Files (*.dat *.sav *.bin *.sl2);;All Files (*.*)")
        if not out_path:
            return
        try:
            saved_path = self.editor.save(destination=out_path, auto_backup=False)
            QMessageBox.information(self, "Success", f"Successfully exported copy to:\n{saved_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed exporting copy: {e}")
