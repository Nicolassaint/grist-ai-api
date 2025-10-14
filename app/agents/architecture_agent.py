"""
═══════════════════════════════════════════════════════════════════════════════
ARCHITECTURE AGENT - Conseiller en structure de données relationnelles
═══════════════════════════════════════════════════════════════════════════════

RÔLE:
    Analyse la structure des tables Grist et donne des conseils simples sur
    l'organisation relationnelle des données.

FONCTIONNEMENT:
    1. Récupère les schémas des tables (noms, colonnes, types)
    2. Détecte les relations Reference entre tables
    3. Calcule quelques métriques basiques
    4. Utilise le LLM pour générer 3-5 conseils simples

EXEMPLES:
    - "Ma structure est-elle bien organisée?"
    - "Comment améliorer mes relations?"
    - "Donne-moi un avis critique sur ma donnée"

SORTIES:
    - Nombre de tables/colonnes
    - Relations détectées
    - 3-5 recommandations courtes et actionnables

═══════════════════════════════════════════════════════════════════════════════
"""

import openai
from typing import Dict, List, Any, Optional
import time

from ..models.architecture import (
    ArchitectureAnalysis,
    ArchitectureMetrics,
    RelationshipAnalysis,
    RelationshipType
)
from ..grist.schema_fetcher import GristSchemaFetcher
from ..utils.logging import AgentLogger


