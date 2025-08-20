from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class NodeType(str, Enum):
    START = "START"
    MESSAGE = "MESSAGE"
    SET_VAR = "SET_VAR"
    BRANCH = "BRANCH"
    END = "END"

@dataclass
class Edge:
    when: str  # expression like "payload.text == 'hi'" or "default"
    next: Optional[str]

@dataclass
class Node:
    id: str
    type: NodeType
    text: Optional[str] = None               # for MESSAGE
    assign: Optional[Dict[str, Any]] = None  # for SET_VAR
    branches: Optional[List[Edge]] = None    # for BRANCH
    next: Optional[str] = None               # for linear transitions

@dataclass
class Flow:
    id: Any
    name: str
    version: int
    start_node_id: str
    nodes: Dict[str, Node] = field(default_factory=dict)

@dataclass
class Session:
    id: Any
    tenant_id: Any
    channel_id: Any
    phone_number: str
    current_node_id: Optional[str]
    vars: Dict[str, Any]
    status: str
    stage: str
    expires_at: Any
    last_activity: Any
    context: Dict[str, Any]  # raw context_jsonb
