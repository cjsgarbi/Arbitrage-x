"""
Configurações para modelos de IA
"""
from typing import Dict, Optional
from dataclasses import dataclass, asdict

@dataclass
class AIConfig:
    """
    Configurações para modelos de IA
    
    Attributes:
        provider (str): Provedor de IA ('huggingface', 'openrouter')
        model_name (str): Nome do modelo a ser usado
        api_key (Optional[str]): Chave de API (se necessário)
        batch_size (int): Tamanho do lote para processamento
        max_retries (int): Número máximo de tentativas
        timeout (int): Timeout em segundos
        cache_ttl (int): Tempo de vida do cache em segundos
    """
    
    provider: str = "openrouter"
    model_name: str = "deepseek/deepseek-r1-distill-llama-70b:free"
    api_key: Optional[str] = None
    batch_size: int = 32
    max_retries: int = 3
    timeout: int = 30
    cache_ttl: int = 300  # 5 minutos
    
    def to_dict(self) -> Dict:
        """Converte configurações para dicionário"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, config: Dict) -> 'AIConfig':
        """Cria instância de configuração a partir de dicionário"""
        return cls(**config)
    
    def validate(self) -> bool:
        """Valida configurações"""
        if not self.provider or not self.model_name:
            return False
            
        if self.provider not in ["huggingface", "openrouter"]:
            return False
            
        if self.provider == "openrouter" and not self.api_key:
            return False
            
        if any(v <= 0 for v in [self.batch_size, self.max_retries, self.timeout, self.cache_ttl]):
            return False
            
        return True

    def get_provider_config(self) -> Dict:
        """Retorna configurações específicas do provedor"""
        provider_configs = {
            "huggingface": {
                "use_auth": False,
                "model_type": "embeddings",
                "max_length": 512
            },
            "openrouter": {
                "use_auth": True,
                "model_type": "completion",
                "temperature": 0.7,
                "max_tokens": 256
            }
        }
        return provider_configs.get(self.provider, {})

    def get_feature_flags(self) -> Dict[str, bool]:
        """Retorna flags de recursos disponíveis"""
        return {
            "use_cache": True,
            "use_batching": self.batch_size > 1,
            "use_retry": self.max_retries > 0,
            "requires_auth": self.provider != "huggingface"
        }
