"""
Tests unitaires pour AnalysisAgent
"""
import pytest
from unittest.mock import Mock, AsyncMock
from app.agents.analysis_agent import AnalysisAgent
from app.models.message import Message, ConversationHistory


@pytest.mark.unit
@pytest.mark.asyncio
class TestAnalysisAgent:
    """Tests pour l'agent d'analyse"""

    @pytest.fixture
    def analysis_agent(self, mock_openai_client):
        """Crée un analysis agent pour les tests"""
        return AnalysisAgent(mock_openai_client, model="gpt-4")

    async def test_process_message_success(
        self,
        analysis_agent,
        sample_user_message,
        sample_conversation_history,
        sample_request_id,
        sample_sql_query,
        sample_sql_results,
        mock_openai_client
    ):
        """Test: Traitement réussi avec données"""
        # Arrange
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Analyse: Les clients ont un âge moyen de 35 ans."))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await analysis_agent.process_message(
            sample_user_message,
            sample_conversation_history,
            sample_sql_query,
            sample_sql_results,
            sample_request_id
        )

        # Assert
        assert isinstance(result, str)
        assert "Analyse" in result or "âge" in result
        mock_openai_client.chat.completions.create.assert_called_once()

    async def test_process_message_sql_error(
        self,
        analysis_agent,
        sample_user_message,
        sample_conversation_history,
        sample_request_id,
        sample_sql_query
    ):
        """Test: Gestion erreur SQL"""
        # Arrange
        sql_results = {
            "success": False,
            "error": "Invalid SQL syntax"
        }

        # Act
        result = await analysis_agent.process_message(
            sample_user_message,
            sample_conversation_history,
            sample_sql_query,
            sql_results,
            sample_request_id
        )

        # Assert
        assert "Erreur" in result
        assert "Invalid SQL syntax" in result

    async def test_process_message_empty_results(
        self,
        analysis_agent,
        sample_user_message,
        sample_conversation_history,
        sample_request_id,
        sample_sql_query
    ):
        """Test: Résultats vides (cas normal)"""
        # Arrange
        sql_results = {
            "success": True,
            "data": [],
            "row_count": 0,
            "columns": []
        }

        # Act
        result = await analysis_agent.process_message(
            sample_user_message,
            sample_conversation_history,
            sample_sql_query,
            sql_results,
            sample_request_id
        )

        # Assert
        assert "aucune donnée" in result or "n'a retourné aucune donnée" in result
        assert "Suggestions" in result

    async def test_process_message_openai_error(
        self,
        analysis_agent,
        sample_user_message,
        sample_conversation_history,
        sample_request_id,
        sample_sql_query,
        sample_sql_results,
        mock_openai_client
    ):
        """Test: Erreur API OpenAI -> fallback"""
        # Arrange
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

        # Act
        result = await analysis_agent.process_message(
            sample_user_message,
            sample_conversation_history,
            sample_sql_query,
            sample_sql_results,
            sample_request_id
        )

        # Assert
        assert isinstance(result, str)
        # Le fallback peut retourner "Aucune donnée trouvée" ou "résultats"
        assert "donnée" in result.lower() or "résultat" in result.lower()

    async def test_generate_analysis_success(
        self,
        analysis_agent,
        sample_user_message,
        sample_conversation_history,
        sample_request_id,
        sample_sql_query,
        mock_openai_client
    ):
        """Test: Génération d'analyse réussie"""
        # Arrange
        formatted_results = "| nom | age |\n| --- | --- |\n| Dupont | 35 |"
        numeric_summary = "Total: 3 lignes"

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Analyse claire des données."))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await analysis_agent._generate_analysis(
            sample_user_message,
            sample_conversation_history,
            sample_sql_query,
            formatted_results,
            numeric_summary,
            sample_request_id
        )

        # Assert
        assert "Analyse" in result
        assert isinstance(result, str)

    def test_format_data_for_analysis_with_data(self, analysis_agent, sample_sql_results):
        """Test: Formatage de données SQL"""
        # Act
        result = analysis_agent._format_data_for_analysis(sample_sql_results)

        # Assert
        assert isinstance(result, str)
        assert "3 lignes" in result  # Row count
        assert "|" in result  # Table format
        assert "nom" in result
        assert "email" in result
        assert "Dupont" in result

    def test_format_data_for_analysis_no_data(self, analysis_agent):
        """Test: Formatage sans données"""
        # Arrange
        empty_results = {"success": True, "data": [], "columns": []}

        # Act
        result = analysis_agent._format_data_for_analysis(empty_results)

        # Assert
        assert "Aucune donnée disponible" in result

    def test_format_data_for_analysis_limits_rows(self, analysis_agent):
        """Test: Limitation à 20 lignes"""
        # Arrange
        large_results = {
            "success": True,
            "data": [{"id": i} for i in range(50)],
            "columns": ["id"]
        }

        # Act
        result = analysis_agent._format_data_for_analysis(large_results)

        # Assert
        assert "50 lignes" in result
        assert "et 30 autres lignes" in result  # 50 - 20

    def test_format_data_for_analysis_truncates_long_values(self, analysis_agent):
        """Test: Troncature des valeurs longues"""
        # Arrange
        results = {
            "success": True,
            "data": [{"description": "A" * 100}],
            "columns": ["description"]
        }

        # Act
        result = analysis_agent._format_data_for_analysis(results)

        # Assert
        assert "..." in result  # Valeur tronquée

    def test_generate_numeric_summary_with_numeric_data(self, analysis_agent):
        """Test: Résumé numérique avec données numériques"""
        # Arrange
        sql_results = {
            "success": True,
            "data": [
                {"age": 25, "score": 80},
                {"age": 35, "score": 90},
                {"age": 45, "score": 85},
            ],
            "columns": ["age", "score"]
        }

        # Act
        result = analysis_agent._generate_numeric_summary(sql_results)

        # Assert
        assert "Total des lignes: 3" in result
        assert "age:" in result
        assert "score:" in result
        assert "Total=" in result
        assert "Moyenne=" in result
        assert "Min=" in result
        assert "Max=" in result

    def test_generate_numeric_summary_no_numeric_data(self, analysis_agent):
        """Test: Résumé sans données numériques"""
        # Arrange
        sql_results = {
            "success": True,
            "data": [{"nom": "Dupont"}, {"nom": "Martin"}],
            "columns": ["nom"]
        }

        # Act
        result = analysis_agent._generate_numeric_summary(sql_results)

        # Assert
        assert "Total des lignes: 2" in result
        # Pas de stats pour les colonnes non-numériques

    def test_generate_numeric_summary_empty_results(self, analysis_agent):
        """Test: Résumé avec résultats vides"""
        # Arrange
        sql_results = {"success": True, "data": [], "columns": []}

        # Act
        result = analysis_agent._generate_numeric_summary(sql_results)

        # Assert
        assert "Aucune donnée numérique disponible" in result

    def test_handle_sql_error(self, analysis_agent):
        """Test: Gestion des erreurs SQL"""
        # Arrange
        sql_results = {
            "success": False,
            "error": "Table not found"
        }

        # Act
        result = analysis_agent._handle_sql_error("Test question", sql_results)

        # Assert
        assert "Erreur" in result
        assert "Table not found" in result
        assert "Suggestions" in result

    def test_handle_empty_results(self, analysis_agent, sample_sql_query):
        """Test: Gestion des résultats vides"""
        # Act
        result = analysis_agent._handle_empty_results("Test question", sample_sql_query)

        # Assert
        assert "aucune donnée" in result or "n'a retourné aucune donnée" in result
        assert "Suggestions" in result
        assert "C'est normal" in result

    def test_get_fallback_analysis_no_data(self, analysis_agent):
        """Test: Analyse de secours sans données"""
        # Arrange
        sql_results = {"data": []}

        # Act
        result = analysis_agent._get_fallback_analysis("Test", sql_results)

        # Assert
        assert "Aucune donnée trouvée" in result

    def test_get_fallback_analysis_with_data(self, analysis_agent, sample_sql_results):
        """Test: Analyse de secours avec données"""
        # Act
        result = analysis_agent._get_fallback_analysis("Test", sample_sql_results)

        # Assert
        assert "3 résultats" in result
        assert "ne peux pas les analyser" in result


