"""
Core do sistema de arbitragem triangular
"""
import os
import sys

# Adiciona o diretório raiz ao PYTHONPATH para permitir imports relativos
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Importa primeiro as inicializações
from .binance_init import (
    AsyncClient,
    BinanceAPIException,
    ThreadedWebsocketManager,
    validate_binance_imports
)

# Verifica se as dependências do Binance estão disponíveis
if not validate_binance_imports():
    raise ImportError("Dependências do Binance não encontradas. Verifique a instalação.")

# Importa os módulos principais
from .ai import ArbitrageAgent, OpenRouterAI, AIConfig
from .binance_websocket import BinanceWebsocketClient
from .storage.vector_store import VectorStore

__all__ = [
    # Binance
    'AsyncClient',
    'BinanceAPIException',
    'ThreadedWebsocketManager',
    'BinanceWebsocketClient',
    
    # AI
    'ArbitrageAgent',
    'OpenRouterAI',
    'AIConfig',
    
    # Storage
    'VectorStore'
]