"""
SaveScope — Sekiro Character & Inventory Studio.
Provides a comprehensive GUI for FromSoftware Sekiro save editing:
- Slot switching (Slots 0 to 9)
- Real-time character stats editing with validation & presets
- Inventory browser (Weapons, Armor, Goods, Storage)
- Real-time search and quantity modification
- Safe item spawner (Weapons, Armor, Consumables)
- Slot importing with Steam ID preservation
- Educational memory offset inspector
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QLineEdit, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QGroupBox, QFormLayout, QFileDialog,
    QSplitter, QFrame, QTextEdit
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, pyqtSignal

from savescope.core.sl2 import SL2Container, SL2Slot
from savescope.core.sekiro import (
    SekiroSlotEditor, SekiroStats, SekiroCatalog,
    OFFSET_STEAM_ID, OFFSET_HP, OFFSET_ATTACK, OFFSET_SOULS,
    OFFSET_EMBLEMS, OFFSET_SKILL_POINTS, OFFSET_GA_START,
    OFFSET_INV_START, OFFSET_STORAGE_START, SLOT_PAYLOAD_SIZE
)


class SekiroStudioWidget(QWidget):
    """
    Sekiro Character & Inventory Studio widget.
    Integrates directly with SaveScope's SL2Container and Tweak Editor.
    """
    dataChanged = pyqtSignal()

    def __init__(self, sl2_container: SL2Container, parent=None):
        super().__init__(parent)
        self.sl2 = sl2_container
        self.catalog = SekiroCatalog.get()
        self.current_slot_idx = 0
        self.current_editor: Optional[SekiroSlotEditor] = None

        self._init_ui()
        self._load_slot(0)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(10)

        # ---------------------------------------------------------------------
        # Top Bar: Slot Selection & Slot Import
        # ---------------------------------------------------------------------
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("<b>Active Save Slot:</b>"))

        self.slot_combo = QComboBox()
        self.slot_combo.setMinimumWidth(320)
        for i in range(min(10, len(self.sl2.slots))):
            slot = self.sl2.slots[i]
            self.slot_combo.addItem(f"Slot {i}: {slot.name}", i)
        self.slot_combo.currentIndexChanged.connect(self._on_slot_selected)
        top_bar.addWidget(self.slot_combo)

        btn_import_slot = QPushButton("📥 Import Slot from External Save...")
        btn_import_slot.setStyleSheet("background-color: #0e639c; color: white; font-weight: bold; padding: 5px 12px;")
        btn_import_slot.clicked.connect(self._import_slot_dialog)
        top_bar.addWidget(btn_import_slot)

        top_bar.addStretch()

        self.lbl_slot_info = QLabel()
        self.lbl_slot_info.setStyleSheet("color: #4ec9b0; font-weight: bold;")
        top_bar.addWidget(self.lbl_slot_info)

        main_layout.addLayout(top_bar)

        # ---------------------------------------------------------------------
        # Main Studio Tabs
        # ---------------------------------------------------------------------
        self.studio_tabs = QTabWidget()

        self._build_stats_tab()
        self._build_inventory_tab()
        self._build_spawner_tab()
        self._build_educational_tab()

        main_layout.addWidget(self.studio_tabs)

    # =========================================================================
    # Tab 1: Character Stats & Presets
    # =========================================================================
    def _build_stats_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # Left Column: Stat spinboxes
        left_group = QGroupBox("Character Attributes")
        form = QFormLayout(left_group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.spin_hp = QSpinBox()
        self.spin_hp.setRange(1, 999999)
        form.addRow("Health (HP):", self.spin_hp)

        self.spin_attack = QSpinBox()
        self.spin_attack.setRange(1, 99)
        form.addRow("Attack Power:", self.spin_attack)

        self.spin_souls = QSpinBox()
        self.spin_souls.setRange(0, 99999999)
        form.addRow("Sen / Money:", self.spin_souls)

        self.spin_emblems = QSpinBox()
        self.spin_emblems.setRange(1, 99)
        form.addRow("Spirit Emblems:", self.spin_emblems)

        self.spin_guard = QSpinBox()
        self.spin_guard.setRange(1, 999999)
        form.addRow("Guard / Posture:", self.spin_guard)

        self.spin_skill_pts = QSpinBox()
        self.spin_skill_pts.setRange(0, 999999)
        form.addRow("Skill Points:", self.spin_skill_pts)

        self.spin_ng = QSpinBox()
        self.spin_ng.setRange(0, 255)
        form.addRow("New Game+ Cycle:", self.spin_ng)

        self.txt_steam_id = QLineEdit()
        self.txt_steam_id.setReadOnly(True)
        self.txt_steam_id.setStyleSheet("background-color: #252526; color: #9cdcfe;")
        form.addRow("Steam ID:", self.txt_steam_id)

        btn_apply_stats = QPushButton("✔ Apply Attribute Changes")
        btn_apply_stats.setStyleSheet("background-color: #2da44e; color: white; font-weight: bold; padding: 8px;")
        btn_apply_stats.clicked.connect(self._apply_stats)
        form.addRow(btn_apply_stats)

        layout.addWidget(left_group, 2)

        # Right Column: Quick Presets & Actions
        right_group = QGroupBox("Quick Buffs & Utility")
        right_layout = QVBoxLayout(right_group)

        btn_max_sen = QPushButton("💰 Max Sen (99,999)")
        btn_max_sen.clicked.connect(lambda: self.spin_souls.setValue(99999))
        right_layout.addWidget(btn_max_sen)

        btn_max_emblems = QPushButton("🔮 Max Emblems (99)")
        btn_max_emblems.clicked.connect(lambda: self.spin_emblems.setValue(99))
        right_layout.addWidget(btn_max_emblems)

        btn_max_attack = QPushButton("⚔️ 99 Attack Power")
        btn_max_attack.clicked.connect(lambda: self.spin_attack.setValue(99))
        right_layout.addWidget(btn_max_attack)

        btn_max_hp = QPushButton("❤️ Max Health (2,000)")
        btn_max_hp.clicked.connect(lambda: self.spin_hp.setValue(2000))
        right_layout.addWidget(btn_max_hp)

        right_layout.addSpacing(15)

        btn_reset_skills = QPushButton("🔄 Reset Allocated Skill Points")
        btn_reset_skills.setStyleSheet("background-color: #d73a49; color: white; font-weight: bold; padding: 6px;")
        btn_reset_skills.clicked.connect(self._reset_skill_points)
        right_layout.addWidget(btn_reset_skills)

        right_layout.addStretch()

        preset_info = QLabel(
            "<i>Note: Changes are validated against native engine limits and automatically recalculate slot MD5 checksums on save.</i>"
        )
        preset_info.setWordWrap(True)
        preset_info.setStyleSheet("color: #888888; font-size: 11px;")
        right_layout.addWidget(preset_info)

        layout.addWidget(right_group, 1)

        self.studio_tabs.addTab(tab, "Character Attributes")

    # =========================================================================
    # Tab 2: Inventory Browser & Quantity Editor
    # =========================================================================
    def _build_inventory_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # Left: Category sub-tabs
        self.inv_tabs = QTabWidget()

        self.table_goods = self._create_item_table()
        self.table_goods.itemSelectionChanged.connect(self._on_good_selected)
        self.inv_tabs.addTab(self.table_goods, "Consumables & Goods")

        self.table_weapons = self._create_item_table()
        self.inv_tabs.addTab(self.table_weapons, "Weapons & Prosthetics")

        self.table_armor = self._create_item_table()
        self.inv_tabs.addTab(self.table_armor, "Outfits & Armor")

        self.table_storage = self._create_item_table()
        self.table_storage.itemSelectionChanged.connect(self._on_storage_selected)
        self.inv_tabs.addTab(self.table_storage, "Storage Box")

        layout.addWidget(self.inv_tabs, 3)

        # Right: Quick Quantity Modifier
        side_panel = QGroupBox("Selected Item Controls")
        side_layout = QVBoxLayout(side_panel)

        side_layout.addWidget(QLabel("<b>Item Name:</b>"))
        self.lbl_selected_item_name = QLabel("None Selected")
        self.lbl_selected_item_name.setStyleSheet("color: #4ec9b0; font-weight: bold;")
        self.lbl_selected_item_name.setWordWrap(True)
        side_layout.addWidget(self.lbl_selected_item_name)

        side_layout.addSpacing(10)
        side_layout.addWidget(QLabel("<b>Modify Quantity (1–99):</b>"))
        self.spin_item_qty = QSpinBox()
        self.spin_item_qty.setRange(0, 99)
        self.spin_item_qty.setValue(1)
        side_layout.addWidget(self.spin_item_qty)

        self.btn_update_qty = QPushButton("Apply Quantity")
        self.btn_update_qty.setStyleSheet("background-color: #0e639c; color: white; font-weight: bold; padding: 6px;")
        self.btn_update_qty.clicked.connect(self._update_selected_quantity)
        side_layout.addWidget(self.btn_update_qty)

        side_layout.addSpacing(15)
        btn_refresh_inv = QPushButton("Refresh Inventory")
        btn_refresh_inv.clicked.connect(self._refresh_inventory)
        side_layout.addWidget(btn_refresh_inv)

        side_layout.addStretch()
        layout.addWidget(side_panel, 1)

        self.studio_tabs.addTab(tab, "Inventory & Storage")

    def _create_item_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Item Name", "Item ID", "Quantity", "Offset"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        return table

    # =========================================================================
    # Tab 3: Item Spawner
    # =========================================================================
    def _build_spawner_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Spawner: Goods
        g_box = QGroupBox("Spawn Consumable Good")
        g_layout = QHBoxLayout(g_box)
        self.combo_spawn_goods = QComboBox()
        self.combo_spawn_goods.setEditable(True)
        self.combo_spawn_goods.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for name in sorted(self.catalog.goods_by_name.keys()):
            self.combo_spawn_goods.addItem(name)
        g_layout.addWidget(self.combo_spawn_goods, 3)

        g_layout.addWidget(QLabel("Qty:"))
        self.spin_spawn_good_qty = QSpinBox()
        self.spin_spawn_good_qty.setRange(1, 99)
        self.spin_spawn_good_qty.setValue(10)
        g_layout.addWidget(self.spin_spawn_good_qty, 1)

        btn_spawn_good = QPushButton("Spawn Good")
        btn_spawn_good.setStyleSheet("background-color: #2da44e; color: white; font-weight: bold; padding: 6px 14px;")
        btn_spawn_good.clicked.connect(self._spawn_good)
        g_layout.addWidget(btn_spawn_good, 1)
        layout.addWidget(g_box)

        # Spawner: Weapons
        w_box = QGroupBox("Spawn Weapon / Combat Art / Prosthetic")
        w_layout = QHBoxLayout(w_box)
        self.combo_spawn_weapons = QComboBox()
        self.combo_spawn_weapons.setEditable(True)
        self.combo_spawn_weapons.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for name in sorted(self.catalog.weapons_by_name.keys()):
            self.combo_spawn_weapons.addItem(name)
        w_layout.addWidget(self.combo_spawn_weapons, 4)

        btn_spawn_weapon = QPushButton("Spawn Weapon")
        btn_spawn_weapon.setStyleSheet("background-color: #2da44e; color: white; font-weight: bold; padding: 6px 14px;")
        btn_spawn_weapon.clicked.connect(self._spawn_weapon)
        w_layout.addWidget(btn_spawn_weapon, 1)
        layout.addWidget(w_box)

        # Spawner: Armor
        a_box = QGroupBox("Spawn Armor / Outfit")
        a_layout = QHBoxLayout(a_box)
        self.combo_spawn_armor = QComboBox()
        self.combo_spawn_armor.setEditable(True)
        self.combo_spawn_armor.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for name in sorted(self.catalog.armor_by_name.keys()):
            self.combo_spawn_armor.addItem(name)
        a_layout.addWidget(self.combo_spawn_armor, 4)

        btn_spawn_armor = QPushButton("Spawn Armor")
        btn_spawn_armor.setStyleSheet("background-color: #2da44e; color: white; font-weight: bold; padding: 6px 14px;")
        btn_spawn_armor.clicked.connect(self._spawn_armor)
        a_layout.addWidget(btn_spawn_armor, 1)
        layout.addWidget(a_box)

        layout.addStretch()

        info = QLabel(
            "<b>Safe Spawner Architecture:</b><br>"
            "Spawning an item automatically locates the next free slot in the 16-byte player inventory and "
            "60-byte GA table, sets appropriate bit flags (0x80 for weapons, 0x90 for armor, 0xB0 for goods), "
            "and increments internal save revision counters to prevent save rejection."
        )
        info.setStyleSheet("color: #cccccc; font-size: 11px; background-color: #1a1a1a; padding: 10px; border-radius: 4px;")
        layout.addWidget(info)

        self.studio_tabs.addTab(tab, "Item Spawner")

    # =========================================================================
    # Tab 4: Educational Memory Map
    # =========================================================================
    def _build_educational_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont("Consolas", 10))
        text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        text.setHtml(
            """
            <h3>Sekiro: Shadows Die Twice — BND4 Save Architecture</h3>
            <p>Sekiro PC save files (<code>S0000.sl2</code>) use FromSoftware's proprietary <b>BND4 archive container</b>.</p>
            <hr>
            <h4>Container Layout:</h4>
            <ul>
                <li><b>0x000 - 0x300:</b> BND4 Header and slot file record table (12 file slots).</li>
                <li><b>0x300 - 0x310:</b> 16-Byte MD5 Checksum for Slot 0 (USER_DATA000).</li>
                <li><b>0x310 - 0x100310:</b> Slot 0 Payload (1,048,576 bytes / 0x100000).</li>
                <li>Each subsequent slot is spaced exactly <code>0x100010</code> bytes apart.</li>
            </ul>
            <h4>Key In-Slot Offsets:</h4>
            <table border="1" cellpadding="4" style="border-collapse: collapse;">
                <tr style="background-color: #252526;"><th>Offset</th><th>Type</th><th>Description</th></tr>
                <tr><td>0x33E54</td><td>uint64</td><td>Steam ID (preserves ownership across machines)</td></tr>
                <tr><td>0x33F34</td><td>uint8</td><td>New Game + cycle</td></tr>
                <tr><td>0x3446C</td><td>uint32</td><td>Character HP</td></tr>
                <tr><td>0x34488</td><td>uint32</td><td>Guard / Posture</td></tr>
                <tr><td>0x3449C</td><td>uint8</td><td>Attack Power (1 - 99)</td></tr>
                <tr><td>0x344D0</td><td>uint32</td><td>Sen / Money</td></tr>
                <tr><td>0x3459A</td><td>uint8</td><td>Spirit Emblems (1 - 99)</td></tr>
                <tr><td>0x345B4</td><td>uint32</td><td>Skill Points</td></tr>
                <tr><td>0x345A8</td><td>bytes[16]</td><td>Skill Point Allocation Block (zeroed on reset)</td></tr>
                <tr><td>0x35614</td><td>Table (60B)</td><td>Game Array (GA) Table for Weapons/Armor handles</td></tr>
                <tr><td>0x8F70C</td><td>Table (16B)</td><td>Player Inventory Table (0x80=Weapon, 0x90=Armor, 0xB0=Good)</td></tr>
                <tr><td>0x987A0</td><td>Table (16B)</td><td>Storage Box Inventory Table</td></tr>
                <tr><td>0xA1958</td><td>Table (8B)</td><td>Storage Lookup Table</td></tr>
                <tr><td>0x8F700</td><td>uint16</td><td>Inventory Revision Counter 1</td></tr>
                <tr><td>0x8F6FC</td><td>uint16</td><td>Inventory Revision Counter 2</td></tr>
                <tr><td>0xA1954</td><td>uint16</td><td>Storage Revision Counter</td></tr>
            </table>
            """
        )
        layout.addWidget(text)
        self.studio_tabs.addTab(tab, "Reverse Engineering Map")

    # =========================================================================
    # Slot Management & Loading
    # =========================================================================
    def _on_slot_selected(self, index: int):
        self._load_slot(index)

    def _load_slot(self, slot_idx: int):
        if slot_idx < 0 or slot_idx >= len(self.sl2.slots):
            return
        self.current_slot_idx = slot_idx
        slot = self.sl2.slots[slot_idx]

        # Slice payload from container data
        payload = self.sl2.data[slot.payload_offset : slot.payload_offset + slot.payload_size]
        self.current_editor = SekiroSlotEditor(payload)

        # Load Stats
        stats = self.current_editor.get_stats()
        self.spin_hp.setValue(stats.hp)
        self.spin_attack.setValue(stats.attack)
        self.spin_souls.setValue(stats.souls)
        self.spin_emblems.setValue(stats.emblems)
        self.spin_guard.setValue(stats.guard)
        self.spin_skill_pts.setValue(stats.skill_points)
        self.spin_ng.setValue(stats.ng_plus)
        self.txt_steam_id.setText(str(stats.steam_id))

        self.lbl_slot_info.setText(f"Slot {slot_idx}: Attack {stats.attack} | HP {stats.hp} | Sen {stats.souls}")

        # Populate Inventory
        self._refresh_inventory()

    def _apply_stats(self):
        if not self.current_editor:
            return
        stats = SekiroStats(
            steam_id=int(self.txt_steam_id.text()) if self.txt_steam_id.text().isdigit() else 0,
            hp=self.spin_hp.value(),
            attack=self.spin_attack.value(),
            guard=self.spin_guard.value(),
            emblems=self.spin_emblems.value(),
            skill_points=self.spin_skill_pts.value(),
            souls=self.spin_souls.value(),
            ng_plus=self.spin_ng.value(),
        )
        self.current_editor.set_stats(stats)
        self._sync_slot_to_container()
        self.lbl_slot_info.setText(f"Slot {self.current_slot_idx}: Attack {stats.attack} | HP {stats.hp} | Sen {stats.souls}")
        QMessageBox.information(self, "Stats Applied", f"Updated character attributes for Slot {self.current_slot_idx}!")

    def _reset_skill_points(self):
        if not self.current_editor:
            return
        reply = QMessageBox.question(
            self, "Reset Skill Points",
            "Are you sure you want to reset all allocated skill points for this slot?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.current_editor.reset_skill_points()
            self._sync_slot_to_container()
            QMessageBox.information(self, "Reset Complete", "Skill points allocation cleared successfully!")

    def _refresh_inventory(self):
        if not self.current_editor:
            return
        inv = self.current_editor.get_inventory()
        self._populate_table(self.table_goods, inv["goods"])
        self._populate_table(self.table_weapons, inv["weapons"])
        self._populate_table(self.table_armor, inv["armor"])
        self._populate_table(self.table_storage, inv["storage"])

    def _populate_table(self, table: QTableWidget, items: list):
        table.setRowCount(len(items))
        for row, item in enumerate(items):
            table.setItem(row, 0, QTableWidgetItem(item.name))
            table.setItem(row, 1, QTableWidgetItem(str(item.item_id)))
            table.setItem(row, 2, QTableWidgetItem(str(item.quantity)))
            table.setItem(row, 3, QTableWidgetItem(f"0x{item.offset:X}"))
            # Store item reference in row 0
            table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item)

    def _on_good_selected(self):
        selected = self.table_goods.selectedItems()
        if selected:
            row = selected[0].row()
            item = self.table_goods.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if item:
                self.lbl_selected_item_name.setText(item.name)
                self.spin_item_qty.setValue(item.quantity)
                self._current_selected_item = item

    def _on_storage_selected(self):
        selected = self.table_storage.selectedItems()
        if selected:
            row = selected[0].row()
            item = self.table_storage.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if item:
                self.lbl_selected_item_name.setText(f"[Storage] {item.name}")
                self.spin_item_qty.setValue(item.quantity)
                self._current_selected_item = item

    def _update_selected_quantity(self):
        if not hasattr(self, "_current_selected_item") or not self._current_selected_item:
            QMessageBox.warning(self, "Selection Required", "Please select an item from the table first.")
            return
        item = self._current_selected_item
        new_qty = self.spin_item_qty.value()
        if self.current_editor.update_good_quantity(item.offset, new_qty):
            self._sync_slot_to_container()
            self._refresh_inventory()
            QMessageBox.information(self, "Quantity Updated", f"Updated {item.name} quantity to {new_qty}!")
        else:
            QMessageBox.critical(self, "Error", "Failed to update item quantity.")

    def _spawn_good(self):
        item_name = self.combo_spawn_goods.currentText()
        qty = self.spin_spawn_good_qty.value()
        if self.current_editor.spawn_good(item_name, qty):
            self._sync_slot_to_container()
            self._refresh_inventory()
            QMessageBox.information(self, "Item Spawned", f"Successfully spawned {qty}x {item_name}!")
        else:
            QMessageBox.critical(self, "Spawning Failed", "Could not spawn item. Inventory may be full or invalid item.")

    def _spawn_weapon(self):
        item_name = self.combo_spawn_weapons.currentText()
        if self.current_editor.spawn_equipment(item_name, "weapon"):
            self._sync_slot_to_container()
            self._refresh_inventory()
            QMessageBox.information(self, "Weapon Spawned", f"Successfully spawned {item_name} into inventory!")
        else:
            QMessageBox.critical(self, "Spawning Failed", "Could not spawn weapon. GA or Inventory table may be full.")

    def _spawn_armor(self):
        item_name = self.combo_spawn_armor.currentText()
        if self.current_editor.spawn_equipment(item_name, "armor"):
            self._sync_slot_to_container()
            self._refresh_inventory()
            QMessageBox.information(self, "Armor Spawned", f"Successfully spawned {item_name} into inventory!")
        else:
            QMessageBox.critical(self, "Spawning Failed", "Could not spawn armor. GA or Inventory table may be full.")

    def _import_slot_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Save File or Slot to Import", "", "Sekiro Saves (*.sl2 *.bin *.dat);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            source_bytes = Path(file_path).read_bytes()
            # If full SL2, extract selected or slot 0
            if SL2Container.is_sl2_file(file_path):
                source_sl2 = SL2Container(file_path)
                source_payload = bytes(source_sl2.data[source_sl2.slots[0].payload_offset : source_sl2.slots[0].payload_offset + source_sl2.slots[0].payload_size])
            elif len(source_bytes) >= SLOT_PAYLOAD_SIZE:
                source_payload = source_bytes[:SLOT_PAYLOAD_SIZE]
            else:
                QMessageBox.critical(self, "Invalid File", f"File size ({len(source_bytes)} B) is too small to be a valid Sekiro slot.")
                return

            reply = QMessageBox.question(
                self, "Preserve Steam ID?",
                "Do you want to preserve your current save's Steam ID on the imported character?\\n"
                "(Recommended: Yes, so the game recognizes your account ownership)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            preserve = (reply == QMessageBox.StandardButton.Yes)

            preserved_id = self.current_editor.import_slot_data(source_payload, preserve_steam_id=preserve)
            self._sync_slot_to_container()
            self._load_slot(self.current_slot_idx)

            QMessageBox.information(
                self, "Slot Imported",
                f"Successfully imported character into Slot {self.current_slot_idx}!\\n"
                f"Preserved Steam ID: {preserved_id}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Failed to import slot: {e}")

    def _sync_slot_to_container(self):
        """Write current slot editor's payload back into SL2Container data buffer."""
        slot = self.sl2.slots[self.current_slot_idx]
        self.sl2.data[slot.payload_offset : slot.payload_offset + slot.payload_size] = self.current_editor.data
        self.dataChanged.emit()
