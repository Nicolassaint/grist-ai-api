import structlog
import logging
import sys
from typing import Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()


def configure_logging():
    """Configure le système de logging riche mais concis"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Configuration de structlog avec couleurs et format concis
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Format coloré et concis
            structlog.dev.ConsoleRenderer(colors=True, pad_event=25)
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configuration du logger standard
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level),
    )


class AgentLogger:
    """Logger riche mais concis pour les agents"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = structlog.get_logger(agent_name)
    
    def info(self, message: str, **kwargs):
        """Log d'information avec emoji et couleurs"""
        # Filtrer les éléments inutiles
        clean_kwargs = {k: v for k, v in kwargs.items() if k not in ['agent', 'client_ip']}
        self.logger.info(f"ℹ️  {message}", agent=self.agent_name, **clean_kwargs)
    
    def error(self, message: str, **kwargs):
        """Log d'erreur avec emoji"""
        clean_kwargs = {k: v for k, v in kwargs.items() if k not in ['agent', 'client_ip']}
        self.logger.error(f"❌ {message}", agent=self.agent_name, **clean_kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log d'avertissement avec emoji"""
        clean_kwargs = {k: v for k, v in kwargs.items() if k not in ['agent', 'client_ip']}
        self.logger.warning(f"⚠️  {message}", agent=self.agent_name, **clean_kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log de debug détaillé"""
        clean_kwargs = {k: v for k, v in kwargs.items() if k not in ['agent', 'client_ip']}
        self.logger.debug(f"🔍 {message}", agent=self.agent_name, **clean_kwargs)
    
    def log_request(self, method: str, path: str, status: int = None):
        """Log concis pour les requêtes HTTP"""
        if status:
            emoji = "✅" if status < 400 else "❌"
            self.info(f"{emoji} {method} {path}", status=status)
        else:
            self.info(f"🔄 {method} {path}")
    
    def log_agent_start(self, agent_type: str, query_preview: str):
        """Log du démarrage d'un agent"""
        self.info(f"🚀 Agent {agent_type} démarré", query=query_preview[:80] + "..." if len(query_preview) > 80 else query_preview)
    
    def log_agent_response(self, agent_type: str, success: bool, duration: float = None):
        """Log du résultat d'un agent"""
        emoji = "✅" if success else "❌"
        if duration:
            self.info(f"{emoji} Agent {agent_type} terminé", duration=f"{duration:.1f}s")
        else:
            self.info(f"{emoji} Agent {agent_type} terminé")
    
    def log_sql_generation(self, sql_query: str, tables_count: int):
        """Log pour la génération SQL"""
        query_preview = sql_query[:60] + "..." if len(sql_query) > 60 else sql_query
        self.info(f"📊 SQL généré", query=query_preview, tables=tables_count)
    
    def log_grist_api(self, endpoint: str, status: int):
        """Log des appels API Grist"""
        emoji = "✅" if status < 400 else "❌"
        endpoint_short = endpoint.split('/')[-1] if '/' in endpoint else endpoint
        self.info(f"{emoji} API Grist", endpoint=endpoint_short, status=status)
    
    def log_chat_request(self, doc_id: str, nb_messages: int):
        """Log concis pour les requêtes chat"""
        self.info(f"💬 Chat request", doc=doc_id[:8], msgs=nb_messages)
    
    def log_chat_response(self, agent_used: str, response_length: int, has_error: bool = False):
        """Log concis pour les réponses chat"""
        emoji = "✅" if not has_error else "⚠️"
        self.info(f"{emoji} Chat response", agent=agent_used, chars=response_length)


# Initialisation du logging
configure_logging() 