@pytest.mark.unit
class TestAnalysisAgentConfiguration:
    """Tests de configuration pour AnalysisAgent"""

    def test_initialization_with_defaults(self, mock_openai_client):
        """Test: Initialisation avec valeurs par défaut"""
        agent = AnalysisAgent(mock_openai_client)

        assert agent.client == mock_openai_client
        assert agent.model == "gpt-4"
        assert agent.analysis_prompt_template is not None

    def test_initialization_with_custom_model(self, mock_openai_client):
        """Test: Initialisation avec modèle personnalisé"""
        agent = AnalysisAgent(mock_openai_client, model="gpt-3.5-turbo")

        assert agent.model == "gpt-3.5-turbo"

    def test_prompt_template_content(self, mock_openai_client):
        """Test: Contenu du template de prompt"""
        agent = AnalysisAgent(mock_openai_client)

        assert "COURTE" in agent.analysis_prompt_template
        assert "DIRECTE" in agent.analysis_prompt_template
        assert "1-2 phrases" in agent.analysis_prompt_template

    @pytest.mark.asyncio
    async def test_openai_call_parameters(
        self,
        mock_openai_client,
        sample_user_message,
        sample_conversation_history,
        sample_request_id,
        sample_sql_query,
        sample_sql_results
    ):
        """Test: Paramètres de l'appel OpenAI"""
        agent = AnalysisAgent(mock_openai_client)

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        await agent.process_message(
            sample_user_message,
            sample_conversation_history,
            sample_sql_query,
            sample_sql_results,
            sample_request_id
        )

        # Vérifier les paramètres
        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["max_tokens"] == 100
        assert call_kwargs["temperature"] == 0.1


