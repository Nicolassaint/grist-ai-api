import openai
from typing import Dict, Any, Optional
from ..models.message import Message, ConversationHistory
from ..utils.logging import AgentLogger
import time
import os
from enum import Enum


class AgentType(str, Enum):
    """Types d'agents disponibles"""
    GENERIC = "generic"
    SQL = "sql"
    ANALYSIS = "analysis"


class RouterAgent:
    """Agent de routing qui dirige les messages vers l'agent approprié"""
    
    def __init__(self, openai_client: openai.AsyncOpenAI, model: str = "gpt-3.5-turbo"):
        self.client = openai_client
        self.model = model
        self.logger = AgentLogger("router_agent")
        
        self.routing_prompt = """Tu es un agent de routing intelligent pour un système d'IA d'analyse de données Grist.

Ta mission est de déterminer quel agent doit traiter la requête utilisateur parmi :

1. **GENERIC** : Questions générales, salutations, petit talk, demandes d'aide générale
2. **SQL** : Demandes d'extraction de données, questions nécessitant une requête SQL
3. **ANALYSIS** : Demandes d'analyse de données existantes, d'insights, de tendances

Exemples :
- "Bonjour, comment ça va ?" → GENERIC
- "Peux-tu m'aider ?" → GENERIC  
- "Montre-moi les ventes du mois dernier" → SQL
- "Combien d'utilisateurs avons-nous ?" → SQL
- "Analyse les tendances des ventes" → SQL (puis ANALYSIS)
- "Que penses-tu de ces résultats ?" → ANALYSIS

Instructions importantes :
- Si la question concerne des données spécifiques = SQL
- Si la question demande une analyse sur des données déjà récupérées = ANALYSIS
- Si c'est général/conversationnel = GENERIC
- En cas de doute entre SQL et ANALYSIS, choisis SQL

Réponds UNIQUEMENT par : GENERIC, SQL ou ANALYSIS"""
    
    async def route_message(self, user_message: str, conversation_history: ConversationHistory, request_id: str) -> AgentType:
        """Détermine quel agent doit traiter le message"""
        start_time = time.time()
        
        self.logger.log_agent_start(request_id, user_message)
        
        try:
            # Construction du contexte pour le routing
            context_messages = [
                {"role": "system", "content": self.routing_prompt},
                {"role": "user", "content": f"Message à router: {user_message}"}
            ]
            
            # Ajout du contexte conversationnel récent
            recent_messages = conversation_history.get_recent_messages(3)
            if recent_messages:
                context = "Contexte récent de la conversation:\n"
                for msg in recent_messages[:-1]:  # Exclure le dernier message (c'est celui qu'on route)
                    context += f"- {msg.role}: {msg.content[:100]}\n"
                context_messages.insert(1, {"role": "system", "content": context})
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=context_messages,
                max_tokens=10,
                temperature=0.1
            )
            
            routing_decision = response.choices[0].message.content.strip().upper()
            
            # Validation et mapping
            agent_mapping = {
                "GENERIC": AgentType.GENERIC,
                "SQL": AgentType.SQL, 
                "ANALYSIS": AgentType.ANALYSIS
            }
            
            selected_agent = agent_mapping.get(routing_decision, AgentType.GENERIC)
            
            execution_time = time.time() - start_time
            self.logger.log_agent_response(
                request_id, 
                f"Routé vers: {selected_agent}",
                execution_time
            )
            
            self.logger.info(
                "Message routé avec succès",
                request_id=request_id,
                selected_agent=selected_agent.value,
                routing_decision=routing_decision
            )
            
            return selected_agent
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(
                f"Erreur lors du routing: {str(e)}",
                request_id=request_id,
                execution_time=execution_time
            )
            # En cas d'erreur, retour vers l'agent générique
            return AgentType.GENERIC
    
    def should_use_sql_then_analysis(self, user_message: str) -> bool:
        """Détermine si on doit utiliser SQL puis ANALYSIS"""
        analysis_keywords = [
            "analyse", "tendance", "insight", "résumé", "compare", 
            "évolution", "pattern", "corrélation", "moyenne", "total",
            "maximum", "minimum", "statistique"
        ]
        
        data_keywords = [
            "vente", "utilisateur", "client", "commande", "produit",
            "données", "table", "ligne", "colonne"
        ]
        
        message_lower = user_message.lower()
        
        has_analysis = any(keyword in message_lower for keyword in analysis_keywords)
        has_data = any(keyword in message_lower for keyword in data_keywords)
        
        return has_analysis and has_data
    
    async def explain_routing(self, user_message: str, selected_agent: AgentType, request_id: str) -> str:
        """Explique pourquoi ce routage a été choisi (pour debug)"""
        explanations = {
            AgentType.GENERIC: "Question générale ou conversationnelle",
            AgentType.SQL: "Requête nécessitant l'extraction de données",
            AgentType.ANALYSIS: "Demande d'analyse de données"
        }
        
        explanation = explanations.get(selected_agent, "Routage par défaut")
        
        self.logger.debug(
            f"Explication du routage: {explanation}",
            request_id=request_id,
            user_message=user_message[:100],
            selected_agent=selected_agent.value
        )
        
        return explanation 