"""
Agente de arbitragem usando OpenRouter e análise vetorial
"""
from typing import Dict, List, Optional, Tuple
import logging
import asyncio
from decimal import Decimal
import time
from datetime import datetime

from .openrouter_ai import OpenRouterAI
from ..storage.vector_store import VectorStore
from triangular_arbitrage.utils.log_config import setup_logging
from ..binance_init import AsyncClient, BinanceAPIException
from ..metrics_manager import metrics_manager

logger = logging.getLogger(__name__)

class ArbitrageAgent:
    def __init__(self, api_key: str, model_name: str = "gpt-4"):
        """
        Inicializa o agente de arbitragem
        
        Args:
            api_key: Chave API do OpenRouter
            model_name: Nome do modelo a ser usado
        """
        self.ai = OpenRouterAI(api_key)
        self.vector_store = VectorStore()
        self.last_analysis = {}
        self.cache = {}
        self.cache_ttl = 500  # 500ms
        
        # Configurações
        self.min_profit = Decimal('0.3')  # 0.3%
        self.min_liquidity = Decimal('2.0')  # 2x volume necessário
        self.max_spread = Decimal('0.15')  # 0.15%
        self.min_confidence = 75  # Score mínimo de confiança
        
        # Configurações de volume e volatilidade
        self.min_volume = Decimal('100000')  # Volume mínimo em USDT
        self.max_volatility = Decimal('5.0')  # Máxima volatilidade em %
        self.min_order_book_depth = Decimal('50000')  # Profundidade mínima
        
        # Setup inicial
        self._setup_logging()
        self._setup_ai(model_name)
        
    def _setup_logging(self):
        """Configura logging específico para o agente"""
        self.loggers = setup_logging("arbitrage_agent")
        
    def _setup_ai(self, model_name: str):
        """Configura o modelo de IA"""
        config = {
            "model_name": model_name,
            "temperature": 0.3,
            "max_tokens": 150
        }
        self.ai.setup(config)
        
    def _filter_pairs(self, prices: Dict, volumes: Dict) -> Dict[str, List[Tuple[str, Decimal]]]:
        """
        Filtra e prioriza pares de negociação
        
        Args:
            prices: Dicionário de preços
            volumes: Dicionário de volumes
            
        Returns:
            Dict com pares filtrados e ordenados por base
        """
        result = {}
        bases = ['BTC', 'ETH', 'USDT', 'BNB']
        
        for base in bases:
            # Filtra pares por base e volume mínimo
            pairs = [
                (k, Decimal(str(v))) for k, v in prices.items()
                if k.endswith(base) and 
                volumes.get(k, 0) >= float(self.min_volume)
            ]
            
            # Ordena por volume decrescente
            pairs.sort(key=lambda x: volumes.get(x[0], 0), reverse=True)
            result[base] = pairs
            
        return result
        
    async def detect_opportunities(self, prices: Dict, volumes: Dict, order_books: Dict) -> List[Dict]:
        """
        Detecta oportunidades de arbitragem triangular
        
        Args:
            prices: Dicionário com preços atuais
            volumes: Dicionário com volumes 24h
            order_books: Dicionário com profundidade do order book
            
        Returns:
            Lista de oportunidades detectadas
        """
        start_time = metrics_manager.start_analysis()
        success = False
        cost = 0
        opportunities = []
        
        try:
            # Filtra e prioriza pares
            filtered_pairs = self._filter_pairs(prices, volumes)
            
            for base, pairs in filtered_pairs.items():
                for pair_a, price_a in pairs:
                    for pair_b, price_b in pairs:
                        if pair_a != pair_b:
                            # Verifica se existe par C que fecha o triângulo
                            symbol_a = pair_a.replace(base, '')
                            symbol_b = pair_b.replace(base, '')
                            pair_c = f"{symbol_a}{symbol_b}"
                            
                            if pair_c in prices:
                                # Verifica liquidez e profundidade
                                if not self._check_liquidity(
                                    order_books.get(pair_a, {}),
                                    order_books.get(pair_b, {}),
                                    order_books.get(pair_c, {})
                                ):
                                    continue
                                
                                opportunity = self._calculate_opportunity(
                                    pair_a, pair_b, pair_c,
                                    price_a, price_b, prices[pair_c],
                                    base,
                                    volumes
                                )
                                
                                if opportunity and self._validate_opportunity(opportunity):
                                    opportunities.append(opportunity)
                                    
            # Ordena por lucro potencial
            opportunities.sort(key=lambda x: x['profit_percentage'], reverse=True)
            success = True
            return opportunities
            
        except Exception as e:
            logger.error(f"Erro ao detectar oportunidades: {e}")
            return []
        finally:
            metrics_manager.end_analysis(start_time, success, cost)
            
    def _check_liquidity(self, book_a: Dict, book_b: Dict, book_c: Dict) -> bool:
        """
        Verifica se há liquidez suficiente nos order books
        
        Args:
            book_a: Order book do par A
            book_b: Order book do par B
            book_c: Order book do par C
            
        Returns:
            bool: True se há liquidez suficiente
        """
        def get_depth(book: Dict) -> Decimal:
            bids = Decimal(sum(Decimal(str(p)) * Decimal(str(q)) for p, q in book.get('bids', [])))
            asks = Decimal(sum(Decimal(str(p)) * Decimal(str(q)) for p, q in book.get('asks', [])))
            return min(bids, asks)
            
        return all(
            get_depth(book) >= self.min_order_book_depth
            for book in [book_a, book_b, book_c]
        )
            
    def _calculate_opportunity(self, 
                             pair_a: str, 
                             pair_b: str, 
                             pair_c: str,
                             price_a: Decimal,
                             price_b: Decimal,
                             price_c: Decimal,
                             base: str,
                             volumes: Dict) -> Optional[Dict]:
        """Calcula detalhes da oportunidade de arbitragem"""
        try:
            # Calcula lucro potencial
            rate = (Decimal('1') / price_a) * price_b * (Decimal('1') / price_c)
            profit_percentage = (rate - Decimal('1')) * Decimal('100')
            
            if profit_percentage > self.min_profit:
                min_volume = min(
                    volumes.get(pair_a, 0),
                    volumes.get(pair_b, 0),
                    volumes.get(pair_c, 0)
                )
                
                return {
                    'pairs': [pair_a, pair_b, pair_c],
                    'base': base,
                    'prices': {
                        pair_a: float(price_a),
                        pair_b: float(price_b),
                        pair_c: float(price_c)
                    },
                    'volumes': {
                        pair_a: volumes.get(pair_a, 0),
                        pair_b: volumes.get(pair_b, 0),
                        pair_c: volumes.get(pair_c, 0)
                    },
                    'profit_percentage': float(profit_percentage),
                    'volume_24h': float(min_volume),
                    'timestamp': datetime.now().timestamp(),
                    'path': f"{pair_a} → {pair_b} → {pair_c}"
                }
                
            return None
            
        except Exception as e:
            logger.error(f"Erro ao calcular oportunidade: {e}")
            return None
            
    def _validate_opportunity(self, opportunity: Dict) -> bool:
        """Valida se uma oportunidade atende os critérios mínimos"""
        try:
            # Verifica cache para evitar análises repetidas
            cache_key = f"{opportunity['path']}"
            if cache_key in self.cache:
                cached_result = self.cache[cache_key]
                if time.time() - cached_result['timestamp'] < self.cache_ttl/1000:
                    return cached_result['valid']
                    
            # Validações básicas
            if opportunity['profit_percentage'] < float(self.min_profit):
                return False
            
            if opportunity['volume_24h'] < float(self.min_volume):
                return False
                
            # Análise com IA
            analysis = self.analyze_opportunity(opportunity)
            
            # Armazena resultado no cache
            is_valid = (
                analysis.get('confidence_score', 0) >= self.min_confidence and
                analysis.get('risk_score', 10) <= 7 and
                Decimal(str(analysis.get('slippage', 1))) <= self.max_spread and
                analysis.get('volume_sufficient', False)
            )
            
            self.cache[cache_key] = {
                'timestamp': time.time(),
                'valid': is_valid
            }
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Erro ao validar oportunidade: {e}")
            return False
            
    def analyze_opportunity(self, opportunity: Dict) -> Dict:
        """
        Analisa uma oportunidade usando OpenRouter
        
        Args:
            opportunity: Dicionário com dados da oportunidade
            
        Returns:
            Dicionário com resultado da análise
        """
        try:
            # Busca oportunidades similares
            similar_ops = self.vector_store.search_similar(opportunity, k=5)
            
            # Prepara prompt para análise
            prompt = self._create_analysis_prompt(opportunity, similar_ops)
            
            # Envia para análise
            result = self.ai.analyze({
                "opportunity": opportunity,
                "prompt": prompt,
                "history": similar_ops
            })
            
            # Armazena resultado
            if result.get('status') == 'success':
                self.vector_store.add_item({
                    **opportunity,
                    'analysis': result['analysis']
                })
                
            return result
            
        except Exception as e:
            logger.error(f"Erro ao analisar oportunidade: {e}")
            return {'error': str(e)}
            
    def _create_analysis_prompt(self, opportunity: Dict, similar_ops: List) -> str:
        """Cria prompt otimizado para análise da IA"""
        return f"""
        Analise a seguinte oportunidade de arbitragem:
        Par A/B: {opportunity['pairs'][0]} - Preço: {opportunity['prices'][opportunity['pairs'][0]]}
        Par B/C: {opportunity['pairs'][1]} - Preço: {opportunity['prices'][opportunity['pairs'][1]]}
        Par A/C: {opportunity['pairs'][2]} - Preço: {opportunity['prices'][opportunity['pairs'][2]]}
        
        Volume 24h:
        {opportunity['pairs'][0]}: {opportunity['volumes'][opportunity['pairs'][0]]} USDT
        {opportunity['pairs'][1]}: {opportunity['volumes'][opportunity['pairs'][1]]} USDT
        {opportunity['pairs'][2]}: {opportunity['volumes'][opportunity['pairs'][2]]} USDT
        
        Histórico de execuções similares: {len(similar_ops)} encontradas
        Taxa média de sucesso: {self._calculate_success_rate(similar_ops)}%

        Considere:
        1. Volume 24h dos pares
        2. Profundidade do order book
        3. Volatilidade recente
        4. Spread atual
        5. Histórico de execuções

        Forneça:
        1. Score de confiança (1-100)
        2. Risco estimado (1-10)
        3. Slippage provável
        4. Tempo máximo recomendado
        5. Recomendação de execução
        """
        
    def _calculate_success_rate(self, similar_ops: List) -> float:
        """Calcula taxa de sucesso com base em operações similares"""
        if not similar_ops:
            return 0.0
            
        successful = sum(1 for op in similar_ops 
                        if op.get('status') == 'executed' and 
                        op.get('profit_real', 0) > 0)
                        
        return (successful / len(similar_ops)) * 100