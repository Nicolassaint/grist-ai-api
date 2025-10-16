import openai
from typing import Dict, Any, Optional
from ..models.message import Message, ConversationHistory
from ..utils.logging import AgentLogger
from ..utils.conversation_formatter import (
    format_conversation_history,
    should_include_conversation_history,
)
from ..grist.sql_runner import GristSQLRunner
import time


class AnalysisAgent:
    """Agent d'analyse qui produit des insights à partir des données et du contexte"""

    def __init__(self, openai_client: openai.AsyncOpenAI, model: str = "gpt-4"):
        self.client = openai_client
        self.model = model
        self.logger = AgentLogger("analysis_agent")

        self.analysis_prompt_template = """Tu es un assistant d'analyse de données. Donne une interprétation COURTE et DIRECTE des résultats.

HISTORIQUE DE CONVERSATION:
{conversation_history}

QUESTION: {user_question}

RÉSULTATS SQL:
{sql_results}

INSTRUCTION: 
Donne une réponse de 1-2 phrases maximum qui explique ce que montrent ces données de manière simple et utile.
Ne fais pas de sections, pas de recommandations complexes, juste l'essentiel.

Exemple de format attendu:
"La moyenne d'âge est de 35 ans, ce qui indique une population majoritairement adulte en milieu de carrière."
"""

    async def process_message(
        self,
        user_message: str,
        conversation_history: ConversationHistory,
        sql_query: str,
        sql_results: Dict[str, Any],
        request_id: str,
    ) -> str:
        """
        Traite un message nécessitant une analyse de données

        Args:
            user_message: Question de l'utilisateur
            conversation_history: Historique de la conversation
            sql_query: Requête SQL qui a été exécutée
            sql_results: Résultats de la requête SQL
            request_id: ID de la requête pour le logging

        Returns:
            str: Réponse d'analyse
        """
        start_time = time.time()

        self.logger.log_agent_start(request_id, user_message)

        try:
            # Formatage des données pour l'analyse
            formatted_results = self._format_data_for_analysis(sql_results)
            numeric_summary = self._generate_numeric_summary(sql_results)

            # Gestion intelligente des données vides vs erreurs
            if not sql_results.get("success"):
                # Vraie erreur SQL
                return self._handle_sql_error(user_message, sql_results)
            elif not sql_results.get("data") or len(sql_results["data"]) == 0:
                # Requête réussie mais sans données - cas normal
                return self._handle_empty_results(user_message, sql_query)

            # Génération de l'analyse via IA avec des données disponibles
            analysis_response = await self._generate_analysis(
                user_message,
                conversation_history,
                sql_query,
                formatted_results,
                numeric_summary,
                request_id,
            )

            execution_time = time.time() - start_time
            self.logger.log_agent_response(
                request_id, analysis_response, execution_time
            )

            return analysis_response

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(
                f"Erreur lors de l'analyse: {str(e)}",
                request_id=request_id,
                execution_time=execution_time,
            )
            return self._get_fallback_analysis(user_message, sql_results)

    async def _generate_analysis(
        self,
        user_message: str,
        conversation_history: ConversationHistory,
        sql_query: str,
        formatted_results: str,
        numeric_summary: str,
        request_id: str,
    ) -> str:
        """Génère l'analyse via l'IA"""

        # Historique de conversation formaté (paires user/assistant complètes)
        conversation_context = (
            format_conversation_history(conversation_history, max_pairs=2)
            if should_include_conversation_history("analysis")
            else "Aucun historique de conversation"
        )

        # Construction du prompt simplifié
        prompt = self.analysis_prompt_template.format(
            conversation_history=conversation_context,
            user_question=user_message,
            sql_results=formatted_results,
        )

        try:
            # 🤖 Log lisible de la requête IA
            self.logger.log_ai_request(
                model=self.model,
                messages_count=1,
                max_tokens=100,
                request_id=request_id,
                prompt_preview=prompt,
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,  # Limité pour forcer la concision
                temperature=0.1,  # Très peu de créativité, plus factuel
            )

            analysis = response.choices[0].message.content.strip()

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
                response_preview=analysis,
            )

            self.logger.info(
                "Analyse générée avec succès",
                request_id=request_id,
                analysis_length=len(analysis),
            )

            return analysis

        except Exception as e:
            self.logger.error(
                f"Erreur lors de la génération d'analyse: {str(e)}",
                request_id=request_id,
            )
            return self._get_fallback_analysis(user_message, {"data": []})

    def _format_data_for_analysis(self, sql_results: Dict[str, Any]) -> str:
        """Formate les données SQL pour l'analyse"""
        if not sql_results.get("success") or not sql_results.get("data"):
            return "Aucune donnée disponible"

        data = sql_results["data"]
        columns = sql_results.get("columns", [])

        # Limitation pour éviter des prompts trop longs
        max_rows = 20

        formatted = f"Données ({len(data)} ligne{'s' if len(data) > 1 else ''}):\n\n"

        if columns:
            # Format tabulaire
            formatted += "| " + " | ".join(columns) + " |\n"
            formatted += "| " + " | ".join(["---"] * len(columns)) + " |\n"

            for i, row in enumerate(data[:max_rows]):
                row_values = []
                for col in columns:
                    value = str(row.get(col, ""))
                    # Limiter la longueur pour la lisibilité
                    if len(value) > 30:
                        value = value[:27] + "..."
                    row_values.append(value)
                formatted += "| " + " | ".join(row_values) + " |\n"

            if len(data) > max_rows:
                formatted += f"\n... et {len(data) - max_rows} autres lignes.\n"
        else:
            # Fallback sans colonnes
            formatted += str(data[:max_rows])

        return formatted

    def _generate_numeric_summary(self, sql_results: Dict[str, Any]) -> str:
        """Génère un résumé numérique des données"""
        if not sql_results.get("success") or not sql_results.get("data"):
            return "Aucune donnée numérique disponible"

        data = sql_results["data"]
        columns = sql_results.get("columns", [])

        summary_parts = [f"Total des lignes: {len(data)}"]

        # Analyse des colonnes numériques
        numeric_stats = {}
        for col in columns:
            numeric_values = []
            for row in data:
                try:
                    value = float(row.get(col, 0))
                    numeric_values.append(value)
                except (ValueError, TypeError):
                    continue

            if numeric_values and len(numeric_values) > 0:
                numeric_stats[col] = {
                    "count": len(numeric_values),
                    "sum": sum(numeric_values),
                    "avg": sum(numeric_values) / len(numeric_values),
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                }

        if numeric_stats:
            summary_parts.append("\nStatistiques par colonne:")
            for col, stats in numeric_stats.items():
                summary_parts.append(
                    f"- {col}: Total={stats['sum']:.2f}, "
                    f"Moyenne={stats['avg']:.2f}, "
                    f"Min={stats['min']:.2f}, "
                    f"Max={stats['max']:.2f}"
                )

        return "\n".join(summary_parts)

    def _handle_no_data_scenario(
        self, user_message: str, sql_results: Dict[str, Any]
    ) -> str:
        """Gère le cas où il n'y a pas de données à analyser"""

        error_msg = sql_results.get("error", "") if sql_results else ""

        response_parts = [
            "## Analyse impossible",
            "",
            "Je ne peux pas effectuer d'analyse car aucune donnée n'est disponible.",
        ]

        if error_msg:
            response_parts.extend(
                [
                    "",
                    f"**Erreur rencontrée :** {error_msg}",
                ]
            )

        response_parts.extend(
            [
                "",
                "### Suggestions :",
                "• Vérifiez que les données existent dans vos tables Grist",
                "• Reformulez votre question pour être plus spécifique",
                "• Assurez-vous que les critères de filtrage ne sont pas trop restrictifs",
                "",
                "**Exemple :** Au lieu de 'Analyse les ventes de janvier 2025', "
                "essayez 'Montre-moi toutes les ventes' d'abord.",
            ]
        )

        return "\n".join(response_parts)

    def _handle_sql_error(self, user_message: str, sql_results: Dict[str, Any]) -> str:
        """Gère les vraies erreurs SQL (échec de requête)"""

        error_msg = sql_results.get("error", "Erreur SQL inconnue")

        response_parts = [
            "## ❌ Erreur d'exécution SQL",
            "",
            "La requête SQL a échoué et ne peut pas être analysée.",
            "",
            f"**Erreur technique :** {error_msg}",
            "",
            "### Suggestions pour résoudre :",
            "• Vérifiez vos permissions d'accès aux données",
            "• Reformulez votre question avec des termes plus simples",
            "• Assurez-vous que les tables et colonnes existent",
            "• Contactez l'administrateur si l'erreur persiste",
        ]

        return "\n".join(response_parts)

    def _handle_empty_results(self, user_message: str, sql_query: str) -> str:
        """Gère les résultats vides (requête réussie mais aucune donnée)"""

        response_parts = [
            "## 📊 Analyse des résultats",
            "",
            "La requête s'est exécutée avec succès mais n'a retourné aucune donnée.",
            "",
            "### 🔍 Que signifie ce résultat ?",
            "",
            "**C'est normal !** Cela peut signifier que :",
            "• Aucune donnée ne correspond à vos critères de recherche",
            "• Les filtres appliqués sont trop restrictifs",
            "• Les données recherchées n'existent pas encore dans votre base",
            "",
            "### 💡 Suggestions pour approfondir :",
            "• **Élargir la recherche :** Essayez avec des critères moins restrictifs",
            "• **Vérifier les données :** Demandez un aperçu général de vos tables",
            "• **Reformuler :** Posez la question différemment",
            "",
            "**Exemples de questions plus larges :**",
            "• 'Montre-moi un aperçu de toutes les données'",
            "• 'Quelles sont les données disponibles dans cette table ?'",
            "• 'Combien de lignes contient cette table ?'",
        ]

        return "\n".join(response_parts)

    def _suggest_alternative_analysis(self, user_message: str) -> str:
        """Suggère des analyses alternatives quand les données sont insuffisantes"""

        suggestions = [
            "## Données insuffisantes pour l'analyse",
            "",
            "Les données récupérées sont vides ou insuffisantes pour une analyse significative.",
            "",
            "### Suggestions d'analyses alternatives :",
            "• **Vue d'ensemble :** 'Montre-moi un aperçu de toutes les données'",
            "• **Par période :** 'Données des 30 derniers jours'",
            "• **Par catégorie :** 'Répartition par type/statut/région'",
            "• **Tendances :** 'Évolution sur les 6 derniers mois'",
            "",
            "Reformulez votre question en étant plus large dans vos critères, "
            "puis nous pourrons affiner l'analyse ensemble.",
        ]

        return "\n".join(suggestions)

    def _get_fallback_analysis(
        self, user_message: str, sql_results: Dict[str, Any]
    ) -> str:
        """Analyse de secours en cas d'erreur"""

        row_count = len(sql_results.get("data", [])) if sql_results else 0

        if row_count == 0:
            return "Aucune donnée trouvée pour cette requête."

        return f"J'ai trouvé {row_count} résultat{'s' if row_count > 1 else ''} mais je ne peux pas les analyser pour le moment."
