"""
Módulo de Integração de IA para Análise de Pares

Este módulo fornece a integração com diferentes provedores de IA
para análise e seleção de pares de trading.
"""

from .huggingface_config import setup_huggingface_env
from .ai_config import AIConfig
from .base_ai import BaseAI
from .openrouter_ai import OpenRouterAI
from .arbitrage_agent import ArbitrageAgent

# Configura ambiente HuggingFace antes de qualquer importação
setup_huggingface_env()

__all__ = [
    'AIConfig',
    'BaseAI',
    'OpenRouterAI',
    'ArbitrageAgent'
]
