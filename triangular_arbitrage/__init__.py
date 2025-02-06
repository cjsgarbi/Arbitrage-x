"""
Triangular Arbitrage Bot
-----------------------

Bot para identificar e executar oportunidades de arbitragem triangular na Binance.
"""

from .config import (
    MIN_PROFIT,
    TRADE_AMOUNT,
    UPDATE_INTERVAL,
    MAX_CONCURRENT_TRADES,
    BASE_CURRENCIES,
    TRADING_CONFIG,
    LOG_CONFIG,
    DB_CONFIG,
    RANKING_CONFIG,
    NOTIFICATION_CONFIG,
    SECURITY_CONFIG,
    RETRY_CONFIG,
    CACHE_CONFIG,
    RATE_LIMIT_CONFIG
)
from .ui.display import Display
from .utils.pair_ranker import PairRanker
from .utils.db_helpers import DBHelpers
from .utils.logger import Logger
from .core.events_core import EventsCore
from .core.trading_core import TradingCore
from .core.currency_core import CurrencyCore, Symbol, Ticker
from .core.bot_core import BotCore
from typing import Dict, List

# Informações do projeto
PROJECT_NAME = "Triangular-Arbitrage-Bot"
VERSION = "2.0.0"
AUTHOR = "Your Name"

# Imports principais


# Configurações

__all__ = [
    # Classes principais
    'BotCore',
    'CurrencyCore',
    'TradingCore',
    'EventsCore',
    'Symbol',
    'Ticker',

    # Utilitários
    'Logger',
    'DBHelpers',
    'PairRanker',

    # Interface
    'Display',

    # Configurações
    'MIN_PROFIT',
    'TRADE_AMOUNT',
    'UPDATE_INTERVAL',
    'MAX_CONCURRENT_TRADES',
    'BASE_CURRENCIES',
    'TRADING_CONFIG',
    'LOG_CONFIG',
    'DB_CONFIG',
    'RANKING_CONFIG',
    'NOTIFICATION_CONFIG',
    'SECURITY_CONFIG',
    'RETRY_CONFIG',
    'CACHE_CONFIG',
    'RATE_LIMIT_CONFIG'
]

# Versão
__version__ = VERSION
