import openai
from typing import Dict, Any, Optional
from ..models.message import Message, ConversationHistory
from ..utils.logging import AgentLogger
from ..utils.conversation_formatter import (
    format_conversation_for_llm_messages,
    should_include_conversation_history,
)
import time


class GenericAgent:
    """Agent principal pour les questions générales et le petit talk"""

    def __init__(self, openai_client: openai.AsyncOpenAI, model: str = "gpt-3.5-turbo"):
        self.client = openai_client
        self.model = model
        self.logger = AgentLogger("generic_agent")

        self.system_prompt = """Tu es un assistant IA intégré à Grist, une plateforme de gestion de données.

Ton rôle est de :
- Répondre aux questions générales sur Grist et ses fonctionnalités
- Aider l'utilisateur à comprendre comment utiliser le widget IA
- Faire du petit talk de manière amicale et professionnelle
- Guider l'utilisateur vers les bonnes questions pour analyser ses données

Contexte : L'utilisateur travaille avec un document Grist contenant des données qu'il peut analyser via ce widget IA.

Instructions :
- Sois amical, utile et professionnel
- Sois précis et détaillé dans tes réponses quand nécessaire
- Si l'utilisateur pose une question sur des données spécifiques, suggère-lui de reformuler pour une analyse de données
- N'invente jamais de données ou d'informations spécifiques au document de l'utilisateur

Exemples de réponses appropriées :
- Salutations et présentations
- Explication des capacités du widget
- Conseils sur comment poser des questions d'analyse
- Aide générale sur Grist"""

    async def process_message(self, context) -> str:
        """Traite un message générique ou fallback d'erreur"""
        start_time = time.time()

        self.logger.log_agent_start("generic", context.user_message[:80])

        # Vérifier si on arrive d'une erreur d'un autre agent
        if context.error:
            return self._handle_error_fallback(context)

        try:
            # Traitement normal pour message générique
            return await self._generate_generic_response(context)
            
        except Exception as e:
            execution_time = time.time() - start_time

            # 🤖 Log lisible d'erreur IA
            self.logger.log_ai_response(
                model=self.model, success=False, request_id=context.request_id
            )

            self.logger.error(
                f"Erreur lors du traitement générique: {str(e)}",
                request_id=context.request_id,
                execution_time=execution_time,
            )
            return self._get_fallback_response(context.user_message)
    
    def _handle_error_fallback(self, context) -> str:
        """Gère les fallbacks d'erreurs d'autres agents"""
        
        if context.agent_used == "sql":
            return self._handle_sql_fallback(context.user_message, context.error)
        elif context.agent_used == "architecture":
            return self._handle_architecture_fallback(context.user_message, context.error)
        else:
            return self._handle_generic_error_fallback(context.user_message, context.error)
    
    def _handle_sql_fallback(self, user_message: str, sql_error: str) -> str:
        """Fallback spécifique pour les erreurs SQL"""
        return f"""Je ne peux pas exécuter votre requête sur les données.

**Problème :** {sql_error}

Vous pouvez essayer de :
• Vérifier vos permissions d'accès au document
• Reformuler votre question différemment
• Me poser une question générale sur Grist

En attendant, je peux vous aider avec d'autres questions !"""
    
    def _handle_architecture_fallback(self, user_message: str, architecture_error: str) -> str:
        """Fallback spécifique pour les erreurs d'architecture"""
        return f"""Je ne peux pas analyser la structure de vos données.

**Problème :** {architecture_error}

Vous pouvez essayer de :
• Vérifier vos permissions d'accès
• Reformuler votre question sur la structure des données
• Me poser d'autres questions sur Grist

Comment puis-je vous aider autrement ?"""
    
    def _handle_generic_error_fallback(self, user_message: str, error: str) -> str:
        """Fallback générique pour autres erreurs"""
        return f"""Je rencontre une difficulté technique.

**Problème :** {error}

Pouvez-vous :
• Reformuler votre question
• Essayer une approche différente
• Me poser une autre question

Je suis là pour vous aider avec Grist !"""
    
    async def _generate_generic_response(self, context) -> str:
        """Génère une réponse générique normale"""
        
        # Construction du contexte conversationnel
        messages = [{"role": "system", "content": self.system_prompt}]

        # Ajout de l'historique de conversation formaté (paires user/assistant complètes)
        if should_include_conversation_history("generic"):
            history_messages = format_conversation_for_llm_messages(
                context.conversation_history, max_pairs=3
            )
            messages.extend(history_messages)

        messages.append({"role": "user", "content": context.user_message})

        # 🤖 Log lisible de la requête IA
        prompt_text = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in messages]
        )
        self.logger.log_ai_request(
            model=self.model,
            messages_count=len(messages),
            max_tokens=800,
            request_id=context.request_id,
            prompt_preview=prompt_text,
        )

        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=800, temperature=0.7
        )

        ai_response = response.choices[0].message.content.strip()

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
            request_id=context.request_id,
            response_preview=ai_response,
        )

        execution_time = time.time() - time.time()
        self.logger.log_agent_response("generic", True, execution_time)

        return ai_response

    def _get_fallback_response(self, user_message: str) -> str:
        """Réponse de secours en cas d'erreur"""
        user_lower = user_message.lower()

        if any(
            greeting in user_lower for greeting in ["bonjour", "salut", "hello", "hey"]
        ):
            return "Bonjour ! Je suis votre assistant IA pour Grist. Comment puis-je vous aider aujourd'hui ?"

        elif any(help_word in user_lower for help_word in ["aide", "help", "comment"]):
            return (
                "Je peux vous aider à analyser vos données Grist ! "
                "Posez-moi des questions sur vos données ou demandez-moi de générer des analyses. "
                "Par exemple : 'Montre-moi les tendances de ventes' ou 'Combien d'utilisateurs avons-nous ?'"
            )

        elif any(what_word in user_lower for what_word in ["quoi", "what", "que"]):
            return (
                "Je suis un assistant IA intégré à votre document Grist. "
                "Je peux analyser vos données, générer des requêtes SQL, et répondre à vos questions générales. "
                "Que souhaitez-vous savoir sur vos données ?"
            )

        else:
            return (
                "Désolé, je rencontre une difficulté technique temporaire. "
                "Pouvez-vous reformuler votre question ? Je suis là pour vous aider avec vos données Grist !"
            )

    def _detect_data_question(self, message: str) -> bool:
        """Détecte si la question concerne des données spécifiques"""
        data_indicators = [
            "données",
            "table",
            "colonne",
            "ligne",
            "enregistrement",
            "vente",
            "client",
            "utilisateur",
            "commande",
            "produit",
            "analyse",
            "statistique",
            "tendance",
            "total",
            "moyenne",
            "maximum",
            "minimum",
            "count",
            "sum",
        ]

        message_lower = message.lower()
        return any(indicator in message_lower for indicator in data_indicators)

    def suggest_data_analysis(self, user_message: str) -> str:
        """Suggère comment reformuler pour une analyse de données"""
        suggestions = [
            "Pour analyser vos données, essayez des questions comme :",
            "• 'Montre-moi les ventes du mois dernier'",
            "• 'Combien d'utilisateurs actifs avons-nous ?'",
            "• 'Analyse les tendances de nos produits'",
            "• 'Quelle est la moyenne des commandes par client ?'",
            "",
            "Je peux accéder à vos données Grist et générer des analyses détaillées !",
        ]

        return "\n".join(suggestions)
