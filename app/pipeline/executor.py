"""
Exécuteur de pipeline d'agents.

Le PipelineExecutor prend un plan et un contexte, puis exécute séquentiellement
les agents définis dans le plan. Chaque agent enrichit le contexte pour l'agent suivant.

Architecture:
    1. Router → Choisit un Plan
    2. PipelineExecutor → Exécute les agents du plan
    3. Agents → Lisent/enrichissent le contexte
    4. PipelineExecutor → Transforme le contexte en réponse

Exemple de flux:
    User: "Montre-moi les ventes"
    → Router choisit plan "data_query" [SQL, Analysis]
    → Executor:
        - SQL Agent: ajoute sql_query + sql_results au contexte
        - Analysis Agent: lit sql_results, ajoute analysis au contexte
    → Executor construit la réponse finale

Gestion d'erreurs:
    - Si un agent échoue, le pipeline continue avec les agents suivants
    - Le contexte garde une trace de toutes les erreurs
    - La réponse finale inclut les erreurs rencontrées
"""

from typing import Dict, Any, Optional
import time
from .context import ExecutionContext
from .plans import ExecutionPlan, AgentType
from ..models.request import ChatResponse
from ..models.message import ConversationHistory
from ..config.history_config import get_agent_config, AgentType as ConfigAgentType
from ..utils.logging import AgentLogger


