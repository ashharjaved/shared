from __future__ import annotations
from abc import ABC, abstractmethod

class PasswordHasherPort(ABC):
    @abstractmethod
    def hash(self, plain: str) -> str:
        pass

    @abstractmethod
    def verify(self, plain: str, hashed: str) -> bool:
        pass