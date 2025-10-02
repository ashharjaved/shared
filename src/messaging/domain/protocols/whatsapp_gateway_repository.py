"""
WhatsApp Gateway Protocol
Abstracts external WhatsApp API integration.
"""
from abc import abstractmethod
from typing import Protocol, Dict, Any, List


class WhatsAppGateway(Protocol):
    """
    Protocol for WhatsApp Business API integration.
    
    Isolates domain from Meta Graph API specifics.
    """
    
    @abstractmethod
    async def send_text_message(
        self, phone_number_id: str, to: str, body: str
    ) -> Dict[str, Any]:
        """Send text message via WhatsApp Cloud API."""
        ...
    
    @abstractmethod
    async def send_template_message(
        self,
        phone_number_id: str,
        to: str,
        template_name: str,
        language_code: str,
        components: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Send template message with variable substitution."""
        ...
    
    @abstractmethod
    async def send_interactive_message(
        self, phone_number_id: str, to: str, interactive: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send interactive message (buttons, lists)."""
        ...
    
    @abstractmethod
    async def get_message_templates(
        self, waba_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch message templates from WhatsApp."""
        ...
    
    @abstractmethod
    async def create_template(
        self, waba_id: str, template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit new template for approval."""
        ...
    
    @abstractmethod
    async def mark_message_read(
        self, phone_number_id: str, message_id: str
    ) -> bool:
        """Mark message as read."""
        ...