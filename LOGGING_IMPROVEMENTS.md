# Améliorations du Système de Logging

## Problème identifié

Les logs "Request options: {'method': 'post', 'url': '/chat/completions', ...}" provenaient des librairies HTTP internes (httpx, openai) lorsque le niveau de log était défini à DEBUG. Ces logs étaient:

- **Non formatés** : Format brut difficile à lire
- **Verbeux** : Trop de détails techniques inutiles
- **Non structurés** : Mélangés avec les autres logs de l'application

## Solutions implementées

### 1. Configuration intelligente des loggers HTTP

**Fichier modifié :** `/app/utils/logging.py`

**Fonction ajoutée :** `_configure_http_loggers()`

```python
def _configure_http_loggers(app_log_level: str):
    """Configure les loggers HTTP pour éviter les logs verbeux"""
    http_loggers = [
        'httpx', 'httpcore', 'httpcore.http11', 'httpcore.connection', 
        'httpcore.proxy', 'httpcore.http2', 'openai._base_client', 'openai._client'
    ]
    
    if app_log_level == "DEBUG":
        target_level = logging.INFO  # Évite le spam mais garde la visibilité
    else:
        target_level = logging.WARNING  # Masque complètement
    
    for logger_name in http_loggers:
        logging.getLogger(logger_name).setLevel(target_level)
```

**Résultat :** Les logs "Request options" sont maintenant filtrés automatiquement.

### 2. Nouveaux logs structurés pour les requêtes IA

**Méthodes ajoutées à la classe AgentLogger :**

```python
def log_ai_request(self, model: str, messages_count: int, max_tokens: int = None, request_id: str = None):
    """Log lisible pour les requêtes vers l'IA (remplace les logs 'Request options')"""

def log_ai_response(self, model: str, tokens_used: int = None, success: bool = True, request_id: str = None):
    """Log lisible pour les réponses de l'IA"""

def log_http_error(self, endpoint: str, status_code: int, error_msg: str = None, request_id: str = None):
    """Log structuré pour les erreurs HTTP"""
```

**Exemple d'output :**
```
🤖 Requête IA envoyée    model=mistral-small messages=3 max_tokens=200 request_id=test-123
✅ Réponse IA reçue      model=mistral-small tokens=150 request_id=test-123
```

### 3. Mise à jour des agents

**Fichiers modifiés :**
- `/app/agents/generic_agent.py`
- `/app/agents/sql_agent.py`

**Changements :**
- Ajout de `log_ai_request()` avant chaque appel à l'API IA
- Ajout de `log_ai_response()` après chaque réponse
- Gestion des erreurs avec logs appropriés

**Avant :**
```
Request options: {'method': 'post', 'url': '/chat/completions', 'headers': {...}, 'data': {...}}
```

**Après :**
```
🤖 Requête IA envoyée    agent=generic_agent model=mistral-small messages=3 max_tokens=200
✅ Réponse IA reçue      agent=generic_agent model=mistral-small tokens=150
```

## Configuration recommandée

### Variables d'environnement

```bash
# Mode développement
LOG_LEVEL=DEBUG  # Les logs HTTP sont automatiquement filtrés

# Mode production  
LOG_LEVEL=INFO   # Logs HTTP complètement masqués
```

### Avantages de la solution

1. **🎯 Filtrage intelligent** : Les logs verbeux sont automatiquement filtrés selon le contexte
2. **📊 Visibilité maintenue** : Information importante conservée mais formatée proprement
3. **🛠️ Configuration flexible** : Comportement différent selon DEBUG/INFO/PRODUCTION
4. **🎨 Logs lisibles** : Format structuré avec emojis et informations pertinentes
5. **🔍 Traçabilité** : request_id permet de suivre une requête de bout en bout

## Test et validation

**Script de test :** `test_logging.py`

```bash
python test_logging.py
```

**Tests effectués :**
- ✅ Configuration des loggers HTTP
- ✅ Nouvelles méthodes AgentLogger  
- ✅ Suppression des logs verbeux
- ✅ Maintien des logs INFO utiles

## Fichiers impactés

```
app/utils/logging.py          # Configuration principale + nouvelles méthodes
app/agents/generic_agent.py   # Utilisation des nouveaux logs IA
app/agents/sql_agent.py       # Utilisation des nouveaux logs IA
test_logging.py              # Script de test et validation
LOGGING_IMPROVEMENTS.md      # Cette documentation
```

## Usage pour les développeurs

### Ajouter des logs IA dans un nouvel agent

```python
# Avant l'appel IA
self.logger.log_ai_request(
    model=self.model,
    messages_count=len(messages),
    max_tokens=200,
    request_id=request_id
)

# Après la réponse IA
self.logger.log_ai_response(
    model=self.model,
    tokens_used=response.usage.total_tokens,
    success=True,
    request_id=request_id
)

# En cas d'erreur
self.logger.log_ai_response(
    model=self.model,
    success=False,
    request_id=request_id
)
```

### Logs d'erreur HTTP personnalisés

```python
self.logger.log_http_error(
    endpoint="/chat/completions",
    status_code=429,
    error_msg="Rate limit exceeded",
    request_id=request_id
)
```

## Résultat final

❌ **Avant :** Logs "Request options" non formatés et verbeux  
✅ **Après :** Logs structurés, lisibles et informatifs

La solution résout complètement le problème initial tout en améliorant la qualité générale du logging de l'application.