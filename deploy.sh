#!/bin/bash

# Script de déploiement pour l'API Widget IA Grist
# Usage: ./deploy.sh {start|stop|restart} [--logs]

# Définir le répertoire du projet
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_DIR/api.pid"
PORT=$(grep '^PORT=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d'=' -f2 || echo "8111")
ENV_MODE="production"  # Mode fixé à production
LOG_FILE="$PROJECT_DIR/api_prod.log"
ENABLE_LOGS=false

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Fonction pour afficher l'aide
show_help() {
    echo "Usage: $0 {start|stop|restart} [--logs]"
    echo ""
    echo "Script de déploiement de l'API Widget IA Grist en production"
    echo ""
    echo "Options:"
    echo "  start    Démarrer l'API en mode production sur le port $PORT"
    echo "  stop     Arrêter l'API"
    echo "  restart  Redémarrer l'API en mode production"
    echo "  --logs   Activer la journalisation dans un fichier (par défaut: désactivé)"
    echo ""
    echo "Exemples:"
    echo "  $0 start           # Démarrer sans logs"
    echo "  $0 start --logs    # Démarrer avec logs dans $LOG_FILE"
    echo "  $0 restart --logs  # Redémarrer avec logs"
    echo ""
    exit 1
}

# Fonction pour vérifier les prérequis
check_prerequisites() {
    log_info "Vérification des prérequis..."
    
    # Vérification de Conda
    if ! command -v conda &> /dev/null; then
        log_error "Conda n'est pas installé ou pas dans le PATH"
        exit 1
    fi
    
    # Initialisation de Conda pour bash
    log_info "Initialisation de l'environnement Conda..."
    eval "$(conda shell.bash hook)"
    
    # Activation de l'environnement finetune
    log_info "Activation de l'environnement Conda 'finetune'..."
    conda activate finetune || {
        log_error "Impossible d'activer l'environnement conda 'finetune'"
        log_info "Créez l'environnement avec : conda create -n finetune python=3.10"
        exit 1
    }
    
    # Vérification du fichier .env
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        log_error "Fichier .env manquant. Copiez .env.example vers .env et configurez-le."
        exit 1
    fi
    
    log_success "Prérequis vérifiés (environnement conda 'finetune' activé)"
}

# Fonction pour démarrer l'API
start_api() {
    log_info "Vérification si l'API est déjà en cours..."
    
    # Vérifier si l'API est déjà en cours
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log_warning "L'API est déjà en cours d'exécution (PID: $PID)"
            exit 1
        else
            log_info "Nettoyage du fichier PID obsolète"
            rm -f "$PID_FILE"
        fi
    fi

    # Vérification des prérequis
    check_prerequisites
    
    # Changement vers le répertoire du projet
    cd "$PROJECT_DIR"

    log_info "Déploiement de l'API Widget IA Grist en PRODUCTION sur le port $PORT..."

    # S'assurer que l'environnement conda est activé
    eval "$(conda shell.bash hook)"
    conda activate finetune

    # Commande de base avec variables d'environnement
    local cmd="python -m app.main"
    
    # Lancer l'API avec nohup et variable d'environnement
    if [ "$ENABLE_LOGS" = true ]; then
        log_info "Démarrage avec logs dans: $LOG_FILE"
        nohup env ENV=$ENV_MODE $cmd > "$LOG_FILE" 2>&1 &
    else
        log_info "Démarrage sans logs (production silencieuse)"
        nohup env ENV=$ENV_MODE $cmd > /dev/null 2>&1 &
    fi
    
    # Sauvegarder le PID
    local api_pid=$!
    echo $api_pid > "$PID_FILE"
    
    # Attendre un peu pour vérifier le démarrage
    sleep 3
    
    if ps -p $api_pid > /dev/null 2>&1; then
        log_success "API déployée en PRODUCTION avec PID $api_pid"
        log_info "URL: http://localhost:$PORT"
        log_info "Documentation: http://localhost:$PORT/docs"
        
        if [ "$ENABLE_LOGS" = true ]; then
            echo "  • Logs: $LOG_FILE"
            echo "  • Voir logs en temps réel: tail -f $LOG_FILE"
        else
            echo "  • Logs: Désactivés (mode production silencieux)"
        fi
        
        # Test de santé rapide
        sleep 2
        if command -v curl &> /dev/null; then
            if curl -s "http://localhost:$PORT/health" > /dev/null; then
                log_success "Test de santé réussi - API opérationnelle"
            else
                log_warning "Test de santé échoué - l'API démarre peut-être encore"
            fi
        fi
    else
        log_error "Échec du démarrage de l'API"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Fonction pour arrêter l'API
stop_api() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        
        if ps -p $PID > /dev/null 2>&1; then
            log_info "Arrêt de l'API en production (PID: $PID)..."
            kill -15 $PID
            
            # Attendre l'arrêt gracieux
            sleep 3
            
            # Force kill si nécessaire
            if ps -p $PID > /dev/null 2>&1; then
                log_warning "Force kill du processus $PID"
                kill -9 $PID
                sleep 1
            fi
            
            if ! ps -p $PID > /dev/null 2>&1; then
                log_success "API arrêtée avec succès"
                rm -f "$PID_FILE"
            else
                log_error "Impossible d'arrêter le processus $PID"
                exit 1
            fi
        else
            log_warning "Processus $PID non trouvé. L'API est peut-être déjà arrêtée."
            rm -f "$PID_FILE"
        fi
    else
        log_warning "Fichier PID non trouvé. L'API n'est peut-être pas en cours d'exécution."
    fi
}

# Fonction pour redémarrer l'API
restart_api() {
    log_info "Redémarrage de l'API..."
    stop_api
    sleep 2
    start_api
}

# Fonction pour afficher le statut
show_status() {
    echo ""
    log_info "Statut de l'API Widget IA Grist:"
    echo "  • Port: $PORT"
    echo "  • Mode: $ENV_MODE"
    echo "  • PID file: $PID_FILE"
    
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            echo "  • Statut: ✅ En cours d'exécution (PID: $pid)"
            echo "  • URL: http://localhost:$PORT"
        else
            echo "  • Statut: ❌ Arrêté (PID obsolète)"
        fi
    else
        echo "  • Statut: ❌ Arrêté"
    fi
    
    if [ "$ENABLE_LOGS" = true ]; then
        echo "  • Logs: $LOG_FILE"
    else
        echo "  • Logs: Désactivés"
    fi
    echo ""
}

# Vérification des options --logs
for arg in "$@"
do
    if [ "$arg" = "--logs" ]; then
        ENABLE_LOGS=true
    fi
done

# Gestion des commandes principales
case "$1" in
    start)
        start_api
        show_status
        ;;
    stop)
        stop_api
        ;;
    restart)
        restart_api
        show_status
        ;;
    status)
        show_status
        ;;
    *)
        show_help
        ;;
esac 