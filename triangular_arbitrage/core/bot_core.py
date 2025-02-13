from typing import Optional, Dict, List
import logging
import asyncio
import time
from datetime import datetime
from binance import AsyncClient, Client, BinanceSocketManager
from binance.enums import (
    FUTURE_ORDER_TYPE_MARKET,
    TIME_IN_FORCE_IOC
)
from binance.exceptions import BinanceAPIException

from ..config import BINANCE_CONFIG, TRADING_CONFIG, DB_CONFIG
from .trading_core import TradingCore
from .currency_core import CurrencyCore
from .events_core import EventsCore
from ..utils.backup_manager import BackupManager
from ..utils.logger import Logger

logger = logging.getLogger(__name__)

class BotCore:
    def __init__(self, db, display, config):
        self.db = db
        self.display = display
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Modos de operação do sistema
        self.test_mode = config.get('test_mode', True)
        self.simulation_mode = config.get('SIMULATION_MODE', False)
        
        # Estado do bot
        self.client = None
        self.bsm = None
        self.is_connected = False
        self.opportunities = []
        self.trades = []
        self.start_time = datetime.now()
        self.last_update = None
        self.running = True
        
        # Locks e controles
        self._update_lock = asyncio.Lock()
        self._price_cache_lock = asyncio.Lock()
        self.price_cache = {}
        self.symbol_pairs = set()
        self.active_streams = []
        self.last_process_time = time.time()
        self.processing_times = []
        self.last_latency = 0
        self._active_tasks = set()
        self._cleanup_event = asyncio.Event()
        
        # Inicializa componentes com configurações atualizadas
        trading_config = TRADING_CONFIG.copy()
        trading_config.update({
            'test_mode': self.test_mode,
            'SIMULATION_MODE': self.simulation_mode
        })
        
        self.exchange = None  # Será definido em initialize()
        self.currency_core = CurrencyCore(
            exchange=self.exchange,
            config=trading_config
        )
        
        self.backup_manager = BackupManager(
            db_path=DB_CONFIG['DB_FILE'],
            backup_dir=DB_CONFIG['BACKUP_DIR'],
            config_dir='data/backups/config',
            logs_dir='data/backups/logs'
        )
        
        # TradingCore será inicializado após termos o client
        self.trading_core: Optional[TradingCore] = None
        self.events_core = EventsCore()

        # Log do modo de operação
        if self.test_mode:
            self.logger.info("🔬 Bot iniciado em modo de teste (monitoramento apenas)")
        elif self.simulation_mode:
            self.logger.info("🎮 Bot iniciado em modo de simulação")
        else:
            self.logger.warning("⚠️ Bot iniciado em modo de execução real - Ordens serão enviadas!")

    async def initialize(self):
        """Inicializa conexão com a Binance com baixa latência"""
        try:
            # Verifica e trata credenciais
            api_key = str(BINANCE_CONFIG['API_KEY']).strip('"\'')
            api_secret = str(BINANCE_CONFIG['API_SECRET']).strip('"\'')
            
            if not api_key or not api_secret:
                self.logger.error("❌ Credenciais da Binance não encontradas")
                raise ValueError("Credenciais da Binance não configuradas")
            
            # Log seguro mostrando apenas parte das credenciais
            self.logger.info(f"API Key detectada: {api_key[:4]}...{api_key[-4:]} (tamanho: {len(api_key)})")
            self.logger.info(f"API Secret detectada: {api_secret[:4]}...{api_secret[-4:]} (tamanho: {len(api_secret)})")
            
            # Inicializa cliente com configurações otimizadas
            try:
                self.client = await AsyncClient.create(
                    api_key=api_key,
                    api_secret=api_secret,
                    requests_params={'timeout': 30}  # Timeout aumentado
                )
                # Configura exchange para o currency_core
                self.exchange = self.client
                self.currency_core.exchange = self.client
                
                # Agora podemos inicializar o TradingCore com o client assíncrono
                self.trading_core = TradingCore(client=self.client)
                
            except Exception as e:
                self.logger.error(f"❌ Erro ao criar cliente Binance: {str(e)}")
                raise
            
            # Configura WebSocket Manager com timeout otimizado
            try:
                self.bsm = BinanceSocketManager(self.client, user_timeout=60)
            except Exception as e:
                self.logger.error(f"❌ Erro ao criar WebSocket Manager: {str(e)}")
                raise
            
            self.is_connected = True
            self.logger.info("✅ Conectado à Binance")
            
            # Inicializa pares e streams
            await self._initialize_trading_pairs()
            await self._start_price_streams()
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao conectar: {str(e)}")
            await self.cleanup()
            raise

    async def _initialize_trading_pairs(self):
        """Inicializa pares de trading válidos"""
        try:
            # Obtém informações com retry
            for attempt in range(3):
                try:
                    if not self.client:
                        raise ValueError("Cliente não inicializado")
                    exchange_info = await self.client.get_exchange_info()
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(1)
            
            # Filtra apenas pares ativos com USDT, BTC, ETH e BNB
            base_assets = {'USDT', 'BTC', 'ETH', 'BNB'}
            
            for symbol_info in exchange_info['symbols']:
                if symbol_info['status'] == 'TRADING':
                    base = symbol_info['baseAsset']
                    quote = symbol_info['quoteAsset']
                    
                    if base in base_assets or quote in base_assets:
                        symbol = symbol_info['symbol']
                        self.symbol_pairs.add(symbol)
            
            self.logger.info(f"✅ {len(self.symbol_pairs)} pares de trading inicializados")
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao inicializar pares: {e}")
            raise

    async def _start_price_streams(self):
        """Inicia streams de preços para todos os pares relevantes"""
        try:
            if not self.symbol_pairs:
                raise ValueError("Nenhum par de trading inicializado")

            # Divide em lotes menores para evitar sobrecarga
            batch_size = 50
            symbol_batches = [list(self.symbol_pairs)[i:i + batch_size]
                            for i in range(0, len(self.symbol_pairs), batch_size)]
            
            # Cria tasks para cada batch
            for batch in symbol_batches:
                task = asyncio.create_task(self._handle_batch_stream(batch))
                self._active_tasks.add(task)
                task.add_done_callback(self._active_tasks.discard)
            
            self.logger.info(f"✅ {len(self.symbol_pairs)} streams de preço iniciados")
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao iniciar streams: {e}")
            raise

    async def _handle_batch_stream(self, symbols):
        """Gerencia um batch de streams"""
        while self.running:
            try:
                streams = [f"{pair.lower()}@bookTicker" for pair in symbols]
                if not self.bsm:
                    self.logger.error("Socket manager não inicializado")
                    await asyncio.sleep(5)
                    continue
                    
                ws = self.bsm.multiplex_socket(streams)
                
                try:
                    async with ws as stream:
                        self.active_streams.append(stream)
                        while self.running:
                            try:
                                data = await asyncio.wait_for(stream.recv(), timeout=10.0)
                                if data:
                                    await self._process_stream_message(data)
                            except asyncio.TimeoutError:
                                if not self.running:
                                    break
                                continue
                            except Exception as e:
                                if not self.running:
                                    break
                                self.logger.error(f"Erro no stream: {e}")
                                await asyncio.sleep(1)
                                continue
                except Exception as e:
                    self.logger.error(f"Erro no websocket: {e}")
                            
            except Exception as e:
                if not self.running:
                    break
                self.logger.error(f"Erro no batch {symbols[0]}...: {e}")
                await asyncio.sleep(5)

    async def _process_stream_message(self, msg):
        """Processa mensagem do stream com prioridade em latência"""
        try:
            data = msg.get('data', msg)
            if data.get('e') == 'bookTicker':
                start_time = time.time()
                
                symbol = data['s']
                bid = float(data['b'])
                ask = float(data['a'])
                bid_qty = float(data['B'])
                ask_qty = float(data['A'])
                event_time = float(data['E'])
                
                # Calcula latência com maior precisão
                latency = (time.time() * 1000) - event_time
                self.last_latency = latency
                
                # Processa apenas se latência for aceitável
                if latency < 500:
                    price_data = {
                        'bid': bid,
                        'ask': ask,
                        'bidVolume': bid_qty,
                        'askVolume': ask_qty,
                        'timestamp': time.time(),
                        'latency': latency
                    }
                    
                    # Usa lock para atualizar cache
                    async with self._price_cache_lock:
                        self.price_cache[symbol] = price_data
                    
                    # Detecta oportunidades se necessário
                    current_time = time.time()
                    if current_time - self.last_process_time >= 0.05:
                        await self._detect_arbitrage_opportunities()
                        self.last_process_time = current_time
                        
                        # Monitora tempo de processamento
                        process_time = (time.time() - start_time) * 1000
                        self.processing_times.append(process_time)
                        
                        if len(self.processing_times) > 1000:
                            self.processing_times = self.processing_times[-1000:]
                    
        except Exception as e:
            self.logger.error(f"❌ Erro no processamento da mensagem: {e}")

    async def _process_price_update(self, symbol: str, data: Dict):
        """Processa atualização de preço recebida"""
        try:
            current_time = time.time()
            
            # Valida dados recebidos
            if not isinstance(data, dict):
                self.logger.warning(f"❌ Dados inválidos recebidos para {symbol}")
                return

            # Extrai dados relevantes
            price_data = {
                'ask': float(data.get('askPrice', 0)),
                'bid': float(data.get('bidPrice', 0)),
                'volume': float(data.get('volume', 0)),
                'timestamp': current_time,
                'latency': (current_time - float(data.get('time', current_time))/1000) * 1000  # em ms
            }

            # Valida preços
            if price_data['ask'] <= 0 and price_data['bid'] <= 0:
                self.logger.warning(f"⚠️ Preços inválidos para {symbol}: ask={price_data['ask']}, bid={price_data['bid']}")
                return

            # Atualiza cache de preços
            async with self._price_cache_lock:
                self.price_cache[symbol] = price_data
                
            # Log de debug
            self.logger.debug(
                f"💹 Preço atualizado - {symbol} | "
                f"Ask: {price_data['ask']:.8f} | "
                f"Bid: {price_data['bid']:.8f} | "
                f"Vol: {price_data['volume']:.2f} | "
                f"Lat: {price_data['latency']:.2f}ms"
            )

            # Dispara detecção de oportunidades se tiver dados suficientes
            if len(self.price_cache) >= 3:  # Mínimo 3 pares para triangular
                await self._detect_arbitrage_opportunities()
                
        except Exception as e:
            self.logger.error(f"❌ Erro ao processar preço de {symbol}: {e}")
            import traceback
            self.logger.error(f"Detalhes: {traceback.format_exc()}")

    async def start(self):
        """Inicia o bot com recuperação automática"""
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                self.logger.info("Iniciando monitoramento em tempo real...")
                await asyncio.gather(
                    self._maintain_connection(),
                    return_exceptions=True
                )
            except Exception as e:
                retry_count += 1
                self.logger.error(f"Erro no bot (tentativa {retry_count}/{max_retries}): {str(e)}")
                if retry_count < max_retries:
                    await asyncio.sleep(1)
                    continue
                break
            finally:
                await self.cleanup()

    async def _maintain_connection(self):
        """Mantém conexão ativa e monitora saúde do sistema"""
        while self.running:
            try:
                await asyncio.sleep(0.1)
                
                if not self.is_connected:
                    await self.initialize()
                    
            except Exception as e:
                self.logger.error(f"Erro de conexão: {e}")
                continue

    async def cleanup(self):
        """Limpa recursos e fecha conexões de forma segura"""
        try:
            self.running = False
            self.is_connected = False
            
            # Cancela todas as tasks ativas
            tasks = list(self._active_tasks)
            if tasks:
                self.logger.info(f"Cancelando {len(tasks)} tasks ativas...")
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Fecha streams
            for stream in self.active_streams:
                try:
                    await stream.__aexit__(None, None, None)
                except Exception as e:
                    self.logger.error(f"Erro ao fechar stream: {e}")
            
            # Fecha conexão WebSocket
            if self.client:
                try:
                    await self.client.close_connection()
                except Exception as e:
                    self.logger.error(f"Erro ao fechar cliente: {e}")
            
            # Limpa dados em memória
            async with self._price_cache_lock:
                self.price_cache.clear()
            self.symbol_pairs.clear()
            self.active_streams.clear()
            self._active_tasks.clear()
            
            # Sinaliza limpeza completa
            self._cleanup_event.set()
            
            self.logger.info("✅ Recursos liberados com sucesso")
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao limpar recursos: {e}")
            raise

    def _calculate_triangular_profit(self, pair1, pair2, pair3, price1_data, price2_data, price3_data):
        """Calcula o profit da arbitragem triangular"""
        try:
            # Valida dados de preço
            required_fields = ['ask', 'bid']
            valid_data = all(
                isinstance(d, dict) and all(field in d for field in required_fields)
                for d in [price1_data, price2_data, price3_data]
            )
            
            if not valid_data:
                return None

            # Obtém preços como float
            price1_ask = float(price1_data['ask'])
            price1_bid = float(price1_data['bid'])
            price2_ask = float(price2_data['ask'])
            price2_bid = float(price2_data['bid'])
            price3_ask = float(price3_data['ask'])
            price3_bid = float(price3_data['bid'])

            if not all(x > 0 for x in [price1_ask, price1_bid, price2_ask, price2_bid, price3_ask, price3_bid]):
                return None

            # Calcula as duas direções possíveis
            # Direção 1: Compra par1, vende par2, vende par3
            profit1 = ((1 / price1_ask) * price2_bid * price3_bid) - 1

            # Direção 2: Compra par3, compra par2, vende par1
            profit2 = ((1 / price3_ask) * (1 / price2_ask) * price1_bid) - 1

            # Considera taxas de trading (0.1% por operação)
            fee = 0.001  # 0.1%
            profit1 = profit1 - (fee * 3)  # 3 operações
            profit2 = profit2 - (fee * 3)

            # Retorna o maior profit em porcentagem
            best_profit = max(profit1, profit2) * 100
            return best_profit if best_profit > 0 else None

        except (ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.debug(f"Erro no cálculo de profit: {e}")
            return None

    async def _detect_arbitrage_opportunities(self):
        """Detecta oportunidades de arbitragem triangular em tempo real"""
        try:
            start_time = time.time()
            opportunities = []
            current_time = datetime.now()
            
            # Copia cache de preços para evitar modificações durante processamento
            async with self._price_cache_lock:
                price_cache = self.price_cache.copy()
            
            # Usa apenas pares com dados recentes (últimos 5 segundos)
            recent_pairs = {
                symbol: data for symbol, data in price_cache.items()
                if isinstance(data, dict) and 'timestamp' in data and time.time() - data['timestamp'] < 5
            }

            if not recent_pairs:
                self.logger.debug("Aguardando dados de preços...")
                return

            # Base pairs para triangular arbitrage (expandido para mais possibilidades)
            base_pairs = ['BTC', 'ETH', 'BNB', 'USDT', 'BUSD', 'USDC']
            
            for base in base_pairs:
                base_markets = [p for p in recent_pairs if base in p]
                
                for pair1 in base_markets:
                    for pair2 in base_markets:
                        if pair1 == pair2:
                            continue
                            
                        # Encontra o terceiro par
                        try:
                            asset1 = pair1.replace(base, '')
                            asset2 = pair2.replace(base, '')

                            # Garante que estamos usando os pares corretos
                            if not asset1 or not asset2:
                                continue
                            
                            pair3 = f"{asset1}{asset2}"
                            if pair3 not in recent_pairs:
                                pair3 = f"{asset2}{asset1}"
                                if pair3 not in recent_pairs:
                                    continue
                            
                            # Calcula profit apenas se todos os pares têm dados válidos
                            price1_data = recent_pairs[pair1]
                            price2_data = recent_pairs[pair2]
                            price3_data = recent_pairs[pair3]

                            # Validação dos dados
                            required_fields = ['ask', 'bid']
                            if not all(isinstance(d, dict) and all(field in d for field in required_fields)
                                     for d in [price1_data, price2_data, price3_data]):
                                continue

                            # Calcula o profit
                            profit = self._calculate_triangular_profit(
                                pair1, pair2, pair3,
                                price1_data,
                                price2_data,
                                price3_data
                            )
                            
                            if profit and profit > 0.1:  # Apenas oportunidades com lucro > 0.1%
                                volume = self._calculate_max_volume(
                                    pair1, pair2, pair3,
                                    price1_data,
                                    price2_data,
                                    price3_data
                                )
                                
                                max_latency = max(
                                    price1_data.get('latency', 0),
                                    price2_data.get('latency', 0),
                                    price3_data.get('latency', 0)
                                )
                                
                                opportunity = {
                                    'id': str(len(opportunities) + 1),
                                    'a_step_from': base,
                                    'a_step_to': asset1,
                                    'b_step_from': asset1,
                                    'b_step_to': asset2,
                                    'c_step_from': asset2,
                                    'c_step_to': base,
                                    'profit': round(profit, 3),
                                    'a_volume': volume,
                                    'timestamp': current_time.isoformat(),
                                    'rate': 1 + (profit / 100),
                                    'latency': round(max_latency, 2),
                                    'status': 'active',
                                    'a_rate': float(price1_data['ask']),
                                    'b_rate': float(price2_data['ask']),
                                    'c_rate': float(price3_data['ask'])
                                }
                                opportunities.append(opportunity)
                                
                                # Log da oportunidade encontrada
                                self.logger.info(
                                    f"💰 Nova oportunidade: {base}→{asset1}→{asset2} | "
                                    f"Profit: {profit:.2f}% | Volume: {volume:.8f} BTC"
                                )

                        except Exception as e:
                            self.logger.debug(f"Erro ao processar par: {e}")
                            continue
            
            # Atualiza apenas se encontrou oportunidades
            if opportunities:
                self.opportunities = sorted(
                    opportunities,
                    key=lambda x: float(x['profit']),
                    reverse=True
                )[:10]  # Mantém apenas as 10 melhores
                self.last_update = current_time
                
                # Log de performance
                process_time = time.time() - start_time
                self.processing_times.append(process_time)
                self.logger.debug(f"⚡ Processamento em {process_time*1000:.2f}ms | {len(opportunities)} oportunidades")
                
        except Exception as e:
            self.logger.error(f"❌ Erro na detecção de arbitragem: {e}")
            import traceback
            self.logger.error(f"Detalhes: {traceback.format_exc()}")
            return

    def _calculate_max_volume(self, pair1, pair2, pair3, price1_data, price2_data, price3_data):
        """Calcula volume máximo possível considerando liquidez"""
        try:
            # Obtém volumes dos books de ordem
            volume1 = float(price1_data.get('volume', 0))
            volume2 = float(price2_data.get('volume', 0))
            volume3 = float(price3_data.get('volume', 0))

            # Converte volumes para BTC
            if not pair1.startswith('BTC'):
                volume1 = volume1 * float(price1_data['ask'])
            if not pair2.startswith('BTC'):
                volume2 = volume2 * float(price2_data['ask'])
            if not pair3.startswith('BTC'):
                volume3 = volume3 * float(price3_data['ask'])

            # Pega o menor volume da rota
            max_volume = min(volume1, volume2, volume3)

            # Limita volume máximo por trade
            max_trade_volume = 0.1  # 0.1 BTC
            max_volume = min(max_volume, max_trade_volume)

            # Arredonda para 8 casas decimais
            return round(max_volume, 8)

        except (ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.debug(f"Erro no cálculo de volume: {e}")
            return 0.001  # Volume mínimo default

    async def stop(self):
        """Para o bot e realiza backup final"""
        try:
            self.running = False
            self.is_connected = False
            
            # Para os componentes em ordem
            tasks = []
            
            # Verifica cada componente antes de adicionar à lista de tasks
            if self.currency_core:
                tasks.append(self.currency_core.stop_ticker_stream())
            
            if self.client:
                tasks.append(self.client.close_connection())
                
            if self.backup_manager:
                try:
                    await self.backup_manager.stop()  # Mudando para método stop()
                except Exception as e:
                    self.logger.error(f"Erro ao finalizar backup manager: {e}")
            
            # Aguarda todas as tarefas terminarem
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            self.logger.info("✅ Bot parado com sucesso")
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao parar bot: {e}")
            raise
        finally:
            # Garante que todas as tarefas pendentes sejam canceladas
            for task in asyncio.all_tasks():
                if task is not asyncio.current_task():
                    task.cancel()

    async def execute_order(self, symbol, side, quantity, price=None, order_type=FUTURE_ORDER_TYPE_MARKET):
        """Executa ordens com baixa latência"""
        try:
            if not self.client:
                raise ValueError("Cliente não inicializado")
                
            order = await self.client.create_order(
                symbol=symbol,
                side=side,
                type=order_type,
                quantity=quantity,
                price=price,
                timeInForce=TIME_IN_FORCE_IOC  # Usando constante da Binance
            )
            self.logger.info(f"Ordem executada: {order}")
            return order
        except Exception as e:
            self.logger.error(f"Erro na ordem: {e}")
            return None

    def get_performance_metrics(self):
        """Retorna métricas de performance do bot"""
        return {
            'latency': {
                'current': round(self.last_latency, 2),
                'avg_process_time': round(sum(self.processing_times) / len(self.processing_times), 2) if self.processing_times else 0
            },
            'opportunities': len(self.opportunities),
            'pairs_monitored': len(self.symbol_pairs),
            'cache_size': len(self.price_cache),
            'uptime': str(datetime.now() - self.start_time)
        }