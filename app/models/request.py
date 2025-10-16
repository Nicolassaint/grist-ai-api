from pydantic import BaseModel, validator
from typing import List, Dict, Any, Optional
from .message import Message
import logging

# Configuration du logger pour les modèles
logger = logging.getLogger("request_models")


class RequestBody(BaseModel):
    """Corps de la requête principale"""

    documentId: str
    messages: List[Dict[str, Any]]  # Format brut des messages
    webhookUrl: str
    executionMode: str = "production"

    @validator("documentId")
    def validate_document_id(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError(
                f"documentId doit être une chaîne non vide, reçu: {v} (type: {type(v)})"
            )
        return v

    @validator("messages")
    def validate_messages(cls, v):
        if not isinstance(v, list):
            raise ValueError(f"messages doit être une liste, reçu: {type(v)}")
        if len(v) == 0:
            logger.warning("Liste de messages vide reçue")
        return v

    @validator("webhookUrl")
    def validate_webhook_url(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError(
                f"webhookUrl doit être une chaîne non vide, reçu: {v} (type: {type(v)})"
            )
        return v


class GristRequest(BaseModel):
    """Requête complète reçue par l'API"""

    headers: Dict[str, Any] = {}
    params: Dict[str, Any] = {}
    query: Dict[str, Any] = {}
    body: RequestBody

    @validator("body")
    def validate_body(cls, v):
        if not v:
            raise ValueError("Le corps de la requête est requis")
        return v

    class Config:
        # Configuration pour avoir des erreurs plus détaillées
        anystr_strip_whitespace = True
        validate_assignment = True


class ProcessedRequest(BaseModel):
    """Requête après traitement interne"""

    document_id: str
    messages: List[Message]
    webhook_url: str
    execution_mode: str
    grist_api_key: Optional[str] = None

    @classmethod
    def from_grist_request(
        cls, grist_request: GristRequest, grist_api_key: str = None
    ) -> "ProcessedRequest":
        """Convertit une GristRequest en ProcessedRequest"""
        logger.info(
            f"Conversion GristRequest vers ProcessedRequest - {len(grist_request.body.messages)} messages"
        )

        # Conversion des messages du format brut vers le format Message
        processed_messages = []
        for i, msg_dict in enumerate(grist_request.body.messages):
            try:
                processed_messages.append(
                    Message(
                        role=msg_dict.get("role", "user"),
                        content=msg_dict.get("content", ""),
                        timestamp=msg_dict.get("timestamp"),
                    )
                )
                logger.debug(
                    f"Message {i} converti: role={msg_dict.get('role')}, content_length={len(msg_dict.get('content', ''))}"
                )
            except Exception as e:
                logger.error(
                    f"Erreur conversion message {i}: {str(e)}, données: {msg_dict}"
                )
                raise ValueError(f"Erreur conversion message {i}: {str(e)}")

        return cls(
            document_id=grist_request.body.documentId,
            messages=processed_messages,
            webhook_url=grist_request.body.webhookUrl,
            execution_mode=grist_request.body.executionMode,
            grist_api_key=grist_api_key,
        )


class ChatResponse(BaseModel):
    """Réponse de l'API chat"""

    response: str
    agent_used: str
    sql_query: Optional[str] = None
    data_analyzed: Optional[bool] = False
    error: Optional[str] = None
