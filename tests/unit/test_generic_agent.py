"""
Tests unitaires pour GenericAgent
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
        sample_conversation_history,
        sample_request_id,
        mock_openai_client,
    ):
        """Test: Traitement réussi d'un message"""
        # Arrange
        user_message = "Bonjour, comment ça va ?"
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Bonjour! Je vais bien, merci."))
        ]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await generic_agent.process_message(
            user_message, sample_conversation_history, sample_request_id
        )

        # Assert
        assert isinstance(result, str)
        assert "Bonjour" in result
        mock_openai_client.chat.completions.create.assert_called_once()

    async def test_process_message_with_conversation_context(
        self, generic_agent, sample_request_id, mock_openai_client
    ):
        """Test: Message avec contexte conversationnel"""
        # Arrange
        conversation = ConversationHistory(
            messages=[
                Message(role="user", content="Bonjour"),
                Message(
                    role="assistant", content="Bonjour! Comment puis-je vous aider?"
                ),
                Message(role="user", content="Parle-moi de Grist"),
            ]
        )

        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(content="Grist est une plateforme de gestion de données.")
            )
        ]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await generic_agent.process_message(
            "Parle-moi de Grist", conversation, sample_request_id
        )

        # Assert
        assert isinstance(result, str)
        assert "Grist" in result

        # Vérifier que le contexte a été inclus
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) >= 4  # system + 3 messages de conversation

    async def test_process_message_limits_recent_messages(
        self, generic_agent, sample_request_id, mock_openai_client
    ):
        """Test: Limite à 5 messages récents"""
        # Arrange
        many_messages = [
            Message(role="user", content=f"Message {i}") for i in range(10)
        ]
        conversation = ConversationHistory(messages=many_messages)

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Réponse"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        await generic_agent.process_message("Test", conversation, sample_request_id)

        # Assert
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        # system + 5 messages récents max
        assert len(messages) <= 6

    async def test_process_message_openai_error(
        self,
        generic_agent,
        sample_conversation_history,
        sample_request_id,
        mock_openai_client,
    ):
        """Test: Erreur API OpenAI -> fallback"""
        # Arrange
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

        # Act
        result = await generic_agent.process_message(
            "Bonjour", sample_conversation_history, sample_request_id
        )

        # Assert
        assert isinstance(result, str)
        assert "Bonjour" in result  # Fallback pour salutation

    async def test_process_message_empty_conversation(
        self, generic_agent, sample_request_id, mock_openai_client
    ):
        """Test: Conversation vide"""
        # Arrange
        empty_conversation = ConversationHistory(messages=[])
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Comment puis-je vous aider?"))
        ]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await generic_agent.process_message(
            "Première question", empty_conversation, sample_request_id
        )

        # Assert
        assert isinstance(result, str)
        # Doit avoir au moins le system prompt
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) >= 1

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

    def test_get_fallback_response_what(self, generic_agent):
        """Test: Fallback pour questions 'quoi/what'"""
        what_messages = ["C'est quoi", "What is this", "Que fais-tu"]

        for msg in what_messages:
            result = generic_agent._get_fallback_response(msg)
            assert "assistant IA" in result or "Grist" in result

    def test_get_fallback_response_generic(self, generic_agent):
        """Test: Fallback générique"""
        result = generic_agent._get_fallback_response("Message aléatoire xyz")

        assert "Désolé" in result or "difficulté" in result
        assert "Grist" in result

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

    def test_suggest_data_analysis(self, generic_agent):
        """Test: Suggestions d'analyse de données"""
        result = generic_agent.suggest_data_analysis("Comment analyser?")

        assert "ventes" in result
        assert "utilisateurs" in result
        assert "tendances" in result
        assert "moyenne" in result
        assert "données Grist" in result

    @pytest.mark.parametrize(
        "user_message,expected_keyword",
        [
            ("bonjour", "Bonjour"),
            ("aide", "analyser"),
            ("c'est quoi", "assistant"),
            ("random text", "Désolé"),
        ],
    )
    def test_fallback_parametrized(self, generic_agent, user_message, expected_keyword):
        """Test: Fallback paramétrés"""
        result = generic_agent._get_fallback_response(user_message)
        assert expected_keyword in result


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

    def test_initialization_with_custom_model(self, mock_openai_client):
        """Test: Initialisation avec modèle personnalisé"""
        agent = GenericAgent(mock_openai_client, model="gpt-4")

        assert agent.model == "gpt-4"

    def test_system_prompt_content(self, mock_openai_client):
        """Test: Contenu du system prompt"""
        agent = GenericAgent(mock_openai_client)

        assert "Grist" in agent.system_prompt
        assert "assistant IA" in agent.system_prompt
        assert "données" in agent.system_prompt
        assert "amical" in agent.system_prompt
        assert "150 mots" in agent.system_prompt

    @pytest.mark.asyncio
    async def test_openai_call_parameters(self, mock_openai_client):
        """Test: Paramètres de l'appel OpenAI"""
        agent = GenericAgent(mock_openai_client)
        conversation = ConversationHistory(messages=[])

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        await agent.process_message("Test", conversation, "req-123")

        # Vérifier les paramètres de l'appel
        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-3.5-turbo"
        assert call_kwargs["max_tokens"] == 200
        assert call_kwargs["temperature"] == 0.7


@pytest.mark.unit
class TestGenericAgentEdgeCases:
    """Tests des cas limites pour GenericAgent"""

    @pytest.fixture
    def generic_agent(self, mock_openai_client):
        return GenericAgent(mock_openai_client)

    def test_detect_data_question_mixed_case(self, generic_agent):
        """Test: Détection insensible à la casse"""
        assert generic_agent._detect_data_question("DONNÉES") is True
        assert generic_agent._detect_data_question("TaBLe") is True
        assert generic_agent._detect_data_question("VeNtEs") is True

    def test_fallback_response_case_insensitive(self, generic_agent):
        """Test: Fallback insensible à la casse"""
        result_lower = generic_agent._get_fallback_response("bonjour")
        result_upper = generic_agent._get_fallback_response("BONJOUR")
        result_mixed = generic_agent._get_fallback_response("BoNjOuR")

        assert all("Bonjour" in r for r in [result_lower, result_upper, result_mixed])

    def test_detect_data_question_multiple_indicators(self, generic_agent):
        """Test: Plusieurs indicateurs de données"""
        question = "Analyse les ventes et les statistiques des clients dans la table"
        result = generic_agent._detect_data_question(question)

        assert result is True

    @pytest.mark.asyncio
    async def test_process_message_strips_whitespace(
        self,
        generic_agent,
        sample_conversation_history,
        sample_request_id,
        mock_openai_client,
    ):
        """Test: Les espaces en trop sont supprimés"""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="  Réponse avec espaces  "))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await generic_agent.process_message(
            "Test", sample_conversation_history, sample_request_id
        )

        assert result == "Réponse avec espaces"
        assert not result.startswith(" ")
        assert not result.endswith(" ")
