"""
Arquivo de configuração do bot de arbitragem triangular
"""
from decimal import Decimal
from typing import List, Dict
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

def get_env_value(key: str, default: str = '') -> str:
    """Retorna valor do ambiente com tratamento de string"""
    value = os.getenv(key, default)
    if isinstance(value, str):
        return value.strip().strip('"\'')
    return value

# Modo de operação
TEST_MODE = get_env_value('TEST_MODE', 'true').lower() == 'true'

# Configurações da Binance
BINANCE_CONFIG = {
    'api_url': 'https://api.binance.com/api/v3',
    'stream_url': 'wss://stream.binance.com:9443/ws',
    'rate_limits': {
        'orders_per_second': 5,
        'orders_per_day': 100000,
    },
    'timeout': 5000,
    'recv_window': 5000,
    'quote_assets': ['USDT', 'BTC', 'ETH', 'BNB', 'BUSD', 'USDC'],
    'API_KEY': get_env_value('BINANCE_API_KEY'),
    'API_SECRET': get_env_value('BINANCE_API_SECRET'),
    'WEBSOCKET': {
        'PING_INTERVAL': 20,
        'RECONNECT_DELAY': 1,
        'MAX_RECONNECTS': 5
    }
}

# Constantes expostas para importação
MIN_PROFIT = Decimal('0.002')  # 0.2% lucro mínimo
TRADE_AMOUNT = Decimal('0.05')  # Máximo por trade em BTC
UPDATE_INTERVAL = 1.0  # Intervalo em segundos
MAX_CONCURRENT_TRADES = 5
BASE_CURRENCIES = ['BTC', 'ETH', 'BNB', 'USDT']

# Configurações da IA
AI_CONFIG = {
    'model_name': 'gpt-4',
    'min_confidence': 75,  # Score mínimo de confiança para execução
    'max_risk': 7,        # Risco máximo aceitável (1-10)
    'analysis_cache_ttl': 500,  # 500ms de cache para análises
    'test_mode': {
        'process_opportunities': True,  # Processa oportunidades reais em modo teste
        'store_opportunities': True,  # Armazena oportunidades reais para aprendizado
        'min_profit': Decimal('0.001'),  # 0.1% para testes
        'risk_tolerance': 8  # Maior tolerância a risco em testes
    },
    'prod_mode': {
        'min_profit': Decimal('0.003'),  # 0.3% para produção
        'risk_tolerance': 6,  # Menor tolerância a risco em produção
        'require_previous_success': True,  # Requer sucesso em operações similares
        'min_success_rate': 70  # Taxa mínima de sucesso em operações similares
    }
}

# Configurações essenciais de trading
TRADING_CONFIG = {
    'test_mode': TEST_MODE,  # Controla se executa trades reais
    'use_bnb_fees': True,
    'max_trade_amount': TRADE_AMOUNT,
    'min_profit': MIN_PROFIT,
    'max_spread': Decimal('0.02'),  # Spread máximo 2%
    'fee_rate': Decimal('0.001'),  # Taxa por operação (0.1%)
    'min_volume_btc': Decimal('0.01'),  # Volume mínimo em BTC
    'min_trades': 10,  # Mínimo de trades nas últimas 24h
    'funds_allocation': {
        'BTC': Decimal('0.01'),
        'ETH': Decimal('0.1'),
        'BNB': Decimal('1.0'),
        'USDT': Decimal('1000.0')
    }
}

# Configurações de display
DISPLAY_CONFIG = {
    'update_interval': UPDATE_INTERVAL,
    'max_opportunities': 10,
    'profit_thresholds': {
        'excellent': 1.0,    # > 1.0% = Excelente
        'good': 0.5,         # > 0.5% = Bom
        'viable': 0.2        # > 0.2% = Viável
    },
    'colors': {
        'excellent': 'bold green',
        'good': 'green',
        'warning': 'yellow',
        'danger': 'red'
    },
    'LOG_LEVEL': 'INFO',
    'CONSOLE_OUTPUT': True
}

# Configurações de logs
LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s [%(levelname)s] %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
    'file': 'data/bot.log',
    'max_size': 10485760,  # 10MB
    'backup_count': 5,
    'console_output': True
}

# Configurações de rate limit
RATE_LIMIT_CONFIG = {
    'max_requests_per_minute': 1200,
    'max_orders_per_second': 5,
    'max_orders_per_day': 100000
}

# Configurações de ranking
RANKING_CONFIG = {
    'min_volume': Decimal('1.0'),
    'min_trades': 10,
    'time_window': 24  # horas
}

# Configurações de notificações
NOTIFICATION_CONFIG = {
    'enabled': True,
    'channels': ['console', 'log'],
    'test_mode': {
        'notify_monitored_opportunities': True,
        'log_level': 'INFO'
    },
    'prod_mode': {
        'notify_all_trades': True,
        'notify_errors': True,
        'log_level': 'WARNING'
    }
}

# Configurações de segurança
SECURITY_CONFIG = {
    'max_trade_amount': TRADE_AMOUNT,
    'max_daily_trades': 100,
    'required_confirmations': 3 if not TEST_MODE else 1  # Mais confirmações em produção
}

# Configurações de retry
RETRY_CONFIG = {
    'max_attempts': 3,
    'delay': 1  # segundos
}

# Configurações de cache
CACHE_CONFIG = {
    'enabled': True,
    'ttl': 60  # segundos
}

# Configurações de banco de dados
DB_CONFIG = {
    'enabled': True,
    'DB_FILE': 'data/bot.db',
    'BACKUP_DIR': 'data/backup',
    'backup_interval': 3600,  # 1 hora
    'max_backups': 24
}

# Criar diretórios necessários
for path in ['data', 'data/backup', 'data/logs']:
    os.makedirs(path, exist_ok=True)
