"""
Tests unitaires pour SQLAgent - Version simple
"""
import pytest
from unittest.mock import Mock, AsyncMock
from app.agents.sql_agent import SQLAgent


@pytest.mark.unit
@pytest.mark.asyncio 
class TestSQLAgentBasic:
    """Tests basiques pour SQLAgent"""

    @pytest.fixture
    def sql_agent(self, mock_openai_client, mock_schema_fetcher, mock_sql_runner, mock_sample_fetcher):
        """Crée un SQL agent pour les tests"""
        return SQLAgent(
            openai_client=mock_openai_client,
            schema_fetcher=mock_schema_fetcher,
            sql_runner=mock_sql_runner,
            sample_fetcher=mock_sample_fetcher
        )

    def test_initialization(self, sql_agent, mock_openai_client, mock_schema_fetcher, mock_sql_runner, mock_sample_fetcher):
        """Test: Initialisation correcte"""
        assert sql_agent.client == mock_openai_client
        assert sql_agent.schema_fetcher == mock_schema_fetcher
        assert sql_agent.sql_runner == mock_sql_runner
        assert sql_agent.sample_fetcher == mock_sample_fetcher
        assert sql_agent.model == "gpt-4"

    def test_extract_sql_from_response_code_block(self, sql_agent):
        """Test: Extraction SQL depuis bloc de code"""
        ai_response = """Voici votre requête:
        
```sql
SELECT nom, age FROM Clients WHERE age > 25
```

Cette requête récupère..."""

        result = sql_agent._extract_sql_from_response(ai_response)
        
        assert result == "SELECT nom, age FROM Clients WHERE age > 25"

    def test_extract_sql_from_response_fallback(self, sql_agent):
        """Test: Extraction SQL fallback sans bloc de code"""
        ai_response = """Je recommande cette requête:
        
SELECT COUNT(*) FROM Commandes

Elle compte le nombre total de commandes."""

        result = sql_agent._extract_sql_from_response(ai_response)
        
        assert result == "SELECT COUNT(*) FROM Commandes"

    def test_extract_sql_from_response_none(self, sql_agent):
        """Test: Aucune requête SQL trouvée"""
        ai_response = "Je ne peux pas générer de requête pour cette demande."

        result = sql_agent._extract_sql_from_response(ai_response)
        
        assert result is None

    def test_format_successful_sql_response_with_data(self, sql_agent, mock_sql_runner):
        """Test: Formatage de réponse avec données"""
        sql_query = "SELECT nom FROM Clients"
        sql_results = {
            "success": True,
            "data": [{"nom": "Dupont"}, {"nom": "Martin"}],
            "columns": ["nom"],
            "row_count": 2
        }
        
        mock_sql_runner.format_results_for_analysis.return_value = "Dupont\nMartin"

        result = sql_agent._format_successful_sql_response(sql_query, sql_results)

        assert "Voici les résultats" in result
        assert "2 lignes" in result
        assert "SELECT nom FROM Clients" in result
        assert "Dupont" in result

    def test_format_successful_sql_response_empty(self, sql_agent):
        """Test: Formatage de réponse avec résultats vides"""
        sql_query = "SELECT * FROM Clients WHERE age > 100"
        sql_results = {
            "success": True,
            "data": [],
            "columns": ["nom", "age"],
            "row_count": 0
        }

        result = sql_agent._format_successful_sql_response(sql_query, sql_results)

        assert "Aucune donnée ne correspond" in result
        assert "Suggestions" in result
        assert sql_query in result

    def test_sql_prompt_template_content(self, sql_agent):
        """Test: Contenu du template de prompt SQL"""
        template = sql_agent.sql_prompt_template

        assert "Tu es un expert SQL" in template
        assert "SCHÉMAS DISPONIBLES" in template
        assert "CAST" in template  # Instructions de conversion de type
        assert "SELECT" in template
        assert "HISTORIQUE DE CONVERSATION" in template