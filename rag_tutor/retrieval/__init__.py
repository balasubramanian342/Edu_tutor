"""
Retrieval Module
Hybrid (dense + sparse) retrieval with cross-encoder reranking and
gap-aware topic boosting over ingested college materials.
"""

from .hybrid_retriever import HybridRetriever, format_context_for_llm, NullRetriever
from .text_utils import tokenize

__all__ = [
    'HybridRetriever',
    'format_context_for_llm',
    'NullRetriever',
    'tokenize',
]
