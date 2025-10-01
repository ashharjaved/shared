from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, Dict, Optional, Union
from uuid import UUID

class TokenServicePort(ABC):
    @abstractmethod
    def create_access(self, sub: Union[str, UUID], tenant_id: Union[str, UUID], role: str,
                      expires: Optional[timedelta] = None) -> str: pass
    
    @abstractmethod
    def create_refresh(self, sub: Union[str, UUID], tenant_id: Union[str, UUID], role: str,
                       expires: Optional[timedelta] = None) -> str: pass
    
    @abstractmethod
    def decode(self, token: str) -> Dict[str, Any]: pass
