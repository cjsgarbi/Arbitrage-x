import logging
import time
from typing import List, Dict, Optional, Any, Union
import asyncio
from datetime import datetime, timedelta
import numpy as np
from transformers import pipeline
from ..config import BINANCE_CONFIG
from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException
from ..utils.error_handler import handle_errors, APIError, ValidationError, error_tracker
from ..utils.debug_logger import debug_logger
from ..utils.circuit_breaker import circuit_breaker, api_circuit
from ..utils.performance_metrics import metrics_manager

logger = logging.getLogger(__name__)

class AIPairFinder:
    def __init__(self, config: Optional[Dict] = None):
        operation_id = debug_logger.start_operation('init_ai_pair_finder', {'config': config})
        
        try:
            self.config = config or {}
            self.logger = logging.getLogger(__name__)
            self.client = None
            
            # Cache de resultados para reduzir chamadas à API
            self.cache = {}
            self.cache_duration = timedelta(minutes=15)  # Atualiza a cada 15 minutos
            self.last_update = None
            
            debug_logger.log_event(
                'cache_config',
                'Configuração de cache inicializada',
                {'cache_duration_minutes': 15}
            )
            
            # Inicializa o modelo de análise de sentimento (grátis na Hugging Face)
            try:
                debug_logger.log_event(
                    'sentiment_model_init',
                    'Iniciando carregamento do modelo de sentimento'
                )
                
                self.sentiment_analyzer = pipeline(
                    "sentiment-analysis",
                    model="finiteautomata/bertweet-base-sentiment-analysis",
                    max_length=512
                )
                
                debug_logger.log_event(
                    'sentiment_model_loaded',
                    'Modelo de sentimento carregado com sucesso',
                    {'model': 'bertweet-base-sentiment-analysis'}
                )
                
            except Exception as e:
                debug_logger.log_event(
                    'sentiment_model_error',
                    'Erro ao carregar modelo de sentimento',
                    {'error': str(e)},
                    level=logging.ERROR
                )
                self.sentiment_analyzer = None

            # Lista base de pares mais comuns
            self.base_pairs = BINANCE_CONFIG['quote_assets']
            debug_logger.log_event(
                'base_pairs_loaded',
                'Pares base carregados',
                {'pairs': self.base_pairs}
            )
            
            # Histórico de performance
            self.performance_history = []
            debug_logger.end_operation(operation_id, 'success')
            
        except Exception as e:
            debug_logger.end_operation(
                operation_id,
                'error',
                {'error': str(e)}
            )
            raise

    async def get_potential_pairs(self) -> List[str]:
        """Retorna lista de pares com potencial de arbitragem"""
        operation_id = debug_logger.start_operation('get_potential_pairs')
        
        try:
            debug_logger.log_event('cache_check', 'Verificando cache')
            
            if self._is_cache_valid():
                cached_pairs = self.cache.get('pairs', [])
                debug_logger.log_event('cache_hit', 'Usando dados do cache', {'pairs_count': len(cached_pairs)})
                return cached_pairs
                
            debug_logger.log_event('binance_pairs_fetch', 'Buscando pares da Binance')
            pairs = await self._get_binance_pairs()
            debug_logger.log_metric('pairs_found', len(pairs))
            
            debug_logger.log_event('market_analysis', 'Iniciando análise de mercado')
            scored_pairs = await self._analyze_market_data(pairs)
            debug_logger.log_metric('pairs_analyzed', len(scored_pairs))
            
            if self.sentiment_analyzer:
                debug_logger.log_event('sentiment_analysis', 'Iniciando análise de sentimento')
                scored_pairs = await self._apply_sentiment_analysis(scored_pairs)
                debug_logger.log_metric('sentiment_analyzed', len(scored_pairs))
            
            debug_logger.log_event('pair_selection', 'Selecionando melhores pares')
            selected_pairs = self._select_best_pairs(scored_pairs)
            
            self.cache['pairs'] = selected_pairs
            self.last_update = datetime.now()
            
            debug_logger.end_operation(operation_id, 'success', {
                'pairs_found': len(pairs),
                'pairs_analyzed': len(scored_pairs),
                'pairs_selected': len(selected_pairs)
            })
            
            return selected_pairs
            
        except Exception as e:
            debug_logger.log_event('error', 'Erro ao buscar pares', {'error': str(e)}, level=logging.ERROR)
            debug_logger.end_operation(operation_id, 'error', {'error': str(e)})
            
            fallback_pairs = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ETHBTC', 'BNBBTC']
            debug_logger.log_event('fallback', 'Usando pares fallback', {'pairs': fallback_pairs})
            return fallback_pairs

    def _is_cache_valid(self) -> bool:
        """Verifica se o cache ainda é válido"""
        if not self.last_update:
            return False
        return datetime.now() - self.last_update < self.cache_duration

    @handle_errors(retries=3, delay=1.0)
    @circuit_breaker(api_circuit, "get_binance_pairs")
    async def _get_binance_pairs(self) -> List[str]:
        """Obtém lista real de pares da Binance"""
        start_time = time.time()
        try:
            if not self.client:
                client_start = time.time()
                self.client = await AsyncClient.create()
                client_latency = time.time() - client_start
                metrics_manager.record_metric(
                    'binance_client_init_latency',
                    client_latency,
                    {'status': 'success' if self.client else 'failed', 'latency': str(client_latency)}
                )
                
                if not self.client:
                    raise APIError(
                        "Falha ao criar cliente Binance",
                        "BINANCE_CLIENT_ERROR",
                        {"reason": "Cliente não inicializado"}
                    )
            
            api_start = time.time()
            exchange_info = await self.client.get_exchange_info()
            api_latency = time.time() - api_start
            
            metrics_manager.record_metric(
                'binance_api_latency',
                api_latency,
                {'operation': 'get_exchange_info'}
            )
            if not exchange_info or 'symbols' not in exchange_info:
                raise APIError(
                    "Dados inválidos da API Binance",
                    "INVALID_EXCHANGE_INFO",
                    {"response": str(exchange_info)}
                )

            process_start = time.time()
            valid_pairs = []
            error_count = 0
            
            for symbol in exchange_info['symbols']:
                try:
                    if (symbol['status'] == 'TRADING' and
                        symbol['isSpotTradingAllowed'] and
                        not symbol['isMarginTradingAllowed']):  # Apenas spot trading
                        valid_pairs.append(symbol['symbol'])
                except KeyError as ke:
                    error_count += 1
                    error_tracker.track_error(
                        ValidationError(
                            "Dados de símbolo inválidos",
                            "INVALID_SYMBOL_DATA",
                            {"symbol": str(symbol), "missing_key": str(ke)}
                        )
                    )
                    continue
            
            processing_time = time.time() - process_start
            metrics_manager.record_metric(
                'pair_processing_time',
                processing_time,
                {
                    'total_pairs': str(len(exchange_info['symbols'])),
                    'valid_pairs': str(len(valid_pairs)),
                    'error_count': str(error_count)
                }
            )
            
            if not valid_pairs:
                raise ValidationError(
                    "Nenhum par válido encontrado",
                    "NO_VALID_PAIRS",
                    {"total_symbols": len(exchange_info['symbols'])}
                )
            
            self.logger.info(f"Obtidos {len(valid_pairs)} pares válidos da Binance")
            return valid_pairs
            
        except BinanceAPIException as e:
            error_tracker.track_error(
                APIError(
                    f"Erro na API Binance: {e.message}",
                    "BINANCE_API_ERROR",
                    {"code": e.code, "message": e.message}
                )
            )
            raise
        except Exception as e:
            error_tracker.track_error(e)
            raise APIError(
                "Erro inesperado ao obter pares",
                "UNEXPECTED_ERROR",
                {"error": str(e)}
            )

    @handle_errors(retries=3, delay=1.0)
    @circuit_breaker(api_circuit, "analyze_market_data")
    async def _analyze_market_data(self, pairs: List[str]) -> List[Dict]:
        """Analisa dados reais de mercado dos pares"""
        if not pairs:
            raise ValidationError(
                "Lista de pares vazia",
                "EMPTY_PAIRS_LIST"
            )

        scored_pairs = []
        errors = []

        for pair in pairs:
            try:
                if not isinstance(pair, str) or len(pair) < 4:
                    raise ValidationError(
                        f"Par inválido: {pair}",
                        "INVALID_PAIR_FORMAT",
                        {"pair": pair}
                    )

                # Verifica e inicializa cliente se necessário
                if not self.client:
                    self.client = await AsyncClient.create()
                    if not self.client:
                        raise APIError(
                            "Falha ao criar cliente Binance",
                            "BINANCE_CLIENT_ERROR",
                            {"reason": "Cliente não inicializado"}
                        )

                # Obtém dados reais do mercado com timeout
                try:
                    ticker_task = asyncio.create_task(
                        asyncio.wait_for(
                            self.client.get_ticker(symbol=pair),
                            timeout=5.0
                        )
                    )
                    depth_task = asyncio.create_task(
                        asyncio.wait_for(
                            self.client.get_order_book(symbol=pair, limit=5),
                            timeout=5.0
                        )
                    )
                    
                    ticker, depth = await asyncio.gather(ticker_task, depth_task)
                except asyncio.TimeoutError:
                    raise APIError(
                        f"Timeout ao obter dados do par {pair}",
                        "API_TIMEOUT",
                        {"pair": pair}
                    )

                # Valida dados recebidos
                required_ticker_fields = ['volume', 'weightedAvgPrice', 'priceChangePercent', 'lastPrice']
                if not all(field in ticker for field in required_ticker_fields):
                    raise ValidationError(
                        f"Dados de ticker incompletos para {pair}",
                        "INCOMPLETE_TICKER_DATA",
                        {"ticker": ticker, "missing_fields": [f for f in required_ticker_fields if f not in ticker]}
                    )

                if not depth.get('asks') or not depth.get('bids'):
                    raise ValidationError(
                        f"Dados de profundidade inválidos para {pair}",
                        "INVALID_DEPTH_DATA",
                        {"depth": depth}
                    )

                # Calcula métricas com validação
                try:
                    volume_24h = float(ticker['volume']) * float(ticker['weightedAvgPrice'])
                    best_ask = float(depth['asks'][0][0])
                    best_bid = float(depth['bids'][0][0])
                    spread = (best_ask - best_bid) / best_bid
                    price_change = abs(float(ticker['priceChangePercent']))
                except (ValueError, IndexError) as e:
                    raise ValidationError(
                        f"Erro ao converter dados do par {pair}",
                        "DATA_CONVERSION_ERROR",
                        {"error": str(e)}
                    )

                score = {
                    'pair': pair,
                    'volume_score': min(volume_24h / 1000000, 1.0),
                    'volatility_score': min(price_change / 10, 1.0),
                    'spread_score': 1 - min(spread * 100, 1.0),
                    'raw_data': {
                        'volume_24h': volume_24h,
                        'spread': spread,
                        'price_change': price_change,
                        'last_price': float(ticker['lastPrice']),
                        'best_bid': best_bid,
                        'best_ask': best_ask,
                        'timestamp': datetime.now().isoformat()
                    }
                }

                self.logger.info(f"Análise de {pair}: Volume={volume_24h:.2f} USDT, Spread={spread*100:.3f}%, Change={price_change:.2f}%")
                scored_pairs.append(score)

            except (BinanceAPIException, ValidationError, APIError) as e:
                error_tracker.track_error(e, {'pair': pair})
                errors.append({
                    'pair': pair,
                    'error': str(e),
                    'code': getattr(e, 'error_code', 'UNKNOWN')
                })
                continue
            except Exception as e:
                error_tracker.track_error(e, {'pair': pair})
                errors.append({
                    'pair': pair,
                    'error': str(e),
                    'code': 'UNEXPECTED_ERROR'
                })
                continue

        if not scored_pairs:
            if errors:
                raise APIError(
                    "Falha ao analisar todos os pares",
                    "ALL_PAIRS_FAILED",
                    {"errors": errors}
                )
            raise ValidationError(
                "Nenhum par analisado com sucesso",
                "NO_PAIRS_ANALYZED"
            )

        self.logger.info(f"Análise concluída: {len(scored_pairs)} pares analisados, {len(errors)} erros")
        return scored_pairs

    @handle_errors(retries=2, delay=0.5)  # Menos retries pois é análise secundária
    async def _apply_sentiment_analysis(self, scored_pairs: List[Dict]) -> List[Dict]:
        """Aplica análise de sentimento nos pares"""
        if not scored_pairs:
            raise ValidationError(
                "Lista de pares pontuados vazia",
                "EMPTY_SCORED_PAIRS"
            )

        if not self.sentiment_analyzer:
            self.logger.warning("Analisador de sentimento não disponível")
            return scored_pairs

        analysis_errors = []
        
        for pair in scored_pairs:
            try:
                if not isinstance(pair, dict) or 'pair' not in pair:
                    raise ValidationError(
                        "Formato inválido de par pontuado",
                        "INVALID_SCORED_PAIR_FORMAT",
                        {"pair_data": pair}
                    )

                # Analisa o par com timeout
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(self.sentiment_analyzer, pair['pair']),
                        timeout=2.0
                    )
                except asyncio.TimeoutError:
                    raise APIError(
                        f"Timeout na análise de sentimento para {pair['pair']}",
                        "SENTIMENT_TIMEOUT"
                    )

                # Valida e processa resultado
                if not result or not isinstance(result, list) or not result:
                    raise ValidationError(
                        "Resultado inválido da análise de sentimento",
                        "INVALID_SENTIMENT_RESULT",
                        {"result": result}
                    )

                sentiment = result[0]
                if not isinstance(sentiment, dict) or 'label' not in sentiment:
                    raise ValidationError(
                        "Formato inválido do resultado de sentimento",
                        "INVALID_SENTIMENT_FORMAT",
                        {"sentiment": sentiment}
                    )

                # Atualiza score com confiança do modelo
                sentiment_score = 1.0 if sentiment['label'] == 'POS' else 0.0
                confidence = float(sentiment.get('score', 0.5))
                
                pair['sentiment_score'] = sentiment_score * confidence
                pair['sentiment_data'] = {
                    'label': sentiment['label'],
                    'confidence': confidence,
                    'timestamp': datetime.now().isoformat()
                }

            except (ValidationError, APIError) as e:
                error_tracker.track_error(e, {'pair': pair.get('pair')})
                analysis_errors.append({
                    'pair': pair.get('pair'),
                    'error': str(e),
                    'code': e.error_code
                })
                pair['sentiment_score'] = 0.5  # Score neutro em caso de erro
            except Exception as e:
                error_tracker.track_error(e, {'pair': pair.get('pair')})
                analysis_errors.append({
                    'pair': pair.get('pair'),
                    'error': str(e),
                    'code': 'UNEXPECTED_ERROR'
                })
                pair['sentiment_score'] = 0.5  # Score neutro em caso de erro

        if analysis_errors:
            self.logger.warning(f"Erros na análise de sentimento: {len(analysis_errors)} de {len(scored_pairs)} pares")

        return scored_pairs

    @handle_errors(retries=1, delay=0.1)  # Operação local, não precisa de muitas tentativas
    def _select_best_pairs(self, scored_pairs: List[Dict]) -> List[str]:
        """Seleciona os melhores pares baseado nos scores"""
        if not scored_pairs:
            raise ValidationError(
                "Lista de pares pontuados vazia",
                "EMPTY_SCORED_PAIRS"
            )

        try:
            # Valida estrutura dos dados
            for pair in scored_pairs:
                if not isinstance(pair, dict):
                    raise ValidationError(
                        "Par inválido na lista",
                        "INVALID_PAIR_FORMAT",
                        {"pair": pair}
                    )
                
                required_fields = ['volume_score', 'volatility_score', 'spread_score']
                missing_fields = [f for f in required_fields if f not in pair]
                if missing_fields:
                    raise ValidationError(
                        "Campos obrigatórios ausentes no par",
                        "MISSING_REQUIRED_FIELDS",
                        {"pair": pair.get('pair'), "missing_fields": missing_fields}
                    )

            # Calcula score final com pesos
            weights = {
                'volume_score': 0.4,
                'volatility_score': 0.3,
                'spread_score': 0.2,
                'sentiment_score': 0.1
            }

            for pair in scored_pairs:
                try:
                    pair['final_score'] = sum(
                        float(pair.get(key, 0)) * weight
                        for key, weight in weights.items()
                    )
                except ValueError as e:
                    raise ValidationError(
                        f"Erro ao calcular score para {pair.get('pair')}",
                        "SCORE_CALCULATION_ERROR",
                        {"error": str(e), "pair_data": pair}
                    )

            # Ordena por score e seleciona os top 20
            sorted_pairs = sorted(
                scored_pairs,
                key=lambda x: float(x.get('final_score', 0)),
                reverse=True
            )

            selected = [p['pair'] for p in sorted_pairs[:20]]
            
            if not selected:
                raise ValidationError(
                    "Nenhum par selecionado após ordenação",
                    "NO_PAIRS_SELECTED"
                )

            self.logger.info(f"Selecionados {len(selected)} pares com melhores scores")
            return selected

        except Exception as e:
            error_tracker.track_error(e)
            raise ValidationError(
                "Erro ao selecionar melhores pares",
                "PAIR_SELECTION_ERROR",
                {"error": str(e)}
            )

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
