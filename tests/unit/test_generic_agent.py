"""
Tests unitaires pour GenericAgent - Version corrigée
"""
import pytest
from unittest.mock import Mock, AsyncMock
from app.agents.generic_agent import GenericAgent
from app.models.message import Message, ConversationHistory


@pytest.mark.unit
@pytest.mark.asyncio
class TestGenericAgent:
    """Tests pour l'agent générique"""

    @pytest.fixture
    def generic_agent(self, mock_openai_client):
        """Crée un generic agent pour les tests"""
        return GenericAgent(mock_openai_client, model="gpt-3.5-turbo")

    async def test_process_message_success(
        self,
        generic_agent,
        mock_execution_context,
        mock_openai_client,
    ):
        """Test: Traitement réussi d'un message normal"""
        # Arrange
        mock_execution_context.user_message = "Bonjour, comment ça va ?"
        mock_execution_context.error = None  # Pas d'erreur
        
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Bonjour! Je vais bien, merci."))
        ]
        mock_response.usage = Mock(total_tokens=50)
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await generic_agent.process_message(mock_execution_context)

        # Assert
        assert isinstance(result, str)
        assert "Bonjour" in result
        mock_openai_client.chat.completions.create.assert_called_once()

    async def test_process_message_sql_error_fallback(
        self,
        generic_agent,
        mock_execution_context,
    ):
        """Test: Fallback pour erreur SQL"""
        # Arrange
        mock_execution_context.user_message = "Montre-moi les ventes"
        mock_execution_context.error = "Permission denied"
        mock_execution_context.agent_used = "sql"

        # Act
        result = await generic_agent.process_message(mock_execution_context)

        # Assert
        assert isinstance(result, str)
        assert "Permission denied" in result
        assert "Vérifier vos permissions" in result
        assert "Reformuler votre question" in result

    async def test_process_message_architecture_error_fallback(
        self,
        generic_agent,
        mock_execution_context,
    ):
        """Test: Fallback pour erreur d'architecture"""
        # Arrange
        mock_execution_context.user_message = "Analyse ma structure"
        mock_execution_context.error = "Impossible d'accéder aux schémas"
        mock_execution_context.agent_used = "architecture"

        # Act
        result = await generic_agent.process_message(mock_execution_context)

        # Assert
        assert isinstance(result, str)
        assert "structure de vos données" in result
        assert "Impossible d'accéder aux schémas" in result

    async def test_process_message_generic_error_fallback(
        self,
        generic_agent,
        mock_execution_context,
    ):
        """Test: Fallback pour erreur générique"""
        # Arrange
        mock_execution_context.user_message = "Question quelconque"
        mock_execution_context.error = "Erreur inconnue"
        mock_execution_context.agent_used = "other"

        # Act
        result = await generic_agent.process_message(mock_execution_context)

        # Assert
        assert isinstance(result, str)
        assert "difficulté technique" in result
        assert "Erreur inconnue" in result

    async def test_process_message_with_conversation_context(
        self, generic_agent, mock_execution_context, mock_openai_client
    ):
        """Test: Message avec contexte conversationnel"""
        # Arrange
        mock_execution_context.user_message = "Parle-moi de Grist"
        mock_execution_context.error = None
        
        conversation = ConversationHistory(
            messages=[
                Message(role="user", content="Bonjour"),
                Message(
                    role="assistant", content="Bonjour! Comment puis-je vous aider?"
                ),
                Message(role="user", content="Parle-moi de Grist"),
            ]
        )
        mock_execution_context.conversation_history = conversation

        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(content="Grist est une plateforme de gestion de données.")
            )
        ]
        mock_response.usage = Mock(total_tokens=75)
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await generic_agent.process_message(mock_execution_context)

        # Assert
        assert isinstance(result, str)
        assert "Grist" in result

        # Vérifier que le contexte a été inclus
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) >= 4  # system + 3 messages de conversation

    async def test_process_message_openai_error(
        self,
        generic_agent,
        mock_execution_context,
        mock_openai_client,
    ):
        """Test: Erreur API OpenAI -> fallback"""
        # Arrange
        mock_execution_context.user_message = "Bonjour"
        mock_execution_context.error = None
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

        # Act
        result = await generic_agent.process_message(mock_execution_context)

        # Assert
        assert isinstance(result, str)
        assert "Bonjour" in result  # Fallback pour salutation

    def test_get_fallback_response_greeting(self, generic_agent):
        """Test: Fallback pour salutation"""
        greetings = ["Bonjour", "Salut", "Hello", "Hey"]

        for greeting in greetings:
            result = generic_agent._get_fallback_response(greeting)
            assert "Bonjour" in result
            assert "assistant IA" in result

    def test_get_fallback_response_help(self, generic_agent):
        """Test: Fallback pour demande d'aide"""
        help_messages = ["aide", "help", "comment faire", "Comment utiliser"]

        for msg in help_messages:
            result = generic_agent._get_fallback_response(msg)
            assert "analyser" in result or "données" in result

    def test_detect_data_question_true(self, generic_agent):
        """Test: Détection de questions sur les données"""
        data_questions = [
            "Montre-moi les ventes",
            "Combien d'utilisateurs actifs?",
            "Analyse les tendances",
            "Quelle est la moyenne des commandes?",
            "Total des produits vendus",
        ]

        for question in data_questions:
            result = generic_agent._detect_data_question(question)
            assert result is True

    def test_detect_data_question_false(self, generic_agent):
        """Test: Pas de question sur les données"""
        non_data_questions = [
            "Bonjour",
            "Merci", 
            "Comment ça va?",
            "Au revoir",
        ]

        for question in non_data_questions:
            result = generic_agent._detect_data_question(question)
            assert result is False


