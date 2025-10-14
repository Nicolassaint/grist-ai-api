"""
Tests unitaires pour SQLAgent
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from app.agents.sql_agent import SQLAgent
from app.models.message import Message, ConversationHistory


@pytest.mark.unit
@pytest.mark.sql
@pytest.mark.asyncio
class TestSQLAgent:
    """Tests pour l'agent SQL"""

    @pytest.fixture
    def sql_agent(self, mock_openai_client, mock_schema_fetcher, mock_sql_runner):
        """Crée un SQL agent pour les tests"""
        return SQLAgent(
            mock_openai_client,
            mock_schema_fetcher,
            mock_sql_runner,
            model="gpt-3.5-turbo"
        )

    async def test_process_message_success(
        self,
        sql_agent,
        sample_user_message,
        sample_conversation_history,
        sample_document_id,
        sample_request_id,
        sample_schemas,
        sample_sql_query,
        sample_sql_results,
        mock_openai_client,
        mock_schema_fetcher,
        mock_sql_runner
    ):
        """Test: Traitement réussi d'un message"""
        # Arrange
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=f"```sql\n{sample_sql_query}\n```"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        mock_schema_fetcher.get_all_schemas.return_value = sample_schemas
        mock_sql_runner.execute_sql.return_value = sample_sql_results

        # Act
        response, sql, results = await sql_agent.process_message(
            sample_user_message,
            sample_conversation_history,
            sample_document_id,
            sample_request_id
        )

        # Assert
        assert isinstance(response, str)
        assert sql == sample_sql_query
        assert results == sample_sql_results
        assert "Voici les résultats" in response
        mock_schema_fetcher.get_all_schemas.assert_called_once()
        mock_sql_runner.execute_sql.assert_called_once()

    async def test_process_message_no_schemas(
        self,
        sql_agent,
        sample_user_message,
        sample_conversation_history,
        sample_document_id,
        sample_request_id,
        mock_schema_fetcher
    ):
        """Test: Pas de schémas disponibles"""
        # Arrange
        mock_schema_fetcher.get_all_schemas.return_value = {}

        # Act
        response, sql, results = await sql_agent.process_message(
            sample_user_message,
            sample_conversation_history,
            sample_document_id,
            sample_request_id
        )

        # Assert
        assert "ne peux pas accéder aux schémas" in response
        assert sql is None
        assert results is None

    async def test_process_message_sql_generation_failed(
        self,
        sql_agent,
        sample_user_message,
        sample_conversation_history,
        sample_document_id,
        sample_request_id,
        sample_schemas,
        mock_openai_client,
        mock_schema_fetcher
    ):
        """Test: Échec de génération SQL"""
        # Arrange
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Je ne peux pas générer de SQL"))]
        mock_openai_client.chat.completions.create.return_value = mock_response
        mock_schema_fetcher.get_all_schemas.return_value = sample_schemas

        # Act
        response, sql, results = await sql_agent.process_message(
            sample_user_message,
            sample_conversation_history,
            sample_document_id,
            sample_request_id
        )

        # Assert
        assert "n'ai pas pu générer" in response
        assert sql is None
        assert results is None

    async def test_process_message_sql_execution_error(
        self,
        sql_agent,
        sample_user_message,
        sample_conversation_history,
        sample_document_id,
        sample_request_id,
        sample_schemas,
        sample_sql_query,
        mock_openai_client,
        mock_schema_fetcher,
        mock_sql_runner
    ):
        """Test: Erreur d'exécution SQL"""
        # Arrange
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=f"```sql\n{sample_sql_query}\n```"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        mock_schema_fetcher.get_all_schemas.return_value = sample_schemas
        mock_sql_runner.execute_sql.return_value = {
            "success": False,
            "error": "Invalid SQL syntax"
        }

        # Act
        response, sql, results = await sql_agent.process_message(
            sample_user_message,
            sample_conversation_history,
            sample_document_id,
            sample_request_id
        )

        # Assert
        assert "elle a produit une erreur" in response
        assert sql == sample_sql_query
        assert results["success"] is False

    async def test_process_message_no_results(
        self,
        sql_agent,
        sample_user_message,
        sample_conversation_history,
        sample_document_id,
        sample_request_id,
        sample_schemas,
        sample_sql_query,
        mock_openai_client,
        mock_schema_fetcher,
        mock_sql_runner
    ):
        """Test: Requête SQL retourne 0 résultats"""
        # Arrange
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=f"```sql\n{sample_sql_query}\n```"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        mock_schema_fetcher.get_all_schemas.return_value = sample_schemas
        mock_sql_runner.execute_sql.return_value = {
            "success": True,
            "data": [],
            "row_count": 0,
            "columns": []
        }

        # Act
        response, sql, results = await sql_agent.process_message(
            sample_user_message,
            sample_conversation_history,
            sample_document_id,
            sample_request_id
        )

        # Assert
        assert "Aucune donnée ne correspond" in response
        assert "Suggestions" in response
        assert sql == sample_sql_query
        assert results["row_count"] == 0

    async def test_generate_sql_query_success(
        self,
        sql_agent,
        sample_user_message,
        sample_conversation_history,
        sample_schemas,
        sample_request_id,
        sample_sql_query,
        mock_openai_client
    ):
        """Test: Génération SQL réussie"""
        # Arrange
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=f"```sql\n{sample_sql_query}\n```\nExplication: Test"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await sql_agent._generate_sql_query(
            sample_user_message,
            sample_conversation_history,
            sample_schemas,
            sample_request_id
        )

        # Assert
        assert result == sample_sql_query
        mock_openai_client.chat.completions.create.assert_called_once()

    async def test_generate_sql_query_with_context(
        self,
        sql_agent,
        sample_request_id,
        sample_schemas,
        sample_sql_query,
        mock_openai_client
    ):
        """Test: Génération SQL avec contexte conversationnel"""
        # Arrange
        conversation = ConversationHistory(messages=[
            Message(role="user", content="Bonjour"),
            Message(role="assistant", content="Bonjour!"),
            Message(role="user", content="Montre les clients"),
        ])

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=f"```sql\n{sample_sql_query}\n```"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await sql_agent._generate_sql_query(
            "Montre les clients",
            conversation,
            sample_schemas,
            sample_request_id
        )

        # Assert
        assert result == sample_sql_query
        # Vérifier que le contexte a été inclus dans le prompt
        call_args = mock_openai_client.chat.completions.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert "CONTEXTE CONVERSATIONNEL" in prompt

    async def test_generate_sql_query_openai_error(
        self,
        sql_agent,
        sample_user_message,
        sample_conversation_history,
        sample_schemas,
        sample_request_id,
        mock_openai_client
    ):
        """Test: Erreur API OpenAI"""
        # Arrange
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

        # Act
        result = await sql_agent._generate_sql_query(
            sample_user_message,
            sample_conversation_history,
            sample_schemas,
            sample_request_id
        )

        # Assert
        assert result is None

    def test_extract_sql_from_response_code_block(self, sql_agent):
        """Test: Extraction SQL depuis un bloc de code"""
        # Arrange
        response = """Voici la requête:
```sql
SELECT * FROM Clients WHERE age > 25
```
Explication: Cette requête..."""

        # Act
        result = sql_agent._extract_sql_from_response(response)

        # Assert
        assert result == "SELECT * FROM Clients WHERE age > 25"

    def test_extract_sql_from_response_select_only(self, sql_agent):
        """Test: Extraction SQL simple (fallback)"""
        # Arrange
        response = "Utilisez cette requête: SELECT nom, email FROM Clients LIMIT 10"

        # Act
        result = sql_agent._extract_sql_from_response(response)

        # Assert
        assert result == "SELECT nom, email FROM Clients LIMIT 10"

    def test_extract_sql_from_response_no_sql(self, sql_agent):
        """Test: Pas de SQL dans la réponse"""
        # Arrange
        response = "Désolé, je ne peux pas générer de SQL pour cette requête."

        # Act
        result = sql_agent._extract_sql_from_response(response)

        # Assert
        assert result is None

    def test_extract_sql_case_insensitive(self, sql_agent):
        """Test: Extraction SQL insensible à la casse"""
        # Arrange
        response = """```SQL
select name from users
```"""

        # Act
        result = sql_agent._extract_sql_from_response(response)

        # Assert
        assert result == "select name from users"

    def test_format_sql_response_success(self, sql_agent, sample_sql_query, mock_sql_runner):
        """Test: Formatage réponse SQL réussie"""
        # Arrange
        sql_results = {
            "success": True,
            "row_count": 5,
            "data": [{"nom": "Test"}]
        }
        mock_sql_runner.format_results_for_analysis.return_value = "Résultats formatés"

        # Act
        result = sql_agent._format_sql_response(
            sample_sql_query,
            sql_results,
            "Test question"
        )

        # Assert
        assert "Voici les résultats" in result
        assert "5 lignes" in result
        assert sample_sql_query in result
        assert "Résultats formatés" in result

    def test_format_sql_response_error(self, sql_agent, sample_sql_query):
        """Test: Formatage réponse SQL avec erreur"""
        # Arrange
        sql_results = {
            "success": False,
            "error": "Syntax error"
        }

        # Act
        result = sql_agent._format_sql_response(
            sample_sql_query,
            sql_results,
            "Test question"
        )

        # Assert
        assert "elle a produit une erreur" in result
        assert "Syntax error" in result
        assert sample_sql_query in result

    def test_format_sql_response_no_results(self, sql_agent, sample_sql_query):
        """Test: Formatage réponse SQL sans résultats"""
        # Arrange
        sql_results = {
            "success": True,
            "row_count": 0,
            "data": []
        }

        # Act
        result = sql_agent._format_sql_response(
            sample_sql_query,
            sql_results,
            "Test question"
        )

        # Assert
        assert "Aucune donnée ne correspond" in result
        assert "Suggestions" in result
        assert sample_sql_query in result

    def test_format_sql_response_single_row(self, sql_agent, sample_sql_query, mock_sql_runner):
        """Test: Formatage avec 1 seul résultat (singulier)"""
        # Arrange
        sql_results = {
            "success": True,
            "row_count": 1,
            "data": [{"nom": "Test"}]
        }
        mock_sql_runner.format_results_for_analysis.return_value = "1 résultat"

        # Act
        result = sql_agent._format_sql_response(
            sample_sql_query,
            sql_results,
            "Test"
        )

        # Assert
        assert "(1 ligne)" in result  # Singulier
        assert "lignes" not in result or "(1 ligne)" in result  # Pas de pluriel

    def test_suggest_improvements(self, sql_agent, sample_schemas):
        """Test: Suggestions d'amélioration"""
        # Act
        result = sql_agent._suggest_improvements("Montre les données", sample_schemas)

        # Assert
        assert "tables disponibles" in result
        assert "Clients" in result
        assert "Commandes" in result
        assert "Exemple" in result

    @pytest.mark.parametrize("sql_response,expected_extracted", [
        ("```sql\nSELECT * FROM T\n```", "SELECT * FROM T"),
        ("SELECT id FROM users WHERE active = 1", "SELECT id FROM users WHERE active = 1"),
        ("Pas de SQL ici", None),
        ("```SQL\nselect name\n```", "select name"),
    ])
    def test_extract_sql_parametrized(self, sql_agent, sql_response, expected_extracted):
        """Test: Extraction SQL paramétrée"""
        result = sql_agent._extract_sql_from_response(sql_response)
        assert result == expected_extracted


