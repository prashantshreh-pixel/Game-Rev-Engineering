import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt6.QtGui import QIcon

from savescope.gui.views.library import LibraryView
from savescope.gui.views.diff_viewer import DiffView
from savescope.gui.views.structure_view import StructureView
from savescope.gui.views.edu_view import EduView
from savescope.gui.widgets.hex_grid import HexViewerWidget

class SaveScopeMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SaveScope — Game Save Reverse Engineering Toolkit")
        self.resize(1200, 750)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tab 1: Game Library
        self.library_view = LibraryView()
        self.tabs.addTab(self.library_view, "Game Library")

        # Tab 2: Diff Engine
        self.diff_view = DiffView()
        self.tabs.addTab(self.diff_view, "Diff Engine & Heuristics")

        # Tab 3: Structure & Save Editor
        self.structure_view = StructureView()
        self.tabs.addTab(self.structure_view, "Save Structure Editor")

        # Tab 4: Standalone Hex Viewer
        self.hex_viewer = HexViewerWidget()
        self.tabs.addTab(self.hex_viewer, "Raw Hex Inspector")

        # Tab 5: Educational Mode
        self.edu_view = EduView()
        self.tabs.addTab(self.edu_view, "Educational Academy")

def run_gui():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = SaveScopeMainWindow()
    win.show()
    sys.exit(app.exec())
