"""
Tests d'intégration pour l'orchestrateur
"""
import pytest
from unittest.mock import AsyncMock, Mock
from app.orchestrator import AIOrchestrator
from app.models.request import ProcessedRequest, ChatResponse


@pytest.mark.integration
@pytest.mark.asyncio
class TestOrchestratorIntegration:
    """Tests d'intégration de l'orchestrateur"""

    def test_orchestrator_initialization(self):
        """Test: Initialisation correcte de l'orchestrateur"""
        # Act
        orch = AIOrchestrator()

        # Assert
        assert orch.router is not None
        assert orch.generic_agent is not None
        assert orch.analysis_agent is not None
        assert hasattr(orch, 'openai_client')
        assert hasattr(orch, 'default_model')
        assert hasattr(orch, 'stats')

    def test_orchestrator_stats_initialization(self):
        """Test: Initialisation des statistiques"""
        # Act
        orch = AIOrchestrator()
        stats = orch.get_stats()

        # Assert
        assert stats["total_requests"] == 0
        assert "plan_usage" in stats
        assert "generic" in stats["plan_usage"]
        assert "data_query" in stats["plan_usage"]
        assert "architecture_review" in stats["plan_usage"]

    async def test_health_check(self, mocker):
        """Test: Vérification de santé du système"""
        # Arrange
        orch = AIOrchestrator()
        
        # Mock de la réponse OpenAI pour éviter les appels réels à l'API
        from unittest.mock import AsyncMock
        mock_response = mocker.MagicMock()
        mock_response.choices = [mocker.MagicMock(message=mocker.MagicMock(content="ok"))]
        
        # Utiliser AsyncMock pour les méthodes async
        orch.openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        # Act
        health = await orch.health_check()

        # Assert
        assert health["status"] == "healthy"
        assert "components" in health
        assert health["components"]["openai"] == "ok"
        assert "stats" in health

    @pytest.mark.skip(reason="Nécessite clé API OpenAI réelle")
    async def test_full_workflow_generic(self, sample_processed_request):
        """Test E2E: Workflow complet generic"""
        # Ce test nécessite une vraie clé OpenAI
        orch = AIOrchestrator()
        response = await orch.process_chat_request(sample_processed_request)
        assert isinstance(response, ChatResponse)
