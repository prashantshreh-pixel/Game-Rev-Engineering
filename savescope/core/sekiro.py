"""
SaveScope — Sekiro: Shadows Die Twice In-Slot Reverse Engineering Engine.
Provides high-fidelity slot parsing, stats editing, inventory management,
item spawning, and multi-slot migration with automatic Steam ID retention.
"""

from __future__ import annotations
import os
import json
import struct
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass, field

# =============================================================================
# Reverse-Engineered Binary Offsets (Within each 0x100000 slot payload)
# =============================================================================
OFFSET_STEAM_ID = 0x33E54        # uint64 (8 bytes)
OFFSET_NG_PLUS = 0x33F34         # uint8  (1 byte)
OFFSET_HP = 0x3446C              # uint32 (4 bytes)
OFFSET_GUARD = 0x34488           # uint32 (4 bytes)
OFFSET_ATTACK = 0x3449C          # uint8  (1 byte, max 99 / 0x62)
OFFSET_SOULS = 0x344D0           # uint32 (4 bytes, Sen / Money)
OFFSET_EMBLEMS = 0x3459A         # uint8  (1 byte, max 99 / 0x62)
OFFSET_SKILL_POINTS = 0x345B4    # uint32 (4 bytes, max 999,999,999)
OFFSET_RESET_SKILL = 0x345A8     # 16 bytes zeroed out

# Table Offsets & Spans
OFFSET_GA_START = 0x35614        # GA Item Table
SIZE_GA_SPAN = 0x59FC4 + 0x3C    # Ends at 0x8F614 (60 bytes per item)
GA_RECORD_SIZE = 0x3C

OFFSET_INV_START = 0x8F70C       # Main Player Inventory
SIZE_INV_SPAN = 0x7000           # Ends at 0x9670C (16 bytes per item)
INV_RECORD_SIZE = 16

OFFSET_KEY_START = 0x9670C       # Key items table
SIZE_KEY_SPAN = 0x2000

OFFSET_STORAGE_START = 0x987A0   # Storage box items
SIZE_STORAGE_SPAN = 0x9000

OFFSET_STORAGE_LOOKUP = 0xA1958  # Storage lookup table
SIZE_STORAGE_LOOKUP_SPAN = 0x4000

# Inventory State Revision Counters (incremented on additions)
OFFSET_COUNTER_1 = 0x8F700       # uint16
OFFSET_COUNTER_2 = 0x8F6FC       # uint16
OFFSET_COUNTER_STORAGE = 0xA1954 # uint16

# Item Type Bitmasks (top nibble of gaitem_handle)
TYPE_EMPTY  = 0x00000000
TYPE_WEAPON = 0x80000000
TYPE_ARMOR  = 0x90000000
TYPE_GOOD   = 0xB0000000

SLOT_PAYLOAD_SIZE = 0x100000


@dataclass
class SekiroStats:
    steam_id: int = 0
    hp: int = 1000
    attack: int = 1
    guard: int = 1000
    emblems: int = 15
    skill_points: int = 0
    souls: int = 0
    ng_plus: int = 0


@dataclass
class SekiroItem:
    category: str        # 'weapon', 'armor', 'good', 'storage'
    handle: int          # gaitem_handle
    item_id: int         # resolved item ID
    name: str            # resolved name from catalog
    quantity: int        # current quantity
    index: int           # sorting index
    offset: int          # byte offset within slot payload


