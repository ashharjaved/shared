from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from .entities import Node, NodeType, Flow

class Action(str, Enum):
    SEND_MESSAGE = "SEND_MESSAGE"
    SET_VAR = "SET_VAR"
    END = "END"
    NOOP = "NOOP"

class RuntimeErrorBase(Exception): ...
class FlowDefinitionError(RuntimeErrorBase): ...
class GuardExceeded(RuntimeErrorBase): ...
class OptimisticLockError(RuntimeErrorBase): ...
class SessionExpired(RuntimeErrorBase): ...

@dataclass
class StepResult:
    node_id: str
    actions: List[Dict[str, Any]]  # e.g., [{"type":"SEND_MESSAGE","payload":{...}}]
    next_node_id: Optional[str]
    ended: bool = False

def evaluate_branch(node: Node, context: Dict[str, Any], eval_fn) -> Optional[str]:
    if not node.branches:
        return node.next
    for edge in node.branches:
        if edge.when.strip().lower() == "default":
            default_next = edge.next
            # evaluate later only if no branch matched
            continue
    # try each non-default in order
    fallback = None
    for edge in node.branches:
        w = edge.when.strip().lower()
        if w == "default":
            fallback = edge.next
            continue
        try:
            if eval_fn(edge.when, context):
                return edge.next
        except Exception:
            continue
    return fallback
