"""
Utilitaires pour formater l'historique de conversation de manière standardisée
"""
from typing import List, Tuple
from ..models.message import ConversationHistory, MessageRole


def format_conversation_history(
    conversation_history: ConversationHistory, max_pairs: int = 2
) -> str:
    """
    Formate l'historique de conversation en paires user/assistant complètes.

    Args:
        conversation_history: Historique complet
        max_pairs: Nombre maximum de paires à inclure (1 paire = 1 user + 1 assistant)

    Returns:
        String formatée avec l'historique des paires complètes

    Exemple:
        user: Bonjour
        assistant: Salut ! Comment puis-je vous aider ?
        user: Quel est l'âge moyen ?
        assistant: L'âge moyen dans votre dataset est de 35 ans.
    """
    if not conversation_history.messages or len(conversation_history.messages) == 0:
        return "Aucun historique de conversation"

    # Extraction des paires complètes (user + assistant)
    complete_pairs = extract_complete_pairs(conversation_history.messages)

    # Limitation au nombre de paires demandé (plus récentes en premier)
    recent_pairs = (
        complete_pairs[-max_pairs:]
        if len(complete_pairs) > max_pairs
        else complete_pairs
    )

    if not recent_pairs:
        return "Aucun historique de conversation (paires incomplètes)"

    # Formatage en texte
    formatted_lines = []
    for user_msg, assistant_msg in recent_pairs:
        formatted_lines.append(f"user: {user_msg.content}")
        formatted_lines.append(f"assistant: {assistant_msg.content}")

    return "\n".join(formatted_lines)


def extract_complete_pairs(messages: List) -> List[Tuple]:
    """
    Extrait les paires complètes user/assistant de l'historique.

    Une paire complète = 1 message user suivi de 1 message assistant.
    Les messages orphelins (sans réponse) sont ignorés.

    Args:
        messages: Liste des messages de l'historique

    Returns:
        Liste de tuples (user_message, assistant_message)
    """
    pairs = []
    i = 0

    while i < len(messages) - 1:  # -1 car on cherche des paires
        current_msg = messages[i]
        next_msg = messages[i + 1]

        # Vérification qu'on a bien une paire user → assistant
        if (
            current_msg.role == MessageRole.USER
            and next_msg.role == MessageRole.ASSISTANT
        ):
            pairs.append((current_msg, next_msg))
            i += 2  # Passer au message suivant la paire
        else:
            i += 1  # Chercher la prochaine paire valide

    return pairs


def format_conversation_for_llm_messages(
    conversation_history: ConversationHistory, max_pairs: int = 2
) -> List[dict]:
    """
    Formate l'historique pour inclusion directe dans les messages d'un LLM.

    Args:
        conversation_history: Historique complet
        max_pairs: Nombre maximum de paires à inclure

    Returns:
        Liste de dictionnaires {"role": "user/assistant", "content": "..."}

    Utilisé par le Generic Agent qui envoie l'historique directement au LLM.
    """
    if not conversation_history.messages:
        return []

    # Extraction des paires complètes
    complete_pairs = extract_complete_pairs(conversation_history.messages)

    # Limitation au nombre de paires demandé
    recent_pairs = (
        complete_pairs[-max_pairs:]
        if len(complete_pairs) > max_pairs
        else complete_pairs
    )

    # Conversion en format LLM
    llm_messages = []
    for user_msg, assistant_msg in recent_pairs:
        llm_messages.append({"role": "user", "content": user_msg.content})
        llm_messages.append({"role": "assistant", "content": assistant_msg.content})

    return llm_messages


def should_include_conversation_history(agent_type: str) -> bool:
    """
    Détermine si un agent a besoin de l'historique conversationnel.

    Args:
        agent_type: Type d'agent ("router", "sql", "analysis", "generic", "architecture")

    Returns:
        True si l'agent a besoin de l'historique
    """
    agents_needing_history = {
        "router": True,  # Pour comprendre le contexte et router correctement
        "sql": True,  # Pour générer des requêtes dans le contexte
        "analysis": True,  # Pour contextualiser l'analyse avec les questions précédentes
        "generic": True,  # Pour maintenir une conversation naturelle
        "architecture": True,  # Pour comprendre le contexte des demandes d'analyse structure
    }

    return agents_needing_history.get(agent_type, False)
