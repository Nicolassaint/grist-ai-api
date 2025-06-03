# API Widget IA Grist

Backend FastAPI pour un widget IA intégré à Grist, capable de traiter des requêtes en langage naturel via des agents IA spécialisés.

## 🎯 Objectif

Créer une API Python 3.10 FastAPI agissant comme backend d'un widget IA dans l'application open-source Grist, capable de traiter des requêtes utilisateurs en langage naturel via des agents IA spécialisés. Le système repose sur une API OpenAI-compatible (Albert / Etalab).

## 🧠 Agents IA

- **Agent Principal** (générique) : Questions générales et petit talk
- **Agent de Routing** : Dirige les messages vers l'agent approprié
- **Agent SQL** : Génère des requêtes SQL à partir de langage naturel
- **Agent d'Analyse** : Analyse les données et fournit des insights

## 🚀 Installation

### Prérequis

- Python 3.10+
- Clé API Albert/Etalab (ou OpenAI compatible)
- Clé API Grist (optionnelle pour les tests)

### Installation locale

1. **Clonez le repository :**
```bash
git clone <url-du-repo>
cd api
```

2. **Créez un environnement virtuel :**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. **Installez les dépendances :**
```bash
pip install -r requirements.txt
```

4. **Configurez les variables d'environnement :**
Copiez `.env.example` vers `.env` et éditez les valeurs :
```ini
OPENAI_API_KEY=sk-votre-clé-etalab
OPENAI_API_BASE=https://albert.api.etalab.gouv.fr/v1
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_ANALYSIS_MODEL=gpt-4
LOG_LEVEL=INFO
```

5. **Lancez l'API :**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Installation avec Docker

1. **Construisez l'image :**
```bash
docker build -t grist-ai-widget .
```

2. **Lancez le conteneur :**
```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-votre-clé \
  -e OPENAI_API_BASE=https://albert.api.etalab.gouv.fr/v1 \
  -e OPENAI_MODEL=gpt-3.5-turbo \
  -e OPENAI_ANALYSIS_MODEL=gpt-4 \
  grist-ai-widget
```

## 📡 API Endpoints

### POST /chat
Endpoint principal pour traiter les requêtes conversationnelles.

**Request Body:**
```json
[
  {
    "headers": {
      "x-api-key": "your-grist-api-key"
    },
    "params": {},
    "query": {},
    "body": {
      "documentId": "DOCUMENT_ID",
      "messages": [
        {
          "role": "user",
          "content": "Montre-moi les ventes du mois dernier"
        }
      ],
      "webhookUrl": "https://./webhook/chat",
      "executionMode": "production"
    }
  }
]
```

**Response:**
```json
{
  "response": "Voici les résultats...",
  "agent_used": "sql",
  "sql_query": "SELECT ...",
  "data_analyzed": true,
  "error": null
}
```

### GET /health
Vérification de l'état de santé de l'API.

### GET /stats
Statistiques d'utilisation des agents.

### GET /agents
Liste des agents disponibles et leurs capacités.

## 🧪 Tests

### Test rapide avec le script intégré

```bash
python test_api.py
```

### Test manuel avec curl

```bash
# Test de base
curl http://localhost:8000/

# Test de santé
curl http://localhost:8000/health

# Test de chat (remplacez les valeurs)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '[{
    "headers": {"x-api-key": "votre-clé-grist"},
    "params": {},
    "query": {},
    "body": {
      "documentId": "test-doc",
      "messages": [{"role": "user", "content": "Bonjour"}],
      "webhookUrl": "https://example.com/webhook",
      "executionMode": "production"
    }
  }]'
```

## 🏗️ Architecture

```
app/
├── main.py                # FastAPI app & route /chat
├── orchestrator.py        # Orchestrateur principal
├── agents/               # Agents IA spécialisés
│   ├── router_agent.py
│   ├── generic_agent.py
│   ├── sql_agent.py
│   └── analysis_agent.py
├── grist/               # Intégration Grist
│   ├── schema_fetcher.py  # Récupère les schémas
│   └── sql_runner.py      # Exécute les requêtes SQL
├── models/              # Modèles Pydantic
│   ├── message.py
│   └── request.py
└── utils/               # Utilitaires
    └── logging.py         # Logging structuré
```

