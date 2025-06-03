import httpx
from typing import Dict, List, Any, Optional
from ..utils.logging import AgentLogger
import os


class GristSchemaFetcher:
    """Récupère et structure les schémas de colonnes depuis l'API Grist"""
    
    def __init__(self, api_key: str, base_url: str = "https://docs.getgrist.com/api"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.logger = AgentLogger("grist_schema_fetcher")
        
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
                self.logger.log_grist_api_call(request_id, url, response.status_code)
                
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
    
    async def get_table_schema(self, document_id: str, table_id: str, request_id: str = "unknown") -> Dict[str, Any]:
        """Récupère le schéma d'une table spécifique"""
        url = f"{self.base_url}/docs/{document_id}/tables/{table_id}/columns"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                self.logger.log_grist_api_call(request_id, url, response.status_code)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Log détaillé des données brutes reçues
                    self.logger.info(
                        "📊 Données schéma brutes reçues",
                        request_id=request_id,
                        table_id=table_id,
                        raw_columns_count=len(data.get("columns", [])),
                        raw_data_keys=list(data.keys()),
                        raw_data_size=len(str(data))
                    )
                    
                    # Structuration du schéma
                    schema = {
                        "table_id": table_id,
                        "columns": []
                    }
                    
                    for col in data.get("columns", []):
                        column_info = {
                            "id": col.get("id"),
                            "label": col.get("label", col.get("id")),
                            "type": col.get("type", "Text"),
                            "formula": col.get("formula", ""),
                            "description": col.get("description", "")
                        }
                        schema["columns"].append(column_info)
                    
                    # Log détaillé du schéma structuré
                    self.logger.info(
                        "🏗️ Schéma structuré créé",
                        request_id=request_id,
                        table_id=table_id,
                        structured_columns=[{
                            "id": col["id"], 
                            "label": col["label"], 
                            "type": col["type"]
                        } for col in schema["columns"]],
                        columns_with_formulas=len([col for col in schema["columns"] if col["formula"]]),
                        columns_with_descriptions=len([col for col in schema["columns"] if col["description"]])
                    )
                    
                    self.logger.info(
                        f"Schéma de table récupéré: {table_id}",
                        request_id=request_id,
                        columns_count=len(schema["columns"])
                    )
                    return schema
                else:
                    self.logger.error(
                        f"Erreur lors de la récupération du schéma: {response.status_code}",
                        request_id=request_id,
                        table_id=table_id,
                        response_text=response.text
                    )
                    return {"table_id": table_id, "columns": []}
                    
        except Exception as e:
            self.logger.error(
                f"Exception lors de la récupération du schéma: {str(e)}",
                request_id=request_id,
                table_id=table_id
            )
            return {"table_id": table_id, "columns": []}
    
    async def get_all_schemas(self, document_id: str, request_id: str = "unknown") -> Dict[str, Dict[str, Any]]:
        """Récupère tous les schémas d'un document"""
        tables = await self.get_document_tables(document_id, request_id)
        
        if not tables:
            self.logger.warning("Aucune table trouvée dans le document", request_id=request_id)
            return {}
        
        schemas = {}
        for table_id in tables:
            schema = await self.get_table_schema(document_id, table_id, request_id)
            if schema["columns"]:  # Seulement si le schéma n'est pas vide
                schemas[table_id] = schema
        
        # Log détaillé des schémas finaux
        self.logger.info(
            "📚 Tous les schémas assemblés",
            request_id=request_id,
            document_id=document_id,
            tables_count=len(schemas),
            total_columns=sum(len(schema["columns"]) for schema in schemas.values()),
            schemas_summary={
                table_id: {
                    "columns_count": len(schema["columns"]),
                    "column_types": list(set(col["type"] for col in schema["columns"]))
                }
                for table_id, schema in schemas.items()
            }
        )
        
        self.logger.info(
            f"Tous les schémas récupérés",
            request_id=request_id,
            document_id=document_id,
            tables_count=len(schemas)
        )
        return schemas
    
    def format_schema_for_prompt(self, schemas: Dict[str, Dict[str, Any]]) -> str:
        """Formate les schémas pour inclusion dans un prompt"""
        if not schemas:
            return "Aucune table disponible dans ce document."
        
        formatted = "# Schémas des tables disponibles:\n\n"
        
        for table_id, schema in schemas.items():
            formatted += f"## Table: {table_id}\n"
            formatted += "| Colonne | Type | Description |\n"
            formatted += "|---------|------|-------------|\n"
            
            for col in schema["columns"]:
                description = col["description"] or col.get("formula", "") or "Aucune description"
                formatted += f"| {col['label']} | {col['type']} | {description} |\n"
            
            formatted += "\n"
        
        return formatted 