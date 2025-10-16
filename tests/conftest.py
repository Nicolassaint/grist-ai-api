"""
Configuration globale et fixtures pour les tests pytest
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any, List
import openai


# ========== CONFIGURATION PYTEST ==========


@pytest.fixture(scope="session")
def event_loop():
    """Crée un event loop pour toute la session de tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ========== FIXTURES GÉNÉRALES ==========


@pytest.fixture
def sample_user_message():
    """Message utilisateur simple pour les tests"""
    return "Montre-moi les ventes du mois dernier"


@pytest.fixture
def sample_request_id():
    """ID de requête pour les tests"""
    return "test-request-123"


@pytest.fixture
def sample_document_id():
    """ID de document Grist pour les tests"""
    return "test-doc-456"


# ========== FIXTURES GRIST ==========


@pytest.fixture
def sample_table_schema():
    """Schéma de table Grist simple pour les tests"""
    return {
        "table_id": "Clients",
        "columns": [
            {
                "id": "A",
                "label": "nom",
                "type": "Text",
                "formula": "",
                "description": "Nom du client",
            },
            {
                "id": "B",
                "label": "email",
                "type": "Text",
                "formula": "",
                "description": "Email du client",
            },
            {
                "id": "C",
                "label": "telephone",
                "type": "Text",
                "formula": "",
                "description": "",
            },
            {
                "id": "D",
                "label": "age",
                "type": "Numeric",
                "formula": "",
                "description": "Âge en années",
            },
        ],
    }


@pytest.fixture
def sample_schemas():
    """Ensemble de schémas Grist pour les tests"""
    return {
        "Clients": {
            "table_id": "Clients",
            "columns": [
                {
                    "id": "A",
                    "label": "nom",
                    "type": "Text",
                    "formula": "",
                    "description": "",
                },
                {
                    "id": "B",
                    "label": "email",
                    "type": "Text",
                    "formula": "",
                    "description": "",
                },
                {
                    "id": "C",
                    "label": "date_creation",
                    "type": "Date",
                    "formula": "",
                    "description": "",
                },
            ],
        },
        "Commandes": {
            "table_id": "Commandes",
            "columns": [
                {
                    "id": "A",
                    "label": "client_id",
                    "type": "Reference",
                    "formula": "$Clients",
                    "description": "",
                },
                {
                    "id": "B",
                    "label": "date",
                    "type": "Date",
                    "formula": "",
                    "description": "",
                },
                {
                    "id": "C",
                    "label": "montant",
                    "type": "Numeric",
                    "formula": "",
                    "description": "",
                },
                {
                    "id": "D",
                    "label": "montant_ttc",
                    "type": "Numeric",
                    "formula": "$montant * 1.2",
                    "description": "",
                },
            ],
        },
        "Produits": {
            "table_id": "Produits",
            "columns": [
                {
                    "id": "A",
                    "label": "nom",
                    "type": "Text",
                    "formula": "",
                    "description": "",
                },
                {
                    "id": "B",
                    "label": "prix",
                    "type": "Numeric",
                    "formula": "",
                    "description": "",
                },
                {
                    "id": "C",
                    "label": "stock",
                    "type": "Integer",
                    "formula": "",
                    "description": "",
                },
            ],
        },
    }


@pytest.fixture
def sample_sql_results():
    """Résultats SQL simulés pour les tests"""
    return {
        "success": True,
        "data": [
            {"nom": "Dupont", "email": "dupont@mail.com", "age": 35},
            {"nom": "Martin", "email": "martin@mail.com", "age": 42},
            {"nom": "Bernard", "email": "bernard@mail.com", "age": 28},
        ],
        "columns": ["nom", "email", "age"],
        "row_count": 3,
    }


@pytest.fixture
def sample_sql_query():
    """Requête SQL simulée pour les tests"""
    return (
        "SELECT nom, email, age FROM Clients WHERE age > 25 ORDER BY age DESC LIMIT 10"
    )


# ========== MOCKS OPENAI ==========


@pytest.fixture
def mock_openai_client():
    """Mock du client OpenAI"""
    mock_client = MagicMock(spec=openai.AsyncOpenAI)

    # Mock de la réponse chat.completions.create
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Réponse simulée de l'IA"))
    ]

    # Créer la structure hiérarchique chat.completions.create
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    return mock_client


@pytest.fixture
def mock_openai_router_response():
    """Mock de réponse du router agent"""

    def _create_response(agent_type: str = "SQL"):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=agent_type))]
        return mock_response

    return _create_response


# ========== MOCKS GRIST ==========


@pytest.fixture
def mock_schema_fetcher(sample_schemas):
    """Mock du GristSchemaFetcher"""
    from app.grist.schema_fetcher import GristSchemaFetcher

    mock_fetcher = AsyncMock(spec=GristSchemaFetcher)
    mock_fetcher.get_all_schemas = AsyncMock(return_value=sample_schemas)
    mock_fetcher.get_document_tables = AsyncMock(
        return_value=list(sample_schemas.keys())
    )
    mock_fetcher.get_table_schema = AsyncMock(
        side_effect=lambda doc_id, table_id, req_id: sample_schemas.get(table_id)
    )
    mock_fetcher.format_schema_for_prompt = Mock(return_value="Schémas formatés")

    return mock_fetcher