@pytest.mark.unit
@pytest.mark.sql
class TestSQLAgentEdgeCases:
    """Tests des cas limites pour SQLAgent"""

    @pytest.fixture
    def sql_agent(self, mock_openai_client, mock_schema_fetcher, mock_sql_runner):
        return SQLAgent(
            mock_openai_client,
            mock_schema_fetcher,
            mock_sql_runner,
            model="gpt-3.5-turbo"
        )

    def test_extract_sql_multiline(self, sql_agent):
        """Test: Extraction SQL multi-lignes"""
        response = """```sql
SELECT
    clients.nom,
    COUNT(commandes.id) as nb_commandes
FROM Clients clients
LEFT JOIN Commandes commandes ON clients.id = commandes.client_id
GROUP BY clients.nom
ORDER BY nb_commandes DESC
```"""

        result = sql_agent._extract_sql_from_response(response)

        assert "SELECT" in result
        assert "GROUP BY" in result
        assert "ORDER BY" in result

    def test_extract_sql_multiple_blocks(self, sql_agent):
        """Test: Plusieurs blocs SQL (prend le premier)"""
        response = """```sql
SELECT * FROM Table1
```
Et aussi:
```sql
SELECT * FROM Table2
```"""

        result = sql_agent._extract_sql_from_response(response)

        assert result == "SELECT * FROM Table1"

    def test_format_sql_response_very_large_results(self, sql_agent, mock_sql_runner):
        """Test: Formatage avec beaucoup de résultats"""
        sql_results = {
            "success": True,
            "row_count": 10000,
            "data": [{"id": i} for i in range(10000)]
        }
        mock_sql_runner.format_results_for_analysis.return_value = "10000 résultats"

        result = sql_agent._format_sql_response("SELECT * FROM T", sql_results, "Test")

        assert "10000 lignes" in result
