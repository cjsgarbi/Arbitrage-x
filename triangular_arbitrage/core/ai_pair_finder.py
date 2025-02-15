import logging
from typing import List, Dict, Optional
import asyncio
from datetime import datetime, timedelta
import numpy as np
from transformers import pipeline
from ..config import BINANCE_CONFIG

logger = logging.getLogger(__name__)

class AIPairFinder:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Cache de resultados para reduzir chamadas à API
        self.cache = {}
        self.cache_duration = timedelta(minutes=15)  # Atualiza a cada 15 minutos
        self.last_update = None
        
        # Inicializa o modelo de análise de sentimento (grátis na Hugging Face)
        try:
            self.sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model="finiteautomata/bertweet-base-sentiment-analysis",
                max_length=512
            )
        except Exception as e:
            self.logger.error(f"Erro ao carregar modelo: {e}")
            self.sentiment_analyzer = None

        # Lista base de pares mais comuns
        self.base_pairs = BINANCE_CONFIG['quote_assets']
        
        # Histórico de performance
        self.performance_history = []

    async def get_potential_pairs(self) -> List[str]:
        """Retorna lista de pares com potencial de arbitragem"""
        try:
            # Verifica cache
            if self._is_cache_valid():
                return self.cache.get('pairs', [])
                
            # Lista inicial de pares da Binance
            pairs = await self._get_binance_pairs()
            
            # Analisa volume e liquidez
            scored_pairs = await self._analyze_market_data(pairs)
            
            # Aplica análise de sentimento nos pares mais promissores
            if self.sentiment_analyzer:
                scored_pairs = await self._apply_sentiment_analysis(scored_pairs)
            
            # Seleciona os melhores pares
            selected_pairs = self._select_best_pairs(scored_pairs)
            
            # Atualiza cache
            self.cache['pairs'] = selected_pairs
            self.last_update = datetime.now()
            
            return selected_pairs
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar pares: {e}")
            # Fallback para lista básica de pares
            return ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ETHBTC', 'BNBBTC']

    async def _get_binance_pairs(self) -> List[str]:
        """Obtém lista inicial de pares da Binance"""
        try:
            # TODO: Implementar chamada real à API da Binance
            # Por enquanto retorna lista fixa
            return [
                'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ETHBTC', 'BNBBTC',
                'ADAUSDT', 'DOGEUSDT', 'XRPUSDT', 'DOTUSDT', 'LINKUSDT'
            ]
        except Exception as e:
            self.logger.error(f"Erro ao obter pares da Binance: {e}")
            return []

    async def _analyze_market_data(self, pairs: List[str]) -> List[Dict]:
        """Analisa dados de mercado dos pares"""
        scored_pairs = []
        
        for pair in pairs:
            try:
                # TODO: Implementar análise real
                # Por enquanto usa score aleatório
                score = {
                    'pair': pair,
                    'volume_score': np.random.random(),
                    'volatility_score': np.random.random(),
                    'spread_score': np.random.random()
                }
                scored_pairs.append(score)
                
            except Exception as e:
                self.logger.error(f"Erro ao analisar {pair}: {e}")
                continue
                
        return scored_pairs

    async def _apply_sentiment_analysis(self, scored_pairs: List[Dict]) -> List[Dict]:
        """Aplica análise de sentimento nos pares"""
        try:
            for pair in scored_pairs:
                # Simula análise de sentimento do mercado
                if self.sentiment_analyzer:
                    sentiment = self.sentiment_analyzer(pair['pair'])[0]
                    sentiment_score = 1.0 if sentiment['label'] == 'POS' else 0.0
                    pair['sentiment_score'] = sentiment_score
                
            return scored_pairs
        except Exception as e:
            self.logger.error(f"Erro na análise de sentimento: {e}")
            return scored_pairs

    def _select_best_pairs(self, scored_pairs: List[Dict]) -> List[str]:
        """Seleciona os melhores pares baseado nos scores"""
        try:
            # Calcula score final
            for pair in scored_pairs:
                pair['final_score'] = (
                    pair.get('volume_score', 0) * 0.4 +
                    pair.get('volatility_score', 0) * 0.3 +
                    pair.get('spread_score', 0) * 0.2 +
                    pair.get('sentiment_score', 0) * 0.1
                )
            
            # Ordena por score e seleciona os top 20
            sorted_pairs = sorted(
                scored_pairs,
                key=lambda x: x['final_score'],
                reverse=True
            )
            
            return [p['pair'] for p in sorted_pairs[:20]]
            
        except Exception as e:
            self.logger.error(f"Erro ao selecionar pares: {e}")
            return []

    def _is_cache_valid(self) -> bool:
        """Verifica se o cache ainda é válido"""
        if not self.last_update:
            return False
        return datetime.now() - self.last_update < self.cache_duration

    def update_performance(self, pair: str, was_profitable: bool):
        """Atualiza histórico de performance dos pares"""
        self.performance_history.append({
            'pair': pair,
            'profitable': was_profitable,
            'timestamp': datetime.now()
        })
        
        # Mantém apenas últimos 1000 registros
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]

    async def get_performance_metrics(self) -> Dict:
        """Retorna métricas de performance do agente"""
        try:
            if not self.performance_history:
                return {}
            
            total = len(self.performance_history)
            profitable = sum(1 for p in self.performance_history if p['profitable'])
            
            return {
                'total_predictions': total,
                'success_rate': profitable / total if total > 0 else 0,
                'pairs_analyzed': len(set(p['pair'] for p in self.performance_history)),
                'last_update': self.last_update.isoformat() if self.last_update else None
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar métricas: {e}")
            return {}
