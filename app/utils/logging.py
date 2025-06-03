import structlog
import logging
import sys
from typing import Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()


def configure_logging():
    """Configure le système de logging structuré et lisible pour l'humain"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Configuration de structlog pour un format lisible
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Format console lisible au lieu de JSON
            structlog.dev.ConsoleRenderer(colors=True)
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configuration du logger standard avec un format plus lisible
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level),
    )


class AgentLogger:
    """Logger spécialisé pour les agents avec format lisible"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = structlog.get_logger(agent_name)
    
    def info(self, message: str, **kwargs):
        """Log d'information"""
        self.logger.info(message, agent=self.agent_name, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log d'erreur"""
        self.logger.error(message, agent=self.agent_name, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log d'avertissement"""
        self.logger.warning(message, agent=self.agent_name, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log de debug"""
        self.logger.debug(message, agent=self.agent_name, **kwargs)
    
    def log_agent_start(self, request_id: str, user_query: str):
        """Log du démarrage d'un agent"""
        query_preview = user_query[:100] + "..." if len(user_query) > 100 else user_query
        self.info(
            f"🚀 Agent démarré",
            request_id=request_id,
            query=query_preview
        )
    
    def log_agent_response(self, request_id: str, response: str, execution_time: float):
        """Log de la réponse d'un agent"""
        self.info(
            f"✅ Agent terminé",
            request_id=request_id,
            response_chars=len(response),
            duration=f"{execution_time:.2f}s"
        )
    
    def log_sql_generation(self, request_id: str, sql_query: str, table_schemas: Dict[str, Any]):
        """Log spécifique pour la génération SQL"""
        self.info(
            f"📊 Requête SQL générée",
            request_id=request_id,
            query=sql_query[:100] + "..." if len(sql_query) > 100 else sql_query,
            tables=len(table_schemas)
        )
    
    def log_grist_api_call(self, request_id: str, endpoint: str, status_code: int):
        """Log des appels API Grist"""
        status_emoji = "✅" if status_code < 400 else "❌"
        self.info(
            f"{status_emoji} Appel API Grist",
            request_id=request_id,
            endpoint=endpoint.split('/')[-2:],  # Dernières parties de l'URL
            status=status_code
        )


# Initialisation du logging
configure_logging() 