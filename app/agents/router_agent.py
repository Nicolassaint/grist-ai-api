"""
═══════════════════════════════════════════════════════════════════════════════
ROUTER AGENT - Agent de routage intelligent
═══════════════════════════════════════════════════════════════════════════════

RÔLE:
    Le Router Agent analyse le message de l'utilisateur et choisit le PLAN
    d'exécution approprié (séquence d'agents à exécuter).

FONCTIONNEMENT:
    1. Reçoit le message utilisateur + historique conversationnel
    2. Utilise un LLM (GPT) pour classifier l'intention
    3. Map l'intention vers un plan d'exécution
    4. Retourne le plan (pas un agent unique!)

PLANS DISPONIBLES:
    - "generic": Conversation simple → [Generic Agent]
    - "data_query": Requête SQL → [SQL Agent, Analysis Agent]
    - "architecture_review": Analyse structure → [Architecture Agent]
    - "full_analysis": Analyse complète → [Architecture, SQL, Analysis]

EXEMPLES:
    User: "Bonjour!"
    → Router: Intention = conversational → Plan "generic"
    → Executor: Generic Agent répond

    User: "Montre-moi les ventes"
    → Router: Intention = data_extraction → Plan "data_query"
    → Executor: SQL Agent (génère requête) → Analysis Agent (analyse résultats)

    User: "Ma structure est-elle bien organisée?"
    → Router: Intention = structure_review → Plan "architecture_review"
    → Executor: Architecture Agent analyse les schémas

AMÉLIORATIONS FUTURES:
    - Cache des décisions pour patterns fréquents
    - Fine-tuning du LLM sur les intentions Grist
    - Détection de patterns multi-tours (suite de conversation)

═══════════════════════════════════════════════════════════════════════════════
"""

import openai
from typing import Dict, Any
from ..models.message import ConversationHistory
from ..utils.logging import AgentLogger
from ..utils.conversation_formatter import (
    format_conversation_history,
    should_include_conversation_history,
)
from ..pipeline.plans import ExecutionPlan, get_plan, AVAILABLE_PLANS
import time


