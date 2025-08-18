from pydantic import BaseModel, Field
from typing import Any, List

class ConfigSetRequest(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: Any

class ConfigItem(BaseModel):
    key: str
    value: Any

class ConfigList(BaseModel):
    items: List[ConfigItem]
