from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum


class MessageRole(str, Enum):
    """Rôles possibles pour les messages de conversation"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Modèle pour un message de conversation"""
    role: MessageRole
    content: str
    timestamp: Optional[str] = None


class ConversationHistory(BaseModel):
    """Historique complet d'une conversation"""
    messages: List[Message]
    
    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """Récupère les N derniers messages"""
        return self.messages[-limit:] if len(self.messages) > limit else self.messages
    
    def get_user_messages(self) -> List[Message]:
        """Récupère uniquement les messages utilisateur"""
        return [msg for msg in self.messages if msg.role == MessageRole.USER]
    
    def get_last_user_message(self) -> Optional[Message]:
        """Récupère le dernier message utilisateur"""
        user_messages = self.get_user_messages()
        return user_messages[-1] if user_messages else None 