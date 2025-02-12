print("Teste do ambiente Python")
import sys
print(f"Python path: {sys.executable}")
print(f"Python version: {sys.version}")

# Tenta importar algumas dependências principais
try:
    import fastapi
    print("FastAPI OK")
except ImportError as e:
    print(f"Erro ao importar FastAPI: {e}")

try:
    from binance.client import Client
    print("python-binance OK")
except ImportError as e:
    print(f"Erro ao importar python-binance: {e}")

try:
    import uvicorn
    print("uvicorn OK")
except ImportError as e:
    print(f"Erro ao importar uvicorn: {e}")