@pytest.mark.unit
class TestAnalysisAgentEdgeCases:
    """Tests des cas limites pour AnalysisAgent"""

    @pytest.fixture
    def analysis_agent(self, mock_openai_client):
        return AnalysisAgent(mock_openai_client)

    def test_format_data_handles_missing_columns(self, analysis_agent):
        """Test: Données sans colonne spécifiée"""
        results = {
            "success": True,
            "data": [{"a": 1, "b": 2}],
            "columns": ["a", "b", "c"]  # c n'existe pas
        }

        result = analysis_agent._format_data_for_analysis(results)

        assert isinstance(result, str)
        # Ne doit pas crasher avec colonne manquante

    def test_numeric_summary_handles_mixed_types(self, analysis_agent):
        """Test: Colonnes avec types mixtes"""
        sql_results = {
            "success": True,
            "data": [
                {"value": 10},
                {"value": "not a number"},
                {"value": 20},
            ],
            "columns": ["value"]
        }

        result = analysis_agent._generate_numeric_summary(sql_results)

        assert "Total des lignes: 3" in result
        # Doit gérer les valeurs non-numériques

    def test_format_data_with_none_values(self, analysis_agent):
        """Test: Données avec valeurs None"""
        results = {
            "success": True,
            "data": [{"name": None, "age": 25}],
            "columns": ["name", "age"]
        }

        result = analysis_agent._format_data_for_analysis(results)

        assert isinstance(result, str)
        # Ne doit pas crasher avec None

    def test_numeric_summary_calculates_correctly(self, analysis_agent):
        """Test: Calculs numériques corrects"""
        sql_results = {
            "success": True,
            "data": [
                {"score": 10},
                {"score": 20},
                {"score": 30},
            ],
            "columns": ["score"]
        }

        result = analysis_agent._generate_numeric_summary(sql_results)

        assert "Total=60.00" in result  # 10 + 20 + 30
        assert "Moyenne=20.00" in result  # 60 / 3
        assert "Min=10.00" in result
        assert "Max=30.00" in result

    @pytest.mark.asyncio
    async def test_process_message_strips_whitespace(
        self,
        analysis_agent,
        sample_user_message,
        sample_conversation_history,
        sample_request_id,
        sample_sql_query,
        sample_sql_results,
        mock_openai_client
    ):
        """Test: Les espaces en trop sont supprimés"""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="  Analyse avec espaces  "))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await analysis_agent.process_message(
            sample_user_message,
            sample_conversation_history,
            sample_sql_query,
            sample_sql_results,
            sample_request_id
        )

        assert result == "Analyse avec espaces"

    def test_handle_sql_error_without_error_message(self, analysis_agent):
        """Test: Erreur SQL sans message d'erreur"""
        sql_results = {"success": False}

        result = analysis_agent._handle_sql_error("Test", sql_results)

        assert "Erreur" in result
        assert "Erreur SQL inconnue" in result