class RouterAgent:
    """
    Agent de routage qui choisit le plan d'exécution approprié.

    Le router ne choisit plus un agent unique, mais un PLAN complet
    (séquence ordonnée d'agents) basé sur l'intention de l'utilisateur.
    """

    def __init__(self, openai_client: openai.AsyncOpenAI, model: str = "gpt-3.5-turbo"):
        """
        Initialise le router.

        Args:
            openai_client: Client OpenAI pour classification
            model: Modèle LLM à utiliser (gpt-3.5-turbo par défaut)
        """
        self.client = openai_client
        self.model = model
        self.logger = AgentLogger("router_agent")

        # Prompt système pour la classification d'intention
        self.routing_prompt = self._build_routing_prompt()

    def _build_routing_prompt(self) -> str:
        """Construit le prompt de routing avec les plans disponibles"""
        plans_description = []
        for plan_name, plan in AVAILABLE_PLANS.items():
            agents_list = " → ".join([a.value for a in plan.agents])
            plans_description.append(
                f"- **{plan_name}**: {plan.description} [{agents_list}]"
            )

        return f"""Tu es un agent de routing intelligent pour Grist AI Assistant.

Ta mission: analyser le message utilisateur et choisir le BON PLAN d'exécution.

PLANS DISPONIBLES:
{chr(10).join(plans_description)}

RÈGLES DE DÉCISION:
1. **generic**: Questions générales, salutations, aide, conversations simples
   Exemples: "Bonjour", "Comment ça marche?", "Merci", "Qu'est-ce que Grist?"

2. **data_query**: L'utilisateur veut RÉCUPÉRER des données spécifiques et les ANALYSER
   Exemples: "Montre les ventes", "Combien de clients?", "Liste les commandes du mois"
   Mots-clés: montre, combien, liste, affiche, extrait, résultats, données
   Note: Ce plan exécute SQL puis Analysis automatiquement

3. **architecture_review**: L'utilisateur veut un CONSEIL sur la STRUCTURE des données
   Exemples: "Ma structure est bonne?", "Comment organiser mes tables?", "Mes relations sont OK?", "Avis sur ma donnée"
   Mots-clés: structure, organisation, normalisation, relations, schéma, architecture, conseil, avis, critique
   Note: Analyse UNIQUEMENT les schémas, pas le contenu des données

IMPORTANT:
- Si l'utilisateur demande un AVIS/CONSEIL sur sa structure → architecture_review
- Si l'utilisateur veut des DONNÉES spécifiques → data_query
- Si c'est une question GÉNÉRALE → generic
- En cas de doute entre architecture et data → choisis celui qui correspond le mieux aux mots-clés

Réponds UNIQUEMENT par le nom du plan: generic, data_query, ou architecture_review"""

    async def route_to_plan(
        self,
        user_message: str,
        conversation_history: ConversationHistory,
        request_id: str,
    ) -> ExecutionPlan:
        """
        Détermine le plan d'exécution approprié pour le message.

        Args:
            user_message: Message de l'utilisateur
            conversation_history: Historique de conversation
            request_id: ID unique de la requête (pour logging)

        Returns:
            ExecutionPlan: Plan d'exécution à suivre

        Exemple:
            >>> plan = await router.route_to_plan(
            ...     "Montre-moi les ventes",
            ...     conversation_history,
            ...     "req-123"
            ... )
            >>> print(plan.name)
            'data_query'
            >>> print(plan.agents)
            [AgentType.SQL, AgentType.ANALYSIS]
        """
        start_time = time.time()

        self.logger.log_agent_start(request_id, user_message)

        try:
            # Appel LLM pour classifier l'intention
            plan_name = await self._classify_intent(
                user_message, conversation_history, request_id
            )

            # Récupérer le plan correspondant
            try:
                plan = get_plan(plan_name)
            except KeyError:
                # Plan inconnu → fallback sur generic
                self.logger.warning(
                    f"Plan inconnu '{plan_name}', fallback sur generic",
                    request_id=request_id,
                )
                plan = get_plan("generic")

            execution_time = time.time() - start_time

            self.logger.log_agent_response(
                request_id, f"Plan sélectionné: {plan.name}", execution_time
            )

            self.logger.info(
                "✅ Routing terminé",
                request_id=request_id,
                plan_name=plan.name,
                agents_count=len(plan.agents),
                requires_api_key=plan.requires_api_key,
            )

            return plan

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(
                f"❌ Erreur lors du routing: {str(e)}",
                request_id=request_id,
                execution_time=execution_time,
            )
            # Fallback sur plan generic en cas d'erreur
            return get_plan("generic")

    async def _classify_intent(
        self,
        user_message: str,
        conversation_history: ConversationHistory,
        request_id: str,
    ) -> str:
        """
        Utilise le LLM pour classifier l'intention et retourner le nom du plan.

        Args:
            user_message: Message à classifier
            conversation_history: Contexte conversationnel
            request_id: ID de requête

        Returns:
            Nom du plan (ex: "data_query")
        """
        # Construction des messages pour le LLM
        messages = [{"role": "system", "content": self.routing_prompt}]

        # Ajout de l'historique conversationnel formaté (paires user/assistant complètes)
        if (
            should_include_conversation_history("router")
            and len(conversation_history.messages) > 0
        ):
            conversation_context = format_conversation_history(
                conversation_history, max_pairs=2
            )
            if conversation_context != "Aucun historique de conversation":
                messages.append(
                    {
                        "role": "system",
                        "content": f"Contexte récent:\n{conversation_context}",
                    }
                )

        # Message utilisateur à classifier
        messages.append(
            {"role": "user", "content": f"Message à router: {user_message}"}
        )

        # 🤖 Log lisible de la requête IA
        prompt_text = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in messages]
        )
        self.logger.log_ai_request(
            model=self.model,
            messages_count=len(messages),
            max_tokens=20,
            request_id=request_id,
            prompt_preview=prompt_text,
        )

        # Appel LLM
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=20,
            temperature=0.1,  # Peu de créativité pour classification
        )

        plan_name = response.choices[0].message.content.strip().lower()

        # 🤖 Log lisible de la réponse IA
        tokens_used = (
            getattr(response.usage, "total_tokens", None)
            if hasattr(response, "usage")
            else None
        )
        self.logger.log_ai_response(
            model=self.model,
            tokens_used=tokens_used,
            success=True,
            request_id=request_id,
            response_preview=plan_name,
        )

        self.logger.debug(
            f"Intention classifiée: {plan_name}",
            request_id=request_id,
            user_message_preview=user_message[:100],
        )

        return plan_name

    async def explain_routing(
        self, user_message: str, plan: ExecutionPlan, request_id: str
    ) -> str:
        """
        Génère une explication lisible de la décision de routing.

        Utile pour debugging et logs.

        Args:
            user_message: Message original
            plan: Plan sélectionné
            request_id: ID de requête

        Returns:
            Explication textuelle

        Exemple:
            >>> explanation = await router.explain_routing(...)
            >>> print(explanation)
            "Message 'Montre les ventes' → Plan 'data_query' car extraction de données détectée"
        """
        agents_str = " → ".join([a.value for a in plan.agents])

        explanation = (
            f"Message '{user_message[:50]}...' → "
            f"Plan '{plan.name}' [{agents_str}] - "
            f"{plan.description}"
        )

        self.logger.debug(f"Explication routing: {explanation}", request_id=request_id)

        return explanation
