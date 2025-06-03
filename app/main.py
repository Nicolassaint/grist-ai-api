import warnings
# Suppression des warnings Pydantic V2 et autres warnings de compatibilité
warnings.filterwarnings("ignore", message="Valid config keys have changed in V2")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from typing import List, Dict, Any
import uuid
import json
from dotenv import load_dotenv

from .models.request import GristRequest, ProcessedRequest, ChatResponse
from .orchestrator import AIOrchestrator
from .utils.logging import AgentLogger

# Chargement des variables d'environnement
load_dotenv()

# Initialisation de l'orchestrateur et logger globaux
orchestrator = None
logger = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire du cycle de vie de l'application"""
    global orchestrator, logger
    
    # Démarrage
    orchestrator = AIOrchestrator()
    logger = AgentLogger("main_api")
    logger.info("Démarrage de l'API Widget IA Grist")
    
    yield
    
    # Arrêt
    logger.info("Arrêt de l'API Widget IA Grist")

# Initialisation de l'application FastAPI avec lifespan
app = FastAPI(
    title="API Widget IA Grist",
    description="Backend FastAPI pour un widget IA intégré à Grist, capable de traiter des requêtes en langage naturel via des agents IA spécialisés.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",  # Alternative localhost
        "https://docs.getgrist.com",  # Grist officiel
        "*"  # Temporaire pour développement - à restreindre en production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Endpoint racine avec informations sur l'API"""
    return {
        "message": "API Widget IA Grist",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/chat",
            "health": "/health",
            "stats": "/stats",
            "docs": "/docs"
        }
    }