@pytest.mark.unit
class TestGenericAgentConfiguration:
    """Tests de configuration pour GenericAgent"""

    def test_initialization_with_defaults(self, mock_openai_client):
        """Test: Initialisation avec valeurs par défaut"""
        agent = GenericAgent(mock_openai_client)

        assert agent.client == mock_openai_client
        assert agent.model == "gpt-3.5-turbo"
        assert agent.system_prompt is not None
        assert "Grist" in agent.system_prompt

    def test_system_prompt_content(self, mock_openai_client):
        """Test: Contenu du system prompt"""
        agent = GenericAgent(mock_openai_client)

        assert "Grist" in agent.system_prompt
        assert "assistant IA" in agent.system_prompt
        assert "données" in agent.system_prompt
        assert "amical" in agent.system_prompt
        assert "150 mots" in agent.system_prompt


@pytest.mark.unit
class TestGenericAgentFallbackMethods:
    """Tests spécifiques aux nouvelles méthodes de fallback"""

    @pytest.fixture
    def generic_agent(self, mock_openai_client):
        return GenericAgent(mock_openai_client)

    def test_handle_sql_fallback(self, generic_agent):
        """Test: Méthode _handle_sql_fallback"""
        result = generic_agent._handle_sql_fallback(
            "Montre-moi les ventes", 
            "Table does not exist"
        )
        
        assert "ne peux pas exécuter votre requête" in result
        assert "Table does not exist" in result
        assert "Vérifier vos permissions" in result

    def test_handle_architecture_fallback(self, generic_agent):
        """Test: Méthode _handle_architecture_fallback"""
        result = generic_agent._handle_architecture_fallback(
            "Analyse ma structure",
            "Schema access denied"
        )
        
        assert "analyser la structure" in result
        assert "Schema access denied" in result
        assert "Reformuler votre question" in result

    def test_handle_generic_error_fallback(self, generic_agent):
        """Test: Méthode _handle_generic_error_fallback"""
        result = generic_agent._handle_generic_error_fallback(
            "Question quelconque",
            "Unknown error"
        )
        
        assert "difficulté technique" in result
        assert "Unknown error" in result
        assert "Reformuler votre question" in result