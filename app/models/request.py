from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from .message import Message


class RequestBody(BaseModel):
    """Corps de la requête principale"""
    documentId: str
    messages: List[Dict[str, Any]]  # Format brut des messages
    webhookUrl: str
    executionMode: str = "production"


class GristRequest(BaseModel):
    """Requête complète reçue par l'API"""
    headers: Dict[str, Any] = {}
    params: Dict[str, Any] = {}
    query: Dict[str, Any] = {}
    body: RequestBody


class ProcessedRequest(BaseModel):
    """Requête après traitement interne"""
    document_id: str
    messages: List[Message]
    webhook_url: str
    execution_mode: str
    grist_api_key: Optional[str] = None
    
    @classmethod
    def from_grist_request(cls, grist_request: GristRequest, grist_api_key: str = None) -> "ProcessedRequest":
        """Convertit une GristRequest en ProcessedRequest"""
        # Conversion des messages du format brut vers le format Message
        processed_messages = []
        for msg_dict in grist_request.body.messages:
            processed_messages.append(Message(
                role=msg_dict.get("role", "user"),
                content=msg_dict.get("content", ""),
                timestamp=msg_dict.get("timestamp")
            ))
        
        return cls(
            document_id=grist_request.body.documentId,
            messages=processed_messages,
            webhook_url=grist_request.body.webhookUrl,
            execution_mode=grist_request.body.executionMode,
            grist_api_key=grist_api_key
        )


class ChatResponse(BaseModel):
    """Réponse de l'API chat"""
    response: str
    agent_used: str
    sql_query: Optional[str] = None
    data_analyzed: Optional[bool] = False
    error: Optional[str] = None 