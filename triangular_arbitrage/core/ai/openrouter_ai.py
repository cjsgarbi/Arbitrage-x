from .base_ai import BaseAI
from typing import Dict, Optional, List
import logging

class OpenRouterAI(BaseAI):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self.is_connected = False
        
    def setup(self, config: Dict) -> bool:
        try:
            self.config = config
            # Mesmo sem API key, marcamos como conectado para testes
            self.is_connected = True
            self.is_ready = True
            self.logger.info("OpenRouter inicializado em modo de teste")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao configurar OpenRouter: {e}")
            self.is_connected = False
            self.is_ready = False
            return False
            
    def analyze(self, data: Dict) -> Dict:
        try:
            if not self.is_connected:
                self.logger.error("OpenRouter não está conectado")
                return {"error": "AI not connected"}
            
            # Aqui implementaríamos a análise real usando o modelo
            # Por enquanto retornamos sucesso para teste
            return {"status": "success", "data": data}
        except Exception as e:
            self.logger.error(f"Erro ao analisar dados: {e}")
            return {"error": str(e)}
            
    def get_supported_features(self) -> List[str]:
        # Sobrescrevendo para adicionar features específicas do OpenRouter
        features = super().get_supported_features()
        features.extend([
            'real_time_analysis',
            'market_prediction',
            'trend_detection'
        ])
        return features
