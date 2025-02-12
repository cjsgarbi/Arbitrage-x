import logging
import sys
import os
from datetime import datetime

# Configura logging para arquivo
os.makedirs('debug_logs', exist_ok=True)
log_file = f'debug_logs/debug_{datetime.now():%Y%m%d_%H%M%S}.log'

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

# Testa o ambiente
logging.info("=== Teste do Ambiente Python ===")
logging.info(f"Python path: {sys.executable}")
logging.info(f"Python version: {sys.version}")

# Testa as dependências
try:
    import fastapi
    logging.info("FastAPI OK")
except ImportError as e:
    logging.error(f"Erro ao importar FastAPI: {e}")

try:
    from binance.client import Client
    logging.info("python-binance OK")
except ImportError as e:
    logging.error(f"Erro ao importar python-binance: {e}")

try:
    import uvicorn
    logging.info("uvicorn OK")
except ImportError as e:
    logging.error(f"Erro ao importar uvicorn: {e}")

logging.info("=== Fim do Teste ===")