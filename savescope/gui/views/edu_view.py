from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QTextBrowser
from savescope.core.educational import EducationalContentEngine

class EduView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)

        self.topic_list = QListWidget()
        self.topics = EducationalContentEngine.get_topics()
        for t in self.topics:
            self.topic_list.addItem(t["title"])
        self.topic_list.currentRowChanged.connect(self._on_topic_selected)
        layout.addWidget(self.topic_list, 1)

        self.browser = QTextBrowser()
        self.browser.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; padding: 12px;")
        layout.addWidget(self.browser, 3)

        if self.topics:
            self.topic_list.setCurrentRow(0)

    def _on_topic_selected(self, row: int):
        if 0 <= row < len(self.topics):
            t_id = self.topics[row]["id"]
            md = EducationalContentEngine.get_topic_content(t_id)
            self.browser.setMarkdown(md)
