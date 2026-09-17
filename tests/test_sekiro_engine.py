import struct
from pathlib import Path
from savescope.core.sekiro import (
    SekiroCatalog, SekiroSlotEditor, SekiroStats,
    OFFSET_STEAM_ID, OFFSET_HP, OFFSET_ATTACK, OFFSET_SOULS,
    OFFSET_EMBLEMS, OFFSET_SKILL_POINTS, OFFSET_RESET_SKILL,
    OFFSET_GA_START, OFFSET_INV_START, SLOT_PAYLOAD_SIZE,
    TYPE_EMPTY, TYPE_WEAPON, TYPE_GOOD
)

def test_sekiro_catalog_loading():
    catalog = SekiroCatalog.get()
    assert len(catalog.weapons) > 0
    assert len(catalog.armor) > 0
    assert len(catalog.goods) > 0

    # Key known items
    assert "Healing Gourd" in catalog.goods_by_name
    assert "Ceramic Shard" in catalog.goods_by_name
    assert "Whirlwind Slash" in catalog.weapons_by_name

def test_sekiro_stats_read_write_clamping():
    payload = bytearray(SLOT_PAYLOAD_SIZE)
    editor = SekiroSlotEditor(payload)

    # Write custom stats
    stats = SekiroStats(
        steam_id=76561199503231545,
        hp=1850,
        attack=50,
        guard=500,
        emblems=20,
        skill_points=42,
        souls=15000,
        ng_plus=2,
    )
    editor.set_stats(stats)

    read_back = editor.get_stats()
    assert read_back.steam_id == 76561199503231545
    assert read_back.hp == 1850
    assert read_back.attack == 50
    assert read_back.guard == 500
    assert read_back.emblems == 20
    assert read_back.skill_points == 42
    assert read_back.souls == 15000
    assert read_back.ng_plus == 2

    # Verify boundary clamping
    oversized = SekiroStats(
        steam_id=123,
        attack=150,    # Max 99
        emblems=200,   # Max 99
        ng_plus=300,   # Max 255
    )
    editor.set_stats(oversized)
    clamped = editor.get_stats()
    assert clamped.attack == 99
    assert clamped.emblems == 99
    assert clamped.ng_plus == 255

def test_sekiro_reset_skill_points():
    payload = bytearray(SLOT_PAYLOAD_SIZE)
    # Fill skill allocation block with dummy bytes
    payload[OFFSET_RESET_SKILL : OFFSET_RESET_SKILL + 16] = b"\xFF" * 16

    editor = SekiroSlotEditor(payload)
    editor.reset_skill_points()

    assert payload[OFFSET_RESET_SKILL : OFFSET_RESET_SKILL + 16] == b"\x00" * 16

def test_sekiro_inventory_parsing_and_quantity_edit():
    payload = bytearray(SLOT_PAYLOAD_SIZE)
    editor = SekiroSlotEditor(payload)

    # Insert a synthetic Healing Gourd (ID 3000) at first inventory slot
    gourd_id = 3000
    handle = 0xB0000001
    struct.pack_into("<IIII", payload, OFFSET_INV_START, handle, gourd_id, 5, 1)

    inv = editor.get_inventory()
    assert len(inv["goods"]) == 1
    gourd = inv["goods"][0]
    assert gourd.item_id == 3000
    assert gourd.name == "Healing Gourd"
    assert gourd.quantity == 5

    # Update quantity
    success = editor.update_good_quantity(OFFSET_INV_START, 10)
    assert success is True

    updated_inv = editor.get_inventory()
    assert updated_inv["goods"][0].quantity == 10

def test_sekiro_spawn_good():
    payload = bytearray(SLOT_PAYLOAD_SIZE)
    editor = SekiroSlotEditor(payload)

    # Spawn Divine Grass
    assert editor.spawn_good("Divine Grass", 3) is True

    inv = editor.get_inventory()
    grass = [item for item in inv["goods"] if "Divine Grass" in item.name]
    assert len(grass) == 1
    assert grass[0].quantity == 3

    # Spawning same good again should increment/update quantity
    assert editor.spawn_good("Divine Grass", 5) is True
    inv_after = editor.get_inventory()
    grass_after = [item for item in inv_after["goods"] if "Divine Grass" in item.name]
    assert len(grass_after) == 1
    assert grass_after[0].quantity == 5

def test_sekiro_spawn_equipment():
    payload = bytearray(SLOT_PAYLOAD_SIZE)
    editor = SekiroSlotEditor(payload)

    # Spawn weapon
    assert editor.spawn_equipment("Whirlwind Slash", "weapon") is True

    inv = editor.get_inventory()
    assert len(inv["weapons"]) == 1
    assert inv["weapons"][0].name == "Whirlwind Slash"

def test_sekiro_import_slot_steam_id_preservation():
    # Slot A (target)
    slot_a = bytearray(SLOT_PAYLOAD_SIZE)
    editor_a = SekiroSlotEditor(slot_a)
    editor_a.set_stats(SekiroStats(steam_id=76561199503231545, hp=1000, attack=5))

    # Slot B (source with different steam id and high stats)
    slot_b = bytearray(SLOT_PAYLOAD_SIZE)
    editor_b = SekiroSlotEditor(slot_b)
    editor_b.set_stats(SekiroStats(steam_id=99999999999999999, hp=2000, attack=99))

    # Import Slot B into Slot A with Steam ID preservation
    preserved_id = editor_a.import_slot_data(bytes(slot_b), preserve_steam_id=True)
    assert preserved_id == 76561199503231545

    # Check that Slot A has Slot B's stats but Slot A's original Steam ID
    final_stats = editor_a.get_stats()
    assert final_stats.steam_id == 76561199503231545
    assert final_stats.hp == 2000
    assert final_stats.attack == 99
