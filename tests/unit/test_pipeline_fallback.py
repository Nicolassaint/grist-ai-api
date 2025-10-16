"""
Tests pour le nouveau système de fallback du pipeline
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.pipeline.executor import PipelineExecutor
from app.pipeline.plans import ExecutionPlan, AgentType
from app.pipeline.context import ExecutionContext
from app.models.request import ChatResponse


@pytest.mark.unit
@pytest.mark.asyncio
class TestPipelineFallback:
    """Tests pour le système de fallback du pipeline"""

    @pytest.fixture
    def pipeline_executor(self, mock_sql_agent, mock_generic_agent):
        """Crée un pipeline executor avec agents mockés"""
        agents = {
            AgentType.SQL: mock_sql_agent,
            AgentType.GENERIC: mock_generic_agent,
        }
        return PipelineExecutor(agents)

    @pytest.fixture
    def sql_plan(self):
        """Plan avec SQL Agent seulement"""
        return ExecutionPlan(
            name="data_query",
            agents=[AgentType.SQL],
            description="Test SQL plan",
            requires_api_key=True
        )

    async def test_sql_success_no_fallback(
        self,
        pipeline_executor,
        sql_plan,
        mock_execution_context,
        mock_sql_agent
    ):
        """Test: SQL réussit, pas de fallback nécessaire"""
        # Arrange
        mock_sql_agent.process_message.return_value = "Résultats SQL trouvés"

        # Act
        response = await pipeline_executor.execute(sql_plan, mock_execution_context)

        # Assert
        assert isinstance(response, ChatResponse)
        assert response.response == "Résultats SQL trouvés"
        assert response.agent_used == "sql"
        assert response.error is None
        mock_sql_agent.process_message.assert_called_once()

    async def test_sql_error_fallback_to_generic(
        self,
        pipeline_executor,
        sql_plan,
        mock_execution_context,
        mock_sql_agent,
        mock_generic_agent
    ):
        """Test: SQL échoue, fallback vers Generic réussit"""
        # Arrange
        mock_sql_agent.process_message.return_value = None  # Échec SQL
        mock_generic_agent.process_message.return_value = "Erreur gérée par Generic"
        
        # Simuler que SQL a mis une erreur dans le contexte
        def sql_side_effect(context):
            context.set_error("Permission denied", "sql")
            return None
        mock_sql_agent.process_message.side_effect = sql_side_effect

        # Act
        response = await pipeline_executor.execute(sql_plan, mock_execution_context)

        # Assert
        assert isinstance(response, ChatResponse)
        assert response.response == "Erreur gérée par Generic"
        assert response.agent_used == "generic"  # Fallback réussi
        assert response.error == "Permission denied"
        
        # Vérifier que les deux agents ont été appelés
        mock_sql_agent.process_message.assert_called_once()
        mock_generic_agent.process_message.assert_called_once()

    async def test_early_termination_after_fallback(
        self,
        mock_sql_agent,
        mock_generic_agent,
        mock_analysis_agent,
        mock_execution_context
    ):
        """Test: Pipeline s'arrête après fallback réussi"""
        # Arrange
        agents = {
            AgentType.SQL: mock_sql_agent,
            AgentType.GENERIC: mock_generic_agent,
            AgentType.ANALYSIS: mock_analysis_agent,
        }
        pipeline = PipelineExecutor(agents)
        
        # Plan avec SQL + Analysis, mais SQL échoue
        plan = ExecutionPlan(
            name="test_plan",
            agents=[AgentType.SQL, AgentType.ANALYSIS],
            description="Test early termination",
            requires_api_key=True
        )
        
        # Mock SQL échoue, Generic réussit
        mock_sql_agent.process_message.return_value = None
        mock_generic_agent.process_message.return_value = "Fallback réussi"
        
        def sql_side_effect(context):
            context.set_error("SQL failed", "sql")
            return None
        mock_sql_agent.process_message.side_effect = sql_side_effect

        # Act
        response = await pipeline.execute(plan, mock_execution_context)

        # Assert
        assert response.response == "Fallback réussi"
        assert response.agent_used == "generic"
        
        # Analysis Agent ne devrait PAS être appelé (early termination)
        mock_analysis_agent.process_message.assert_not_called()

    async def test_data_query_plan_continues_to_analysis(
        self,
        mock_sql_agent,
        mock_generic_agent,
        mock_analysis_agent,
        mock_execution_context
    ):
        """Test: Plan data_query - SQL réussit puis Analysis s'exécute"""
        # Arrange
        agents = {
            AgentType.SQL: mock_sql_agent,
            AgentType.GENERIC: mock_generic_agent,
            AgentType.ANALYSIS: mock_analysis_agent,
        }
        pipeline = PipelineExecutor(agents)
        
        # Plan data_query typique avec SQL + Analysis
        plan = ExecutionPlan(
            name="data_query",
            agents=[AgentType.SQL, AgentType.ANALYSIS],
            description="Data query with analysis",
            requires_api_key=True
        )
        
        # Mock SQL réussit et set les résultats dans le contexte
        def sql_success_side_effect(context):
            context.sql_query = "SELECT * FROM users"
            context.sql_results = {"success": True, "data": [{"id": 1, "name": "test"}]}
            context.data_analyzed = True
            return "Résultats SQL trouvés"
        
        mock_sql_agent.process_message.side_effect = sql_success_side_effect
        mock_analysis_agent.process_message.return_value = "Analyse des résultats: 1 utilisateur trouvé"

        # Act
        response = await pipeline.execute(plan, mock_execution_context)

        # Assert
        assert response.agent_used == "analysis"  # Analysis agent a la réponse finale
        assert "Analyse des résultats" in response.response
        
        # Les deux agents doivent être appelés
        mock_sql_agent.process_message.assert_called_once()
        mock_analysis_agent.process_message.assert_called_once()
        
        # Le contexte doit avoir les données SQL
        assert mock_execution_context.sql_query == "SELECT * FROM users"
        assert mock_execution_context.sql_results is not None

    async def test_missing_api_key_error(
        self,
        pipeline_executor,
        sql_plan,
        mock_execution_context
    ):
        """Test: Erreur de clé API manquante"""
        # Arrange
        mock_execution_context.grist_api_key = None  # Pas de clé API

        # Act
        response = await pipeline_executor.execute(sql_plan, mock_execution_context)

        # Assert
        assert isinstance(response, ChatResponse)
        assert "clé API Grist" in response.error

    async def test_context_error_propagation(
        self,
        pipeline_executor,
        sql_plan,
        mock_execution_context,
        mock_sql_agent,
        mock_generic_agent
    ):
        """Test: Propagation correcte des erreurs via le contexte"""
        # Arrange
        def sql_side_effect(context):
            context.set_error("Specific SQL error", "sql")
            context.add_trace("sql", "Failed with error")
            return None
        
        mock_sql_agent.process_message.side_effect = sql_side_effect
        mock_generic_agent.process_message.return_value = "Generic handled it"

        # Act
        response = await pipeline_executor.execute(sql_plan, mock_execution_context)

        # Assert
        assert response.error == "Specific SQL error"
        assert len(mock_execution_context.execution_trace) > 0
        assert mock_execution_context.agent_used == "generic"