@pytest.fixture
def mock_sql_runner(sample_sql_results, sample_sql_query):
    """Mock du GristSQLRunner"""
    from app.grist.sql_runner import GristSQLRunner

    mock_runner = AsyncMock(spec=GristSQLRunner)
    mock_runner.execute_sql = AsyncMock(return_value=sample_sql_results)
    mock_runner.validate_sql_query = Mock(return_value=(True, "Valid"))
    mock_runner.format_results_for_analysis = Mock(return_value="Résultats formatés")

    return mock_runner


# ========== FIXTURES AGENTS ==========


@pytest.fixture
def mock_router_agent():
    """Mock du RouterAgent"""
    from app.agents.router_agent import RouterAgent
    from app.pipeline.plans import ExecutionPlan, AgentType

    mock_agent = AsyncMock(spec=RouterAgent)

    # Mock du plan retourné
    mock_plan = ExecutionPlan(
        name="data_query",
        agents=[AgentType.SQL, AgentType.ANALYSIS],
        description="Test plan",
        requires_api_key=True,
    )
    mock_agent.route_to_plan = AsyncMock(return_value=mock_plan)

    return mock_agent


@pytest.fixture
def mock_generic_agent():
    """Mock du GenericAgent"""
    from app.agents.generic_agent import GenericAgent

    mock_agent = AsyncMock(spec=GenericAgent)
    mock_agent.process_message = AsyncMock(
        return_value="Bonjour! Comment puis-je vous aider?"
    )

    return mock_agent


@pytest.fixture
def mock_sql_agent(sample_sql_query, sample_sql_results):
    """Mock du SQLAgent"""
    from app.agents.sql_agent import SQLAgent

    mock_agent = AsyncMock(spec=SQLAgent)
    mock_agent.process_message = AsyncMock(
        return_value=("Réponse SQL", sample_sql_query, sample_sql_results)
    )

    return mock_agent


@pytest.fixture
def mock_analysis_agent():
    """Mock de l'AnalysisAgent"""
    from app.agents.analysis_agent import AnalysisAgent

    mock_agent = AsyncMock(spec=AnalysisAgent)
    mock_agent.process_message = AsyncMock(
        return_value="Analyse des données: tendance à la hausse"
    )

    return mock_agent


@pytest.fixture
def mock_architecture_agent():
    """Mock du DataArchitectureAgent"""
    from app.agents.architecture_agent import DataArchitectureAgent
    from app.models.architecture import ArchitectureAnalysis, ArchitectureMetrics

    mock_agent = AsyncMock(spec=DataArchitectureAgent)

    # Créer une analyse simulée
    mock_analysis = ArchitectureAnalysis(
        document_id="test-doc",
        user_question="Analyse ma structure",
        schemas={"Clients": {"columns": []}},
        metrics=ArchitectureMetrics(
            total_tables=3,
            total_columns=10,
            avg_columns_per_table=3.3,
            total_relationships=2,
        ),
        recommendations=["Améliorer la normalisation"],
    )

    mock_agent.analyze_document_structure = AsyncMock(return_value=mock_analysis)

    return mock_agent


# ========== FIXTURES MESSAGES ==========


@pytest.fixture
def sample_conversation_history():
    """Historique de conversation simulé"""
    from app.models.message import Message, ConversationHistory

    messages = [
        Message(role="user", content="Bonjour"),
        Message(role="assistant", content="Bonjour! Comment puis-je vous aider?"),
        Message(role="user", content="Montre-moi les ventes"),
    ]

    return ConversationHistory(messages=messages)


@pytest.fixture
def sample_processed_request(sample_document_id, sample_conversation_history):
    """Requête traitée simulée"""
    from app.models.request import ProcessedRequest

    return ProcessedRequest(
        document_id=sample_document_id,
        messages=sample_conversation_history.messages,
        grist_api_key="test-api-key-123",
        execution_mode="test",
        webhook_url="http://test-webhook.com/callback",
    )


# ========== FIXTURES COMPLEXES ==========


@pytest.fixture
def complex_schemas_with_issues():
    """Schémas complexes avec des problèmes intentionnels pour tester l'architecture agent"""
    return {
        "TableTropLarge": {
            "table_id": "TableTropLarge",
            "columns": [
                {
                    "id": f"col{i}",
                    "label": f"column_{i}",
                    "type": "Text",
                    "formula": "",
                    "description": "",
                }
                for i in range(25)  # 25 colonnes = trop large
            ],
        },
        "TableIsolee": {
            "table_id": "TableIsolee",
            "columns": [
                {
                    "id": "A",
                    "label": "data",
                    "type": "Text",
                    "formula": "",
                    "description": "",
                },
            ],
        },
        "Table Mal Nommée": {  # Espace dans le nom
            "table_id": "Table Mal Nommée",
            "columns": [
                {
                    "id": "A",
                    "label": "col1",
                    "type": "Any",
                    "formula": "",
                    "description": "",
                },  # Type Any
            ],
        },
    }


# ========== HELPERS ==========


@pytest.fixture
def assert_async_called_with():
    """Helper pour vérifier les appels de mocks async"""

    def _assert(mock_func, *args, **kwargs):
        mock_func.assert_called_once()
        actual_args, actual_kwargs = mock_func.call_args
        assert actual_args == args
        for key, value in kwargs.items():
            assert actual_kwargs[key] == value

    return _assert


# ========== NETTOYAGE ==========


@pytest.fixture(autouse=True)
def reset_mocks(mocker):
    """Reset automatique des mocks entre les tests"""
    yield
    mocker.resetall()
