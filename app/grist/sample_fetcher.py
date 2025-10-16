"""
Service pour récupérer des échantillons de données depuis Grist.
Fournit un contexte concret aux agents pour améliorer la génération de requêtes.
"""
import httpx
from typing import Dict, List, Any, Optional
from ..utils.logging import AgentLogger


class GristSampleFetcher:
    """
    Fetcher pour récupérer des échantillons de données (premières lignes) depuis Grist.

    Utilisé pour donner du contexte aux agents SQL et Architecture afin qu'ils comprennent
    mieux la structure et le contenu des données.
    """

    def __init__(self, base_url: str = "https://grist.numerique.gouv.fr"):
        """
        Initialise le fetcher de samples.

        Args:
            base_url: URL de base de l'instance Grist
        """
        self.base_url = base_url.rstrip("/")
        self.logger = AgentLogger("grist_sample_fetcher")

    async def fetch_table_samples(
        self,
        document_id: str,
        table_id: str,
        grist_api_key: str,
        limit: int = 5,
        request_id: str = None,
    ) -> Dict[str, Any]:
        """
        Récupère un échantillon de données d'une table Grist.

        Args:
            document_id: ID du document Grist
            table_id: ID de la table
            grist_api_key: Clé API Grist
            limit: Nombre de lignes à récupérer (défaut: 5)
            request_id: ID de requête pour logging

        Returns:
            Dict contenant:
            - success: bool
            - data: List[Dict] - Les lignes échantillonnées
            - columns: List[str] - Noms des colonnes
            - total_rows: int - Nombre total de lignes dans la table (si disponible)
            - sample_info: Dict - Métadonnées sur l'échantillon
        """
        url = f"{self.base_url}/api/docs/{document_id}/tables/{table_id}/records"

        params = {
            "auth": grist_api_key,
            "limit": limit,  # Limite le nombre de lignes récupérées
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)

                self.logger.log_grist_api(
                    f"records?limit={limit}", response.status_code
                )

                if response.status_code == 200:
                    data = response.json()
                    processed_sample = self._process_sample_data(
                        data, table_id, limit, request_id
                    )

                    self.logger.info(
                        f"✅ Échantillon récupéré",
                        table_id=table_id,
                        sample_rows=len(processed_sample.get("data", [])),
                        request_id=request_id,
                    )

                    return processed_sample
                else:
                    self.logger.error(
                        f"❌ Erreur API Grist pour échantillon",
                        table_id=table_id,
                        status=response.status_code,
                        request_id=request_id,
                    )
                    return {
                        "success": False,
                        "error": f"Erreur API: {response.status_code}",
                        "data": [],
                        "columns": [],
                        "sample_info": {},
                    }

        except Exception as e:
            self.logger.error(
                f"❌ Exception lors de la récupération d'échantillon",
                table_id=table_id,
                error=str(e)[:100],
                request_id=request_id,
            )
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "columns": [],
                "sample_info": {},
            }

    async def fetch_all_samples(
        self,
        document_id: str,
        table_schemas: Dict[str, Dict],
        grist_api_key: str,
        limit: int = 5,
        request_id: str = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Récupère des échantillons pour toutes les tables du document.

        Args:
            document_id: ID du document Grist
            table_schemas: Schémas des tables (depuis GristSchemaFetcher)
            grist_api_key: Clé API Grist
            limit: Nombre de lignes par table
            request_id: ID de requête pour logging

        Returns:
            Dict[table_id] -> sample_data
        """
        all_samples = {}

        for table_id in table_schemas.keys():
            sample = await self.fetch_table_samples(
                document_id=document_id,
                table_id=table_id,
                grist_api_key=grist_api_key,
                limit=limit,
                request_id=request_id,
            )
            all_samples[table_id] = sample

        self.logger.info(
            f"📦 Tous les échantillons récupérés",
            tables_count=len(all_samples),
            successful_samples=sum(
                1 for s in all_samples.values() if s.get("success", False)
            ),
            request_id=request_id,
        )

        return all_samples

    def _process_sample_data(
        self, raw_data: Dict, table_id: str, limit: int, request_id: str = None
    ) -> Dict[str, Any]:
        """
        Traite les données brutes de l'API Grist pour créer un échantillon structuré.

        Args:
            raw_data: Données brutes de l'API Grist
            table_id: ID de la table
            limit: Limite demandée
            request_id: ID de requête

        Returns:
            Dict structuré avec les données échantillonnées
        """
        try:
            records = raw_data.get("records", [])

            # Extraction des colonnes depuis le premier enregistrement
            columns = []
            sample_rows = []

            if records and len(records) > 0:
                # Les colonnes sont les clés du champ "fields" du premier record
                first_record = records[0]
                if "fields" in first_record:
                    columns = list(first_record["fields"].keys())

                # Traitement des enregistrements
                for record in records[:limit]:  # Assurer la limite
                    if "fields" in record:
                        sample_rows.append(record["fields"])

            # Métadonnées sur l'échantillon
            sample_info = {
                "requested_limit": limit,
                "actual_rows": len(sample_rows),
                "columns_count": len(columns),
                "is_empty": len(sample_rows) == 0,
                "table_id": table_id,
            }

            self.logger.debug(
                f"📋 Échantillon traité",
                table_id=table_id,
                columns_count=len(columns),
                rows_count=len(sample_rows),
                request_id=request_id,
            )

            return {
                "success": True,
                "data": sample_rows,
                "columns": columns,
                "sample_info": sample_info,
                "table_id": table_id,
            }

        except Exception as e:
            self.logger.error(
                f"❌ Erreur lors du traitement d'échantillon",
                table_id=table_id,
                error=str(e)[:100],
                request_id=request_id,
            )
            return {
                "success": False,
                "error": f"Erreur traitement: {str(e)}",
                "data": [],
                "columns": [],
                "sample_info": {"table_id": table_id, "is_empty": True},
            }

    def format_sample_for_prompt(
        self, sample_data: Dict[str, Any], max_rows: int = 5
    ) -> str:
        """
        Formate un échantillon de données pour inclusion dans un prompt.

        Args:
            sample_data: Données échantillonnées (depuis fetch_table_samples)
            max_rows: Nombre maximum de lignes à afficher

        Returns:
            String formatée pour inclusion dans le prompt
        """
        if not sample_data.get("success") or not sample_data.get("data"):
            return f"Table {sample_data.get('table_id', 'inconnue')}: Aucune donnée"

        table_id = sample_data.get("table_id", "Table")
        columns = sample_data.get("columns", [])
        rows = sample_data.get("data", [])[:max_rows]

        if not rows:
            return f"Table {table_id}: Vide"

        # Format concis : | col1 | col2 | col3 |
        formatted = f"**{table_id}** ({len(rows)} échantillons):\n"

        # En-tête du tableau
        header = "| " + " | ".join(columns) + " |"
        separator = "|" + "|".join([" --- " for _ in columns]) + "|"
        formatted += header + "\n" + separator + "\n"

        # Données
        for row in rows:
            values = []
            for col in columns:
                value = row.get(col, "NULL")
                # Troncature des valeurs trop longues pour tableau
                if isinstance(value, str) and len(value) > 15:
                    value = value[:12] + "..."
                values.append(str(value))
            formatted += "| " + " | ".join(values) + " |\n"

        return formatted

    def format_all_samples_for_prompt(
        self, all_samples: Dict[str, Dict[str, Any]], max_rows_per_table: int = 3
    ) -> str:
        """
        Formate tous les échantillons pour inclusion dans un prompt.

        Args:
            all_samples: Dict[table_id] -> sample_data
            max_rows_per_table: Nombre max de lignes par table

        Returns:
            String formatée avec tous les échantillons
        """
        if not all_samples:
            return "ÉCHANTILLONS DE DONNÉES: Aucun échantillon disponible"

        formatted_sections = []

        for table_id, sample_data in all_samples.items():
            sample_text = self.format_sample_for_prompt(sample_data, max_rows_per_table)
            formatted_sections.append(sample_text)

        full_text = "ÉCHANTILLONS DE DONNÉES:\n" + "\n\n".join(formatted_sections)

        return full_text
