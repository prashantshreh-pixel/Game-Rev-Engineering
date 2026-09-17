from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QProgressBar,
    QSplitter, QListWidget, QListWidgetItem, QGroupBox, QFrame
)
from pathlib import Path
import os
import time

from savescope.core.discovery import GameDiscoveryEngine
from savescope.models.game import DiscoveredGame, SaveSlot
from savescope.gui.views.tweak_dialog import SaveTweakDialog
from savescope.gui.widgets.game_icon import GameIconManager

class ScanWorker(QThread):
    finished = pyqtSignal(list)
    status_updated = pyqtSignal(str)

    def run(self):
        games = GameDiscoveryEngine.scan_common_locations(
            progress_callback=self.status_updated.emit
        )
        self.finished.emit(games)

class LibraryView(QWidget):
    """
    Modern Gaming Suite UI (Inspired by NVIDIA App & Game Launchers):
    - Left Panel: Visual Game Cards with high-DPI custom icons/badges and file counts.
    - Right Panel: Sleek Overview with game header, save slot management, format badges, and 1-click tweak.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Top Action Bar
        top_bar = QHBoxLayout()
        self.btn_scan = QPushButton("Scan PC for Installed Games")
        self.btn_scan.setStyleSheet("""
            QPushButton {
                background-color: #76b900; 
                color: #000000; 
                font-weight: bold; 
                font-size: 13px;
                padding: 9px 20px; 
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #8ce000;
            }
        """)
        self.btn_scan.clicked.connect(self._start_scan)
        top_bar.addWidget(self.btn_scan)

        self.status_lbl = QLabel("Click Scan to discover installed games and save profiles.")
        self.status_lbl.setStyleSheet("color: #888888; font-size: 12px;")
        top_bar.addWidget(self.status_lbl)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setStyleSheet("QProgressBar { border: none; background: #222; height: 3px; } QProgressBar::chunk { background: #76b900; }")
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Main 2-Panel Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #2b2b2b; width: 2px; }")

        # Left Panel: Games List with Icons
        left_group = QGroupBox("Installed Games")
        left_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #333333;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                color: #cccccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        left_layout = QVBoxLayout(left_group)
        left_layout.setContentsMargins(6, 12, 6, 6)

        self.games_list = QListWidget()
        self.games_list.setIconSize(QSize(36, 36))
        self.games_list.setStyleSheet("""
            QListWidget {
                background-color: #1a1a1a;
                border: none;
                outline: none;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px 6px;
                border-radius: 4px;
                color: #e0e0e0;
                font-size: 13px;
                font-weight: 500;
            }
            QListWidget::item:hover {
                background-color: #262626;
            }
            QListWidget::item:selected {
                background-color: #004d20;
                border-left: 3px solid #76b900;
                color: #ffffff;
            }
        """)
        self.games_list.currentRowChanged.connect(self._on_game_selected)
        left_layout.addWidget(self.games_list)
        splitter.addWidget(left_group)

        # Right Panel: Game Saves & Tweak Actions
        right_group = QGroupBox("Save Files & Tweak Settings")
        right_group.setStyleSheet(left_group.styleSheet())
        right_layout = QVBoxLayout(right_group)
        right_layout.setContentsMargins(10, 12, 10, 10)

        # Selected Game Header Card
        self.header_card = QFrame()
        self.header_card.setStyleSheet("background-color: #222222; border-radius: 6px; padding: 10px;")
        header_layout = QHBoxLayout(self.header_card)

        self.game_icon_lbl = QLabel()
        self.game_icon_lbl.setFixedSize(48, 48)
        header_layout.addWidget(self.game_icon_lbl)

        game_info_v = QVBoxLayout()
        self.selected_game_title = QLabel("No game selected")
        self.selected_game_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        game_info_v.addWidget(self.selected_game_title)

        self.selected_game_sub = QLabel("Select a game from the left sidebar to tweak its save data.")
        self.selected_game_sub.setStyleSheet("font-size: 11px; color: #888888;")
        game_info_v.addWidget(self.selected_game_sub)
        header_layout.addLayout(game_info_v)
        header_layout.addStretch()

        self.btn_open_folder = QPushButton("Open Folder in Explorer")
        self.btn_open_folder.setStyleSheet("background-color: #333333; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_open_folder.clicked.connect(self._open_current_save_folder)
        self.btn_open_folder.setEnabled(False)
        header_layout.addWidget(self.btn_open_folder)

        right_layout.addWidget(self.header_card)

        # Table of Saves / Config Files
        self.saves_table = QTableWidget()
        self.saves_table.setColumnCount(5)
        self.saves_table.setHorizontalHeaderLabels([
            "File Name", "Type", "File Size", "Last Modified", "Action"
        ])
        self.saves_table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a1a;
                gridline-color: #262626;
                border: 1px solid #282828;
                border-radius: 4px;
                color: #d4d4d4;
            }
            QHeaderView::section {
                background-color: #222222;
                color: #888888;
                font-weight: bold;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #333333;
            }
        """)
        self.saves_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.saves_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.saves_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.saves_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.saves_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        right_layout.addWidget(self.saves_table)

        splitter.addWidget(right_group)
        splitter.setSizes([340, 860])
        layout.addWidget(splitter)

        self.discovered_games: list[DiscoveredGame] = []
        self.current_game: DiscoveredGame = None
        self.worker: ScanWorker = None

    def _start_scan(self):
        self.btn_scan.setEnabled(False)
        self.progress_bar.show()
        self.status_lbl.setText("Scanning PC for games and save directories...")

        self.worker = ScanWorker()
        self.worker.status_updated.connect(self.status_lbl.setText)
        self.worker.finished.connect(self._on_scan_finished)
        self.worker.start()

    def _on_scan_finished(self, games: list[DiscoveredGame]):
        self.btn_scan.setEnabled(True)
        self.progress_bar.hide()
        self.discovered_games = games
        self.status_lbl.setText(f"Scan complete: {len(games)} games detected.")

        self.games_list.clear()
        for g in games:
            icon = GameIconManager.get_icon(g.name)
            item = QListWidgetItem(icon, f"{g.name}  ({len(g.save_files)})")
            self.games_list.addItem(item)

        if games:
            self.games_list.setCurrentRow(0)

    def _on_game_selected(self, row: int):
        if not (0 <= row < len(self.discovered_games)):
            return

        self.current_game = self.discovered_games[row]
        self.selected_game_title.setText(self.current_game.name)
        self.selected_game_sub.setText(f"Location: {self.current_game.save_dir}")

        icon = GameIconManager.get_icon(self.current_game.name)
        self.game_icon_lbl.setPixmap(icon.pixmap(48, 48))
        self.btn_open_folder.setEnabled(True)

        self.saves_table.setRowCount(len(self.current_game.save_files))
        for r, slot in enumerate(self.current_game.save_files):
            # Name
            self.saves_table.setItem(r, 0, QTableWidgetItem(slot.name))

            # Format Badge
            fmt_item = QTableWidgetItem(slot.format_type.upper())
            fmt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if slot.is_tweakable_text:
                fmt_item.setForeground(Qt.GlobalColor.green)
            else:
                fmt_item.setForeground(Qt.GlobalColor.cyan)
            self.saves_table.setItem(r, 1, fmt_item)

            # Size
            size_kb = f"{slot.size_bytes / 1024:.1f} KB" if slot.size_bytes > 1024 else f"{slot.size_bytes} B"
            self.saves_table.setItem(r, 2, QTableWidgetItem(size_kb))

            # Time
            mod_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(slot.modified_time))
            self.saves_table.setItem(r, 3, QTableWidgetItem(mod_time))

            # Action button
            btn_tweak = QPushButton("Tweak / Edit")
            if slot.is_tweakable_text:
                btn_tweak.setStyleSheet("""
                    QPushButton {
                        background-color: #2da44e; 
                        color: white; 
                        font-weight: bold; 
                        padding: 5px 12px; 
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #2c974b;
                    }
                """)
                btn_tweak.setToolTip("Open in-app Tweak Editor (JSON, XML, or INI)")
            else:
                btn_tweak.setStyleSheet("""
                    QPushButton {
                        background-color: #0e639c; 
                        color: white; 
                        font-weight: 500;
                        padding: 5px 12px; 
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #1177bb;
                    }
                """)
                btn_tweak.setToolTip("Inspect binary save container in Hex Viewer")

            btn_tweak.clicked.connect(lambda _, s=slot: self._open_tweak_editor(s))
            self.saves_table.setCellWidget(r, 4, btn_tweak)

    def _open_tweak_editor(self, slot: SaveSlot):
        dialog = SaveTweakDialog(slot, self.current_game.name, self)
        dialog.exec()
        if self.current_game and self.games_list.currentRow() >= 0:
            self._on_game_selected(self.games_list.currentRow())

    def _open_current_save_folder(self):
        if self.current_game and self.current_game.save_dir and self.current_game.save_dir.exists():
            os.system(f'explorer "{self.current_game.save_dir}"')
