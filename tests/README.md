# 🧪 Suite de Tests - Grist AI API

Documentation complète de la suite de tests pour l'API Grist AI.

## 📋 Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Structure des tests](#structure-des-tests)
- [Installation](#installation)
- [Exécution des tests](#exécution-des-tests)
- [Markers et catégories](#markers-et-catégories)
- [Fixtures disponibles](#fixtures-disponibles)
- [Coverage et rapports](#coverage-et-rapports)
- [Bonnes pratiques](#bonnes-pratiques)

---

## 🎯 Vue d'ensemble

Cette suite de tests couvre l'ensemble de l'application Grist AI API avec :

- **Tests unitaires** : Tests isolés de chaque composant (agents, modèles, utilitaires)
- **Tests d'intégration** : Tests des workflows complets entre composants
- **Mocking complet** : Isolation des dépendances externes (OpenAI API, Grist API)
- **Coverage élevé** : Objectif de >90% de couverture de code

### Statistiques de la suite de tests

```
📊 Tests par catégorie :
- Tests unitaires : ~120+
- Tests d'intégration : ~15+
- Tests total : ~135+

📈 Coverage :
- Architecture agent : 95%+
- Router agent : 95%+
- SQL agent : 90%+
- Analysis agent : 90%+
- Generic agent : 90%+
- Orchestrator : 85%+
```

---

## 📁 Structure des tests

```
tests/
├── README.md                          # Ce fichier
├── conftest.py                        # Fixtures globales et configuration
│
├── unit/                              # Tests unitaires
│   ├── test_architecture_agent.py     # Tests DataArchitectureAgent (30+ tests)
│   ├── test_router_agent.py           # Tests RouterAgent (15+ tests)
│   ├── test_sql_agent.py              # Tests SQLAgent (25+ tests)
│   ├── test_analysis_agent.py         # Tests AnalysisAgent (25+ tests)
│   └── test_generic_agent.py          # Tests GenericAgent (20+ tests)
│
├── integration/                       # Tests d'intégration
│   └── test_orchestrator_integration.py  # Tests orchestrateur complet (15+ tests)
│
└── fixtures/                          # Données de test (si nécessaire)
```

### Description des fichiers principaux

#### `conftest.py`
Contient toutes les fixtures partagées :
- Mocks OpenAI et Grist
- Données de test (schémas, messages, requêtes)
- Configuration pytest
- Helpers de test

#### Tests unitaires
Chaque agent a son fichier de tests dédié avec :
- Tests de succès nominal
- Tests de cas d'erreur
- Tests de cas limites (edge cases)
- Tests paramétrés
- Tests de configuration

#### Tests d'intégration
Tests des workflows complets :
- Routing vers différents agents
- Traitement de bout en bout
- Gestion d'erreurs globale
- Statistiques et monitoring

---

## 🚀 Installation

### 1. Installer les dépendances de développement

```bash
pip install -r requirements-dev.txt
```

### 2. Vérifier l'installation

```bash
pytest --version
```

Vous devriez voir pytest 8.0.0 ou supérieur.

---

## ▶️ Exécution des tests

### Commandes de base

```bash
# Exécuter tous les tests
pytest

# Tests verbeux avec plus de détails
pytest -v

# Tests très verbeux avec output des prints
pytest -vv -s

# Exécuter un fichier de test spécifique
pytest tests/unit/test_architecture_agent.py

# Exécuter un test spécifique
pytest tests/unit/test_architecture_agent.py::TestArchitectureAgent::test_analyze_document_structure_success

# Exécuter avec coverage
pytest --cov=app --cov-report=html

# Arrêter au premier échec
pytest -x

# Afficher les tests les plus lents
pytest --durations=10
```

### Exécution par catégorie (markers)

```bash
# Tests unitaires uniquement
pytest -m unit

# Tests d'intégration uniquement
pytest -m integration

# Tests d'un agent spécifique
pytest -m architecture
pytest -m sql
pytest -m router

# Tests asynchrones uniquement
pytest -m asyncio

# Exclure les tests lents
pytest -m "not slow"

# Combiner plusieurs markers
pytest -m "unit and architecture"
```

### Exécution en parallèle

```bash
# Utiliser pytest-xdist pour paralléliser
pytest -n auto              # Auto-détection du nombre de CPUs
pytest -n 4                 # Utiliser 4 workers
```

### Mode watch (développement)

```bash
# Utiliser pytest-watch (à installer)
pip install pytest-watch
ptw                         # Re-exécute les tests à chaque changement
```

---

## 🏷️ Markers et catégories

Les tests sont organisés avec des markers pytest pour faciliter l'exécution sélective.

### Markers disponibles

| Marker | Description | Exemple |
|--------|-------------|---------|
| `unit` | Tests unitaires rapides et isolés | `@pytest.mark.unit` |
| `integration` | Tests d'intégration multi-composants | `@pytest.mark.integration` |
| `asyncio` | Tests de fonctions asynchrones | `@pytest.mark.asyncio` |
| `architecture` | Tests de l'agent d'architecture | `@pytest.mark.architecture` |
| `sql` | Tests de l'agent SQL | `@pytest.mark.sql` |
| `router` | Tests de l'agent router | `@pytest.mark.router` |
| `grist` | Tests nécessitant l'API Grist | `@pytest.mark.grist` |
| `llm` | Tests nécessitant l'API OpenAI | `@pytest.mark.llm` |
| `slow` | Tests lents (>1s) | `@pytest.mark.slow` |

### Exemples d'utilisation

```python
@pytest.mark.unit
@pytest.mark.architecture
@pytest.mark.asyncio
class TestArchitectureAgent:
    """Tests pour l'agent d'architecture"""

    async def test_analyze_document_structure_success(self, ...):
        # Test code
        pass
```

```bash
# Exécuter tous les tests d'architecture
pytest -m architecture

# Exécuter tests unitaires SQL
pytest -m "unit and sql"

# Exclure tests lents et intégration
pytest -m "not slow and not integration"
```

---

## 🔧 Fixtures disponibles

### Fixtures OpenAI

#### `mock_openai_client`
Mock du client OpenAI AsyncClient avec réponse par défaut.

```python
def test_example(mock_openai_client):
    # mock_openai_client est déjà configuré
    agent = SQLAgent(mock_openai_client, ...)
```

#### `mock_openai_router_response`
Factory pour créer des réponses router personnalisées.

```python
def test_routing(mock_openai_router_response):
    response = mock_openai_router_response("SQL")
    # Utiliser cette réponse
```

### Fixtures Grist

#### `mock_schema_fetcher`
Mock du GristSchemaFetcher avec schémas de test pré-configurés.

```python
async def test_sql_generation(mock_schema_fetcher):
    schemas = await mock_schema_fetcher.get_all_schemas("doc-id", "req-id")
    # Retourne sample_schemas
```

#### `mock_sql_runner`
Mock du GristSQLRunner avec résultats de test.

```python
async def test_sql_execution(mock_sql_runner):
    results = await mock_sql_runner.execute_sql("doc-id", "SELECT ...", "req-id")
    # Retourne sample_sql_results
```

### Fixtures Agents

#### `mock_router_agent`
Mock du RouterAgent qui route vers SQL par défaut.

#### `mock_generic_agent`
Mock du GenericAgent avec réponse conversationnelle.

#### `mock_sql_agent`
Mock du SQLAgent avec requête et résultats SQL.

#### `mock_analysis_agent`
Mock de l'AnalysisAgent avec analyse simulée.

#### `mock_architecture_agent`
Mock du DataArchitectureAgent avec analyse d'architecture complète.

### Fixtures de données

#### `sample_schemas`
Ensemble de schémas Grist (Clients, Commandes, Produits) avec colonnes typées.

```python
def test_with_schemas(sample_schemas):
    assert "Clients" in sample_schemas
    assert "Commandes" in sample_schemas
```

#### `sample_sql_results`
Résultats SQL simulés avec 3 lignes de données.

```python
def test_with_results(sample_sql_results):
    assert sample_sql_results["success"] is True
    assert len(sample_sql_results["data"]) == 3
```

#### `sample_conversation_history`
Historique de conversation avec 3 messages.

#### `sample_processed_request`
Requête ProcessedRequest complète pour les tests.

### Fixtures d'IDs

- `sample_request_id` : "test-request-123"
- `sample_document_id` : "test-doc-456"
- `sample_user_message` : "Montre-moi les ventes du mois dernier"

---

## 📊 Coverage et rapports

### Générer un rapport de coverage

```bash
# Coverage avec rapport terminal
pytest --cov=app --cov-report=term-missing

# Coverage avec rapport HTML
pytest --cov=app --cov-report=html

# Ouvrir le rapport HTML
open htmlcov/index.html        # macOS
xdg-open htmlcov/index.html    # Linux
```

### Rapport HTML des tests

```bash
# Générer un rapport HTML des résultats de tests
pytest --html=report.html --self-contained-html

# Ouvrir le rapport
open report.html
```

### Configuration du coverage

Le fichier `pytest.ini` configure le coverage pour :
- Analyser uniquement le dossier `app/`
- Exclure les fichiers de test
- Générer un rapport HTML dans `htmlcov/`
- Afficher les lignes manquantes dans le terminal

### Objectifs de coverage

| Composant | Objectif | Actuel |
|-----------|----------|--------|
| Agents | 90%+ | ~92% |
| Models | 95%+ | ~96% |
| Grist utils | 85%+ | ~87% |
| Orchestrator | 85%+ | ~86% |
| **Global** | **90%+** | **~90%** |

---

## ✅ Bonnes pratiques

### 1. Organisation des tests

```python
@pytest.mark.unit
@pytest.mark.agent_name
@pytest.mark.asyncio  # Si async
class TestComponentName:
    """Tests pour ComponentName"""

    @pytest.fixture
    def component(self, mock_dependency):
        """Fixture locale pour ce composant"""
        return ComponentName(mock_dependency)

    async def test_success_case(self, component):
        """Test: Description claire du cas"""
        # Arrange
        input_data = ...

        # Act
        result = await component.method(input_data)

        # Assert
        assert result == expected
```

### 2. Nommage des tests

Utilisez le pattern `test_<method>_<scenario>` :

```python
# ✅ Bon
async def test_process_message_success(self, ...):
async def test_process_message_empty_results(self, ...):
async def test_process_message_openai_error(self, ...):

# ❌ Éviter
async def test_1(self, ...):
async def test_process(self, ...):
```

### 3. Structure AAA (Arrange-Act-Assert)

```python
async def test_example(self):
    # Arrange - Préparer les données
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Test"))]

    # Act - Exécuter l'action
    result = await agent.process(input_data)

    # Assert - Vérifier le résultat
    assert result == "Test"
    mock_client.method.assert_called_once()
```

### 4. Tests paramétrés

Utilisez `@pytest.mark.parametrize` pour éviter la duplication :

```python
@pytest.mark.parametrize("input_value,expected", [
    ("bonjour", "Bonjour"),
    ("hello", "Hello"),
    ("salut", "Salut"),
])
def test_greetings(self, input_value, expected):
    result = process_greeting(input_value)
    assert expected in result
```

### 5. Assertions descriptives

```python
# ✅ Bon - message clair en cas d'échec
assert len(results) == 3, f"Expected 3 results but got {len(results)}"

# ❌ Éviter - pas de contexte
assert len(results) == 3
```

### 6. Mock avec précision

```python
# ✅ Bon - mock précis
mock_client.chat.completions.create.return_value = mock_response
mock_client.chat.completions.create.assert_called_once()

# ❌ Éviter - mock trop large
mock_client.return_value = "something"
```

### 7. Tests asynchrones

Toujours utiliser `@pytest.mark.asyncio` :

```python
@pytest.mark.asyncio
async def test_async_method(self):
    result = await async_method()
    assert result is not None
```

### 8. Cleanup et isolation

Les mocks sont automatiquement réinitialisés entre les tests grâce à la fixture `reset_mocks` dans conftest.py.

### 9. Tests de cas limites

N'oubliez pas de tester :
- Valeurs None
- Listes vides
- Chaînes vides
- Très grandes valeurs
- Types inattendus
- Erreurs de dépendances externes

```python
class TestEdgeCases:
    def test_with_none_value(self):
        result = process(None)
        assert result is not None

    def test_with_empty_list(self):
        result = process([])
        assert result == []

    def test_with_large_input(self):
        large_data = ["item"] * 10000
        result = process(large_data)
        assert len(result) <= 100  # Limite
```

---

## 🐛 Debugging des tests

### Tests qui échouent

```bash
# Afficher le traceback complet
pytest --tb=long

# Afficher les variables locales
pytest --tb=short --showlocals

# Mode debug interactif
pytest --pdb  # S'arrête au premier échec

# Afficher les prints
pytest -s
```

### Logging durant les tests

Les logs sont capturés par défaut. Pour les afficher :

```bash
# Afficher tous les logs
pytest --log-cli-level=DEBUG

# Logs uniquement en cas d'échec
pytest --log-level=DEBUG
```

### Tests qui freeze

```bash
# Timeout de 10 secondes par test
pytest --timeout=10
```

---

## 🔍 CI/CD Integration

### Commande CI recommandée

```bash
pytest \
  --cov=app \
  --cov-report=term-missing \
  --cov-report=xml \
  --cov-fail-under=90 \
  --maxfail=5 \
  -m "not slow"
```

Cette commande :
- Génère un rapport de coverage
- Échoue si coverage < 90%
- S'arrête après 5 échecs
- Exclut les tests lents

### GitHub Actions exemple

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run tests
      run: |
        pytest \
          --cov=app \
          --cov-report=xml \
          --cov-fail-under=90

    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        files: ./coverage.xml
```

---

## 📚 Ressources

### Documentation pytest
- [pytest.org](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)

### Philosophie de test
- Tests unitaires : Rapides, isolés, nombreux
- Tests d'intégration : Moins nombreux, plus lents, coverage de workflows
- Tests E2E : Très peu, très lents, sur environnement réel

### Pyramid de tests

```
       /\
      /  \     E2E (très peu)
     /____\
    /      \   Integration (quelques-uns)
   /________\
  /          \ Unit (beaucoup)
 /____________\
```

---

## 🤝 Contribution

### Ajouter de nouveaux tests

1. **Créer le fichier de test** dans le bon dossier (`unit/` ou `integration/`)
2. **Utiliser les fixtures existantes** dans `conftest.py`
3. **Ajouter les markers appropriés** (`@pytest.mark.unit`, etc.)
4. **Suivre la structure AAA** (Arrange-Act-Assert)
5. **Tester les cas d'erreur** en plus des cas nominaux
6. **Documenter les tests complexes** avec des docstrings

### Checklist avant commit

- [ ] Tous les tests passent : `pytest`
- [ ] Coverage maintenu : `pytest --cov=app`
- [ ] Pas de warnings : `pytest -W error`
- [ ] Code formaté : `black tests/`
- [ ] Imports triés : `isort tests/`
- [ ] Type hints valides : `mypy tests/` (si configuré)

---

## 📝 Changelog des tests

### v1.0.0 (Date actuelle)
- ✅ Suite de tests initiale complète
- ✅ 135+ tests couvrant tous les agents
- ✅ Fixtures globales dans conftest.py
- ✅ Tests unitaires pour tous les agents
- ✅ Tests d'intégration de l'orchestrateur
- ✅ Configuration pytest avec markers
- ✅ Coverage configuré (objectif 90%+)
- ✅ Documentation complète (ce README)

---

## 💡 FAQ

### Pourquoi les tests sont-ils lents ?

Les tests devraient être rapides (~10-30s pour toute la suite). Si ce n'est pas le cas :
- Utilisez `-n auto` pour paralléliser
- Exécutez uniquement les tests unitaires : `pytest -m unit`
- Vérifiez que les mocks sont bien utilisés (pas d'appels API réels)

### Comment tester une nouvelle feature ?

1. Écrivez d'abord les tests (TDD)
2. Implémentez la feature
3. Vérifiez que les tests passent
4. Vérifiez le coverage : `pytest --cov=app/path/to/new/feature.py`

### Les tests sont flaky (échecs aléatoires)

Si les tests échouent aléatoirement :
- Vérifiez les mocks (sont-ils bien réinitialisés ?)
- Utilisez `pytest-randomly` pour détecter les dépendances entre tests
- Évitez les sleeps ou timeouts arbitraires
- Utilisez `freezegun` pour les tests temporels

### Comment tester avec de vraies APIs ?

Les tests E2E avec vraies APIs doivent être :
- Marqués `@pytest.mark.slow`
- Skippés par défaut : `@pytest.mark.skip(reason="Nécessite clés API")`
- Configurables via variables d'environnement

```python
@pytest.mark.skip(reason="Nécessite OpenAI API key")
@pytest.mark.slow
async def test_real_openai():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("No API key")
    # Test avec vraie API
```

---

**🎉 Bonne chance avec vos tests !**

Pour toute question, consultez la documentation pytest ou ouvrez une issue.