@pytest.mark.unit
class TestPipelineExecutorSQLAgent:
    """Tests spécifiques à l'exécution SQL dans le pipeline"""

    @pytest.fixture
    def pipeline_executor(self, mock_sql_agent, mock_generic_agent):
        agents = {
            AgentType.SQL: mock_sql_agent,
            AgentType.GENERIC: mock_generic_agent,
        }
        return PipelineExecutor(agents)

    async def test_sql_agent_context_enrichment(
        self,
        pipeline_executor,
        mock_execution_context,
        mock_sql_agent
    ):
        """Test: SQL Agent enrichit correctement le contexte en cas de succès"""
        # Arrange
        mock_sql_agent.process_message.return_value = "SQL success response"
        
        def sql_side_effect(context):
            # Simuler l'enrichissement du contexte par SQL Agent
            context.sql_query = "SELECT * FROM test"
            context.sql_results = {"success": True, "row_count": 5}
            context.data_analyzed = True
            return "SQL success response"
        
        mock_sql_agent.process_message.side_effect = sql_side_effect
        
        plan = ExecutionPlan(
            name="sql_only",
            agents=[AgentType.SQL],
            description="SQL only",
            requires_api_key=True
        )

        # Act
        response = await pipeline_executor.execute(plan, mock_execution_context)

        # Assert
        assert response.sql_query == "SELECT * FROM test"
        assert response.data_analyzed is True
        assert mock_execution_context.sql_query == "SELECT * FROM test"
        assert mock_execution_context.sql_results["success"] is True

    async def test_sql_agent_error_logging(
        self,
        pipeline_executor,
        mock_execution_context,
        mock_sql_agent,
        mock_generic_agent
    ):
        """Test: Logging correct des erreurs SQL"""
        # Arrange
        def sql_side_effect(context):
            context.set_error("Database connection failed", "sql")
            return None
        
        mock_sql_agent.process_message.side_effect = sql_side_effect
        mock_generic_agent.process_message.return_value = "Fallback response"
        
        plan = ExecutionPlan(
            name="test",
            agents=[AgentType.SQL],
            description="Test",
            requires_api_key=True
        )

        # Act
        with patch('app.pipeline.executor.AgentLogger') as mock_logger_class:
            mock_logger = Mock()
            mock_logger_class.return_value = mock_logger
            
            executor = PipelineExecutor({
                AgentType.SQL: mock_sql_agent,
                AgentType.GENERIC: mock_generic_agent
            })
            
            response = await executor.execute(plan, mock_execution_context)

        # Assert
        assert response.error == "Database connection failed"
        # Vérifier que le logger a été appelé pour le fallback
        mock_logger.info.assert_called()


@pytest.mark.unit 
class TestPipelineExecutorEdgeCases:
    """Tests pour les cas limites du pipeline"""

    async def test_agent_not_available(
        self,
        mock_execution_context
    ):
        """Test: Agent non disponible dans le pipeline"""
        # Arrange
        pipeline = PipelineExecutor({})  # Aucun agent disponible
        plan = ExecutionPlan(
            name="test",
            agents=[AgentType.SQL],
            description="Test",
            requires_api_key=True
        )

        # Act
        response = await pipeline.execute(plan, mock_execution_context)

        # Assert
        assert response.response == "Désolé, je n'ai pas pu générer de réponse."
        assert response.agent_used == "none"

    async def test_exception_in_agent_execution(
        self,
        mock_execution_context
    ):
        """Test: Exception pendant l'exécution d'un agent"""
        # Arrange
        mock_sql_agent = AsyncMock()
        mock_sql_agent.process_message.side_effect = Exception("Agent crashed")
        
        pipeline = PipelineExecutor({AgentType.SQL: mock_sql_agent})
        plan = ExecutionPlan(
            name="test",
            agents=[AgentType.SQL],
            description="Test",
            requires_api_key=True
        )

        # Act
        response = await pipeline.execute(plan, mock_execution_context)

        # Assert
        assert response.agent_used == "none"
        assert "Agent crashed" in mock_execution_context.execution_trace[-1]