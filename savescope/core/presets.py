from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class PresetAction:
    field_key: str
    target_value: Any
    operation: str = "set"  # set, add, multiply

@dataclass
class SavePreset:
    name: str
    description: str
    actions: list[PresetAction]

class PresetLibrary:
    """
    Phase 8: Configurable preset system.
    """
    @staticmethod
    def get_standard_presets() -> list[SavePreset]:
        return [
            SavePreset(
                name="Max Wealth",
                description="Sets gold and major currencies to maximum allowed value.",
                actions=[PresetAction(field_key="gold", target_value=999999)]
            ),
            SavePreset(
                name="Hero Overhaul",
                description="Maxes HP, MP, level, and character stats.",
                actions=[
                    PresetAction(field_key="level", target_value=99),
                    PresetAction(field_key="hp", target_value=9999),
                    PresetAction(field_key="max_hp", target_value=9999),
                    PresetAction(field_key="mp", target_value=999),
                    PresetAction(field_key="max_mp", target_value=999),
                ]
            ),
            SavePreset(
                name="Starter Boost",
                description="Provides a gentle initial advantage (1,000 Gold, Level 5).",
                actions=[
                    PresetAction(field_key="gold", target_value=1000),
                    PresetAction(field_key="level", target_value=5),
                ]
            )
        ]
