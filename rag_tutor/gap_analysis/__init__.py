"""
Gap Analysis Module
Identifies knowledge gaps and generates personalized remediation plans.
"""

from .gap_analyzer import GapAnalyzer, KnowledgeGap, GapType
from .remediation_planner import RemediationPlanner, RemediationPlan

__all__ = [
    'GapAnalyzer',
    'KnowledgeGap',
    'GapType',
    'RemediationPlanner',
    'RemediationPlan'
]
