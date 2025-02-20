"""
Analisador de oportunidades de arbitragem usando IA
"""
from typing import Dict, List, Optional
import logging
from datetime import datetime
from decimal import Decimal
import asyncio
from transformers import pipeline
from ...utils.error_handler import handle_errors
from ...utils.debug_logger import debug_logger
from ...config import AI_CONFIG

logger = logging.getLogger(__name__)

class ArbitrageAnalyzer:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.test_mode = self.config.get('test_mode', True)
        self.mode_config = AI_CONFIG['test_mode'] if self.test_mode else AI_CONFIG['prod_mode']
        
        # Cache de análises
        self.analysis_cache = {}
        self.cache_ttl = AI_CONFIG.get('analysis_cache_ttl', 500)  # 500ms default
        
        # Histórico de operações
        self.operation_history = []
        
    @handle_errors(retries=2, delay=0.5)
    async def analyze_opportunity(self, opportunity: Dict) -> Dict:
        """Analisa uma oportunidade de arbitragem"""
        try:
            # Verifica cache
            cache_key = f"{opportunity['path']}"
            if cache_key in self.analysis_cache:
                cached = self.analysis_cache[cache_key]
                if (datetime.now().timestamp() - cached['timestamp']) < (self.cache_ttl / 1000):
                    return cached['analysis']

            # Análise básica
            profit = Decimal(str(opportunity['profit_percentage']))
            if profit < self.mode_config['min_profit']:
                return self._create_analysis_result(confidence_score=0, risk_score=10)

            # Análise profunda com base no histórico
            similar_ops = self._find_similar_operations(opportunity)
            success_rate = self._calculate_success_rate(similar_ops)

            # Calcula scores
            confidence_score = self._calculate_confidence_score(opportunity, similar_ops)
            risk_score = self._calculate_risk_score(opportunity, similar_ops)
            
            result = self._create_analysis_result(
                confidence_score=confidence_score,
                risk_score=risk_score,
                success_rate=success_rate,
                success_history=bool(similar_ops),
                volume_sufficient=self._check_volume_requirements(opportunity)
            )

            # Atualiza cache
            self.analysis_cache[cache_key] = {
                'timestamp': datetime.now().timestamp(),
                'analysis': result
            }

            return result

        except Exception as e:
            logger.error(f"Erro na análise de oportunidade: {e}")
            return self._create_analysis_result(confidence_score=0, risk_score=10)

    def _find_similar_operations(self, opportunity: Dict) -> List[Dict]:
        """Encontra operações similares no histórico"""
        similar_ops = []
        current_path = opportunity['path']

        for op in self.operation_history:
            if op['path'] == current_path:
                similar_ops.append(op)

        return similar_ops[-20:]  # Retorna as 20 operações mais recentes

    def _calculate_success_rate(self, operations: List[Dict]) -> float:
        """Calcula taxa de sucesso de operações similares"""
        if not operations:
            return 0.0

        successful = sum(1 for op in operations if op.get('success', False))
        return (successful / len(operations)) * 100

    def _calculate_confidence_score(self, opportunity: Dict, similar_ops: List[Dict]) -> float:
        """Calcula score de confiança para a oportunidade"""
        if not opportunity:
            return 0.0

        # Base score from profit
        base_score = min(float(opportunity['profit_percentage']) * 20, 50)
        
        # History score
        history_score = 0
        if similar_ops:
            success_rate = self._calculate_success_rate(similar_ops)
            history_score = min(success_rate / 2, 50)

        return base_score + history_score

    def _calculate_risk_score(self, opportunity: Dict, similar_ops: List[Dict]) -> int:
        """Calcula score de risco (1-10)"""
        base_risk = 5

        # Ajusta baseado no profit (maior profit = maior risco)
        profit_risk = min(float(opportunity['profit_percentage']), 5)
        base_risk += profit_risk

        # Ajusta baseado no histórico
        if similar_ops:
            success_rate = self._calculate_success_rate(similar_ops)
            history_adjustment = (100 - success_rate) / 20
            base_risk += history_adjustment

        return min(max(int(base_risk), 1), 10)

    def _check_volume_requirements(self, opportunity: Dict) -> bool:
        """Verifica se volumes atendem requisitos mínimos"""
        try:
            return all(
                float(volume) >= 100.0  # Mínimo 100 USDT
                for volume in opportunity.get('volumes', {}).values()
            )
        except (ValueError, AttributeError):
            return False

    def _create_analysis_result(self, confidence_score: float = 0, 
                              risk_score: int = 10,
                              success_rate: float = 0,
                              success_history: bool = False,
                              volume_sufficient: bool = False) -> Dict:
        """Cria resultado padronizado da análise"""
        return {
            'confidence_score': confidence_score,
            'risk_score': risk_score,
            'success_rate': success_rate,
            'success_history': success_history,
            'volume_sufficient': volume_sufficient,
            'timestamp': datetime.now().isoformat()
        }

    async def store_result(self, opportunity: Dict, result: Dict):
        """Armazena resultado de uma operação"""
        operation = {
            'path': opportunity['path'],
            'profit_expected': float(opportunity['profit_percentage']),
            'profit_real': result.get('profit', 0),
            'success': result.get('success', False),
            'timestamp': datetime.now().isoformat()
        }

        self.operation_history.append(operation)
        
        # Mantém apenas últimas 1000 operações
        if len(self.operation_history) > 1000:
            self.operation_history = self.operation_history[-1000:]