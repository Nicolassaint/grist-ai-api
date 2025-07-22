import openai
from typing import Dict, Any, Optional, Tuple
from ..models.message import Message, ConversationHistory
from ..utils.logging import AgentLogger
from ..grist.schema_fetcher import GristSchemaFetcher
from ..grist.sql_runner import GristSQLRunner
import time
import re


class SQLAgent:
    """Agent SQL qui génère des requêtes SQL à partir de langage naturel"""
    
    def __init__(self, openai_client: openai.AsyncOpenAI, schema_fetcher: GristSchemaFetcher, 
                 sql_runner: GristSQLRunner, model: str = "gpt-4"):
        self.client = openai_client
        self.schema_fetcher = schema_fetcher
        self.sql_runner = sql_runner
        self.model = model
        self.logger = AgentLogger("sql_agent")
        
        self.sql_prompt_template = """Tu es un expert SQL spécialisé dans la génération de requêtes pour Grist.

        SCHÉMAS DISPONIBLES:
        {schemas}

        INSTRUCTIONS IMPORTANTES:
        1. Génère UNIQUEMENT des requêtes SELECT (pas de INSERT, UPDATE, DELETE, DROP)
        2. Utilise exactement les noms de tables et colonnes fournis dans les schémas
        3. Si plusieurs tables sont disponibles, utilise les JOINtures appropriées
        4. Optimise pour la performance (LIMIT quand approprié)
        5. Gère les types de données correctement (Text, Numeric, Date, etc.)
        6. Si la question est ambiguë, propose la requête la plus probable

        QUESTION UTILISATEUR: {user_question}

        CONTEXTE CONVERSATIONNEL:
        {conversation_context}

        Réponds avec :
        1. La requête SQL (entre ```sql et ```)
        2. Une explication brève de ce que fait la requête
        3. Les limitations ou hypothèses éventuelles

        Format de réponse attendu :
        ```sql
        SELECT ...
        ```

        Explication : Cette requête récupère..."""
    
    async def process_message(self, user_message: str, conversation_history: ConversationHistory, 
                            document_id: str, request_id: str) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
        """
        Traite un message nécessitant une requête SQL
        
        Returns:
            tuple: (response_text, sql_query, sql_results)
        """
        start_time = time.time()
        
        self.logger.log_agent_start(request_id, user_message)
        
        try:
            # 1. Récupération des schémas
            schemas = await self.schema_fetcher.get_all_schemas(document_id, request_id)
            
            if not schemas:
                return ("Désolé, je ne peux pas accéder aux schémas de données de ce document. "
                       "Vérifiez que le document existe et que vous avez les permissions appropriées."), None, None
            
            # 2. Génération de la requête SQL
            sql_query = await self._generate_sql_query(user_message, conversation_history, schemas, request_id)
            
            if not sql_query:
                return ("Je n'ai pas pu générer une requête SQL appropriée pour votre question. "
                       "Pouvez-vous la reformuler ou être plus spécifique ?"), None, None
            
            # 3. Exécution de la requête
            sql_results = await self.sql_runner.execute_sql(document_id, sql_query, request_id)
            
            # 4. Formatage de la réponse
            response_text = self._format_sql_response(sql_query, sql_results, user_message)
            
            execution_time = time.time() - start_time
            self.logger.log_agent_response(request_id, response_text, execution_time)
            self.logger.log_sql_generation(sql_query, len(schemas))
            
            return response_text, sql_query, sql_results
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(
                f"Erreur lors du traitement SQL: {str(e)}",
                request_id=request_id,
                execution_time=execution_time
            )
            return (f"Désolé, j'ai rencontré une erreur lors de l'analyse de vos données : {str(e)}"), None, None
    
    async def _generate_sql_query(self, user_message: str, conversation_history: ConversationHistory, 
                                 schemas: Dict[str, Dict[str, Any]], request_id: str) -> Optional[str]:
        """Génère une requête SQL à partir du langage naturel"""
        
        # Formatage des schémas pour le prompt
        schemas_text = self.schema_fetcher.format_schema_for_prompt(schemas)
        
        # Contexte conversationnel
        recent_messages = conversation_history.get_recent_messages(3)
        context = "\n".join([f"{msg.role}: {msg.content}" for msg in recent_messages[:-1]])
        
        # Construction du prompt
        prompt = self.sql_prompt_template.format(
            schemas=schemas_text,
            user_question=user_message,
            conversation_context=context if context else "Aucun contexte précédent"
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1  # Peu de créativité pour la génération SQL
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Extraction de la requête SQL
            sql_query = self._extract_sql_from_response(ai_response)
            
            if sql_query:
                self.logger.info(
                    "Requête SQL générée avec succès",
                    request_id=request_id,
                    sql_length=len(sql_query)
                )
                return sql_query
            else:
                self.logger.warning(
                    "Aucune requête SQL extraite de la réponse",
                    request_id=request_id,
                    ai_response=ai_response[:200]
                )
                return None
                
        except Exception as e:
            self.logger.error(
                f"Erreur lors de la génération SQL: {str(e)}",
                request_id=request_id
            )
            return None
    
    def _extract_sql_from_response(self, ai_response: str) -> Optional[str]:
        """Extrait la requête SQL de la réponse de l'IA"""
        
        # Recherche de blocs SQL entre ```sql et ```
        sql_pattern = r'```sql\s*(.*?)\s*```'
        matches = re.findall(sql_pattern, ai_response, re.DOTALL | re.IGNORECASE)
        
        if matches:
            return matches[0].strip()
        
        # Fallback : recherche de SELECT...
        select_pattern = r'(SELECT\s+.*?)(?:\n\n|\Z)'
        matches = re.findall(select_pattern, ai_response, re.DOTALL | re.IGNORECASE)
        
        if matches:
            return matches[0].strip()
        
        return None
    
    def _format_sql_response(self, sql_query: str, sql_results: Dict[str, Any], user_question: str) -> str:
        """Formate la réponse finale avec les résultats SQL"""
        
        if not sql_results["success"]:
            return (f"J'ai généré cette requête SQL :\n\n```sql\n{sql_query}\n```\n\n"
                   f"Mais elle a produit une erreur : {sql_results.get('error', 'Erreur inconnue')}\n\n"
                   f"Pouvez-vous vérifier votre question ou les données disponibles ?")
        
        row_count = sql_results.get("row_count", 0)
        
        if row_count == 0:
            return (f"J'ai exécuté cette requête :\n\n```sql\n{sql_query}\n```\n\n"
                   f"**Résultat :** Aucune donnée ne correspond aux critères de votre recherche.\n\n"
                   f"💡 **Suggestions :**\n"
                   f"• Vérifiez si les données existent dans vos tables\n"
                   f"• Essayez d'élargir vos critères de recherche\n"
                   f"• Reformulez votre question avec des termes différents\n\n"
                   f"*Cette absence de résultats peut être normale selon vos données.*")
        
        # Formatage des résultats
        formatted_results = self.sql_runner.format_results_for_analysis(sql_results)
        
        response = [
            f"Voici les résultats pour votre question :",
            f"",
            f"**Requête exécutée :**",
            f"```sql",
            f"{sql_query}",
            f"```",
            f"",
            f"**Résultats ({row_count} ligne{'s' if row_count > 1 else ''}) :**",
            f"",
            formatted_results
        ]
        
        return "\n".join(response)
    
    def _suggest_improvements(self, user_message: str, schemas: Dict[str, Dict[str, Any]]) -> str:
        """Suggère des améliorations pour des questions ambiguës"""
        
        available_tables = list(schemas.keys())
        
        suggestions = [
            f"Pour vous aider davantage, voici les tables disponibles : {', '.join(available_tables)}",
            "",
            "Vous pouvez être plus spécifique en mentionnant :",
            "• La période qui vous intéresse (mois dernier, cette année...)",
            "• Les critères de filtrage souhaités",
            "• Le type d'agrégation (somme, moyenne, nombre...)",
            "",
            "Exemple : 'Montre-moi le total des ventes par mois pour cette année'"
        ]
        
        return "\n".join(suggestions) 