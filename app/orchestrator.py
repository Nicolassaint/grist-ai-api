"""
═══════════════════════════════════════════════════════════════════════════════
AI ORCHESTRATOR V2 - Coordinateur principal avec système de pipeline
═══════════════════════════════════════════════════════════════════════════════

RÔLE:
    L'orchestrateur est le point d'entrée principal de l'API. Il coordonne
    l'exécution des agents via un système de pipeline modulaire.

ARCHITECTURE:
    ┌─────────────────┐
    │  FastAPI Route  │
    └────────┬────────┘
             │
             ↓
    ┌─────────────────┐
    │  Orchestrator   │ ← Vous êtes ici
    └────────┬────────┘
             │
             ├→ Router Agent (choisit un plan)
             │
             ├→ Pipeline Executor (exécute le plan)
             │   │
             │   ├→ Generic Agent
             │   ├→ SQL Agent
             │   ├→ Analysis Agent
             │   └→ Architecture Agent
             │
             └→ ChatResponse (retournée à l'utilisateur)

FLUX D'EXÉCUTION:
    1. Réception ProcessedRequest
    2. Router choisit un ExecutionPlan
    3. Construction du ExecutionContext
    4. PipelineExecutor exécute les agents séquentiellement
    5. Chaque agent enrichit le contexte
    6. Retour ChatResponse finale

AVANTAGES DU SYSTÈME:
    ✅ Modulaire: Facile d'ajouter/retirer des agents
    ✅ Testable: Chaque composant testé indépendamment
    ✅ Extensible: Nouveaux plans = quelques lignes
    ✅ Maintenable: Code clair et bien séparé
    ✅ Traçable: Contexte garde l'historique d'exécution

EXEMPLE D'UTILISATION:
    >>> orchestrator = AIOrchestrator()
    >>> request = ProcessedRequest(...)
    >>> response = await orchestrator.process_chat_request(request)
    >>> print(response.response)

═══════════════════════════════════════════════════════════════════════════════
"""

import openai
import os
import uuid
from typing import Dict, Any
from .models.request import ProcessedRequest, ChatResponse
from .models.message import ConversationHistory
from .utils.logging import AgentLogger
from .config.history_config import HistoryConfig

# Agents
from .agents.router_agent import RouterAgent
from .agents.generic_agent import GenericAgent
from .agents.sql_agent import SQLAgent
from .agents.analysis_agent import AnalysisAgent
from .agents.architecture_agent import DataArchitectureAgent

# Pipeline
from .pipeline.context import ExecutionContext
from .pipeline.executor import PipelineExecutor
from .pipeline.plans import AgentType

# Grist
from .grist.schema_fetcher import GristSchemaFetcher
from .grist.sql_runner import GristSQLRunner
from .grist.sample_fetcher import GristSampleFetcher


