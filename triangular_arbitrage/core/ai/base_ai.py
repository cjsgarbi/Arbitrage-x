"""
Classe base para implementações de IA
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

class BaseAI(ABC):
    """Classe abstrata base para implementações de IA"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Inicializa a classe base de IA
        
        Args:
            config (Dict, optional): Configurações do modelo
        """
        self.config = config or {}
        self.model = None
        self.is_ready = False

    @abstractmethod
    def setup(self, config: Dict) -> bool:
        """
        Configura o modelo de IA
        
        Args:
            config (Dict): Configurações específicas do modelo
            
        Returns:
            bool: True se configurado com sucesso, False caso contrário
        """
        pass

    @abstractmethod
    def analyze(self, data: Dict) -> Dict:
        """
        Analisa dados usando o modelo de IA
        
        Args:
            data (Dict): Dados para análise
            
        Returns:
            Dict: Resultados da análise
        """
        pass

    @abstractmethod
    def get_supported_features(self) -> List[str]:
        """
        Lista recursos suportados pelo modelo
        
        Returns:
            List[str]: Lista de recursos suportados
        """
        pass

    def is_initialized(self) -> bool:
        """
        Verifica se o modelo está inicializado
        
        Returns:
            bool: True se inicializado, False caso contrário
        """
        return self.model is not None and self.is_ready

    def validate_config(self, config: Dict) -> bool:
        """
        Valida configurações do modelo
        
        Args:
            config (Dict): Configurações para validar
            
        Returns:
            bool: True se válido, False caso contrário
        """
        required_fields = ['model_name', 'provider']
        return all(field in config for field in required_fields)

    def get_model_info(self) -> Dict:
        """
        Retorna informações sobre o modelo atual
        
        Returns:
            Dict: Informações do modelo
        """
        return {
            'provider': self.config.get('provider', 'unknown'),
            'model_name': self.config.get('model_name', 'unknown'),
            'is_ready': self.is_ready,
            'supported_features': self.get_supported_features()
        }
