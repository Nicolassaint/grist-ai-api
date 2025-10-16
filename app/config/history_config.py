"""
═══════════════════════════════════════════════════════════════════════════════
HISTORY CONFIGURATION MODULE - Gestion centralisée de l'historique conversationnel
═══════════════════════════════════════════════════════════════════════════════

RÔLE:
    Module centralisé pour gérer comment l'historique de conversation est utilisé
    par les différents agents du système.

FEATURES:
    ✅ Activer/désactiver l'historique globalement
    ✅ Contrôler le nombre de messages injectés dans les prompts
    ✅ Filtrer par type de message (user/assistant/system)
    ✅ Configuration via variables d'environnement ou code
    ✅ Configurations spécifiques par agent (optionnel)

UTILISATION:
    >>> config = HistoryConfig(enabled=True, max_messages=5)
    >>> filtered = config.filter_history(conversation_history)
    >>> messages = [{"role": msg.role.value, "content": msg.content} for msg in filtered]

VARIABLES D'ENVIRONNEMENT:
    - HISTORY_ENABLED: "true" ou "false" (défaut: true)
    - HISTORY_MAX_MESSAGES: Nombre max de messages (défaut: 5)
    - HISTORY_INCLUDE_SYSTEM: "true" ou "false" (défaut: false)

═══════════════════════════════════════════════════════════════════════════════
"""

import os
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum
from ..models.message import ConversationHistory, Message, MessageRole
from ..pipeline.plans import AgentType


# Extension de AgentType pour inclure ROUTER (utilisé seulement pour la config)
class ConfigAgentType(str, Enum):
    """Types d'agents pour configuration (étend AgentType du pipeline)"""

    ROUTER = "router"
    GENERIC = "generic"
    SQL = "sql"
    ANALYSIS = "analysis"
    ARCHITECTURE = "architecture"


