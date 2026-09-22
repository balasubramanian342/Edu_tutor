"""
LLM Integration Module
Provides the GeminiLLMClient used by the explanation generator,
question generator, and auto-grader for real (non-template) generation.
AnthropicLLMClient/OpenAILLMClient are kept as aliases for backward
compatibility with existing imports (see llm/client.py for why).
"""

from .client import GeminiLLMClient, AnthropicLLMClient, OpenAILLMClient, build_llm_client

__all__ = ['GeminiLLMClient', 'AnthropicLLMClient', 'OpenAILLMClient', 'build_llm_client']
