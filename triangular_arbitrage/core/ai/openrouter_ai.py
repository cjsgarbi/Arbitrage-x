"""
Implementação do OpenRouter AI para análise de arbitragem
"""
from .base_ai import BaseAI
from typing import Dict, Optional, List
import logging
import requests
import time
import os
from tenacity import retry, stop_after_attempt, wait_exponential
from limits import strategies, parse
from limits.storage import MemoryStorage
from functools import wraps
from ..metrics_manager import metrics_manager

logger = logging.getLogger(__name__)

# Configuração do Rate Limiting
RATE_LIMIT_STRING = "60/minute"  # 60 requisições por minuto
STORAGE = MemoryStorage()
STRATEGY = strategies.MovingWindowRateLimiter(STORAGE)
LIMIT = parse(RATE_LIMIT_STRING)

# Configuração do Cache
CACHE_ENABLED = os.environ.get("OPENROUTER_CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL = int(os.environ.get("OPENROUTER_CACHE_TTL", "60"))  # Default 60 segundos

# Configuração de Custos
MAX_COST_PER_ANALYSIS = float(os.environ.get("MAX_COST_PER_ANALYSIS", "0.05"))  # USD
TOTAL_COST_BUDGET = float(os.environ.get("TOTAL_COST_BUDGET", "10.0"))  # USD
COST_ALERT_THRESHOLD = float(os.environ.get("COST_ALERT_THRESHOLD", "0.8"))  # 80% do orçamento

class CostTracker:
    def __init__(self, budget: float):
        self.budget = budget
        self.total_cost = 0.0
        self.last_alert_time = 0

    def add_cost(self, cost: float):
        self.total_cost += cost
        
        # Envia alerta se atingir o threshold
        if self.total_cost >= self.budget * COST_ALERT_THRESHOLD and \
           time.time() - self.last_alert_time > 3600:  # Apenas 1 alerta por hora
            logger.warning(f"Atingido {COST_ALERT_THRESHOLD*100}% do orçamento: {self.total_cost:.2f} / {self.budget:.2f} USD")
            self.last_alert_time = time.time()
            
        if self.total_cost >= self.budget:
            logger.critical(f"Orçamento excedido: {self.total_cost:.2f} / {self.budget:.2f} USD. Desativando análises.")
            return True
        return False

    def get_total_cost(self) -> float:
        return self.total_cost

cost_tracker = CostTracker(TOTAL_COST_BUDGET)

def ratelimit():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if STRATEGY.hit(LIMIT):
                logger.warning("Rate limit atingido. Aguardando...")
                time.sleep(1)  # Aguarda um pouco antes de tentar novamente
                return {"error": "Rate limit atingido"}
            return func(*args, **kwargs)
        return wrapper
    return decorator

class OpenRouterAI(BaseAI):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self.is_connected = False
        self.base_url = "https://openrouter.ai/api/v1"
        self.response_cache = {}  # Cache de respostas
        
    def setup(self, config: Dict) -> bool:
        try:
            self.config = config
            self.api_key = config.get('api_key')
            
            if not self.api_key:
                self.logger.error("API key não fornecida")
                return False
                
            # Testa a conexão com o OpenRouter
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(f"{self.base_url}/models", headers=headers)
            if response.status_code == 200:
                self.is_connected = True
                self.is_ready = True
                self.logger.info("OpenRouter conectado com sucesso")
                return True
            else:
                self.logger.error(f"Erro na conexão com OpenRouter: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro ao configurar OpenRouter: {e}")
            self.is_connected = False
            self.is_ready = False
            return False
            
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    @ratelimit()
    def analyze(self, data: Dict) -> Dict:
        start_time = metrics_manager.start_analysis()
        cost = 0
        success = False
        cache_key = str(data)  # Simplifica a chave do cache
        
        if CACHE_ENABLED and cache_key in self.response_cache:
            cached_response, timestamp = self.response_cache[cache_key]
            if time.time() - timestamp <= CACHE_TTL:
                logger.debug("Retornando resposta do cache")
                metrics_manager.end_analysis(start_time, True, cost)
                return cached_response
            else:
                logger.debug("Cache expirado. Requisitando nova análise.")
        
        try:
            if not self.is_connected:
                self.logger.error("OpenRouter não está conectado")
                metrics_manager.end_analysis(start_time, False, cost)
                return {"error": "AI not connected"}
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Prepara os dados para análise
            payload = {
                "model": self.config.get('model_name', 'gpt-4'),
                "messages": [
                    {
                        "role": "system",
                        "content": "Você é um especialista em análise de arbitragem triangular."
                    },
                    {
                        "role": "user",
                        "content": str(data)
                    }
                ]
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Calcula o custo da análise (estimativa)
                input_tokens = len(str(data)) / 4  # Aproximação
                output_tokens = len(result['choices'][0]['message']['content']) / 4 # Aproximação
                cost = (input_tokens + output_tokens) / 1000 * MAX_COST_PER_ANALYSIS
                
                # Verifica se o orçamento foi excedido
                if cost_tracker.add_cost(cost):
                    metrics_manager.end_analysis(start_time, False, cost)
                    return {"error": "Orçamento excedido. Análises desativadas."}
                
                # Armazena no cache
                if CACHE_ENABLED:
                    self.response_cache[cache_key] = (result, time.time())
                    logger.debug("Resposta armazenada no cache")
                
                success = True
                metrics_manager.end_analysis(start_time, True, cost)
                return {
                    "status": "success",
                    "analysis": result['choices'][0]['message']['content']
                }
            else:
                self.logger.error(f"Erro na análise: {response.text}")
                metrics_manager.end_analysis(start_time, False, cost)
                raise Exception(f"Falha na análise: {response.text}")
                
        except Exception as e:
            self.logger.error(f"Erro ao analisar dados: {e}")
            metrics_manager.end_analysis(start_time, False, cost)
            return {"error": str(e)}
            
    def get_supported_features(self) -> List[str]:
        return [
            'market_analysis',
            'arbitrage_detection',
            'risk_assessment',
            'real_time_processing'
        ]
        
    def validate_rate_limits(self) -> bool:
        """Valida limites de taxa do OpenRouter"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(f"{self.base_url}/limits", headers=headers)
            return response.status_code == 200
        except:
            return False
