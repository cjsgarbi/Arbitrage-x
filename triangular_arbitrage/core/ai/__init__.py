"""
Módulo de Integração de IA para Análise de Pares

Este módulo fornece a integração com diferentes provedores de IA
para análise e seleção de pares de trading.
"""

from .ai_config import AIConfig
from .base_ai import BaseAI
from .huggingface_ai import HuggingFaceAI

__all__ = [
    'AIConfig',
    'BaseAI',
    'HuggingFaceAI'
]