class DataArchitectureAgent:
    """Agent de conseil en architecture de données relationnelles"""

    def __init__(self, openai_client: openai.AsyncOpenAI, schema_fetcher: GristSchemaFetcher,
                 model: str = "gpt-4"):
        self.client = openai_client
        self.schema_fetcher = schema_fetcher
        self.model = model
        self.logger = AgentLogger("architecture_agent")

    async def analyze_document_structure(
        self,
        document_id: str,
        user_question: str,
        request_id: str
    ) -> ArchitectureAnalysis:
        """
        Analyse la structure du document et retourne des conseils simples
        """
        start_time = time.time()
        self.logger.log_agent_start(request_id, user_question)

        try:
            # 1. Récupérer les schémas
            schemas = await self.schema_fetcher.get_all_schemas(document_id, request_id)

            if not schemas:
                self.logger.warning("Aucun schéma récupéré", request_id=request_id)
                return self._create_empty_analysis(document_id, user_question)

            # 2. Calculer métriques basiques
            metrics = self._calculate_metrics(schemas)

            # 3. Détecter relations
            relationships = self._find_relationships(schemas)

            # 4. Générer recommandations via LLM
            recommendations = await self._generate_recommendations(
                schemas, metrics, relationships, user_question, request_id
            )

            # 5. Construire l'analyse
            analysis = ArchitectureAnalysis(
                document_id=document_id,
                user_question=user_question,
                schemas=schemas,
                metrics=metrics,
                relationships=relationships,
                recommendations=recommendations
            )

            execution_time = time.time() - start_time
            self.logger.log_agent_response(
                request_id,
                f"Analyse terminée: {len(schemas)} tables",
                execution_time
            )

            return analysis

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(
                f"Erreur lors de l'analyse: {str(e)}",
                request_id=request_id,
                execution_time=execution_time
            )
            raise

    def _calculate_metrics(self, schemas: Dict[str, Dict[str, Any]]) -> ArchitectureMetrics:
        """Calcule des métriques simples"""
        total_tables = len(schemas)
        total_columns = sum(len(s["columns"]) for s in schemas.values())

        # Compter les relations Reference
        total_relationships = sum(
            sum(1 for col in s["columns"] if col["type"] in ["Reference", "Reference List"])
            for s in schemas.values()
        )

        return ArchitectureMetrics(
            total_tables=total_tables,
            total_columns=total_columns,
            avg_columns_per_table=total_columns / total_tables if total_tables > 0 else 0,
            total_relationships=total_relationships
        )

    def _find_relationships(self, schemas: Dict[str, Dict[str, Any]]) -> List[RelationshipAnalysis]:
        """Trouve les relations Reference entre tables"""
        relationships = []

        for table_id, schema in schemas.items():
            for col in schema["columns"]:
                if col["type"] == "Reference":
                    relationships.append(RelationshipAnalysis(
                        from_table=table_id,
                        to_table="unknown",  # Grist ne donne pas toujours la cible
                        relationship_type=RelationshipType.ONE_TO_MANY,
                        column_name=col["label"]
                    ))
                elif col["type"] == "Reference List":
                    relationships.append(RelationshipAnalysis(
                        from_table=table_id,
                        to_table="unknown",
                        relationship_type=RelationshipType.MANY_TO_MANY,
                        column_name=col["label"]
                    ))

        return relationships

    async def _generate_recommendations(
        self,
        schemas: Dict[str, Any],
        metrics: ArchitectureMetrics,
        relationships: List[RelationshipAnalysis],
        user_question: str,
        request_id: str
    ) -> List[str]:
        """Génère 3-5 conseils simples via LLM"""

        # Construire résumé schémas
        schemas_summary = "\n".join([
            f"- **{table_id}**: {len(schema['columns'])} colonnes ({', '.join([col['label'] for col in schema['columns'][:5]])}{'...' if len(schema['columns']) > 5 else ''})"
            for table_id, schema in schemas.items()
        ])

        # Résumé relations
        if relationships:
            relations_summary = f"{len(relationships)} relation(s) détectée(s)"
        else:
            relations_summary = "Aucune relation détectée"

        # Prompt simple
        prompt = f"""Tu es un conseiller en architecture de données pour Grist.

L'utilisateur a cette structure:

{schemas_summary}

{relations_summary}

QUESTION: {user_question}

Donne 3-5 conseils SIMPLES et ACTIONNABLES sur l'organisation de ses données.

IMPORTANT:
- Réponds DIRECTEMENT par les conseils, sans introduction
- Un conseil par ligne, commence par un tiret "-"
- Maximum 1-2 phrases par conseil
- Sois concis, clair et bienveillant

Exemple:
- Renomme la colonne "A" pour qu'elle soit plus descriptive
- Utilise des types de données appropriés (Numeric pour age, Date pour date)
- Crée des relations Reference si tu as des entités séparées"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3
            )

            recommendations_text = response.choices[0].message.content.strip()

            # Debug: log la réponse brute
            self.logger.info(
                f"Réponse LLM brute: {recommendations_text[:200]}...",
                request_id=request_id
            )

            recommendations = self._parse_recommendations(recommendations_text)

            # Si parsing échoue, retourner le texte brut
            if not recommendations and recommendations_text:
                self.logger.warning(
                    f"Parsing échoué, retour texte brut",
                    request_id=request_id
                )
                recommendations = [recommendations_text]

            self.logger.info(
                f"Recommandations générées: {len(recommendations)}",
                request_id=request_id
            )

            return recommendations

        except Exception as e:
            self.logger.error(f"Erreur LLM: {e}", request_id=request_id)
            return [
                "Impossible de générer des recommandations pour le moment.",
                f"Votre structure contient {metrics.total_tables} table(s) et {metrics.total_columns} colonnes."
            ]

    def _parse_recommendations(self, text: str) -> List[str]:
        """Retourne exactement ce que le LLM a généré, SANS AUCUNE MODIFICATION"""
        # Retourner le texte brut ligne par ligne
        lines = text.strip().split('\n')
        recommendations = []

        for line in lines:
            line = line.strip()
            if line:  # Garder seulement les lignes non-vides
                recommendations.append(line)

        return recommendations

    def _create_empty_analysis(self, document_id: str, user_question: str) -> ArchitectureAnalysis:
        """Analyse vide en cas d'erreur"""
        return ArchitectureAnalysis(
            document_id=document_id,
            user_question=user_question,
            schemas={},
            metrics=ArchitectureMetrics(
                total_tables=0,
                total_columns=0,
                avg_columns_per_table=0,
                total_relationships=0
            ),
            recommendations=["Impossible d'analyser la structure du document"]
        )
