import openai
from typing import Dict, Any, Optional
import uuid
import os
from dotenv import load_dotenv

from .models.message import ConversationHistory, Message
from .models.request import ProcessedRequest, ChatResponse
from .utils.logging import AgentLogger
from .grist.schema_fetcher import GristSchemaFetcher
from .grist.sql_runner import GristSQLRunner
from .agents.router_agent import RouterAgent, AgentType
from .agents.generic_agent import GenericAgent
from .agents.sql_agent import SQLAgent
from .agents.analysis_agent import AnalysisAgent
from .agents.structure_agent import StructureAgent

load_dotenv()


class AIOrchestrator:
    """Orchestrateur principal qui coordonne tous les agents IA"""
    
    def __init__(self):
        self.logger = AgentLogger("orchestrator")
        
        # Configuration OpenAI (Albert/Etalab)
        self.openai_client = openai.AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE")
        )
        
        # Configuration des modèles depuis les variables d'environnement
        self.default_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.analysis_model = os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-4")
        
        # Configuration par défaut pour Grist (optionnelle, pour les tests)
        self.default_grist_key = os.getenv("GRIST_API_KEY", None)
        
        # Initialisation des composants
        self._init_components()
        
        # Statistiques d'utilisation
        self.stats = {
            "total_requests": 0,
            "agent_usage": {agent_type.value: 0 for agent_type in AgentType}
        }
    
    def _init_components(self):
        """Initialise tous les composants (agents et intégrations)"""
        # Agents IA avec modèles configurés
        self.router_agent = RouterAgent(self.openai_client, self.default_model)
        self.generic_agent = GenericAgent(self.openai_client, self.default_model)
        self.analysis_agent = AnalysisAgent(self.openai_client, self.analysis_model)
        
        # Note: Les composants Grist sont initialisés par requête car ils dépendent de la clé API
        # L'agent structure sera initialisé par requête avec les composants Grist
        self.logger.info("Orchestrateur initialisé avec succès", 
                        default_model=self.default_model,
                        analysis_model=self.analysis_model)
    
    async def process_chat_request(self, processed_request: ProcessedRequest) -> ChatResponse:
        """
        Traite une requête de chat complète
        
        Args:
            processed_request: Requête traitée contenant les messages et métadonnées
            
        Returns:
            ChatResponse: Réponse structurée avec les détails de traitement
        """
        request_id = str(uuid.uuid4())
        self.stats["total_requests"] += 1
        
        self.logger.info(
            "Nouvelle requête de chat",
            request_id=request_id,
            document_id=processed_request.document_id,
            messages_count=len(processed_request.messages)
        )
        
        try:
            # 1. Extraction du dernier message utilisateur
            conversation_history = ConversationHistory(messages=processed_request.messages)
            last_user_message = conversation_history.get_last_user_message()
            
            if not last_user_message:
                return ChatResponse(
                    response="Aucun message utilisateur trouvé dans la conversation.",
                    agent_used=AgentType.GENERIC.value,
                    error="No user message found"
                )
            
            # 2. Routing du message vers l'agent approprié
            selected_agent = await self.router_agent.route_message(
                last_user_message.content, 
                conversation_history, 
                request_id
            )
            
            self.stats["agent_usage"][selected_agent.value] += 1
            
            # 3. Traitement par l'agent sélectionné
            response_data = await self._process_with_agent(
                selected_agent, 
                last_user_message.content,
                conversation_history,
                processed_request,
                request_id
            )
            
            # Logs détaillés du résultat de l'orchestrateur
            self.logger.info(
                "🎯 Traitement orchestrateur terminé",
                request_id=request_id,
                selected_agent=selected_agent.value,
                final_agent_used=response_data.agent_used,
                response_length=len(response_data.response),
                has_sql_query=response_data.sql_query is not None,
                data_analyzed=response_data.data_analyzed,
                has_error=response_data.error is not None
            )
            
            if response_data.sql_query:
                self.logger.info(
                    "📋 Requête SQL dans la réponse",
                    request_id=request_id,
                    sql_query=response_data.sql_query
                )
            
            return response_data
            
        except Exception as e:
            self.logger.error(
                f"Erreur lors du traitement de la requête: {str(e)}",
                request_id=request_id,
                document_id=processed_request.document_id
            )
            
            return ChatResponse(
                response=f"Désolé, j'ai rencontré une erreur technique : {str(e)}",
                agent_used=AgentType.GENERIC.value,
                error=str(e)
            )
    
    async def _process_with_agent(self, agent_type: AgentType, user_message: str,
                                conversation_history: ConversationHistory,
                                processed_request: ProcessedRequest,
                                request_id: str) -> ChatResponse:
        """Traite le message avec l'agent sélectionné"""
        
        if agent_type == AgentType.GENERIC:
            return await self._process_generic(user_message, conversation_history, request_id)
        
        elif agent_type == AgentType.SQL:
            return await self._process_sql(user_message, conversation_history, processed_request, request_id)
        
        elif agent_type == AgentType.ANALYSIS:
            # Pour l'analyse, on a besoin de données SQL existantes
            # Si pas de données dans l'historique, on redirige vers SQL d'abord
            return await self._process_analysis_or_redirect(user_message, conversation_history, processed_request, request_id)
        
        elif agent_type == AgentType.STRUCTURE:
            return await self._process_structure(user_message, conversation_history, processed_request, request_id)
        
        else:
            # Fallback vers générique
            return await self._process_generic(user_message, conversation_history, request_id)
    
    async def _process_generic(self, user_message: str, conversation_history: ConversationHistory, 
                             request_id: str) -> ChatResponse:
        """Traite avec l'agent générique"""
        
        response_text = await self.generic_agent.process_message(
            user_message, conversation_history, request_id
        )
        
        # Log du résultat de l'agent générique
        self.logger.info(
            "💬 Résultat agent générique",
            request_id=request_id,
            response_length=len(response_text),
            response_preview=response_text[:150] + "..." if len(response_text) > 150 else response_text
        )
        
        return ChatResponse(
            response=response_text,
            agent_used=AgentType.GENERIC.value
        )
    
    async def _process_sql(self, user_message: str, conversation_history: ConversationHistory,
                         processed_request: ProcessedRequest, request_id: str) -> ChatResponse:
        """Traite avec l'agent SQL puis analyse automatiquement"""
        
        # Initialisation des composants Grist pour cette requête
        grist_key = processed_request.grist_api_key or self.default_grist_key
        if not grist_key:
            self.logger.warning(
                "⚠️ Clé API Grist manquante",
                request_id=request_id,
                document_id=processed_request.document_id
            )
            return ChatResponse(
                response="Configuration manquante : clé API Grist non fournie.",
                agent_used=AgentType.SQL.value,
                error="Missing Grist API key"
            )
        
        schema_fetcher = GristSchemaFetcher(grist_key)
        sql_runner = GristSQLRunner(grist_key)
        sql_agent = SQLAgent(self.openai_client, schema_fetcher, sql_runner, self.analysis_model)
        
        self.logger.info(
            "🔧 Composants Grist initialisés",
            request_id=request_id,
            document_id=processed_request.document_id,
            has_grist_key=bool(grist_key)
        )
        
        # Traitement SQL
        response_text, sql_query, sql_results = await sql_agent.process_message(
            user_message, conversation_history, processed_request.document_id, request_id
        )
        
        # Logs détaillés des résultats SQL
        self.logger.info(
            "🗄️ Résultat agent SQL",
            request_id=request_id,
            response_length=len(response_text),
            sql_query_length=len(sql_query) if sql_query else 0,
            sql_success=sql_results.get("success", False) if sql_results else False,
            sql_row_count=sql_results.get("row_count", 0) if sql_results else 0
        )
        
        if sql_results:
            self.logger.info(
                "📊 Détails résultats SQL",
                request_id=request_id,
                sql_results_keys=list(sql_results.keys()),
                sql_data_preview=str(sql_results.get("data", []))[:200] + "..." if sql_results.get("data") and len(str(sql_results.get("data", []))) > 200 else str(sql_results.get("data", [])),
                sql_error=sql_results.get("error")
            )
        
        # ANALYSE INTELLIGENTE après une requête SQL réussie
        if sql_results and sql_results.get("success"):
            # Vérifier s'il y a des données à analyser
            has_data = sql_results.get("data") and len(sql_results.get("data", [])) > 0
            
            if has_data:
                self.logger.info(
                    "🔬 Analyse automatique avec données",
                    request_id=request_id,
                    sql_success=True,
                    data_count=len(sql_results.get("data", []))
                )
                
                analysis_text = await self.analysis_agent.process_message(
                    user_message, conversation_history, sql_query, sql_results, request_id
                )
                
                self.logger.info(
                    "📈 Résultat analyse automatique",
                    request_id=request_id,
                    analysis_length=len(analysis_text),
                    analysis_preview=analysis_text[:150] + "..." if len(analysis_text) > 150 else analysis_text
                )
                
                # Retourner UNIQUEMENT l'analyse (pas de concaténation)
                return ChatResponse(
                    response=analysis_text,
                    agent_used=AgentType.ANALYSIS.value,
                    sql_query=sql_query,
                    data_analyzed=True
                )
            else:
                # Cas particulier : requête réussie mais aucun résultat
                # Ce n'est PAS une erreur, juste une absence de données correspondantes
                self.logger.info(
                    "✅ Requête SQL réussie mais sans résultats",
                    request_id=request_id,
                    sql_success=True,
                    data_count=0
                )
                
                # Retourner directement la réponse SQL optimisée pour les résultats vides
                return ChatResponse(
                    response=response_text,
                    agent_used=AgentType.SQL.value,
                    sql_query=sql_query,
                    data_analyzed=False
                )
        else:
            # Si échec SQL, pas d'analyse possible
            self.logger.warning(
                "⚠️ Pas d'analyse car échec SQL",
                request_id=request_id,
                sql_success=False,
                sql_error=sql_results.get("error") if sql_results else "Aucun résultat"
            )
        
        return ChatResponse(
            response=response_text,
            agent_used=AgentType.SQL.value,
            sql_query=sql_query,
            data_analyzed=False
        )
    
    async def _process_structure(self, user_message: str, conversation_history: ConversationHistory,
                               processed_request: ProcessedRequest, request_id: str) -> ChatResponse:
        """Traite avec l'agent structure pour analyser la structure des données"""
        
        # Initialisation des composants Grist pour cette requête
        grist_key = processed_request.grist_api_key or self.default_grist_key
        if not grist_key:
            self.logger.warning(
                "⚠️ Clé API Grist manquante pour l'agent structure",
                request_id=request_id,
                document_id=processed_request.document_id
            )
            return ChatResponse(
                response="Configuration manquante : clé API Grist non fournie pour analyser la structure des données.",
                agent_used=AgentType.STRUCTURE.value,
                error="Missing Grist API key"
            )
        
        from .grist.content_fetcher import GristContentFetcher
        
        schema_fetcher = GristSchemaFetcher(grist_key)
        content_fetcher = GristContentFetcher(grist_key)
        structure_agent = StructureAgent(self.openai_client, schema_fetcher, content_fetcher, analysis_model=self.analysis_model)
        
        self.logger.info(
            "🏗️ Composants Grist initialisés pour l'agent structure",
            request_id=request_id,
            document_id=processed_request.document_id,
            has_grist_key=bool(grist_key)
        )
        
        # Traitement avec l'agent structure
        response_text = await structure_agent.process_message(
            user_message, conversation_history, processed_request.document_id, request_id
        )
        
        # Logs détaillés des résultats
        self.logger.info(
            "🏗️ Résultat agent structure",
            request_id=request_id,
            response_length=len(response_text),
            response_preview=response_text[:150] + "..." if len(response_text) > 150 else response_text
        )
        
        return ChatResponse(
            response=response_text,
            agent_used=AgentType.STRUCTURE.value
        )
    
    async def _process_analysis_or_redirect(self, user_message: str, conversation_history: ConversationHistory,
                                          processed_request: ProcessedRequest, request_id: str) -> ChatResponse:
        """Traite l'analyse ou redirige vers SQL si pas de données"""
        
        # Recherche de données SQL dans l'historique récent
        recent_messages = conversation_history.get_recent_messages(5)
        
        # Pour simplifier, on redirige vers SQL + analyse
        return await self._process_sql(user_message, conversation_history, processed_request, request_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques d'utilisation"""
        return {
            "total_requests": self.stats["total_requests"],
            "agent_usage": self.stats["agent_usage"].copy(),
            "most_used_agent": max(self.stats["agent_usage"], key=self.stats["agent_usage"].get)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Vérifie l'état de santé du système"""
        health_status = {
            "status": "healthy",
            "components": {},
            "timestamp": str(uuid.uuid4())  # Simplification pour le timestamp
        }
        
        # Test de l'API OpenAI
        try:
            await self.openai_client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            health_status["components"]["openai"] = "healthy"
        except Exception as e:
            health_status["components"]["openai"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Test Grist (si clé disponible)
        if self.default_grist_key:
            try:
                schema_fetcher = GristSchemaFetcher(self.default_grist_key)
                # Test simple (on ne peut pas tester sans document ID)
                health_status["components"]["grist"] = "configured"
            except Exception as e:
                health_status["components"]["grist"] = f"error: {str(e)}"
        else:
            health_status["components"]["grist"] = "not_configured"
        
        return health_status 