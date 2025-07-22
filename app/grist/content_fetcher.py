import httpx
from typing import Dict, List, Any, Optional
from ..utils.logging import AgentLogger


class GristContentFetcher:
    """Récupère les noms des tables et leur contenu depuis l'API Grist"""
    
    def __init__(self, api_key: str, base_url: str = "https://docs.getgrist.com/api"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.logger = AgentLogger("grist_content_fetcher")
        
        # Headers par défaut
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def get_document_tables(self, document_id: str, request_id: str = "unknown") -> List[str]:
        """Récupère la liste des tables d'un document"""
        url = f"{self.base_url}/docs/{document_id}/tables"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                self.logger.log_grist_api(url, response.status_code)
                
                if response.status_code == 200:
                    data = response.json()
                    tables = [table["id"] for table in data.get("tables", [])]
                    
                    # Logs détaillés des données reçues
                    self.logger.info(
                        "📋 Tables récupérées depuis Grist",
                        request_id=request_id,
                        document_id=document_id,
                        tables_count=len(tables),
                        tables_list=tables,
                        raw_data_size=len(str(data))
                    )
                    
                    self.logger.info(f"Tables récupérées: {tables}", request_id=request_id)
                    return tables
                else:
                    self.logger.error(
                        f"Erreur lors de la récupération des tables: {response.status_code}",
                        request_id=request_id,
                        response_text=response.text
                    )
                    return []
                    
        except Exception as e:
            self.logger.error(f"Exception lors de la récupération des tables: {str(e)}", request_id=request_id)
            return []
    
    async def get_table_content_csv(self, document_id: str, table_id: str, request_id: str = "unknown") -> str:
        """Récupère le contenu d'une table spécifique en format CSV sous forme de string"""
        url = f"{self.base_url}/docs/{document_id}/download/csv"
        
        # Paramètres pour spécifier la table et le format des headers
        params = {
            "tableId": table_id,
            "header": "label"  # Utilise les labels des colonnes plutôt que les colIds
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers, params=params)
                self.logger.log_grist_api(url, response.status_code)
                
                if response.status_code == 200:
                    # Retourner directement le contenu CSV comme string
                    csv_content = response.text
                    
                    # Logs simplifiés sans parsing
                    lines = csv_content.strip().split('\n')
                    line_count = len(lines)
                    
                    self.logger.info(
                        "📊 Contenu CSV récupéré depuis Grist",
                        request_id=request_id,
                        table_id=table_id,
                        line_count=line_count,
                        content_size=len(csv_content)
                    )
                    
                    if line_count > 1:
                        self.logger.info(
                            "📋 Aperçu du contenu de la table",
                            request_id=request_id,
                            table_id=table_id,
                            first_lines=lines[:3] if len(lines) > 3 else lines
                        )
                    else:
                        self.logger.info(
                            "✅ Table récupérée avec succès mais vide",
                            request_id=request_id,
                            table_id=table_id,
                            note="La table ne contient aucune donnée - c'est normal pour une table vide"
                        )
                    
                    self.logger.info(
                        f"Contenu de table récupéré: {table_id}",
                        request_id=request_id,
                        row_count=len(rows),
                        columns_count=len(columns)
                    )
                    
                    return csv_content
                    
                else:
                    error_msg = f"Erreur HTTP {response.status_code}: {response.text}"
                    self.logger.error(
                        "Erreur lors de la récupération du contenu CSV",
                        request_id=request_id,
                        table_id=table_id,
                        status_code=response.status_code,
                        response_text=response.text
                    )
                    return f"# Erreur lors de la récupération de la table {table_id}\n# {error_msg}"
                    
        except httpx.TimeoutException:
            error_msg = "Timeout lors de la récupération du contenu CSV"
            self.logger.error(error_msg, request_id=request_id, table_id=table_id)
            return f"# Erreur Timeout pour la table {table_id}\n# {error_msg}"
            
        except Exception as e:
            error_msg = f"Exception lors de la récupération du contenu CSV: {str(e)}"
            self.logger.error(error_msg, request_id=request_id, table_id=table_id)
            return f"# Erreur Exception pour la table {table_id}\n# {error_msg}"
    
    async def get_all_tables_content(self, document_id: str, request_id: str = "unknown") -> str:
        """Récupère le contenu de toutes les tables d'un document en format CSV concaténé"""
        tables = await self.get_document_tables(document_id, request_id)
        
        if not tables:
            self.logger.warning("Aucune table trouvée dans le document", request_id=request_id)
            return "# Aucune table trouvée dans le document"
        
        all_csv_content = []
        total_rows = 0
        
        for table_id in tables:
            csv_content = await self.get_table_content_csv(document_id, table_id, request_id)
            
            # Ajouter un header pour identifier la table
            table_section = f"\n# ===== TABLE: {table_id} =====\n"
            table_section += csv_content
            table_section += f"\n# ===== FIN TABLE: {table_id} =====\n"
            
            all_csv_content.append(table_section)
            
            # Compter les lignes pour les logs (en excluant l'header)
            if not csv_content.startswith("#"):  # Si ce n'est pas une erreur
                lines = csv_content.strip().split('\n')
                if len(lines) > 1:  # Header + données
                    total_rows += len(lines) - 1
        
        # Assembler tout le contenu
        final_content = f"# Document Grist ID: {document_id}\n"
        final_content += f"# Nombre de tables: {len(tables)}\n"
        final_content += f"# Tables: {', '.join(tables)}\n"
        final_content += "".join(all_csv_content)
        
        # Log détaillé des contenus finaux
        self.logger.info(
            "📚 Tous les contenus de tables assemblés en CSV",
            request_id=request_id,
            document_id=document_id,
            tables_count=len(tables),
            total_rows=total_rows,
            total_csv_size=len(final_content),
            tables_list=tables
        )
        
        self.logger.info(
            f"Tous les contenus de tables récupérés en format CSV",
            request_id=request_id,
            document_id=document_id,
            tables_count=len(tables),
            total_rows=total_rows
        )
        return final_content

        
    async def get_all_tables_preview(self, document_id: str, request_id: str = "unknown") -> str:
        """Récupère un aperçu de toutes les tables d'un document via l'endpoint /records"""
        try:
            # Récupération des tables du document
            tables = await self.get_document_tables(document_id, request_id)
            
            if not tables:
                self.logger.warning("Aucune table trouvée dans le document", request_id=request_id)
                return "# Aucune table trouvée dans le document"
            
            preview_parts = []
            
            # Récupérer un aperçu de TOUTES les tables via /records
            for table_id in tables:
                try:
                    # Utilisation de format_csv_content_for_analysis qui utilise /records
                    formatted_content = await self.format_csv_content_for_analysis(
                        document_id, table_id, request_id, limit=10
                    )
                    
                    if formatted_content and not formatted_content.startswith("Erreur"):
                        preview_parts.append(formatted_content)
                    else:
                        # En cas d'erreur, ajouter le message d'erreur
                        preview_parts.append(f"# Erreur lors de la récupération de la table {table_id}: {formatted_content}")
                        
                except Exception as e:
                    self.logger.warning(f"Erreur lors de la récupération de l'aperçu de {table_id}: {str(e)}")
                    preview_parts.append(f"# Erreur lors de la récupération de la table {table_id}: {str(e)}")
                    continue
            
            # Assemblage final
            if preview_parts:
                final_content = f"# Aperçu du document Grist ID: {document_id}\n"
                final_content += f"# Nombre de tables: {len(tables)}\n"
                final_content += f"# Tables: {', '.join(tables)}\n\n"
                final_content += "\n\n".join(preview_parts)
                
                # Log détaillé
                self.logger.info(
                    "📋 Aperçu de toutes les tables assemblé via /records",
                    request_id=request_id,
                    document_id=document_id,
                    tables_count=len(tables),
                    tables_list=tables,
                    preview_size=len(final_content)
                )
                
                return final_content
            else:
                return "# Aucun contenu disponible"
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération de l'aperçu: {str(e)}")
            return f"# Erreur lors de la génération de l'aperçu: {str(e)}"
    
    async def format_csv_content_for_analysis(self, document_id: str, table_id: str, request_id: str = "unknown", limit: int = 10) -> str:
        """Récupère et formate le contenu d'une table pour l'analyse via l'endpoint /records avec limite"""
        url = f"{self.base_url}/docs/{document_id}/tables/{table_id}/records"
        
        # Paramètres pour limiter le nombre d'enregistrements
        params = {
            "limit": limit
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers, params=params)
                self.logger.log_grist_api(url, response.status_code)
                
                if response.status_code == 200:
                    data = response.json()
                    records = data.get("records", [])
                    
                    if not records:
                        return f"La table '{table_id}' ne contient aucun enregistrement."
                    
                    # Conversion des enregistrements en format CSV-like
                    csv_lines = []
                    
                    # Récupération des noms de colonnes depuis le premier enregistrement
                    if records:
                        columns = list(records[0].get("fields", {}).keys())
                        csv_lines.append(",".join(columns))
                        
                        # Ajout des données
                        for record in records:
                            fields = record.get("fields", {})
                            row_values = []
                            for col in columns:
                                value = fields.get(col, "")
                                # Conversion en string et échappement des virgules
                                str_value = str(value) if value is not None else ""
                                # Limiter la taille de chaque cellule pour éviter les contenus massifs
                                if len(str_value) > 200:  # Limite à 200 caractères par cellule
                                    str_value = str_value[:200] + "..."
                                if "," in str_value:
                                    str_value = f'"{str_value}"'
                                row_values.append(str_value)
                            csv_lines.append(",".join(row_values))
                    
                    csv_content = "\n".join(csv_lines)
                    
                    # Formatage pour l'analyse
                    total_lines = len(csv_lines)
                    data_lines = total_lines - 1 if total_lines > 0 else 0
                    
                    formatted = f"Contenu de la table '{table_id}' ({data_lines} lignes de données récupérées via /records):\n\n"
                    formatted += csv_content
                    
                    # Logs détaillés
                    self.logger.info(
                        "📊 Contenu pour analyse récupéré via /records",
                        request_id=request_id,
                        table_id=table_id,
                        records_count=len(records),
                        limit=limit,
                        content_size=len(formatted)
                    )
                    
                    return formatted
                    
                else:
                    error_msg = f"Erreur lors de la récupération des enregistrements de {table_id}: HTTP {response.status_code}"
                    self.logger.error(
                        f"Erreur lors de la récupération des enregistrements: {response.status_code}",
                        request_id=request_id,
                        table_id=table_id,
                        response_text=response.text
                    )
                    return f"Erreur lors de la récupération du contenu de la table {table_id}: {error_msg}"
                    
        except Exception as e:
            error_msg = f"Erreur lors de la récupération des enregistrements de {table_id}: {str(e)}"
            self.logger.error(f"Erreur lors de la récupération des enregistrements: {str(e)}", request_id=request_id)
            return error_msg
    
    def extract_csv_summary(self, csv_content: str, table_id: str = "Unknown") -> Dict[str, Any]:
        """Extrait un résumé simple du contenu CSV d'une table"""
        if csv_content.startswith("#"):
            return {"summary": "Erreur lors de la récupération", "table_id": table_id, "error": csv_content}
        
        try:
            lines = csv_content.strip().split('\n')
            line_count = len(lines)
            
            summary = {
                "table_id": table_id,
                "total_lines": line_count,
                "content_size": len(csv_content),
                "first_line": lines[0] if lines else "",
                "sample_lines": lines[:3] if len(lines) > 3 else lines
            }
            
            return summary
            
        except Exception as e:
            return {"summary": f"Erreur lors de l'analyse: {str(e)}", "table_id": table_id} 
            
 