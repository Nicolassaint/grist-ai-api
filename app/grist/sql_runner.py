import httpx
from typing import Dict, List, Any, Optional
from ..utils.logging import AgentLogger
import re
import urllib.parse


class GristSQLRunner:
    """Exécute des requêtes SQL sur Grist et récupère les résultats"""
    
    def __init__(self, api_key: str, base_url: str = "https://docs.getgrist.com/api"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.logger = AgentLogger("grist_sql_runner")
        
        # Headers par défaut
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def validate_sql_query(self, sql_query: str) -> tuple[bool, str]:
        """Valide une requête SQL avant exécution"""
        sql_clean = sql_query.strip().upper()
        
        # Vérifications de sécurité
        forbidden_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        
        for keyword in forbidden_keywords:
            if keyword in sql_clean:
                return False, f"Requête interdite: contient le mot-clé '{keyword}'"
        
        # Vérifier que c'est bien une requête SELECT
        if not sql_clean.startswith('SELECT'):
            return False, "Seules les requêtes SELECT sont autorisées"
        
        # Vérifications basiques de syntaxe
        if sql_clean.count('(') != sql_clean.count(')'):
            return False, "Parenthèses non équilibrées"
        
        return True, "Requête valide"
    
    async def execute_sql(self, document_id: str, sql_query: str, request_id: str = "unknown") -> Dict[str, Any]:
        """Exécute une requête SQL sur un document Grist"""
        
        # Validation de la requête
        is_valid, validation_message = self.validate_sql_query(sql_query)
        if not is_valid:
            self.logger.error(
                f"Requête SQL invalide: {validation_message}",
                request_id=request_id,
                sql_query=sql_query
            )
            return {
                "success": False,
                "error": validation_message,
                "data": [],
                "columns": []
            }
        
        # Encodage de la requête pour l'URL
        encoded_query = urllib.parse.quote(sql_query)
        url = f"{self.base_url}/docs/{document_id}/sql?q={encoded_query}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                self.logger.log_grist_api_call(request_id, url, response.status_code)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    result = {
                        "success": True,
                        "data": data.get("records", []),
                        "columns": data.get("columns", []),
                        "row_count": len(data.get("records", []))
                    }
                    
                    self.logger.info(
                        "Requête SQL exécutée avec succès",
                        request_id=request_id,
                        sql_query=sql_query,
                        row_count=result["row_count"]
                    )
                    return result
                    
                else:
                    error_msg = f"Erreur HTTP {response.status_code}: {response.text}"
                    self.logger.error(
                        "Erreur lors de l'exécution SQL",
                        request_id=request_id,
                        sql_query=sql_query,
                        status_code=response.status_code,
                        response_text=response.text
                    )
                    return {
                        "success": False,
                        "error": error_msg,
                        "data": [],
                        "columns": []
                    }
                    
        except httpx.TimeoutException:
            error_msg = "Timeout lors de l'exécution de la requête SQL"
            self.logger.error(error_msg, request_id=request_id, sql_query=sql_query)
            return {
                "success": False,
                "error": error_msg,
                "data": [],
                "columns": []
            }
            
        except Exception as e:
            error_msg = f"Exception lors de l'exécution SQL: {str(e)}"
            self.logger.error(error_msg, request_id=request_id, sql_query=sql_query)
            return {
                "success": False,
                "error": error_msg,
                "data": [],
                "columns": []
            }
    
    def format_results_for_analysis(self, sql_result: Dict[str, Any]) -> str:
        """Formate les résultats SQL pour l'analyse"""
        if not sql_result["success"]:
            return f"Erreur lors de l'exécution de la requête: {sql_result.get('error', 'Erreur inconnue')}"
        
        data = sql_result["data"]
        columns = sql_result["columns"]
        
        if not data:
            return "Aucune donnée trouvée pour cette requête."
        
        # Formatage en tableau lisible
        formatted = f"Résultats de la requête ({len(data)} lignes):\n\n"
        
        # En-têtes
        if columns:
            formatted += "| " + " | ".join(columns) + " |\n"
            formatted += "| " + " | ".join(["---"] * len(columns)) + " |\n"
            
            # Données (limiter à 10 lignes pour éviter des réponses trop longues)
            for i, row in enumerate(data[:10]):
                row_values = []
                for col in columns:
                    value = str(row.get(col, ""))
                    # Limiter la longueur des valeurs pour la lisibilité
                    if len(value) > 50:
                        value = value[:47] + "..."
                    row_values.append(value)
                formatted += "| " + " | ".join(row_values) + " |\n"
            
            if len(data) > 10:
                formatted += f"\n... et {len(data) - 10} autres lignes.\n"
        else:
            # Fallback si pas de colonnes définies
            formatted += str(data)
        
        return formatted
    
    def extract_numeric_summary(self, sql_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extrait un résumé numérique des résultats"""
        if not sql_result["success"] or not sql_result["data"]:
            return {"summary": "Aucune donnée disponible"}
        
        data = sql_result["data"]
        columns = sql_result["columns"]
        
        summary = {
            "total_rows": len(data),
            "numeric_columns": {}
        }
        
        # Analyser les colonnes numériques
        for col in columns:
            numeric_values = []
            for row in data:
                try:
                    value = float(row.get(col, 0))
                    numeric_values.append(value)
                except (ValueError, TypeError):
                    continue
            
            if numeric_values:
                summary["numeric_columns"][col] = {
                    "count": len(numeric_values),
                    "sum": sum(numeric_values),
                    "avg": sum(numeric_values) / len(numeric_values),
                    "min": min(numeric_values),
                    "max": max(numeric_values)
                }
        
        return summary 