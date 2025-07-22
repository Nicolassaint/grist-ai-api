import openai
from typing import Dict, Any, Optional
from ..models.message import Message, ConversationHistory
from ..utils.logging import AgentLogger
from ..grist.schema_fetcher import GristSchemaFetcher
from ..grist.content_fetcher import GristContentFetcher
import time


class StructureAgent:
    """Agent spécialisé dans l'analyse de structure des données Grist"""
    
    def __init__(self, openai_client: openai.AsyncOpenAI, schema_fetcher: GristSchemaFetcher, 
                 content_fetcher: GristContentFetcher, analysis_model: str = "mistral-small", quality_analysis: bool = False):
        self.client = openai_client
        self.schema_fetcher = schema_fetcher
        self.content_fetcher = content_fetcher
        self.analysis_model = analysis_model
        self.quality_analysis = quality_analysis
        self.logger = AgentLogger("structure_agent")
        
        # 🎯 PROMPT SYSTÈME ADAPTÉ POUR L'ANALYSE DE STRUCTURE
        self.system_prompt = """Tu es un assistant IA spécialisé dans l'analyse de la structure des données Grist.

Ton rôle est de :
- Analyser et expliquer la structure des tables et colonnes
- Identifier les relations entre les tables
- Suggérer des améliorations de structure de données
- Expliquer les types de données et leurs implications
- Aider à comprendre l'organisation des données

Contexte : L'utilisateur travaille avec un document Grist et souhaite comprendre ou améliorer la structure de ses données. Tu as TOUJOURS accès aux schémas des tables ET à un aperçu du contenu réel. Pour les questions concernant la qualité des données, tu as accès au contenu COMPLET.

Instructions :
- Sois précis et technique dans tes analyses
- Utilise des exemples concrets tirés des données
- Structure ta réponse de manière claire (sections, listes)
- Fournis des recommandations actionables
- Reste concis mais complet dans tes explications
- Explique clairement les relations entre les tables
- Suggère des bonnes pratiques de structuration


Exemples de réponses appropriées :
    "📊 La table Produits contient une colonne Catégorie avec des valeurs répétées. Je recommande de créer une table de référence Catégories liée via un champ category_id
    "🔗 La table Commandes est liée à Clients via client_id, mais cette colonne n'est pas de type Référence. Convertir ce champ permettrait d'établir une relation native Grist et d'afficher des données liées plus facilement."
    "⚠️ Le champ montant_total est de type Texte, alors qu’il devrait être de type Numérique pour permettre des calculs et des tris fiables."
    "🚨 Données manquantes : 35% des lignes de la table Utilisateurs ont un champ email vide. Cela peut poser problème pour des envois automatisé"
    "💡 Votre table Événements contient à la fois des données sur l’événement et l’organisateur. Séparer ces entités dans deux tables distinctes permettrait une meilleure normalisation."
    "💡 La colonne status contient plusieurs variantes de la même valeur ('En cours', 'en cours', 'EN COURS'). Créez un champ de type 'Choix' pour standardiser ces valeurs."
    "✅ Bonne pratique : la table Employés utilise une colonne employee_id en tant que clé primaire, avec des valeurs uniques et bien formatées."
    "✅ Vos relations entre Commandes, Clients et Produits sont bien définies, ce qui permet une structure relationnelle robuste."

Format de réponse :
- Utilise des sections claires avec des emojis
- Donne des exemples concrets
- Propose des actions concrètes quand approprié"""
    
    async def process_message(self, user_message: str, conversation_history: ConversationHistory, 
                            document_id: str, request_id: str) -> str:
        """Traite un message utilisateur pour l'analyse de structure"""
        start_time = time.time()
        
        self.logger.log_agent_start("structure", user_message)
        
        try:
            # Récupération des données Grist
            schemas = await self.schema_fetcher.get_all_schemas(document_id, request_id)
            schema = self.schema_fetcher.format_schema_for_prompt(schemas)
            
            # Récupération du contenu selon le mode
            if self.quality_analysis:
                content = await self.content_fetcher.get_all_tables_content(document_id, request_id)
                self.logger.info("📊 Mode qualité: contenu complet récupéré", request_id=request_id)
            else:
                content = await self.content_fetcher.get_all_tables_preview(document_id, request_id)
                self.logger.info("📋 Mode structure: aperçu via /records récupéré", request_id=request_id, content_size=len(content))
            
            # Construction du contexte conversationnel
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Ajout de l'historique récent (3 derniers messages)
            recent_messages = conversation_history.get_recent_messages(3)
            for msg in recent_messages[:-1]:  # Exclure le message actuel
                role = "user" if msg.role == "user" else "assistant"
                messages.append({"role": role, "content": msg.content})
            
            # Construction du message avec les données Grist
            analysis_type = "qualité des données" if self.quality_analysis else "structure des données"
            content_note = "Contenu complet des tables pour analyse approfondie" if self.quality_analysis else "Aperçu des tables (10 lignes max par table)"
            
            prompt_with_data = f"""ANALYSE DE {analysis_type.upper()}

SCHÉMA DU DOCUMENT:
{schema}

CONTENU DES DONNÉES:
{content_note}
{content}

REQUÊTE UTILISATEUR:
{user_message}"""
            
            messages.append({"role": "user", "content": prompt_with_data})
            
            # Appel API avec paramètres optimisés pour l'analyse
            max_tokens = 3000
            response = await self.client.chat.completions.create(
                model=self.analysis_model,
                messages=messages,
                max_tokens=max_tokens,  # Plus de tokens pour les analyses de qualité
                temperature=0.4,  # Température basse pour plus de précision
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            agent_response = response.choices[0].message.content.strip()
            
            # Log de la réponse
            processing_time = time.time() - start_time
            self.logger.log_agent_response("structure", True, processing_time)
            
            return agent_response
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Erreur lors de l'analyse de structure: {str(e)}"
            
            self.logger.error(error_msg, request_id=request_id, duration=f"{processing_time:.1f}s")
            
            # 🚨 MESSAGE D'ERREUR PERSONNALISÉ
            return f"Désolé, une erreur s'est produite lors de l'analyse de la structure: {str(e)}"
    
