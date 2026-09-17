from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QTableWidget, QTableWidgetItem, QSplitter, QHeaderView
)
from PyQt6.QtCore import Qt
from pathlib import Path

from savescope.core.diff_engine import DiffEngine
from savescope.gui.widgets.hex_grid import HexViewerWidget

class DiffView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # File Select Bar
        top_bar = QHBoxLayout()
        self.btn_load_a = QPushButton("Select Save File A...")
        self.btn_load_a.clicked.connect(self._select_file_a)
        self.lbl_file_a = QLabel("File A: (None)")
        top_bar.addWidget(self.btn_load_a)
        top_bar.addWidget(self.lbl_file_a)

        self.btn_load_b = QPushButton("Select Save File B...")
        self.btn_load_b.clicked.connect(self._select_file_b)
        self.lbl_file_b = QLabel("File B: (None)")
        top_bar.addWidget(self.btn_load_b)
        top_bar.addWidget(self.lbl_file_b)

        self.btn_run_diff = QPushButton("Run Diff Analysis")
        self.btn_run_diff.setStyleSheet("background-color: #0e639c; color: white; font-weight: bold; padding: 6px;")
        self.btn_run_diff.clicked.connect(self._run_diff)
        top_bar.addWidget(self.btn_run_diff)
        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Side by side Hex Viewers
        hex_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.hex_a = HexViewerWidget()
        self.hex_b = HexViewerWidget()
        hex_splitter.addWidget(self.hex_a)
        hex_splitter.addWidget(self.hex_b)
        splitter.addWidget(hex_splitter)

        # Results Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Offset", "Hex", "Inferred Type", "Endian", "Val A", "Val B", "Delta", "Confidence"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.table)

        layout.addWidget(splitter)

        self.path_a = None
        self.path_b = None

    def _select_file_a(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Save A", "", "All Files (*.*)")
        if file_path:
            self.path_a = Path(file_path)
            self.lbl_file_a.setText(f"File A: {self.path_a.name}")

    def _select_file_b(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Save B", "", "All Files (*.*)")
        if file_path:
            self.path_b = Path(file_path)
            self.lbl_file_b.setText(f"File B: {self.path_b.name}")

    def _run_diff(self):
        if not self.path_a or not self.path_b:
            return

        res = DiffEngine.compare_files(self.path_a, self.path_b)
        highlights_a = {off: "#ff5555" for off in res.changed_offsets}
        highlights_b = {off: "#55ff55" for off in res.changed_offsets}

        self.hex_a.load_bytes(self.path_a.read_bytes(), highlights_a)
        self.hex_b.load_bytes(self.path_b.read_bytes(), highlights_b)

        self.table.setRowCount(len(res.candidates))
        for row, cand in enumerate(res.candidates):
            self.table.setItem(row, 0, QTableWidgetItem(str(cand.offset)))
            self.table.setItem(row, 1, QTableWidgetItem(f"0x{cand.offset:04X}"))
            self.table.setItem(row, 2, QTableWidgetItem(cand.data_type.value))
            self.table.setItem(row, 3, QTableWidgetItem(cand.endianness.value))
            self.table.setItem(row, 4, QTableWidgetItem(str(cand.val_a)))
            self.table.setItem(row, 5, QTableWidgetItem(str(cand.val_b)))
            self.table.setItem(row, 6, QTableWidgetItem(f"{cand.delta:+}" if isinstance(cand.delta, (int, float)) else str(cand.delta)))
            self.table.setItem(row, 7, QTableWidgetItem(f"{cand.confidence * 100:.0f}%"))
