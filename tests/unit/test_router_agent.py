"""
Tests unitaires pour RouterAgent
"""
import pytest
from unittest.mock import Mock
from app.agents.router_agent import RouterAgent
from app.pipeline.plans import ExecutionPlan, AgentType, get_plan
from app.models.message import Message, ConversationHistory


@pytest.mark.unit
@pytest.mark.router
@pytest.mark.asyncio
class TestRouterAgent:
    """Tests pour l'agent de routing"""

    @pytest.fixture
    def router_agent(self, mock_openai_client):
        """Crée un router agent pour les tests"""
        return RouterAgent(mock_openai_client, model="gpt-3.5-turbo")

    async def test_route_to_generic_plan(
        self,
        router_agent,
        sample_conversation_history,
        sample_request_id,
        mock_openai_client
    ):
        """Test: Routing vers le plan generic"""
        # Arrange
        user_message = "Bonjour, comment ça va ?"
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="generic"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await router_agent.route_to_plan(
            user_message,
            sample_conversation_history,
            sample_request_id
        )

        # Assert
        assert isinstance(result, ExecutionPlan)
        assert result.name == "generic"
        assert result.agents == [AgentType.GENERIC]
        mock_openai_client.chat.completions.create.assert_called_once()

    async def test_route_to_data_query_plan(
        self,
        router_agent,
        sample_conversation_history,
        sample_request_id,
        mock_openai_client
    ):
        """Test: Routing vers le plan data_query"""
        # Arrange
        user_message = "Montre-moi les ventes du mois dernier"
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="data_query"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await router_agent.route_to_plan(
            user_message,
            sample_conversation_history,
            sample_request_id
        )

        # Assert
        assert isinstance(result, ExecutionPlan)
        assert result.name == "data_query"
        assert AgentType.SQL in result.agents
        assert AgentType.ANALYSIS in result.agents

    async def test_route_to_architecture_plan(
        self,
        router_agent,
        sample_conversation_history,
        sample_request_id,
        mock_openai_client
    ):
        """Test: Routing vers le plan architecture_review"""
        # Arrange
        user_message = "Analyse la structure de mon document"
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="architecture_review"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await router_agent.route_to_plan(
            user_message,
            sample_conversation_history,
            sample_request_id
        )

        # Assert
        assert isinstance(result, ExecutionPlan)
        assert result.name == "architecture_review"
        assert result.agents == [AgentType.ARCHITECTURE]

    async def test_route_invalid_plan_fallback(
        self,
        router_agent,
        sample_conversation_history,
        sample_request_id,
        mock_openai_client
    ):
        """Test: Fallback vers generic si plan invalide"""
        # Arrange
        user_message = "Test"
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="invalid_plan"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await router_agent.route_to_plan(
            user_message,
            sample_conversation_history,
            sample_request_id
        )

        # Assert
        assert result.name == "generic"  # Fallback

    async def test_route_error_fallback(
        self,
        router_agent,
        sample_conversation_history,
        sample_request_id,
        mock_openai_client
    ):
        """Test: Fallback vers generic en cas d'erreur"""
        # Arrange
        user_message = "Test"
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

        # Act
        result = await router_agent.route_to_plan(
            user_message,
            sample_conversation_history,
            sample_request_id
        )

        # Assert
        assert result.name == "generic"  # Fallback sur erreur

    async def test_route_with_context(
        self,
        router_agent,
        sample_request_id,
        mock_openai_client
    ):
        """Test: Routing avec contexte conversationnel"""
        # Arrange
        conversation = ConversationHistory(messages=[
            Message(role="user", content="Bonjour"),
            Message(role="assistant", content="Bonjour!"),
            Message(role="user", content="Montre les ventes"),
        ])
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="data_query"))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        # Act
        result = await router_agent.route_to_plan(
            "Montre les ventes",
            conversation,
            sample_request_id
        )

        # Assert
        assert result.name == "data_query"
        # Vérifier que le contexte a été inclus
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) >= 2  # System + user au minimum
