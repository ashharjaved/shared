# Begin: src/conversation/domain/value_objects.py ***
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum
import re
from typing import Dict, List, Mapping, MutableMapping, Optional, Union


# -------------------------
# JSON type (no Any)
# -------------------------
JSONValue = Union[str, int, float, bool, None, "JSONObject", "JSONArray"]
JSONObject = Dict[str, JSONValue]
JSONArray = List[JSONValue]


class SessionStatus(StrEnum):
    """Conversation session lifecycle status."""
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"


_E164 = re.compile(r"^\+[1-9]\d{1,14}$")


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    """E.164 phone number value object."""

    value: str

    def __post_init__(self) -> None:
        if not _E164.match(self.value):
            raise ValueError("phone_number must be E.164 (e.g., +14155552671)")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass(frozen=True, slots=True)
class MenuOption:
    """
    An option shown under a menu.
    - label: human-friendly label (“Appointments”)
    - next_menu: key of the next menu to navigate to (within the same flow), or None
    - action: action identifier for ActionRouter, or None
    """
    label: str
    next_menu: Optional[str]
    action: Optional[str]


@dataclass(slots=True)
class MenuDefinition:
    """
    Wrapper around the JSON definition stored in DB.

    Expected shape (example):
    {
      "menus": {
        "main": {
          "prompt": "Welcome...",
          "options": {
            "1": {"label": "Appointments", "next_menu": "appointments", "action": null},
            "2": {"label": "Help", "next_menu": null, "action": "HELP"}
          }
        },
        "appointments": { ... }
      }
    }
    """

    _raw: JSONObject

    # ---- Construction helpers ----
    @staticmethod
    def from_json(data: Mapping[str, JSONValue]) -> "MenuDefinition":
        return MenuDefinition(_raw=dict(data))  # copy to detach from caller

    def to_json(self) -> JSONObject:
        # Shallow copy to avoid external mutation
        return dict(self._raw)

    # ---- Accessors ----
    def has_menu(self, key: str) -> bool:
        menus = self._menus_map()
        return key in menus

    def prompt_for(self, key: str) -> str:
        menu = self._menu_obj(key)
        prompt = menu.get("prompt")
        if not isinstance(prompt, str):
            raise KeyError(f"menu '{key}' missing 'prompt'")
        return prompt

    def options_for(self, key: str) -> Dict[str, MenuOption]:
        menu = self._menu_obj(key)
        raw_opts = menu.get("options")
        if not isinstance(raw_opts, dict):
            raise KeyError(f"menu '{key}' missing 'options'")
        out: Dict[str, MenuOption] = {}
        for k, v in raw_opts.items():
            if not isinstance(v, dict):
                raise KeyError(f"menu '{key}' option '{k}' invalid")
            label = v.get("label")
            next_menu = v.get("next_menu")
            action = v.get("action")
            if not isinstance(label, str):
                raise KeyError(f"menu '{key}' option '{k}' missing 'label'")
            nm = str(next_menu) if isinstance(next_menu, str) else None
            ac = str(action) if isinstance(action, str) else None
            out[str(k)] = MenuOption(label=label, next_menu=nm, action=ac)
        return out

    def resolve_option(self, key: str, selection: str) -> MenuOption | None:
        """
        Resolve user selection for the given menu key.

        - Match by numeric key: "1", "2", ...
        - Else fallback to case-insensitive label match.
        """
        selection_norm = selection.strip()
        options = self.options_for(key)

        # 1) by numeric/index key
        if selection_norm in options:
            return options[selection_norm]

        # 2) by case-insensitive label
        sel_lower = selection_norm.lower()
        for opt in options.values():
            if opt.label.lower() == sel_lower:
                return opt
        return None

    # ---- internals ----
    def _menus_map(self) -> Mapping[str, JSONValue]:
        menus = self._raw.get("menus")
        if not isinstance(menus, dict):
            raise KeyError("definition missing 'menus' dictionary")
        return menus

    def _menu_obj(self, key: str) -> Mapping[str, JSONValue]:
        menus = self._menus_map()
        obj = menus.get(key)
        if not isinstance(obj, dict):
            raise KeyError(f"menu '{key}' not found")
        return obj