@dataclass
class HistoryConfig:
    """
    Configuration de l'historique conversationnel.

    Cette classe centralise tous les paramètres contrôlant comment l'historique
    de conversation est utilisé dans les prompts des agents.

    Attributes:
        enabled: Active/désactive l'injection d'historique (défaut: True)
        max_messages: Nombre maximum de messages d'historique (défaut: 5)
        include_system_messages: Inclure les messages système (défaut: False)
        exclude_current: Exclure le message actuel du comptage (défaut: True)

    Examples:
        >>> # Configuration par défaut
        >>> config = HistoryConfig()
        >>>
        >>> # Configuration personnalisée
        >>> config = HistoryConfig(enabled=True, max_messages=10)
        >>>
        >>> # Désactiver l'historique
        >>> config = HistoryConfig(enabled=False)
    """

    enabled: bool = True
    max_messages: int = 5
    include_system_messages: bool = False
    exclude_current: bool = True

    def filter_history(
        self, conversation_history: ConversationHistory, exclude_last: bool = None
    ) -> List[Message]:
        """
        Filtre l'historique selon la configuration.

        Args:
            conversation_history: L'historique complet de conversation
            exclude_last: Override pour exclude_current (optionnel)

        Returns:
            Liste de messages filtrés selon la configuration

        Examples:
            >>> config = HistoryConfig(enabled=True, max_messages=3)
            >>> messages = config.filter_history(conversation_history)
            >>> print(len(messages))  # Maximum 3 messages
        """
        # Si l'historique est désactivé, retourner liste vide
        if not self.enabled:
            return []

        # Récupérer tous les messages
        all_messages = conversation_history.messages

        # Filtrer les messages système si nécessaire
        if not self.include_system_messages:
            all_messages = [
                msg for msg in all_messages if msg.role != MessageRole.SYSTEM
            ]

        # Décider si on exclut le dernier message
        should_exclude_last = (
            exclude_last if exclude_last is not None else self.exclude_current
        )

        # Si on doit exclure le dernier message (généralement le message utilisateur actuel)
        if should_exclude_last and len(all_messages) > 0:
            all_messages = all_messages[:-1]

        # Limiter au nombre max de messages (les plus récents)
        if self.max_messages > 0:
            all_messages = all_messages[-self.max_messages :]

        return all_messages

    def get_message_count(self, conversation_history: ConversationHistory) -> int:
        """
        Retourne le nombre de messages qui seront injectés.

        Args:
            conversation_history: L'historique de conversation

        Returns:
            Nombre de messages après filtrage
        """
        return len(self.filter_history(conversation_history))

    def format_for_prompt(
        self, conversation_history: ConversationHistory, exclude_last: bool = None
    ) -> List[dict]:
        """
        Formate l'historique filtré pour injection dans un prompt LLM.

        Args:
            conversation_history: L'historique de conversation
            exclude_last: Override pour exclude_current

        Returns:
            Liste de dictionnaires au format {"role": "user", "content": "..."}

        Examples:
            >>> config = HistoryConfig(max_messages=3)
            >>> messages = config.format_for_prompt(conversation_history)
            >>> # Peut être directement utilisé dans un prompt OpenAI
            >>> response = await client.chat.completions.create(
            ...     model="gpt-4",
            ...     messages=[{"role": "system", "content": "..."}, *messages]
            ... )
        """
        filtered_messages = self.filter_history(conversation_history, exclude_last)

        return [
            {"role": msg.role.value, "content": msg.content}
            for msg in filtered_messages
        ]

    def format_as_context_string(
        self,
        conversation_history: ConversationHistory,
        max_chars_per_message: Optional[int] = None,
    ) -> str:
        """
        Formate l'historique en une chaîne de caractères pour inclusion textuelle.

        Utile pour ajouter du contexte dans un prompt sans structure de messages.

        Args:
            conversation_history: L'historique de conversation
            max_chars_per_message: Limite de caractères par message (optionnel)

        Returns:
            Chaîne de caractères formatée

        Examples:
            >>> config = HistoryConfig(max_messages=3)
            >>> context = config.format_as_context_string(conversation_history, max_chars_per_message=100)
            >>> print(context)
            Contexte récent:
            - user: Comment analyser mes ventes?
            - assistant: Je vais générer une requête SQL...
        """
        if not self.enabled:
            return "Aucun contexte précédent"

        filtered_messages = self.filter_history(conversation_history)

        if not filtered_messages:
            return "Aucun contexte précédent"

        context_lines = ["Contexte récent:"]

        for msg in filtered_messages:
            content = msg.content
            if max_chars_per_message and len(content) > max_chars_per_message:
                content = content[:max_chars_per_message] + "..."
            context_lines.append(f"- {msg.role.value}: {content}")

        return "\n".join(context_lines)

    @classmethod
    def from_env(cls) -> "HistoryConfig":
        """
        Crée une configuration depuis les variables d'environnement.

        Variables supportées:
            - HISTORY_ENABLED: "true" ou "false"
            - HISTORY_MAX_MESSAGES: nombre entier
            - HISTORY_INCLUDE_SYSTEM: "true" ou "false"

        Returns:
            Instance de HistoryConfig configurée

        Examples:
            >>> # Dans le code
            >>> config = HistoryConfig.from_env()
            >>>
            >>> # Dans .env
            >>> # HISTORY_ENABLED=true
            >>> # HISTORY_MAX_MESSAGES=10
        """
        enabled = os.getenv("HISTORY_ENABLED", "true").lower() == "true"
        max_messages = int(os.getenv("HISTORY_MAX_MESSAGES", "5"))
        include_system = os.getenv("HISTORY_INCLUDE_SYSTEM", "false").lower() == "true"

        return cls(
            enabled=enabled,
            max_messages=max_messages,
            include_system_messages=include_system,
        )

    def with_overrides(
        self,
        enabled: Optional[bool] = None,
        max_messages: Optional[int] = None,
        include_system_messages: Optional[bool] = None,
    ) -> "HistoryConfig":
        """
        Crée une nouvelle config avec des overrides spécifiques.

        Utile pour créer des configurations par agent.

        Args:
            enabled: Override pour enabled
            max_messages: Override pour max_messages
            include_system_messages: Override pour include_system_messages

        Returns:
            Nouvelle instance de HistoryConfig

        Examples:
            >>> # Config par défaut
            >>> default_config = HistoryConfig(max_messages=5)
            >>>
            >>> # Config spécifique pour router (moins de messages)
            >>> router_config = default_config.with_overrides(max_messages=3)
            >>>
            >>> # Config pour SQL agent (plus de messages)
            >>> sql_config = default_config.with_overrides(max_messages=10)
        """
        return HistoryConfig(
            enabled=enabled if enabled is not None else self.enabled,
            max_messages=max_messages
            if max_messages is not None
            else self.max_messages,
            include_system_messages=include_system_messages
            if include_system_messages is not None
            else self.include_system_messages,
            exclude_current=self.exclude_current,
        )


# Configuration par défaut pour chaque agent
AGENT_HISTORY_CONFIGS = {
    ConfigAgentType.ROUTER: {
        "max_messages": 3
    },  # Router n'a besoin que du contexte immédiat
    ConfigAgentType.GENERIC: {
        "max_messages": 5
    },  # Generic conversation bénéficie de plus d'historique
    ConfigAgentType.SQL: {
        "max_messages": 3
    },  # SQL se concentre sur la requête actuelle
    ConfigAgentType.ANALYSIS: {
        "max_messages": 5
    },  # Analysis peut bénéficier de contexte
    ConfigAgentType.ARCHITECTURE: {
        "max_messages": 2
    },  # Architecture se concentre sur structure actuelle
}


def get_agent_config(
    base_config: HistoryConfig, agent_type: ConfigAgentType
) -> HistoryConfig:
    """
    Obtient une configuration spécifique pour un type d'agent.

    Args:
        base_config: Configuration de base
        agent_type: Type d'agent

    Returns:
        Configuration adaptée pour l'agent

    Examples:
        >>> base = HistoryConfig.from_env()
        >>> router_config = get_agent_config(base, AgentType.ROUTER)
        >>> print(router_config.max_messages)  # 3 (config spécifique router)
    """
    overrides = AGENT_HISTORY_CONFIGS.get(agent_type, {})
    return base_config.with_overrides(**overrides)


# Instance par défaut (chargée depuis env)
default_history_config = HistoryConfig.from_env()
