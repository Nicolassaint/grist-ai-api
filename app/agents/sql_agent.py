import openai
from typing import Dict, Any, Optional, Tuple
from ..models.message import Message, ConversationHistory
from ..utils.logging import AgentLogger
from ..utils.conversation_formatter import (
    format_conversation_history,
    should_include_conversation_history,
)
from ..grist.schema_fetcher import GristSchemaFetcher
from ..grist.sql_runner import GristSQLRunner
from ..grist.sample_fetcher import GristSampleFetcher
import time
import re


class SQLAgent:
    """Agent SQL qui génère des requêtes SQL à partir de langage naturel"""

    def __init__(
        self,
        openai_client: openai.AsyncOpenAI,
        schema_fetcher: GristSchemaFetcher,
        sql_runner: GristSQLRunner,
        sample_fetcher: GristSampleFetcher,
        model: str = "gpt-4",
    ):
        self.client = openai_client
        self.schema_fetcher = schema_fetcher
        self.sql_runner = sql_runner
        self.sample_fetcher = sample_fetcher
        self.model = model
        self.logger = AgentLogger("sql_agent")

        self.sql_prompt_template = """Tu es un expert SQL spécialisé dans la génération de requêtes pour Grist.

SCHÉMAS DISPONIBLES:
{schemas}

{data_samples}

INSTRUCTIONS IMPORTANTES:
1. Génère UNIQUEMENT des requêtes SELECT (pas de INSERT, UPDATE, DELETE, DROP)
2. Utilise exactement les noms de tables et colonnes fournis dans les schémas
3. Si plusieurs tables sont disponibles, utilise les JOINtures appropriées
4. Optimise pour la performance (LIMIT quand approprié)
5. **ATTENTION aux types de données** : Certaines colonnes peuvent être typées "Text" même si elles contiennent des nombres. Regarde les échantillons pour identifier le contenu réel. Pour les comparaisons numériques sur des colonnes "Text" contenant des nombres, utilise CAST(colonne AS REAL) ou CAST(colonne AS INTEGER)
6. Utilise les échantillons de données pour mieux comprendre le contenu et ajuster ta requête
7. Si la question est ambiguë, propose la requête la plus probable

EXEMPLE de conversion de type :
- Mauvais: `SELECT MAX(age) FROM table` (compare en texte : "9" > "35")  
- Bon: `SELECT MAX(CAST(age AS REAL)) FROM table` (compare en nombre : 35 > 9)

HISTORIQUE DE CONVERSATION:
{conversation_history}

QUESTION UTILISATEUR: {user_question}

Réponds avec :
1. La requête SQL (entre ```sql et ```)
2. Une explication brève de ce que fait la requête
3. Les limitations ou hypothèses éventuelles

Format de réponse attendu :
```sql
SELECT ...
```

Explication : Cette requête récupère..."""

    async def process_message(
        self,
        user_message: str,
        conversation_history: ConversationHistory,
        document_id: str,
        grist_api_key: str,
        request_id: str,
    ) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
        """
        Traite un message nécessitant une requête SQL

        Returns:
            tuple: (response_text, sql_query, sql_results)
        """
        start_time = time.time()

        self.logger.log_agent_start("sql", user_message[:80])

        try:
            # 1. Récupération des schémas
            schemas = await self.schema_fetcher.get_all_schemas(document_id, request_id)

            if not schemas:
                return (
                    (
                        "Désolé, je ne peux pas accéder aux schémas de données de ce document. "
                        "Vérifiez que le document existe et que vous avez les permissions appropriées."
                    ),
                    None,
                    None,
                )

            # 2. Récupération des échantillons de données
            data_samples = await self.sample_fetcher.fetch_all_samples(
                document_id, schemas, grist_api_key, limit=5, request_id=request_id
            )

            # 3. Génération de la requête SQL
            sql_query = await self._generate_sql_query(
                user_message, conversation_history, schemas, data_samples, request_id
            )

            if not sql_query:
                return (
                    (
                        "Je n'ai pas pu générer une requête SQL appropriée pour votre question. "
                        "Pouvez-vous la reformuler ou être plus spécifique ?"
                    ),
                    None,
                    None,
                )

            # 4. Exécution de la requête
            sql_results = await self.sql_runner.execute_sql(context.document_id, sql_query, context.request_id)
            
            # 5. Vérification des résultats
            if not sql_results["success"]:
                context.set_error(sql_results.get('error', 'Erreur inconnue lors de l\'exécution SQL'), "sql")
                context.sql_query = sql_query  # Garder la requête pour debug
                return None  # Fallback vers Generic
            
            # 6. Succès - formatage de la réponse
            context.sql_query = sql_query
            context.sql_results = sql_results
            context.data_analyzed = True
            
            response_text = self._format_successful_sql_response(sql_query, sql_results)
            
            execution_time = time.time() - start_time
            self.logger.log_agent_response("sql", True, execution_time)
            self.logger.log_sql_generation(sql_query, len(schemas))
            
            return response_text
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(
                f"Erreur lors du traitement SQL: {str(e)}",
                request_id=context.request_id,
                execution_time=execution_time
            )
            context.set_error(f"Erreur technique: {str(e)}", "sql")
            return None  # Fallback vers Generic

    async def _generate_sql_query(
        self,
        user_message: str,
        conversation_history: ConversationHistory,
        schemas: Dict[str, Dict[str, Any]],
        data_samples: Dict[str, Dict[str, Any]],
        request_id: str,
    ) -> Optional[str]:
        """Génère une requête SQL à partir du langage naturel"""

        # Formatage des schémas pour le prompt
        schemas_text = self.schema_fetcher.format_schema_for_prompt(schemas)

        # Formatage des échantillons de données
        samples_text = (
            self.sample_fetcher.format_all_samples_for_prompt(
                data_samples, max_rows_per_table=5
            )
            if data_samples
            else "Aucun échantillon de données disponible"
        )

        # Historique de conversation formaté (paires user/assistant complètes)
        conversation_context = (
            format_conversation_history(conversation_history, max_pairs=2)
            if should_include_conversation_history("sql")
            else "Aucun historique de conversation"
        )

        # Construction du prompt
        prompt = self.sql_prompt_template.format(
            schemas=schemas_text,
            data_samples=samples_text,
            user_question=user_message,
            conversation_history=conversation_context,
        )

        try:
            # 🤖 Log lisible de la requête IA
            self.logger.log_ai_request(
                model=self.model,
                messages_count=1,  # Un seul message pour la génération SQL
                max_tokens=500,
                request_id=request_id,
                prompt_preview=prompt,
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1,  # Peu de créativité pour la génération SQL
            )

            ai_response = response.choices[0].message.content.strip()

            # 🤖 Log lisible de la réponse IA
            tokens_used = (
                getattr(response.usage, "total_tokens", None)
                if hasattr(response, "usage")
                else None
            )
            self.logger.log_ai_response(
                model=self.model,
                tokens_used=tokens_used,
                success=True,
                request_id=request_id,
                response_preview=ai_response,
            )

            # Extraction de la requête SQL
            sql_query = self._extract_sql_from_response(ai_response)

            if sql_query:
                self.logger.info(
                    "Requête SQL générée avec succès",
                    request_id=request_id,
                    sql_length=len(sql_query),
                )
                return sql_query
            else:
                self.logger.warning(
                    "Aucune requête SQL extraite de la réponse",
                    request_id=request_id,
                    ai_response=ai_response[:200],
                )
                return None

        except Exception as e:
            # 🤖 Log lisible d'erreur IA
            self.logger.log_ai_response(
                model=self.model, success=False, request_id=request_id
            )

            self.logger.error(
                f"Erreur lors de la génération SQL: {str(e)}", request_id=request_id
            )
            return None

    def _extract_sql_from_response(self, ai_response: str) -> Optional[str]:
        """Extrait la requête SQL de la réponse de l'IA"""

        # Recherche de blocs SQL entre ```sql et ```
        sql_pattern = r"```sql\s*(.*?)\s*```"
        matches = re.findall(sql_pattern, ai_response, re.DOTALL | re.IGNORECASE)

        if matches:
            return matches[0].strip()

        # Fallback : recherche de SELECT...
        select_pattern = r"(SELECT\s+.*?)(?:\n\n|\Z)"
        matches = re.findall(select_pattern, ai_response, re.DOTALL | re.IGNORECASE)

        if matches:
            return matches[0].strip()

        return None

    def _format_successful_sql_response(self, sql_query: str, sql_results: Dict[str, Any]) -> str:
        """Formate la réponse pour une requête SQL réussie"""
        
        row_count = sql_results.get("row_count", 0)

        if row_count == 0:
            return (
                f"J'ai exécuté cette requête :\n\n```sql\n{sql_query}\n```\n\n"
                f"**Résultat :** Aucune donnée ne correspond aux critères de votre recherche.\n\n"
                f"💡 **Suggestions :**\n"
                f"• Vérifiez si les données existent dans vos tables\n"
                f"• Essayez d'élargir vos critères de recherche\n"
                f"• Reformulez votre question avec des termes différents\n\n"
                f"*Cette absence de résultats peut être normale selon vos données.*"
            )

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
            formatted_results,
        ]

        return "\n".join(response)

