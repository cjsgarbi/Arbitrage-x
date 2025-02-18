"""
Inicialização e configuração do cliente Binance
"""
from binance.client import AsyncClient
from binance.exceptions import BinanceAPIException
from binance.streams import BinanceSocketManager
from binance import ThreadedWebsocketManager

def get_binance_imports():
    """
    Retorna os imports necessários do Binance
    para garantir que estejam disponíveis
    """
    return {
        'AsyncClient': AsyncClient,
        'BinanceAPIException': BinanceAPIException,
        'BinanceSocketManager': BinanceSocketManager,
        'ThreadedWebsocketManager': ThreadedWebsocketManager
    }

def validate_binance_imports():
    """
    Valida se todas as dependências do Binance 
    estão disponíveis e carregadas corretamente
    """
    try:
        imports = get_binance_imports()
        return all(imports.values())
    except ImportError:
        return False

__all__ = [
    'AsyncClient',
    'BinanceAPIException',
    'BinanceSocketManager',
    'ThreadedWebsocketManager',
    'get_binance_imports',
    'validate_binance_imports'
]