from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import uuid
from dotenv import load_dotenv

from .models.request import GristRequest, ProcessedRequest, ChatResponse
from .orchestrator import AIOrchestrator
from .utils.logging import AgentLogger

# Chargement des variables d'environnement
load_dotenv()

# Initialisation de l'application FastAPI
app = FastAPI(
    title="API Widget IA Grist",
    description="Backend FastAPI pour un widget IA intégré à Grist, capable de traiter des requêtes en langage naturel via des agents IA spécialisés.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialisation de l'orchestrateur
orchestrator = AIOrchestrator()
logger = AgentLogger("main_api")


@app.on_event("startup")
async def startup_event():
    """Événement de démarrage de l'application"""
    logger.info("Démarrage de l'API Widget IA Grist")


@app.on_event("shutdown")
async def shutdown_event():
    """Événement d'arrêt de l'application"""
    logger.info("Arrêt de l'API Widget IA Grist")


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


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request_data: List[GristRequest]):
    """
    Endpoint principal pour traiter les requêtes conversationnelles
    
    Args:
        request_data: Liste de requêtes Grist (généralement une seule)
        
    Returns:
        ChatResponse: Réponse structurée avec le résultat du traitement
    """
    request_id = str(uuid.uuid4())
    
    try:
        # Validation de la requête
        if not request_data or len(request_data) == 0:
            raise HTTPException(
                status_code=400, 
                detail="Liste de requêtes vide"
            )
        
        # On traite la première requête (format attendu selon specs)
        grist_request = request_data[0]
        
        logger.info(
            "Nouvelle requête /chat",
            request_id=request_id,
            document_id=grist_request.body.documentId,
            execution_mode=grist_request.body.executionMode
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
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8502, 
        reload=True,
        log_level="info"
    ) 