# src/conversation/domain/entities/flow_step.py
"""Flow step entity - represents a single step in a conversation flow."""

from typing import Optional, Dict, Any, List, Set
from uuid import UUID

from src.shared_.domain.entity import Entity
from src.conversation.domain.value_objects import StepType, StepAction


class FlowStep(Entity):
    """
    Flow step entity.
    
    Represents a single step in a conversation flow with its configuration,
    actions, and transitions.
    """
    
    def __init__(
        self,
        id: UUID,
        flow_id: UUID,
        step_key: str,
        step_type: StepType,
        order: int,
        prompt: Dict[str, str],  # language -> message text
        options: Optional[List[Dict[str, Any]]] = None,
        validation: Optional[Dict[str, Any]] = None,
        actions: Optional[List[StepAction]] = None,
        transitions: Optional[Dict[str, str]] = None,  # condition -> next_step_key
        metadata: Optional[Dict[str, Any]] = None,
        is_entry_point: bool = False,
    ):
        super().__init__(id)
        self.flow_id = flow_id
        self.step_key = step_key
        self.step_type = step_type
        self.order = order
        self.prompt = prompt
        self.options = options or []
        self.validation = validation or {}
        self.actions = actions or []
        self.transitions = transitions or {}
        self.metadata = metadata or {}
        self.is_entry_point = is_entry_point
    
    def get_prompt(self, language: str = "en") -> str:
        """Get prompt text for specified language with fallback."""
        return self.prompt.get(language, self.prompt.get("en", ""))
    
    def add_transition(self, condition: str, next_step_key: str) -> None:
        """Add a transition rule."""
        self.transitions[condition] = next_step_key
    
    def get_next_step(self, user_input: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Determine next step based on user input and context.
        
        Returns next step key or None if no match.
        """
        context = context or {}
        
        # For menu steps, match by option key
        if self.step_type == StepType.MENU and user_input:
            # Try to match option by key or index
            for idx, option in enumerate(self.options, 1):
                if user_input == option.get("key") or user_input == str(idx):
                    return option.get("next_step")
        
        # For conditional transitions, evaluate conditions
        for condition, next_step in self.transitions.items():
            if self._evaluate_condition(condition, user_input, context):
                return next_step
        
        # Default transition
        return self.transitions.get("default")
    
    def _evaluate_condition(self, condition: str, user_input: Optional[str], context: Dict[str, Any]) -> bool:
        """Evaluate a transition condition."""
        # Simple condition evaluation (can be extended)
        if condition == "default":
            return True
        
        if condition.startswith("input_equals:"):
            expected = condition.split(":", 1)[1]
            return user_input == expected
        
        if condition.startswith("context_has:"):
            key = condition.split(":", 1)[1]
            return key in context
        
        return False
    
    def validate(self, available_step_keys: Set[str]) -> List[str]:
        """
        Validate step configuration.
        
        Returns list of validation errors.
        """
        errors = []
        
        # Validate prompts
        if not self.prompt:
            errors.append("No prompt defined")
        
        # Validate menu options
        if self.step_type == StepType.MENU:
            if not self.options:
                errors.append("Menu step must have options")
            else:
                for idx, option in enumerate(self.options):
                    if "key" not in option:
                        errors.append(f"Option {idx} missing key")
                    if "text" not in option:
                        errors.append(f"Option {idx} missing text")
        
        # Validate transitions reference valid steps
        for condition, next_step in self.transitions.items():
            if next_step not in available_step_keys and next_step != "END":
                errors.append(f"Transition '{condition}' references unknown step '{next_step}'")
        
        # Validate actions
        for action in self.actions:
            action_errors = action.validate()
            errors.extend(action_errors)
        
        return errors