## 🔧 Configuration

### Variables d'environnement

| Variable | Description | Obligatoire |
|----------|-------------|-------------|
| `OPENAI_API_KEY` | Clé API Albert/Etalab | ✅ |
| `OPENAI_API_BASE` | URL de base de l'API | ✅ |
| `OPENAI_MODEL` | Modèle par défaut (routing, generic) | ❌ |
| `OPENAI_ANALYSIS_MODEL` | Modèle pour SQL et analyse | ❌ |
| `LOG_LEVEL` | Niveau de log (INFO, DEBUG, etc.) | ❌ |
| `GRIST_API_KEY` | Clé API Grist (tests uniquement) | ❌ |

### Intégration Grist

L'API reçoit la clé Grist dans le header `x-api-key` de chaque requête :
```json
{
  "headers": {
    "x-api-key": "votre-clé-grist"
  },
  "body": { ... }
}
```

Une clé par défaut peut être configurée via `GRIST_API_KEY` pour les tests locaux, mais en production la clé est toujours fournie par requête.

## 🚦 Fonctionnalités

### ✅ Implémentées

- [x] Architecture modulaire avec agents spécialisés
- [x] Orchestration intelligente via routeur
- [x] Agent générique pour petit talk
- [x] Agent SQL avec génération et validation sécurisée
- [x] Agent d'analyse avec insights automatiques
- [x] Intégration complète API Grist (schémas + SQL)
- [x] Logging structuré par agent
- [x] Gestion d'erreurs robuste
- [x] Documentation API automatique
- [x] Support Docker
- [x] Tests intégrés

### 🔄 Prochaines étapes

- [ ] Cache des schémas Grist
- [ ] Rate limiting
- [ ] Authentification avancée
- [ ] Métriques et monitoring
- [ ] Tests unitaires complets
- [ ] Support multi-documents

## 🐛 Debug et Logs

Les logs sont maintenant dans un format lisible et coloré pour l'humain :
```
2025-06-03 12:00:00 [info    ] 🚀 Agent démarré                 agent=sql_agent request_id=abc-123 query=Montre-moi les ventes...
2025-06-03 12:00:01 [info    ] 📊 Requête SQL générée           agent=sql_agent request_id=abc-123 query=SELECT * FROM ventes... tables=2
2025-06-03 12:00:02 [info    ] ✅ Appel API Grist               agent=grist_schema_fetcher endpoint=['docs', 'document-id'] status=200
2025-06-03 12:00:03 [info    ] ✅ Agent terminé                 agent=sql_agent request_id=abc-123 response_chars=1245 duration=2.34s
```

Les logs incluent :
- 🚀 Emojis pour identifier rapidement les événements
- `agent` : Nom de l'agent qui traite
- `request_id` : ID unique de la requête  
- `duration` : Temps d'exécution formaté
- Contexte spécifique selon l'agent

Pour activer les logs de debug : `LOG_LEVEL=DEBUG`

## 📚 Exemples d'utilisation

### Questions générales
```
"Bonjour, comment ça va ?"
"Aide-moi à comprendre ce widget"
"Quelles sont tes capacités ?"
```

### Requêtes de données
```
"Montre-moi les ventes du mois dernier"
"Combien d'utilisateurs avons-nous ?"
"Liste les 10 dernières commandes"
```

### Analyses
```
"Analyse les tendances de ventes"
"Que penses-tu de ces résultats ?"
"Quels sont les insights sur nos données ?"
```

## 🤝 Contribution

1. Fork le projet
2. Créez une branche feature (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Committez vos changements (`git commit -am 'Ajout nouvelle fonctionnalité'`)
4. Push vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Créez une Pull Request

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🆘 Support

Pour toute question ou problème :
1. Vérifiez les logs avec `LOG_LEVEL=DEBUG`
2. Testez avec `/health` pour vérifier la configuration
3. Consultez la documentation automatique sur `/docs`
4. Ouvrez une issue avec les détails de l'erreur 