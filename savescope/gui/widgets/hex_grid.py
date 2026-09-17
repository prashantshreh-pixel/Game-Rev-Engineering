from PyQt6.QtWidgets import (
    QWidget, QTextEdit, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
)
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtCore import Qt, pyqtSignal

class HexViewerWidget(QWidget):
    """
    Interactive Hex Editor & Viewer Widget.
    Renders memory offset, hex bytes, and ASCII representation.
    Supports in-place byte editing, jump-to-offset, and byte range highlighting.
    """
    bytes_modified = pyqtSignal(int, bytes)  # (offset, new_bytes)

    def __init__(self, parent=None, editable: bool = False):
        super().__init__(parent)
        self.editable = editable
        self._data = bytearray()
        self._modified_offsets: set[int] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Toolbar
        nav_layout = QHBoxLayout()
        self.offset_input = QLineEdit()
        self.offset_input.setPlaceholderText("Jump to Offset (e.g. 0x0300 or 768)...")
        self.offset_input.returnPressed.connect(self.jump_to_offset)
        nav_layout.addWidget(self.offset_input)

        jump_btn = QPushButton("Go")
        jump_btn.clicked.connect(self.jump_to_offset)
        nav_layout.addWidget(jump_btn)

        # Patch Byte tools
        self.patch_offset = QLineEdit()
        self.patch_offset.setPlaceholderText("Edit Offset (0x...)")
        self.patch_offset.setFixedWidth(120)
        nav_layout.addWidget(self.patch_offset)

        self.patch_hex = QLineEdit()
        self.patch_hex.setPlaceholderText("Hex Value (e.g. FF 00)")
        self.patch_hex.setFixedWidth(140)
        nav_layout.addWidget(self.patch_hex)

        self.btn_patch = QPushButton("Write Bytes")
        self.btn_patch.setStyleSheet("background-color: #0e639c; color: white; font-weight: bold;")
        self.btn_patch.clicked.connect(self._apply_patch)
        nav_layout.addWidget(self.btn_patch)

        layout.addLayout(nav_layout)

        # Main text view
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.text_edit)

    @property
    def current_bytes(self) -> bytes:
        return bytes(self._data)

    def load_bytes(self, data: bytes, highlights: dict[int, str] = None) -> None:
        self._data = bytearray(data)
        self._highlights = highlights or {}
        self._render_view()

    def patch_byte_at(self, offset: int, new_bytes: bytes) -> None:
        if 0 <= offset and offset + len(new_bytes) <= len(self._data):
            self._data[offset : offset + len(new_bytes)] = new_bytes
            for i in range(len(new_bytes)):
                self._modified_offsets.add(offset + i)
            self._render_view()
            self.bytes_modified.emit(offset, new_bytes)

    def _render_view(self) -> None:
        lines = []
        hdr = "Offset    00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F   0123456789ABCDEF"
        lines.append(f"<span style='color: #888888;'>{hdr}</span>")
        lines.append("<span style='color: #444444;'>--------------------------------------------------------------------------</span>")

        # Limit render display to first 65,536 bytes for fluid high-speed rendering
        max_render = min(len(self._data), 65536)

        for offset in range(0, max_render, 16):
            chunk = self._data[offset : offset + 16]
            off_str = f"{offset:08X}  "

            hex_parts = []
            ascii_parts = []

            for i in range(16):
                if i < len(chunk):
                    b = chunk[i]
                    curr_off = offset + i

                    is_modified = curr_off in self._modified_offsets
                    color = "#00ffcc" if is_modified else self._highlights.get(curr_off, None)

                    hex_b = f"{b:02X}"
                    if color:
                        hex_parts.append(f"<span style='color: {color}; font-weight: bold;'>{hex_b}</span>")
                    else:
                        hex_parts.append(f"<span style='color: #d4d4d4;'>{hex_b}</span>")

                    char_str = chr(b) if 32 <= b <= 126 else "."
                    if color:
                        ascii_parts.append(f"<span style='color: {color}; font-weight: bold;'>{char_str}</span>")
                    else:
                        ascii_parts.append(f"<span style='color: #888888;'>{char_str}</span>")
                else:
                    hex_parts.append("  ")
                    ascii_parts.append(" ")

                if i == 7:
                    hex_parts.append(" ")

            line_str = (
                f"<span style='color: #569cd6;'>{off_str}</span>"
                + " ".join(hex_parts)
                + "   "
                + "".join(ascii_parts)
            )
            lines.append(line_str)

        if len(self._data) > max_render:
            lines.append(f"<span style='color: #888888;'>... [Showing first {max_render} of {len(self._data)} bytes]</span>")

        self.text_edit.setHtml("<pre style='font-family: Consolas;'>" + "<br>".join(lines) + "</pre>")

    def jump_to_offset(self) -> None:
        text = self.offset_input.text().strip()
        if not text:
            return
        try:
            offset = int(text, 16) if text.lower().startswith("0x") else int(text)
        except ValueError:
            return

        line_idx = (offset // 16) + 2
        cursor = QTextCursor(self.text_edit.document().findBlockByNumber(line_idx))
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

    def _apply_patch(self) -> None:
        off_text = self.patch_offset.text().strip()
        hex_text = self.patch_hex.text().strip().replace(" ", "").replace("0x", "")

        if not off_text or not hex_text:
            QMessageBox.warning(self, "Missing Fields", "Please enter both an offset (e.g. 0x0310) and hex bytes (e.g. FF 00 7A).")
            return

        try:
            offset = int(off_text, 16) if off_text.lower().startswith("0x") else int(off_text)
            new_bytes = bytes.fromhex(hex_text)
        except Exception as e:
            QMessageBox.critical(self, "Invalid Input", f"Error parsing offset or hex bytes: {e}")
            return

        if offset < 0 or offset + len(new_bytes) > len(self._data):
            QMessageBox.critical(self, "Bounds Error", f"Offset 0x{offset:X} exceeds file bounds (0..{len(self._data):X}).")
            return

        self.patch_byte_at(offset, new_bytes)
        self.offset_input.setText(hex(offset))
        self.jump_to_offset()
        QMessageBox.information(self, "Bytes Patched", f"Successfully patched {len(new_bytes)} byte(s) at offset 0x{offset:04X}!")
