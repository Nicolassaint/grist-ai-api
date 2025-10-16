"""
Contexte d'exécution du pipeline d'agents.

Le contexte circule entre les agents et accumule les résultats intermédiaires.
Chaque agent peut lire le contexte et l'enrichir avec ses propres résultats.

Exemple de flux:
    1. User Message → Context créé
    2. SQL Agent → ajoute sql_query et sql_results au contexte
    3. Analysis Agent → lit sql_results, ajoute analysis au contexte
    4. Context → transformé en ChatResponse finale
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from ..models.message import ConversationHistory, Message
from ..models.architecture import ArchitectureAnalysis
from ..config.history_config import HistoryConfig, default_history_config


@dataclass
class ExecutionContext:
    """
    Contexte partagé entre tous les agents du pipeline.

    Attributs de base (toujours présents):
        user_message: Le dernier message de l'utilisateur
        conversation_history: L'historique complet de la conversation
        document_id: ID du document Grist
        grist_api_key: Clé API pour accéder à Grist
        request_id: ID unique de la requête (pour logging)

    Résultats intermédiaires (ajoutés par les agents):
        schemas: Schémas des tables Grist (ajouté par Architecture ou SQL)
        sql_query: Requête SQL générée (ajouté par SQL Agent)
        sql_results: Résultats de la requête SQL (ajouté par SQL Agent)
        analysis: Analyse textuelle des résultats (ajouté par Analysis Agent)
        architecture_analysis: Analyse complète de structure (ajouté par Architecture Agent)
        response_text: Réponse finale pour l'utilisateur (ajouté par n'importe quel agent)

    Métadonnées:
        agent_used: Nom du dernier agent ayant contribué
        data_analyzed: Flag indiquant si des données ont été analysées
        error: Message d'erreur éventuel
    """

    # Données d'entrée (toujours présentes)
    user_message: str
    conversation_history: ConversationHistory
    document_id: str
    grist_api_key: Optional[str]
    request_id: str
    history_config: HistoryConfig = field(default_factory=lambda: default_history_config)

    # Résultats intermédiaires (enrichis par les agents)
    schemas: Optional[Dict[str, Any]] = None
    sql_query: Optional[str] = None
    sql_results: Optional[Dict[str, Any]] = None
    analysis: Optional[str] = None
    architecture_analysis: Optional[ArchitectureAnalysis] = None
    response_text: Optional[str] = None

    # Métadonnées
    agent_used: str = "none"
    data_analyzed: bool = False
    error: Optional[str] = None

    # Historique d'exécution (pour debugging)
    execution_trace: List[str] = field(default_factory=list)

    def has(self, key: str) -> bool:
        """
        Vérifie si une donnée est disponible dans le contexte.

        Args:
            key: Nom de l'attribut à vérifier

        Returns:
            True si l'attribut existe et n'est pas None

        Exemple:
            >>> context.has("sql_results")
            True  # Si SQL Agent a déjà ajouté les résultats
        """
        value = getattr(self, key, None)
        return value is not None

    def add_trace(self, agent_name: str, action: str):
        """
        Ajoute une entrée dans l'historique d'exécution.

        Args:
            agent_name: Nom de l'agent
            action: Description de l'action effectuée

        Exemple:
            >>> context.add_trace("sql_agent", "Executed SQL query")
        """
        self.execution_trace.append(f"{agent_name}: {action}")

    def set_response(self, text: str, agent_name: str):
        """
        Définit la réponse finale et l'agent responsable.

        Args:
            text: Texte de la réponse
            agent_name: Nom de l'agent ayant généré la réponse
        """
        self.response_text = text
        self.agent_used = agent_name
        self.add_trace(agent_name, f"Set response ({len(text)} chars)")

    def set_error(self, error_message: str, agent_name: str):
        """
        Enregistre une erreur dans le contexte.

        Args:
            error_message: Message d'erreur
            agent_name: Nom de l'agent où l'erreur s'est produite
        """
        self.error = error_message
        self.agent_used = agent_name
        self.add_trace(agent_name, f"Error: {error_message}")

    def get_filtered_history(self, exclude_last: bool = None) -> List[Message]:
        """
        Retourne l'historique filtré selon la configuration.

        Cette méthode est un helper pour les agents, qui peuvent simplement
        appeler context.get_filtered_history() au lieu de gérer manuellement
        la configuration d'historique.

        Args:
            exclude_last: Override pour exclure le dernier message (optionnel)

        Returns:
            Liste de messages filtrés selon history_config

        Exemple:
            >>> # Dans un agent
            >>> filtered_messages = context.get_filtered_history()
            >>> for msg in filtered_messages:
            ...     messages.append({"role": msg.role.value, "content": msg.content})
        """
        return self.history_config.filter_history(
            self.conversation_history,
            exclude_last=exclude_last
        )

    def format_history_for_prompt(self, exclude_last: bool = None) -> List[dict]:
        """
        Formate l'historique pour injection directe dans un prompt LLM.

        Args:
            exclude_last: Override pour exclure le dernier message (optionnel)

        Returns:
            Liste de dictionnaires au format {"role": "...", "content": "..."}

        Exemple:
            >>> # Dans un agent
            >>> messages = [
            ...     {"role": "system", "content": system_prompt},
            ...     *context.format_history_for_prompt(),
            ...     {"role": "user", "content": context.user_message}
            ... ]
            >>> response = await client.chat.completions.create(model="gpt-4", messages=messages)
        """
        return self.history_config.format_for_prompt(
            self.conversation_history,
            exclude_last=exclude_last
        )

    def format_history_as_context(self, max_chars_per_message: Optional[int] = None) -> str:
        """
        Formate l'historique en chaîne de caractères pour contexte textuel.

        Args:
            max_chars_per_message: Limite de caractères par message (optionnel)

        Returns:
            Chaîne formatée du contexte conversationnel

        Exemple:
            >>> # Dans un agent
            >>> context_string = context.format_history_as_context(max_chars_per_message=100)
            >>> prompt = f"Schémas: {schemas}\n\n{context_string}\n\nQuestion: {context.user_message}"
        """
        return self.history_config.format_as_context_string(
            self.conversation_history,
            max_chars_per_message=max_chars_per_message
        )
