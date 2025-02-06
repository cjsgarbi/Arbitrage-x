from decimal import Decimal
from typing import List, Dict

# Configurações da Binance Testnet
BINANCE_CONFIG = {
    'use_testnet': True,  # Força uso da testnet
    'test_mode': True,    # Ativa modo de teste
    'testnet_api_url': 'https://testnet.binance.vision/api/v3',
    'testnet_stream_url': 'wss://testnet.binance.vision/stream',
    'rate_limits': {
        'orders_per_second': 5,
        'orders_per_day': 100000,
    },
    'timeout': 10000,
    'recv_window': 60000,  # Aumentado para 60 segundos
    'order_types': ['LIMIT', 'MARKET'],
    'time_in_force': ['GTC', 'IOC', 'FOK'],
    'quote_assets': ['USDT', 'BTC', 'ETH', 'BNB', 'BUSD', 'USDC'],
    'max_requests_per_minute': 1200,
    'max_orders_per_second': 10,
    'websocket_timeout': 5
}

# Configurações gerais
# 0.2% lucro mínimo (reduzido para detectar mais oportunidades)
MIN_PROFIT = Decimal('0.002')
TRADE_AMOUNT = Decimal('0.01')  # Quantidade base para trades
UPDATE_INTERVAL = 0.5  # Intervalo reduzido para 0.5 segundos
MAX_CONCURRENT_TRADES = 5  # Aumentado para 5 trades simultâneos

# Moedas base para triangulação
BASE_CURRENCIES = [
    'BTC', 'ETH', 'BNB', 'USDT',  # Principais
    'BUSD', 'USDC',  # Stablecoins adicionais
]

# Configurações de display
MIN_PROFIT_DISPLAY = Decimal('0.001')  # 0.1% lucro mínimo para exibição
MAX_OPPORTUNITIES = 10  # Reduzido para mostrar apenas as melhores

# Configurações de Display
DISPLAY_CONFIG = {
    'update_interval': 1.0,  # Intervalo de atualização em segundos
    'max_opportunities': 10,  # Máximo de oportunidades exibidas
    'profit_thresholds': {
        'excellent': 1.0,    # Lucro > 1.0% = Excelente
        'good': 0.5,         # Lucro > 0.5% = Bom
        'viable': 0.2        # Lucro > 0.2% = Viável
    },
    'volume_thresholds': {
        'high': 0.1,         # Volume > 0.1 BTC = Alto
        'medium': 0.01,      # Volume > 0.01 BTC = Médio
        'low': 0.001         # Volume > 0.001 BTC = Baixo
    },
    'spread_thresholds': {
        'low': 0.5,          # Spread < 0.5% = Bom
        'medium': 1.0,       # Spread < 1.0% = Médio
        'high': 2.0          # Spread > 2.0% = Alto
    },
    'score_weights': {
        'profit': 0.4,       # Peso do lucro no score
        'volume': 0.4,       # Peso do volume no score
        'spread': 0.2        # Peso do spread no score
    },
    'colors': {
        'excellent': 'bold green',
        'good': 'green',
        'warning': 'yellow',
        'danger': 'red'
    }
}

# Configurações de trading
TRADING_CONFIG = {
    'use_bnb_fees': True,
    'max_slippage': Decimal('0.002'),  # Aumentado para 0.2%
    'order_type': 'LIMIT',
    'time_in_force': 'IOC',  # Mudado para IOC para execução mais rápida
    'test_mode': True,       # Força modo de teste
    'fee_rate': 0.001,      # Taxa por operação (0.1%)
    'min_profit': 0.2,      # Lucro mínimo para considerar oportunidade
    'max_spread': 0.02,     # Spread máximo aceitável (2%)
    'min_volume_btc': 0.01,  # Volume mínimo em BTC
    'min_trades': 10,       # Mínimo de trades nas últimas 24h
    'demo_balance': {
        'BTC': '1.0',
        'ETH': '10.0',
        'BNB': '100.0',
        'USDT': '10000.0'
    }
}

# Configurações de logs
LOG_CONFIG = {
    'log_trades': True,  # Salva trades em arquivo
    'log_opportunities': True,  # Salva oportunidades em arquivo
    'cleanup_days': 30,  # Remove logs mais antigos que X dias
    'level': 'INFO',
    'format': '%(asctime)s [%(levelname)s] %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
    'file': 'data/bot.log',
    'max_size': 10485760,  # 10MB
    'backup_count': 5,
    'console_output': True
}

# Configurações de banco de dados
DB_CONFIG = {
    'path': 'data/arbitrage.db',
    'backup_path': 'data/backups/',
    'max_rows': 1000000,
    'vacuum_threshold': 0.2,
    'backup_interval': 86400,  # 24 horas em segundos
    'tables': {
        'opportunities': {
            'retention_days': 30,
            'max_rows': 100000
        },
        'trades': {
            'retention_days': 90,
            'max_rows': 50000
        },
        'logs': {
            'retention_days': 7,
            'max_rows': 10000
        }
    }
}

# Configurações de ranking
RANKING_CONFIG = {
    'window_minutes': 15,  # Reduzido para 15 minutos
    'min_trades': 3,  # Reduzido para 3 trades
    'max_spread': Decimal('0.03'),  # Aumentado para 3%
    'volume_weight': Decimal('0.8'),
    'volatility_weight': Decimal('0.2')
}

# Configurações de notificações
NOTIFICATION_CONFIG = {
    'enabled': False,
    'telegram_token': '',
    'telegram_chat_id': '',
    'notify_on_trade': True,
    'notify_on_error': True,
    'min_profit_notify': Decimal('0.005'),  # 0.5% lucro mínimo para notificar
}

# Configurações de segurança
SECURITY_CONFIG = {
    'max_daily_trades': 1000,  # Aumentado limite
    'max_trade_amount': Decimal('0.05'),
    'max_daily_volume': Decimal('1.0'),
    'blacklisted_pairs': [],
    'whitelisted_pairs': []  # Vazio para considerar todos os pares
}

# Configurações de retry
RETRY_CONFIG = {
    'max_retries': 3,  # Máximo de tentativas
    'retry_delay': 1.0,  # Delay entre tentativas em segundos
    'exponential_backoff': True,  # Aumenta delay exponencialmente
}

# Configurações de cache
CACHE_CONFIG = {
    'enabled': True,
    'ttl': 30,  # Reduzido para 30 segundos
    'max_size': 2000  # Aumentado tamanho do cache
}

# Configurações de rate limit
RATE_LIMIT_CONFIG = {
    'max_requests_per_minute': 1200,
    'max_orders_per_second': 5,
    'max_orders_per_day': 100000
}