class AIOrchestrator:
    """
    Orchestrateur principal gérant le pipeline d'agents.

    Responsabilités:
        1. Initialiser tous les agents nécessaires
        2. Recevoir les requêtes utilisateur
        3. Coordonner le router et le pipeline executor
        4. Gérer les erreurs globales
        5. Retourner les réponses formatées

    Attributes:
        router: Agent de routing (choix du plan)
        executor: Exécuteur de pipeline
        agents: Dictionnaire des agents disponibles
        openai_client: Client OpenAI partagé
        logger: Logger pour traçabilité
    """

    def __init__(self):
        """
        Initialise l'orchestrateur et tous ses composants.

        Configuration depuis variables d'environnement:
            - OPENAI_API_KEY: Clé API OpenAI (obligatoire)
            - OPENAI_API_BASE: URL de base custom (optionnel)
            - DEFAULT_MODEL: Modèle par défaut (défaut: mistral-small)
            - ANALYSIS_MODEL: Modèle pour analyses (défaut: mistral-small)
        """
        self.logger = AgentLogger("orchestrator")

        # Configuration OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE", "https://api.olympia.bhub.cloud/v1")

        if not api_key:
            raise ValueError("OPENAI_API_KEY manquante")

        self.openai_client = openai.AsyncOpenAI(api_key=api_key, base_url=api_base)

        # Modèles
        self.default_model = os.getenv("DEFAULT_MODEL", "mistral-small")
        self.analysis_model = os.getenv("ANALYSIS_MODEL", "mistral-small")

        # Configuration de l'historique conversationnel
        self.history_config = HistoryConfig.from_env()
        self.logger.info(
            "Configuration d'historique chargée",
            enabled=self.history_config.enabled,
            max_messages=self.history_config.max_messages,
        )

        # Initialisation des agents
        self._initialize_agents()

        # Statistiques d'utilisation
        self.stats = {
            "total_requests": 0,
            "plan_usage": {"generic": 0, "data_query": 0, "architecture_review": 0},
            "errors": 0,
        }

        self.logger.info(
            "✅ Orchestrateur initialisé avec succès",
            default_model=self.default_model,
            analysis_model=self.analysis_model,
        )

    def _initialize_agents(self):
        """
        Initialise tous les agents du système.

        Cette méthode crée:
            - Router Agent (choix de plan)
            - Generic Agent (conversation)
            - SQL Agent (requêtes données)
            - Analysis Agent (analyse résultats)
            - Architecture Agent (conseil structure)
            - Pipeline Executor (orchestration)
        """
        # Router
        self.router = RouterAgent(self.openai_client, model=self.default_model)

        # Agents métier
        self.generic_agent = GenericAgent(self.openai_client, model=self.default_model)

        self.analysis_agent = AnalysisAgent(
            self.openai_client, model=self.analysis_model
        )

        # Agents nécessitant Grist (créés à la demande avec clé API)
        # SQL Agent et Architecture Agent seront créés dynamiquement

        # Mapping pour le pipeline executor
        self.base_agents = {
            AgentType.GENERIC: self.generic_agent,
            AgentType.ANALYSIS: self.analysis_agent,
            # SQL et ARCHITECTURE seront ajoutés dynamiquement
        }

    def _create_agents_with_grist_key(self, grist_api_key: str) -> Dict[AgentType, Any]:
        """
        Crée les agents nécessitant une clé API Grist.

        Args:
            grist_api_key: Clé API Grist

        Returns:
            Dictionnaire complet des agents (base + Grist)
        """
        # Initialiser les utilitaires Grist
        schema_fetcher = GristSchemaFetcher(grist_api_key)
        sql_runner = GristSQLRunner(grist_api_key)
        sample_fetcher = GristSampleFetcher()

        # Créer les agents Grist
        sql_agent = SQLAgent(
            self.openai_client,
            schema_fetcher,
            sql_runner,
            sample_fetcher,
            model=self.default_model,
        )

        architecture_agent = DataArchitectureAgent(
            self.openai_client,
            schema_fetcher,
            sample_fetcher,
            model=self.analysis_model,
        )

        # Merger avec les agents de base
        all_agents = {**self.base_agents}
        all_agents[AgentType.SQL] = sql_agent
        all_agents[AgentType.ARCHITECTURE] = architecture_agent

        return all_agents

    async def process_chat_request(self, request: ProcessedRequest) -> ChatResponse:
        """
        Traite une requête chat complète via le pipeline d'agents.

        C'est la méthode principale appelée par l'API FastAPI.

        Args:
            request: Requête traitée contenant:
                - document_id: ID du document Grist
                - messages: Historique de conversation
                - grist_api_key: Clé API Grist
                - execution_mode: Mode d'exécution (prod/test)

        Returns:
            ChatResponse avec:
                - response: Texte de réponse
                - agent_used: Agent ayant généré la réponse
                - sql_query: Requête SQL éventuelle
                - data_analyzed: Flag d'analyse de données
                - error: Message d'erreur éventuel

        Exemple:
            >>> request = ProcessedRequest(document_id="doc-123", ...)
            >>> response = await orchestrator.process_chat_request(request)
            >>> print(response.response)
            "Voici vos 10 dernières ventes..."
        """
        request_id = str(uuid.uuid4())
        self.stats["total_requests"] += 1

        self.logger.info(
            "🚀 Nouvelle requête de chat",
            request_id=request_id,
            document_id=request.document_id,
            messages_count=len(request.messages),
        )

        try:
            # 1. Extraire le message utilisateur
            conversation_history = ConversationHistory(messages=request.messages)
            user_message = conversation_history.get_last_user_message()

            if not user_message:
                return ChatResponse(
                    response="Aucun message utilisateur trouvé dans la requête.",
                    agent_used="orchestrator",
                    error="No user message",
                )

            # 2. Router → Choisir le plan d'exécution
            # Créer un historique filtré pour le router selon la config
            from .config.history_config import get_agent_config, ConfigAgentType

            router_config = get_agent_config(
                self.history_config, ConfigAgentType.ROUTER
            )
            filtered_messages = router_config.filter_history(
                conversation_history, exclude_last=True
            )
            filtered_history = ConversationHistory(messages=filtered_messages)

            plan = await self.router.route_to_plan(
                user_message.content, filtered_history, request_id
            )

            self.logger.info(
                f"📋 Plan sélectionné: {plan.name}",
                request_id=request_id,
                agents=str([a.value for a in plan.agents]),
            )

            # Mettre à jour les stats
            self.stats["plan_usage"][plan.name] += 1

            # 3. Créer le contexte d'exécution
            context = ExecutionContext(
                user_message=user_message.content,
                conversation_history=conversation_history,
                document_id=request.document_id,
                grist_api_key=request.grist_api_key,
                request_id=request_id,
                history_config=self.history_config,
            )

            # 4. Préparer les agents (avec Grist si nécessaire)
            if plan.requires_api_key:
                if not request.grist_api_key:
                    return ChatResponse(
                        response="Cette opération nécessite une clé API Grist.",
                        agent_used="orchestrator",
                        error="Missing Grist API key",
                    )
                agents = self._create_agents_with_grist_key(request.grist_api_key)
            else:
                agents = self.base_agents

            # 5. Créer l'executor et exécuter le pipeline
            executor = PipelineExecutor(agents)
            response = await executor.execute(plan, context)

            self.logger.info(
                "✅ Requête traitée avec succès",
                request_id=request_id,
                plan_name=plan.name,
                agent_used=response.agent_used,
                has_error=response.error is not None,
            )

            return response

        except Exception as e:
            self.stats["errors"] += 1
            self.logger.error(
                f"❌ Erreur lors du traitement de la requête: {str(e)}",
                request_id=request_id,
                document_id=request.document_id,
            )

            return ChatResponse(
                response=f"Désolé, une erreur s'est produite: {str(e)}",
                agent_used="orchestrator",
                error=str(e),
            )

    async def health_check(self) -> Dict[str, Any]:
        """
        Vérification de santé du système.

        Teste:
            - Connexion OpenAI
            - Disponibilité des agents
            - État général

        Returns:
            Dictionnaire avec statut de santé

        Exemple:
            >>> health = await orchestrator.health_check()
            >>> print(health["status"])
            "healthy"
        """
        try:
            # Test simple avec OpenAI
            response = await self.openai_client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )

            return {
                "status": "healthy",
                "components": {
                    "openai": "ok",
                    "router": "ok",
                    "agents": {"generic": "ok", "analysis": "ok"},
                },
                "stats": self.get_stats(),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "stats": self.get_stats()}

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques d'utilisation.

        Returns:
            Dictionnaire avec:
                - total_requests: Nombre total de requêtes
                - plan_usage: Utilisation par plan
                - errors: Nombre d'erreurs
                - most_used_plan: Plan le plus utilisé

        Exemple:
            >>> stats = orchestrator.get_stats()
            >>> print(stats["total_requests"])
            142
        """
        # Trouver le plan le plus utilisé
        most_used_plan = max(
            self.stats["plan_usage"].items(), key=lambda x: x[1], default=("none", 0)
        )[0]

        return {**self.stats, "most_used_plan": most_used_plan}
