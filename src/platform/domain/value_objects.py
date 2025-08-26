# src/platform/domain/value_objects.py
from __future__ import annotations

from enum import Enum

class ConfigType(str, Enum):
    GENERAL = "GENERAL"
    WHITELABEL = "WHITELABEL"
    INTEGRATION = "INTEGRATION"
    RISK = "RISK"

class ConfigSourceLevel(str, Enum):
    PLATFORM = "PLATFORM"
    RESELLER = "RESELLER"
    CLIENT = "CLIENT"