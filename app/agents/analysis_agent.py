import openai
from typing import Dict, Any, Optional
from ..models.message import Message, ConversationHistory
from ..utils.logging import AgentLogger
from ..grist.sql_runner import GristSQLRunner
import time


class AnalysisAgent:
    """Agent d'analyse qui produit des insights à partir des données et du contexte"""
    
    def __init__(self, openai_client: openai.AsyncOpenAI, model: str = "gpt-4"):
        self.client = openai_client
        self.model = model
        self.logger = AgentLogger("analysis_agent")
        
        self.analysis_prompt_template = """Tu es un expert en analyse de données travaillant avec Grist.

Ta mission est d'analyser les données fournies et de produire des insights pertinents et actionnables.

QUESTION UTILISATEUR: {user_question}

REQUÊTE SQL EXÉCUTÉE:
```sql
{sql_query}
```

RÉSULTATS DE LA REQUÊTE:
{sql_results}

RÉSUMÉ NUMÉRIQUE:
{numeric_summary}

CONTEXTE CONVERSATIONNEL:
{conversation_context}

INSTRUCTIONS POUR L'ANALYSE:
1. Résume clairement ce que montrent les données
2. Identifie les tendances, patterns ou anomalies importantes
3. Propose des insights actionnables basés sur ces données
4. Si les données sont insuffisantes, explique les limitations et suggère des analyses complémentaires
5. Utilise un langage accessible et évite le jargon technique excessif
6. Structure ta réponse avec des sections claires (Résumé, Insights, Recommandations)

LIMITATIONS:
- Ne fais jamais d'affirmations sur des données que tu ne vois pas
- Si les résultats sont vides ou insuffisants, redirige vers des questions plus spécifiques
- Reste factuel et base-toi uniquement sur les données fournies

Ta réponse doit être structurée et utile pour la prise de décision."""
    
    async def process_message(self, user_message: str, conversation_history: ConversationHistory,
                            sql_query: str, sql_results: Dict[str, Any], request_id: str) -> str:
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
            # Vérification des données
            if not sql_results or not sql_results.get("success"):
                return self._handle_no_data_scenario(user_message, sql_results)
            
            # Préparation des données pour l'analyse
            formatted_results = self._format_data_for_analysis(sql_results)
            numeric_summary = self._generate_numeric_summary(sql_results)
            
            # Si pas de données significatives, redirection
            if not sql_results.get("data") or len(sql_results["data"]) == 0:
                return self._suggest_alternative_analysis(user_message)
            
            # Génération de l'analyse via IA
            analysis_response = await self._generate_analysis(
                user_message, conversation_history, sql_query, 
                formatted_results, numeric_summary, request_id
            )
            
            execution_time = time.time() - start_time
            self.logger.log_agent_response(request_id, analysis_response, execution_time)
            
            return analysis_response
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(
                f"Erreur lors de l'analyse: {str(e)}",
                request_id=request_id,
                execution_time=execution_time
            )
            return self._get_fallback_analysis(user_message, sql_results)
    
    async def _generate_analysis(self, user_message: str, conversation_history: ConversationHistory,
                               sql_query: str, formatted_results: str, numeric_summary: str,
                               request_id: str) -> str:
        """Génère l'analyse via l'IA"""
        
        # Contexte conversationnel
        recent_messages = conversation_history.get_recent_messages(3)
        context = "\n".join([f"{msg.role}: {msg.content[:100]}" for msg in recent_messages[:-1]])
        
        # Construction du prompt d'analyse
        prompt = self.analysis_prompt_template.format(
            user_question=user_message,
            sql_query=sql_query,
            sql_results=formatted_results,
            numeric_summary=numeric_summary,
            conversation_context=context if context else "Aucun contexte précédent"
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.3  # Créativité modérée pour l'analyse
            )
            
            analysis = response.choices[0].message.content.strip()
            
            self.logger.info(
                "Analyse générée avec succès",
                request_id=request_id,
                analysis_length=len(analysis)
            )
            
            return analysis
            
        except Exception as e:
            self.logger.error(
                f"Erreur lors de la génération d'analyse: {str(e)}",
                request_id=request_id
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
                    "max": max(numeric_values)
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
    
    def _handle_no_data_scenario(self, user_message: str, sql_results: Dict[str, Any]) -> str:
        """Gère le cas où il n'y a pas de données à analyser"""
        
        error_msg = sql_results.get("error", "") if sql_results else ""
        
        response_parts = [
            "## Analyse impossible",
            "",
            "Je ne peux pas effectuer d'analyse car aucune donnée n'est disponible.",
        ]
        
        if error_msg:
            response_parts.extend([
                "",
                f"**Erreur rencontrée :** {error_msg}",
            ])
        
        response_parts.extend([
            "",
            "### Suggestions :",
            "• Vérifiez que les données existent dans vos tables Grist",
            "• Reformulez votre question pour être plus spécifique",
            "• Assurez-vous que les critères de filtrage ne sont pas trop restrictifs",
            "",
            "**Exemple :** Au lieu de 'Analyse les ventes de janvier 2025', "
            "essayez 'Montre-moi toutes les ventes' d'abord."
        ])
        
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
            "puis nous pourrons affiner l'analyse ensemble."
        ]
        
        return "\n".join(suggestions)
    
    def _get_fallback_analysis(self, user_message: str, sql_results: Dict[str, Any]) -> str:
        """Analyse de secours en cas d'erreur"""
        
        row_count = len(sql_results.get("data", [])) if sql_results else 0
        
        if row_count == 0:
            return self._handle_no_data_scenario(user_message, sql_results)
        
        return (
            f"## Analyse des données récupérées\n\n"
            f"J'ai récupéré {row_count} ligne{'s' if row_count > 1 else ''} de données.\n\n"
            f"Malheureusement, je rencontre une difficulté technique pour générer "
            f"une analyse détaillée en ce moment.\n\n"
            f"**Ce que je peux vous dire :**\n"
            f"• {row_count} enregistrement{'s' if row_count > 1 else ''} correspond{'ent' if row_count > 1 else ''} à votre recherche\n"
            f"• Les données sont disponibles et accessibles\n\n"
            f"Pouvez-vous reformuler votre question d'analyse ou être plus spécifique "
            f"sur ce que vous souhaitez analyser dans ces données ?"
        ) 