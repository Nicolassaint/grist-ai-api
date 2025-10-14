"""
Plans d'exécution prédéfinis pour le pipeline d'agents.

Un plan définit la séquence d'agents à exécuter pour répondre à une intention utilisateur.

Exemples de plans:
    - "generic": Conversation simple → [Generic Agent]
    - "data_query": Requête SQL → [SQL Agent, Analysis Agent]
    - "architecture_review": Analyse structure → [Architecture Agent]

Comment ajouter un nouveau plan:
    1. Définir le plan dans AVAILABLE_PLANS
    2. Ajouter la logique de routing dans router_agent.py
    3. C'est tout! Le pipeline s'occupe du reste.
"""

from dataclasses import dataclass
from typing import List
from enum import Enum


class AgentType(str, Enum):
    """Types d'agents disponibles dans le système"""
    GENERIC = "generic"
    SQL = "sql"
    ANALYSIS = "analysis"
    ARCHITECTURE = "architecture"


@dataclass
class ExecutionPlan:
    """
    Plan d'exécution définissant la séquence d'agents.

    Attributes:
        name: Nom unique du plan (ex: "data_query")
        agents: Liste ordonnée des agents à exécuter
        description: Description lisible du plan
        requires_api_key: Si True, nécessite une clé API Grist

    Exemple:
        >>> plan = ExecutionPlan(
        ...     name="data_query",
        ...     agents=[AgentType.SQL, AgentType.ANALYSIS],
        ...     description="Requête de données avec analyse"
        ... )
    """
    name: str
    agents: List[AgentType]
    description: str
    requires_api_key: bool = False

    def __repr__(self) -> str:
        agent_names = " → ".join([a.value for a in self.agents])
        return f"Plan({self.name}: {agent_names})"


# ==================== PLANS DISPONIBLES ====================

AVAILABLE_PLANS = {
    # Plan 1: Conversation générale
    "generic": ExecutionPlan(
        name="generic",
        agents=[AgentType.GENERIC],
        description="Conversation générale, questions sur Grist, aide",
        requires_api_key=False
    ),

    # Plan 2: Requête de données simple
    "data_query": ExecutionPlan(
        name="data_query",
        agents=[AgentType.SQL, AgentType.ANALYSIS],
        description="Requête SQL + analyse des résultats",
        requires_api_key=True
    ),

    # Plan 3: Analyse d'architecture seule
    "architecture_review": ExecutionPlan(
        name="architecture_review",
        agents=[AgentType.ARCHITECTURE],
        description="Analyse de la structure des données (normalisation, relations)",
        requires_api_key=True
    ),
}


def get_plan(name: str) -> ExecutionPlan:
    """
    Récupère un plan par son nom.

    Args:
        name: Nom du plan (ex: "data_query")

    Returns:
        Le plan correspondant

    Raises:
        KeyError: Si le plan n'existe pas

    Exemple:
        >>> plan = get_plan("data_query")
        >>> print(plan.agents)
        [AgentType.SQL, AgentType.ANALYSIS]
    """
    if name not in AVAILABLE_PLANS:
        raise KeyError(
            f"Plan '{name}' inconnu. Plans disponibles: {list(AVAILABLE_PLANS.keys())}"
        )
    return AVAILABLE_PLANS[name]


def list_plans() -> List[str]:
    """
    Liste tous les plans disponibles.

    Returns:
        Liste des noms de plans

    Exemple:
        >>> list_plans()
        ['generic', 'data_query', 'architecture_review', 'full_analysis']
    """
    return list(AVAILABLE_PLANS.keys())