class SekiroCatalog:
    """Catalog lookup for weapons, armor, and consumables."""
    _instance: Optional["SekiroCatalog"] = None

    def __init__(self):
        catalog_dir = Path(__file__).resolve().parent.parent / "data" / "games" / "sekiro"
        self.weapons = self._load_json(catalog_dir / "weapons.json")
        self.armor = self._load_json(catalog_dir / "armor.json")
        self.goods = self._load_json(catalog_dir / "goods.json")

        self.weapons_by_name = {item["name"]: int(item["id"]) for item in self.weapons if item.get("name")}
        self.armor_by_name = {item["name"]: int(item["id"]) for item in self.armor if item.get("name")}
        self.goods_by_name = {item["name"]: int(item["id"]) for item in self.goods if item.get("name")}

        self.weapons_by_id = {int(item["id"]): item["name"] for item in self.weapons if item.get("name") and item.get("id")}
        self.armor_by_id = {int(item["id"]): item["name"] for item in self.armor if item.get("name") and item.get("id")}
        self.goods_by_id = {int(item["id"]): item["name"] for item in self.goods if item.get("name") and item.get("id")}

    @classmethod
    def get(cls) -> "SekiroCatalog":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _load_json(path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []


class SekiroSlotEditor:
    """
    In-memory reverse engineering editor for a single Sekiro save slot (0x100000 payload).
    Operates on a bytearray slice of the BND4 container.
    """

    def __init__(self, payload: bytearray):
        if len(payload) < SLOT_PAYLOAD_SIZE:
            raise ValueError(f"Payload size {len(payload)} is smaller than expected Sekiro slot ({SLOT_PAYLOAD_SIZE}).")
        self.data = payload
        self.catalog = SekiroCatalog.get()

    # =========================================================================
    # Character Stats Read / Write
    # =========================================================================
    def get_stats(self) -> SekiroStats:
        steam_id = struct.unpack_from("<Q", self.data, OFFSET_STEAM_ID)[0]
        ng_plus = struct.unpack_from("<B", self.data, OFFSET_NG_PLUS)[0]
        hp = struct.unpack_from("<I", self.data, OFFSET_HP)[0]
        guard = struct.unpack_from("<I", self.data, OFFSET_GUARD)[0]
        attack = struct.unpack_from("<B", self.data, OFFSET_ATTACK)[0]
        souls = struct.unpack_from("<I", self.data, OFFSET_SOULS)[0]
        emblems = struct.unpack_from("<B", self.data, OFFSET_EMBLEMS)[0]
        skill_points = struct.unpack_from("<I", self.data, OFFSET_SKILL_POINTS)[0]

        return SekiroStats(
            steam_id=steam_id,
            hp=hp,
            attack=attack,
            guard=guard,
            emblems=emblems,
            skill_points=skill_points,
            souls=souls,
            ng_plus=ng_plus,
        )

    def set_stats(self, stats: SekiroStats) -> None:
        struct.pack_into("<Q", self.data, OFFSET_STEAM_ID, stats.steam_id)
        struct.pack_into("<B", self.data, OFFSET_NG_PLUS, max(0, min(255, stats.ng_plus)))
        struct.pack_into("<I", self.data, OFFSET_HP, max(0, min(0xFFFFFFFF, stats.hp)))
        struct.pack_into("<I", self.data, OFFSET_GUARD, max(0, min(0xFFFFFFFF, stats.guard)))
        struct.pack_into("<B", self.data, OFFSET_ATTACK, max(0, min(99, stats.attack)))
        struct.pack_into("<I", self.data, OFFSET_SOULS, max(0, min(0xFFFFFFFF, stats.souls)))
        struct.pack_into("<B", self.data, OFFSET_EMBLEMS, max(0, min(99, stats.emblems)))
        struct.pack_into("<I", self.data, OFFSET_SKILL_POINTS, max(0, min(999999999, stats.skill_points)))

    def reset_skill_points(self) -> None:
        """Reset allocated skill points by clearing the 16-byte skill block at 0x345A8."""
        self.data[OFFSET_RESET_SKILL : OFFSET_RESET_SKILL + 16] = b"\x00" * 16

    # =========================================================================
    # Inventory Parsing
    # =========================================================================
    def get_inventory(self) -> dict[str, list[SekiroItem]]:
        result: dict[str, list[SekiroItem]] = {
            "weapons": [],
            "armor": [],
            "goods": [],
            "storage": [],
        }

        # 1. Main player inventory
        end_inv = OFFSET_INV_START + SIZE_INV_SPAN
        offset = OFFSET_INV_START
        while offset < end_inv:
            handle, raw_id, qty, idx = struct.unpack_from("<IIII", self.data, offset)
            type_bits = handle & 0xF0000000
            item_id = raw_id & 0x00FFFFFF

            if type_bits != TYPE_EMPTY and item_id != 0:
                if type_bits == TYPE_WEAPON:
                    name = self.catalog.weapons_by_id.get(item_id, f"Unknown Weapon (ID: {item_id})")
                    category = "weapon"
                elif type_bits == TYPE_ARMOR:
                    name = self.catalog.armor_by_id.get(item_id, f"Unknown Armor (ID: {item_id})")
                    category = "armor"
                else:
                    name = self.catalog.goods_by_id.get(item_id, f"Unknown Good (ID: {item_id})")
                    category = "good"

                item = SekiroItem(
                    category=category,
                    handle=handle,
                    item_id=item_id,
                    name=name,
                    quantity=qty,
                    index=idx,
                    offset=offset,
                )
                if type_bits == TYPE_WEAPON:
                    result["weapons"].append(item)
                elif type_bits == TYPE_ARMOR:
                    result["armor"].append(item)
                elif type_bits == TYPE_GOOD:
                    result["goods"].append(item)

            offset += INV_RECORD_SIZE

        # 2. Storage items
        end_storage = OFFSET_STORAGE_START + SIZE_STORAGE_SPAN
        offset = OFFSET_STORAGE_START
        while offset < end_storage:
            handle, raw_id, qty, idx = struct.unpack_from("<IIII", self.data, offset)
            type_bits = handle & 0xF0000000
            item_id = raw_id & 0x00FFFFFF

            if type_bits == TYPE_GOOD and item_id != 0:
                name = self.catalog.goods_by_id.get(item_id, f"Unknown Item (ID: {item_id})")
                result["storage"].append(
                    SekiroItem(
                        category="storage",
                        handle=handle,
                        item_id=item_id,
                        name=name,
                        quantity=qty,
                        index=idx,
                        offset=offset,
                    )
                )
            offset += INV_RECORD_SIZE

        return result

    # =========================================================================
    # Inventory Modifications & Spawning
    # =========================================================================
    def update_good_quantity(self, item_offset: int, new_quantity: int) -> bool:
        """Update consumable quantity (0..99) at the specific inventory offset."""
        if not (OFFSET_INV_START <= item_offset < OFFSET_INV_START + SIZE_INV_SPAN or
                OFFSET_STORAGE_START <= item_offset < OFFSET_STORAGE_START + SIZE_STORAGE_SPAN):
            return False
        clamped = max(0, min(99, new_quantity))
        qty_offset = item_offset + 8
        struct.pack_into("<I", self.data, qty_offset, clamped)
        return True

    def _increment_inventory_counters(self) -> None:
        for counter_off in (OFFSET_COUNTER_1, OFFSET_COUNTER_2, OFFSET_COUNTER_STORAGE):
            val = struct.unpack_from("<H", self.data, counter_off)[0]
            struct.pack_into("<H", self.data, counter_off, (val + 1) & 0xFFFF)

    def spawn_good(self, item_name: str, quantity: int) -> bool:
        """
        Spawns a consumable good. If item already exists in inventory, increments quantity.
        Otherwise, finds the first available empty slot, configures the 16-byte entry,
        allocates a storage lookup slot, and bumps inventory counters.
        """
        if item_name not in self.catalog.goods_by_name:
            return False
        item_id = self.catalog.goods_by_name[item_name]
        clamped_qty = max(1, min(99, quantity))

        # Check if already present in main inventory
        inv = self.get_inventory()
        for existing in inv["goods"]:
            if existing.item_id == item_id:
                return self.update_good_quantity(existing.offset, clamped_qty)

        # Find first empty inventory slot
        empty_offset: Optional[int] = None
        all_indices: list[int] = []
        end_inv = OFFSET_INV_START + SIZE_INV_SPAN
        offset = OFFSET_INV_START
        while offset < end_inv:
            handle, raw_id, qty, idx = struct.unpack_from("<IIII", self.data, offset)
            if handle & 0xF0000000 == TYPE_EMPTY and empty_offset is None:
                empty_offset = offset
            if handle & 0xF0000000 != TYPE_EMPTY:
                all_indices.append(idx & 0x0FFF)
            offset += INV_RECORD_SIZE

        if empty_offset is None:
            return False  # Inventory full

        all_indices.sort()
        highest_index = all_indices[-1] if all_indices else 0
        new_index = highest_index + 1

        # Construct 16-byte good slot
        rand_byte = os.urandom(1)[0]
        slot_bytes = bytearray(
            struct.pack("<IIII", item_id, item_id, clamped_qty, new_index)
        )
        slot_bytes[3] = 0xB0
        slot_bytes[7] = 0x40
        slot_bytes[14] = rand_byte

        self.data[empty_offset : empty_offset + 16] = slot_bytes

        # Storage lookup entry (8 bytes: <II)
        end_lookup = OFFSET_STORAGE_LOOKUP + SIZE_STORAGE_LOOKUP_SPAN
        lookup_off = OFFSET_STORAGE_LOOKUP
        while lookup_off < end_lookup:
            l_id, _ = struct.unpack_from("<II", self.data, lookup_off)
            if l_id == 0:
                l_bytes = bytearray(struct.pack("<II", item_id, 1))
                l_bytes[3] = 0x40
                self.data[lookup_off : lookup_off + 8] = l_bytes
                break
            lookup_off += 8

        self._increment_inventory_counters()
        return True

    def spawn_equipment(self, item_name: str, item_type: str) -> bool:
        """
        Spawns a weapon or armor costume.
        Allocates a 60-byte GA slot entry and a 16-byte player inventory entry.
        """
        if item_type == "weapon":
            if item_name not in self.catalog.weapons_by_name:
                return False
            item_id = self.catalog.weapons_by_name[item_name]
            type_flag = 0x80
        elif item_type == "armor":
            if item_name not in self.catalog.armor_by_name:
                return False
            item_id = self.catalog.armor_by_name[item_name]
            type_flag = 0x90
        else:
            return False

        # 1. Find first empty GA slot
        end_ga = OFFSET_GA_START + SIZE_GA_SPAN
        ga_offset = OFFSET_GA_START
        empty_ga_offset: Optional[int] = None
        highest_ga_index = 0

        while ga_offset < end_ga:
            handle, g_id = struct.unpack_from("<II", self.data, ga_offset)
            if handle & 0xF0000000 == TYPE_EMPTY and empty_ga_offset is None:
                empty_ga_offset = ga_offset
            if handle & 0xF0000000 in (TYPE_WEAPON, TYPE_ARMOR):
                ga_idx = handle & 0xFFFF0000
                if ga_idx > highest_ga_index:
                    highest_ga_index = ga_idx
            ga_offset += GA_RECORD_SIZE

        if empty_ga_offset is None:
            return False  # GA table full

        new_ga_index = highest_ga_index + 1

        # Build 60-byte GA entry
        ga_entry = bytearray(60)
        struct.pack_into("<II", ga_entry, 0, new_ga_index, item_id)
        ga_entry[3] = type_flag
        ga_entry[2] = 0x80
        ga_entry[16] = 0x01
        if item_type == "armor":
            ga_entry[7] = 0x10
            ga_entry[8] = 0xE7
            ga_entry[9] = 0x03

        self.data[empty_ga_offset : empty_ga_offset + GA_RECORD_SIZE] = ga_entry

        # 2. Find first empty Inventory slot
        end_inv = OFFSET_INV_START + SIZE_INV_SPAN
        inv_offset = OFFSET_INV_START
        empty_inv_offset: Optional[int] = None
        highest_inv_index = 0

        while inv_offset < end_inv:
            handle, raw_id, qty, idx = struct.unpack_from("<IIII", self.data, inv_offset)
            if handle & 0xF0000000 == TYPE_EMPTY and empty_inv_offset is None:
                empty_inv_offset = inv_offset
            if handle & 0xF0000000 != TYPE_EMPTY:
                clean_idx = idx & 0x0FFF
                if clean_idx > highest_inv_index:
                    highest_inv_index = clean_idx
            inv_offset += INV_RECORD_SIZE

        if empty_inv_offset is None:
            return False  # Inventory full

        new_inv_index = highest_inv_index + 1
        rand_bytes = os.urandom(2)

        inv_entry = bytearray(16)
        struct.pack_into("<IIII", inv_entry, 0, new_ga_index, item_id, 1, new_inv_index)
        inv_entry[3] = type_flag
        inv_entry[2] = 0x80
        if item_type == "armor":
            inv_entry[7] = 0x10
        inv_entry[14] = rand_bytes[0]
        inv_entry[15] = rand_bytes[1]

        self.data[empty_inv_offset : empty_inv_offset + 16] = inv_entry

        self._increment_inventory_counters()
        return True

    # =========================================================================
    # Slot Import with Steam ID Preservation
    # =========================================================================
    def import_slot_data(self, source_payload: bytes, preserve_steam_id: bool = True) -> int:
        """
        Replaces current slot's payload with source slot payload,
        preserving the current slot's Steam ID so the game loads it seamlessly.
        Returns the preserved Steam ID.
        """
        if len(source_payload) < SLOT_PAYLOAD_SIZE:
            raise ValueError(f"Import source data is {len(source_payload)} bytes, expected at least {SLOT_PAYLOAD_SIZE}")

        current_steam_id = struct.unpack_from("<Q", self.data, OFFSET_STEAM_ID)[0]
        self.data[:SLOT_PAYLOAD_SIZE] = source_payload[:SLOT_PAYLOAD_SIZE]

        if preserve_steam_id:
            struct.pack_into("<Q", self.data, OFFSET_STEAM_ID, current_steam_id)

        return current_steam_id
