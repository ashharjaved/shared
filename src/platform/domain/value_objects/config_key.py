from __future__ import annotations

import re
from dataclasses import dataclass


_KEY_RE = re.compile(r"^[a-z0-9_.:-]{1,100}$")


@dataclass(frozen=True, slots=True)
class ConfigKey:
    """
    Value object for configuration keys.
    Keeps a conservative character set and max length aligned to DB.
    """
    value: str

    def __post_init__(self) -> None:
        if not _KEY_RE.match(self.value):
            # Keep message concise; format enforcement mirrors optional DB CHECK.
            raise ValueError("config key must match ^[a-z0-9_.:-]{1,100}$")

    def __str__(self) -> str:  # convenience for building cache keys
        return self.value
