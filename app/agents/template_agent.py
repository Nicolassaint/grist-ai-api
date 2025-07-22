import openai
from typing import Dict, Any, Optional
from ..models.message import Message, ConversationHistory
from ..utils.logging import AgentLogger
import time


class TemplateAgent:
    """Agent template générique - À modifier selon vos besoins"""
    
    def __init__(self, openai_client: openai.AsyncOpenAI, model: str = "gpt-3.5-turbo"):
        self.client = openai_client
        self.model = model
        self.logger = AgentLogger("template_agent")
        
        # 🎯 PERSONNALISEZ CE PROMPT SELON VOS BESOINS
        self.system_prompt = """Tu es un assistant IA spécialisé dans [VOTRE DOMAINE].

Ton rôle est de :
- [FONCTION 1]
- [FONCTION 2] 
- [FONCTION 3]

Contexte : [DÉCRIVEZ LE CONTEXTE D'UTILISATION]

Instructions :
- [INSTRUCTION 1]
- [INSTRUCTION 2]
- [INSTRUCTION 3]
- Reste concis dans tes réponses (max 200 mots)
- Sois précis et utile

Exemples de réponses appropriées :
- [EXEMPLE 1]
- [EXEMPLE 2]
- [EXEMPLE 3]"""
    
    async def process_message(self, user_message: str, conversation_history: ConversationHistory, request_id: str) -> str:
        """Traite un message utilisateur"""
        start_time = time.time()
        
        self.logger.log_agent_start(request_id, user_message)
        
        try:
            # Construction du contexte conversationnel
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Ajout de l'historique récent (5 derniers messages)
            recent_messages = conversation_history.get_recent_messages(5)
            for msg in recent_messages:
                role = "user" if msg.sender == "user" else "assistant"
                messages.append({"role": role, "content": msg.content})
            
            # Ajout du message actuel
            messages.append({"role": "user", "content": user_message})
            
            # 🔧 PERSONNALISEZ LES PARAMÈTRES D'APPEL API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,  # Ajustez selon vos besoins
                temperature=0.7,  # Ajustez la créativité (0.0-1.0)
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            agent_response = response.choices[0].message.content.strip()
            
            # Log de la réponse
            processing_time = time.time() - start_time
            self.logger.log_agent_response(request_id, agent_response, processing_time)
            
            return agent_response
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Erreur lors du traitement du message: {str(e)}"
            
            self.logger.log_agent_error(request_id, error_msg, processing_time)
            
            # 🚨 PERSONNALISEZ LE MESSAGE D'ERREUR
            return "Désolé, je rencontre des difficultés techniques. Pouvez-vous reformuler votre question ?"
    
    # 🔧 AJOUTEZ VOS MÉTHODES PERSONNALISÉES ICI
    
    def validate_input(self, user_message: str) -> bool:
        """Valide l'entrée utilisateur (à personnaliser)"""
        if not user_message or len(user_message.strip()) == 0:
            return False
        
        # Ajoutez vos validations personnalisées ici
        # Exemple : vérifier la longueur, le contenu, etc.
        
        return True
    
    def preprocess_message(self, user_message: str) -> str:
        """Prétraite le message avant envoi à l'IA (à personnaliser)"""
        # Nettoyage basique
        processed = user_message.strip()
        
        # Ajoutez vos traitements personnalisés ici
        # Exemple : correction orthographique, normalisation, etc.
        
        return processed
    
    def postprocess_response(self, response: str) -> str:
        """Post-traite la réponse de l'IA (à personnaliser)"""
        # Nettoyage basique
        processed = response.strip()
        
        # Ajoutez vos traitements personnalisés ici
        # Exemple : formatage, ajout de liens, etc.
        
        return processed
    
    def get_agent_capabilities(self) -> Dict[str, Any]:
        """Retourne les capacités de l'agent (à personnaliser)"""
        return {
            "name": "TemplateAgent",
            "description": "Agent template générique à personnaliser",
            "capabilities": [
                "Traitement de messages génériques",
                "Gestion de l'historique conversationnel",
                "Logging détaillé",
                "Gestion d'erreurs"
            ],
            "model": self.model,
            "max_tokens": 500,
            "temperature": 0.7
        }
    
    # 🎛️ MÉTHODES UTILITAIRES (OPTIONNELLES)
    
    async def get_context_info(self, request_id: str) -> Dict[str, Any]:
        """Récupère des informations contextuelles (à personnaliser)"""
        # Exemple : informations sur l'utilisateur, préférences, etc.
        return {
            "request_id": request_id,
            "timestamp": time.time(),
            "agent_type": "template"
        }
    
    def should_escalate(self, user_message: str) -> bool:
        """Détermine si le message doit être escaladé vers un autre agent"""
        # Logique d'escalade personnalisée
        escalation_keywords = ["urgent", "critique", "erreur", "problème"]
        
        return any(keyword in user_message.lower() for keyword in escalation_keywords)
    
    def get_suggested_follow_ups(self, user_message: str, response: str) -> list:
        """Génère des suggestions de questions de suivi (à personnaliser)"""
        # Exemple de suggestions génériques
        suggestions = [
            "Pouvez-vous me donner plus de détails ?",
            "Y a-t-il autre chose que je puisse vous aider ?",
            "Souhaitez-vous un exemple concret ?"
        ]
        
        # Ajoutez votre logique de suggestions personnalisées ici
        
        return suggestions 