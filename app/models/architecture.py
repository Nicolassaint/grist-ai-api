"""
Modèles de données pour l'analyse d'architecture de base de données
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class IssueSeverity(str, Enum):
    """Niveaux de sévérité des problèmes détectés"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class IssueType(str, Enum):
    """Types de problèmes structurels"""
    NORMALIZATION = "normalization"
    NAMING = "naming"
    RELATIONSHIPS = "relationships"
    REDUNDANCY = "redundancy"
    DATA_QUALITY = "data_quality"
    BEST_PRACTICE = "best_practice"
    PERFORMANCE = "performance"


class RelationshipType(str, Enum):
    """Types de relations entre tables"""
    ONE_TO_ONE = "one-to-one"
    ONE_TO_MANY = "one-to-many"
    MANY_TO_MANY = "many-to-many"


@dataclass
class StructuralIssue:
    """Représente un problème de structure détecté"""
    type: IssueType
    severity: IssueSeverity
    table: str
    column: Optional[str] = None
    description: str = ""
    impact: str = ""
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation"""
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "table": self.table,
            "column": self.column,
            "description": self.description,
            "impact": self.impact,
            "recommendation": self.recommendation
        }


@dataclass
class RelationshipAnalysis:
    """Analyse des relations entre tables"""
    from_table: str
    to_table: str
    relationship_type: RelationshipType
    column_name: str
    is_properly_indexed: bool = True
    recommendation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation"""
        return {
            "from_table": self.from_table,
            "to_table": self.to_table,
            "relationship_type": self.relationship_type.value,
            "column_name": self.column_name,
            "is_properly_indexed": self.is_properly_indexed,
            "recommendation": self.recommendation
        }


@dataclass
class NormalizationCheck:
    """Résultats de vérification de normalisation"""
    table: str
    normal_form: str  # "1NF", "2NF", "3NF", "BCNF"
    violations: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    score: float = 10.0  # 0-10, 10 = parfaitement normalisé

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation"""
        return {
            "table": self.table,
            "normal_form": self.normal_form,
            "violations": self.violations,
            "suggestions": self.suggestions,
            "score": self.score
        }


@dataclass
class ArchitectureMetrics:
    """Métriques quantitatives sur la structure - VERSION SIMPLIFIÉE"""
    total_tables: int
    total_columns: int
    avg_columns_per_table: float
    total_relationships: int
    formula_columns: int = 0  # Optionnel
    isolated_tables: int = 0  # Optionnel
    complexity_score: float = 0.0  # Optionnel

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation"""
        return {
            "total_tables": self.total_tables,
            "total_columns": self.total_columns,
            "avg_columns_per_table": round(self.avg_columns_per_table, 2),
            "total_relationships": self.total_relationships,
            "formula_columns": self.formula_columns,
            "isolated_tables": self.isolated_tables,
            "complexity_score": round(self.complexity_score, 2)
        }


@dataclass
class ArchitectureAnalysis:
    """Résultat complet de l'analyse d'architecture"""
    document_id: str
    user_question: str
    schemas: Dict[str, Any]
    metrics: ArchitectureMetrics
    issues: List[StructuralIssue] = field(default_factory=list)
    relationships: List[RelationshipAnalysis] = field(default_factory=list)
    normalization: List[NormalizationCheck] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    severity_score: float = 0.0  # 0-10, 10 = très problématique

    def get_critical_issues_count(self) -> int:
        """Retourne le nombre de problèmes critiques"""
        return len([i for i in self.issues if i.severity == IssueSeverity.CRITICAL])

    def get_warning_issues_count(self) -> int:
        """Retourne le nombre d'avertissements"""
        return len([i for i in self.issues if i.severity == IssueSeverity.WARNING])

    def get_quality_score(self) -> float:
        """Retourne un score de qualité global (0-10, 10 = excellent)"""
        return max(0.0, 10.0 - self.severity_score)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation"""
        return {
            "document_id": self.document_id,
            "user_question": self.user_question,
            "metrics": self.metrics.to_dict(),
            "issues": [i.to_dict() for i in self.issues],
            "relationships": [r.to_dict() for r in self.relationships],
            "normalization": [n.to_dict() for n in self.normalization],
            "recommendations": self.recommendations,
            "severity_score": round(self.severity_score, 2),
            "quality_score": round(self.get_quality_score(), 2),
            "critical_issues": self.get_critical_issues_count(),
            "warning_issues": self.get_warning_issues_count()
        }