# Gestionnaire d'erreur pour les erreurs de validation
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Gestionnaire personnalisé pour les erreurs de validation"""
    request_id = str(uuid.uuid4())
    
    # Log des détails de l'erreur de validation
    logger.error(
        "Erreur de validation de requête",
        request_id=request_id,
        method=request.method,
        url=str(request.url),
        validation_errors=exc.errors(),
        raw_body=await get_raw_body(request)
    )
    
    return {
        "detail": "Erreur de validation des données",
        "errors": exc.errors(),
        "request_id": request_id
    }


async def get_raw_body(request: Request) -> str:
    """Récupère le corps brut de la requête pour debug"""
    try:
        body = await request.body()
        return body.decode('utf-8') if body else "Corps vide"
    except Exception as e:
        return f"Erreur lecture corps: {str(e)}"


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: Request):
    """
    Endpoint principal pour traiter les requêtes conversationnelles
    
    Args:
        request: Requête HTTP brute pour debug
        
    Returns:
        ChatResponse: Réponse structurée avec le résultat du traitement
    """
    request_id = str(uuid.uuid4())
    
    try:
        # Lecture du corps brut pour debug
        raw_body = await request.body()
        logger.info(
            "Requête /chat - Corps brut reçu",
            request_id=request_id,
            raw_body_length=len(raw_body),
            raw_body_complete=raw_body.decode('utf-8')  # Affichage complet pour debug
        )
        
        # Parsing JSON manuel pour debug
        try:
            json_data = json.loads(raw_body.decode('utf-8'))
            logger.info(
                "Parsing JSON réussi",
                request_id=request_id,
                json_type=type(json_data).__name__,
                json_keys=list(json_data.keys()) if isinstance(json_data, dict) else "N/A",
                json_length=len(json_data) if isinstance(json_data, (list, dict)) else "N/A"
            )
        except json.JSONDecodeError as e:
            logger.error(
                "Erreur parsing JSON",
                request_id=request_id,
                json_error=str(e)
            )
            raise HTTPException(
                status_code=400,
                detail=f"JSON invalide: {str(e)}"
            )
        
        # Construction de la requête Grist à partir des éléments HTTP
        try:
            # Récupération des headers HTTP
            headers_dict = dict(request.headers)
            
            # Récupération des paramètres de query
            query_params = dict(request.query_params)
            
            # Le JSON reçu est traité comme le body
            grist_request_data = {
                "headers": headers_dict,
                "params": {},  # Pas de params dans le path pour ce endpoint
                "query": query_params,
                "body": json_data  # Le JSON reçu devient le body
            }
            
            # Validation Pydantic avec la structure complète
            grist_request = GristRequest(**grist_request_data)
                
            logger.info(
                "Construction requête Grist réussie",
                request_id=request_id,
                headers_count=len(headers_dict),
                query_params_count=len(query_params),
                body_keys=list(json_data.keys()) if isinstance(json_data, dict) else "N/A"
            )
            
        except Exception as e:
            logger.error(
                "Erreur construction requête Grist",
                request_id=request_id,
                construction_error=str(e),
                json_data_keys=list(json_data.keys()) if isinstance(json_data, dict) else "N/A"
            )
            raise HTTPException(
                status_code=422,
                detail=f"Erreur construction requête: {str(e)}"
            )
        
        # Validation de la requête
        if not grist_request:
            raise HTTPException(
                status_code=400, 
                detail="Requête Grist invalide"
            )
        
        logger.info(
            "Nouvelle requête /chat validée",
            request_id=request_id,
            document_id=grist_request.body.documentId,
            execution_mode=grist_request.body.executionMode,
            nb_messages=len(grist_request.body.messages)
        )
        
        # Extraction de la clé API Grist depuis le header x-api-key
        grist_api_key = grist_request.headers.get("x-api-key")
        
        # Conversion vers le format interne
        processed_request = ProcessedRequest.from_grist_request(
            grist_request, 
            grist_api_key
        )
        
        # Traitement par l'orchestrateur
        response = await orchestrator.process_chat_request(processed_request)
        
        # Logs détaillés du résultat final
        logger.info(
            "🔍 Résultat final du traitement",
            request_id=request_id,
            agent_used=response.agent_used,
            response_length=len(response.response),
            response_preview=response.response[:200] + "..." if len(response.response) > 200 else response.response,
            sql_query=response.sql_query,
            data_analyzed=response.data_analyzed,
            has_error=response.error is not None
        )
        
        if response.sql_query:
            logger.info(
                "📊 Requête SQL générée",
                request_id=request_id,
                sql_query=response.sql_query
            )
        
        if response.error:
            logger.warning(
                "⚠️ Erreur dans la réponse",
                request_id=request_id,
                error=response.error
            )
        
        logger.info(
            "Requête /chat traitée avec succès",
            request_id=request_id,
            agent_used=response.agent_used,
            response_length=len(response.response)
        )
        
        return response
        
    except HTTPException:
        # Re-raise les HTTPException
        raise
        
    except Exception as e:
        logger.error(
            f"Erreur lors du traitement /chat: {str(e)}",
            request_id=request_id
        )
        
        # Retour d'une réponse d'erreur mais pas d'exception HTTP
        # pour éviter de casser l'intégration Grist
        return ChatResponse(
            response=f"Désolé, j'ai rencontré une erreur technique : {str(e)}",
            agent_used="error",
            error=str(e)
        )


@app.get("/health")
async def health_check():
    """
    Endpoint de vérification de l'état de santé de l'API
    
    Returns:
        Dict: Statut de santé des composants
    """
    try:
        health_status = await orchestrator.health_check()
        
        # Détermination du code de statut HTTP
        status_code = 200
        if health_status["status"] == "degraded":
            status_code = 206  # Partial Content
        elif health_status["status"] == "unhealthy":
            status_code = 503  # Service Unavailable
            
        return health_status
        
    except Exception as e:
        logger.error(f"Erreur lors du health check: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "components": {}
        }


@app.get("/stats")
async def get_stats():
    """
    Endpoint pour récupérer les statistiques d'utilisation
    
    Returns:
        Dict: Statistiques d'utilisation des agents
    """
    try:
        stats = orchestrator.get_stats()
        return {
            "status": "success",
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération des statistiques: {str(e)}"
        )


@app.get("/agents")
async def list_agents():
    """
    Endpoint pour lister les agents disponibles et leurs capacités
    
    Returns:
        Dict: Liste des agents et leurs descriptions
    """
    agents_info = {
        "generic": {
            "name": "Agent Générique",
            "description": "Répond aux questions générales et fait du petit talk",
            "capabilities": [
                "Salutations et conversations générales",
                "Aide sur l'utilisation du widget",
                "Guidance vers les bonnes questions"
            ]
        },
        "sql": {
            "name": "Agent SQL", 
            "description": "Génère des requêtes SQL à partir de langage naturel",
            "capabilities": [
                "Génération de requêtes SELECT",
                "Extraction de données depuis Grist",
                "Validation de sécurité des requêtes"
            ]
        },
        "analysis": {
            "name": "Agent d'Analyse",
            "description": "Analyse les données et fournit des insights",
            "capabilities": [
                "Analyse de tendances",
                "Résumés statistiques",
                "Recommandations basées sur les données"
            ]
        },
        "router": {
            "name": "Agent de Routing",
            "description": "Dirige les messages vers l'agent approprié",
            "capabilities": [
                "Classification automatique des requêtes",
                "Optimisation du routage",
                "Gestion du contexte conversationnel"
            ]
        }
    }
    
    return {
        "status": "success",
        "agents": agents_info,
        "routing_logic": "Automatique basé sur l'analyse du contenu du message"
    }


# Middleware pour logging des requêtes
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware pour logger toutes les requêtes HTTP"""
    
    # Génération d'un ID de requête
    request_id = str(uuid.uuid4())
    
    # Log de la requête entrante
    logger.info(
        "Requête HTTP entrante",
        request_id=request_id,
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else "unknown"
    )
    
    # Traitement de la requête
    response = await call_next(request)
    
    # Log de la réponse
    logger.info(
        "Réponse HTTP sortante",
        request_id=request_id,
        status_code=response.status_code
    )
    
    return response


if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.getenv("PORT", 8000))  # Port depuis .env ou 8000 par défaut
    
    # Mode développement vs production
    is_dev = os.getenv("ENV", "development") == "development"
    
    uvicorn_config = {
        "host": "0.0.0.0",
        "port": port,
        "log_level": "info"
    }
    
    # Configuration spécifique au développement
    if is_dev:
        uvicorn_config.update({
            "reload": True,
            "reload_excludes": [
                "*.log",
                "*.pid", 
                "__pycache__",
                "*.pyc",
                ".git",
                "node_modules"
            ]
        })
    
    uvicorn.run("app.main:app", **uvicorn_config) 