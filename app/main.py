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
from .pipeline.plans import list_plans, AVAILABLE_PLANS

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
    logger.error(f"Validation échouée", path=request.url.path, errors=len(exc.errors()))
    
    return {
        "detail": "Erreur de validation des données",
        "errors": exc.errors()
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
    """
    try:
        # Lecture et parsing du JSON
        raw_body = await request.body()
        
        try:
            json_data = json.loads(raw_body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"JSON invalide: {str(e)}")
            raise HTTPException(status_code=400, detail=f"JSON invalide: {str(e)}")
        
        # Construction de la requête Grist
        try:
            grist_request_data = {
                "headers": dict(request.headers),
                "params": {},
                "query": dict(request.query_params),
                "body": json_data
            }
            
            grist_request = GristRequest(**grist_request_data)
                
        except Exception as e:
            logger.error(f"Erreur construction requête", error=str(e)[:100])
            raise HTTPException(status_code=422, detail=f"Erreur construction requête: {str(e)}")
        
        # Log concis de la requête
        logger.log_chat_request(grist_request.body.documentId, len(grist_request.body.messages))

        # Extraction de la clé API et traitement
        # Debug: afficher tous les headers reçus
        all_headers = list(grist_request.headers.keys())
        logger.info(f"🔍 Tous les headers ({len(all_headers)}): {all_headers}")

        # Afficher les valeurs de quelques headers importants
        for key in ['x-api-key', 'authorization', 'content-type']:
            value = grist_request.headers.get(key, 'NON TROUVÉ')
            if value != 'NON TROUVÉ' and len(value) > 20:
                value = value[:20] + '...'
            logger.info(f"  📋 {key}: {value}")

        grist_api_key = grist_request.headers.get("x-api-key")
        if not grist_api_key:
            # Essayer d'autres variantes possibles
            logger.warning(f"❌ Clé 'x-api-key' non trouvée, recherche alternatives...")
            for key in grist_request.headers.keys():
                logger.info(f"    🔎 Vérification header: {key}")
                if 'api' in key.lower() and 'key' in key.lower():
                    logger.info(f"📌 Header trouvé: {key} = {grist_request.headers[key][:20]}...")
                    grist_api_key = grist_request.headers[key]
                    break

        if grist_api_key:
            logger.info(f"✅ Token Grist trouvé ({len(grist_api_key)} chars): {grist_api_key[:30]}...")
        else:
            logger.error(f"❌ AUCUN token Grist trouvé dans les headers!")
            logger.error(f"❌ Corps de la requête: {json.dumps(json_data, indent=2)[:500]}")

        processed_request = ProcessedRequest.from_grist_request(grist_request, grist_api_key)
        
        # Traitement par l'orchestrateur
        response = await orchestrator.process_chat_request(processed_request)
        
        # Log concis du résultat
        logger.log_chat_response(response.agent_used, len(response.response), bool(response.error))
        
        if response.sql_query:
            logger.log_sql_generation(response.sql_query, 1)  # tables_count approximatif
        
        return response
        
    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"Erreur inattendue", error=str(e)[:100])
        return ChatResponse(
            response=f"Erreur technique : {str(e)}",
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
        Dict: Statistiques d'utilisation des plans et agents
    """
    try:
        stats = orchestrator.get_stats()
        return {
            "status": "success",
            "architecture_version": "v2_pipeline",
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
        "architecture": {
            "name": "Agent d'Architecture",
            "description": "Conseille sur la structure et l'organisation des données",
            "capabilities": [
                "Analyse de normalisation (1NF, 2NF, 3NF, BCNF)",
                "Détection des relations entre tables",
                "Recommandations d'amélioration structurelle",
                "Métriques de complexité"
            ]
        }
    }

    # Informations sur les plans disponibles
    plans_info = {}
    for plan_name, plan in AVAILABLE_PLANS.items():
        agents_list = [a.value for a in plan.agents]
        plans_info[plan_name] = {
            "description": plan.description,
            "agents": agents_list,
            "requires_api_key": plan.requires_api_key
        }

    return {
        "status": "success",
        "architecture": "pipeline",
        "agents": agents_info,
        "plans": plans_info,
        "routing_logic": "Le router choisit automatiquement le plan d'exécution approprié basé sur l'intention de l'utilisateur"
    }


# Middleware pour logging des requêtes
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware pour logger les requêtes importantes"""
    
    # Traitement de la requête
    response = await call_next(request)
    
    # Log seulement pour les endpoints importants
    if request.url.path in ["/chat", "/health", "/stats"]:
        logger.log_request(request.method, request.url.path, response.status_code)
    
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