class PipelineExecutor:
    """
    Exécuteur séquentiel de pipeline d'agents.

    Le PipelineExecutor:
    - Prend un plan d'exécution et un contexte
    - Exécute chaque agent dans l'ordre
    - Gère les erreurs et le logging
    - Retourne une ChatResponse finale

    Attributes:
        agents: Dictionnaire {AgentType: Agent instance}
        logger: Logger pour tracer l'exécution
    """

    def __init__(self, agents: Dict[AgentType, Any]):
        """
        Initialise l'exécuteur avec les agents disponibles.

        Args:
            agents: Mapping AgentType → instance d'agent
                Exemple: {
                    AgentType.SQL: sql_agent_instance,
                    AgentType.ANALYSIS: analysis_agent_instance,
                    ...
                }
        """
        self.agents = agents
        self.logger = AgentLogger("pipeline_executor")

    async def execute(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext
    ) -> ChatResponse:
        """
        Exécute le pipeline d'agents défini par le plan.

        Args:
            plan: Plan d'exécution (séquence d'agents)
            context: Contexte initial avec les données utilisateur

        Returns:
            ChatResponse avec la réponse finale

        Exemple:
            >>> plan = get_plan("data_query")
            >>> context = ExecutionContext(user_message="...", ...)
            >>> response = await executor.execute(plan, context)
        """
        start_time = time.time()

        self.logger.info(
            f"🚀 Début exécution pipeline",
            request_id=context.request_id,
            plan_name=plan.name,
            agents_count=len(plan.agents)
        )

        # Vérifications préalables
        if plan.requires_api_key and not context.grist_api_key:
            context.set_error(
                "Cette opération nécessite une clé API Grist",
                "pipeline_executor"
            )
            return self._build_response(context, plan, time.time() - start_time)

        # Exécution séquentielle des agents
        for agent_type in plan.agents:
            try:
                await self._execute_agent(agent_type, context)
            except Exception as e:
                self.logger.error(
                    f"Erreur lors de l'exécution de {agent_type.value}: {str(e)}",
                    request_id=context.request_id,
                    agent_type=agent_type.value
                )
                # On continue avec les agents suivants même en cas d'erreur
                context.add_trace(agent_type.value, f"Error: {str(e)}")

        execution_time = time.time() - start_time

        self.logger.info(
            f"✅ Pipeline terminé",
            request_id=context.request_id,
            plan_name=plan.name,
            execution_time=f"{execution_time:.2f}s",
            agents_executed=len(context.execution_trace)
        )

        return self._build_response(context, plan, execution_time)

    async def _execute_agent(
        self,
        agent_type: AgentType,
        context: ExecutionContext
    ):
        """
        Exécute un agent spécifique et enrichit le contexte.

        Args:
            agent_type: Type d'agent à exécuter
            context: Contexte (sera modifié in-place)
        """
        if agent_type not in self.agents:
            self.logger.warning(
                f"Agent {agent_type.value} non disponible",
                request_id=context.request_id
            )
            return

        agent = self.agents[agent_type]

        self.logger.info(
            f"▶️  Exécution agent {agent_type.value}",
            request_id=context.request_id
        )

        # Exécution selon le type d'agent
        if agent_type == AgentType.GENERIC:
            await self._execute_generic_agent(agent, context)

        elif agent_type == AgentType.SQL:
            await self._execute_sql_agent(agent, context)

        elif agent_type == AgentType.ANALYSIS:
            await self._execute_analysis_agent(agent, context)

        elif agent_type == AgentType.ARCHITECTURE:
            await self._execute_architecture_agent(agent, context)

    def _get_filtered_history(
        self,
        context: ExecutionContext,
        agent_type: Optional[ConfigAgentType] = None
    ) -> ConversationHistory:
        """
        Crée un ConversationHistory filtré selon la configuration.

        Au lieu de passer l'historique complet aux agents, on leur passe
        un historique pré-filtré selon la configuration. Les agents n'ont
        plus besoin de gérer le filtrage eux-mêmes.

        Si agent_type est fourni, utilise la configuration spécifique pour cet agent.

        Args:
            context: Contexte d'exécution contenant history_config
            agent_type: Type d'agent pour config spécifique (optionnel)

        Returns:
            Nouveau ConversationHistory avec messages filtrés
        """
        # Obtenir la config spécifique à l'agent si fournie
        if agent_type:
            agent_config = get_agent_config(context.history_config, agent_type)
            filtered_messages = agent_config.filter_history(
                context.conversation_history,
                exclude_last=True
            )
        else:
            filtered_messages = context.get_filtered_history(exclude_last=True)

        return ConversationHistory(messages=filtered_messages)

    async def _execute_generic_agent(self, agent, context: ExecutionContext):
        """Exécute l'agent générique"""
        # Passer un historique pré-filtré à l'agent avec config spécifique generic
        filtered_history = self._get_filtered_history(context, ConfigAgentType.GENERIC)

        response = await agent.process_message(
            context.user_message,
            filtered_history,
            context.request_id
        )
        context.set_response(response, "generic")

    async def _execute_sql_agent(self, agent, context: ExecutionContext):
        """Exécute l'agent SQL"""
        # Passer un historique pré-filtré à l'agent avec config spécifique SQL
        filtered_history = self._get_filtered_history(context, ConfigAgentType.SQL)

        response, sql_query, sql_results = await agent.process_message(
            context.user_message,
            filtered_history,
            context.document_id,
            context.request_id
        )

        # Enrichir le contexte
        context.sql_query = sql_query
        context.sql_results = sql_results
        context.data_analyzed = True

        # Ne set la réponse que si pas d'agent suivant qui va l'utiliser
        # (Analysis agent va override si présent)
        if not context.has("analysis"):
            context.set_response(response, "sql")

        context.add_trace("sql", f"Executed query, got {sql_results.get('row_count', 0) if sql_results else 0} rows")

    async def _execute_analysis_agent(self, agent, context: ExecutionContext):
        """Exécute l'agent d'analyse"""
        # Analysis agent nécessite les résultats SQL
        if not context.has("sql_results"):
            self.logger.warning(
                "Analysis agent nécessite des résultats SQL",
                request_id=context.request_id
            )
            return

        # Passer un historique pré-filtré à l'agent avec config spécifique ANALYSIS
        filtered_history = self._get_filtered_history(context, ConfigAgentType.ANALYSIS)

        response = await agent.process_message(
            context.user_message,
            filtered_history,
            context.sql_query,
            context.sql_results,
            context.request_id
        )

        context.analysis = response
        context.set_response(response, "analysis")
        context.add_trace("analysis", f"Generated analysis ({len(response)} chars)")

    async def _execute_architecture_agent(self, agent, context: ExecutionContext):
        """Exécute l'agent d'architecture"""
        analysis = await agent.analyze_document_structure(
            context.document_id,
            context.user_message,
            context.request_id
        )

        context.architecture_analysis = analysis
        context.data_analyzed = True

        # Formater la réponse
        response_text = self._format_architecture_response(analysis)
        context.set_response(response_text, "architecture")
        context.add_trace("architecture", f"Analyzed {analysis.metrics.total_tables} tables")

    def _format_architecture_response(self, analysis) -> str:
        """Retourne les recommandations brutes sans aucun formatage"""
        if not analysis.recommendations:
            return "Votre structure semble correcte pour l'instant."

        # Retourner les recommandations exactement comme le LLM les a générées
        return "\n".join(analysis.recommendations)

    def _build_response(
        self,
        context: ExecutionContext,
        plan: ExecutionPlan,
        execution_time: float
    ) -> ChatResponse:
        """
        Construit la réponse finale à partir du contexte.

        Args:
            context: Contexte enrichi par les agents
            plan: Plan exécuté
            execution_time: Temps d'exécution total

        Returns:
            ChatResponse prête à être envoyée à l'utilisateur
        """
        # Réponse par défaut si aucun agent n'a répondu
        if not context.response_text:
            context.response_text = "Désolé, je n'ai pas pu générer de réponse."
            context.agent_used = "none"

        return ChatResponse(
            response=context.response_text,
            agent_used=context.agent_used,
            sql_query=context.sql_query,
            data_analyzed=context.data_analyzed,
            error=context.error
        )
