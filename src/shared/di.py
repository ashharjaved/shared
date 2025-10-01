from __future__ import annotations
from typing import Any, Callable, Dict

_ServiceFactory = Callable[..., Any]

class _Registry:
    def __init__(self) -> None:
        self._items: Dict[str, _ServiceFactory] = {}

    def register(self, key: str, factory: _ServiceFactory) -> None:
        if key in self._items:
            raise ValueError(f"Factory already registered for key: {key}")
        self._items[key] = factory

    def resolve(self, key: str, /, **kwargs: Any) -> Any:
        try:
            return self._items[key](**kwargs)
        except KeyError as e:
            raise KeyError(f"No factory registered for key: {key}") from e

services = _Registry()

__all__ = ["services"]