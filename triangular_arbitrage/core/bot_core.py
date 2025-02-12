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
            # Determina direção da ordem para cada par
            direction1 = 'ask' if pair1.endswith(pair2.split(pair1[-3:])[0]) else 'bid'
            direction2 = 'ask' if pair2.endswith(pair3.split(pair2[-3:])[0]) else 'bid'
            direction3 = 'ask' if pair3.endswith(pair1.split(pair3[-3:])[0]) else 'bid'
            
            # Calcula taxas
            fee = 0.00075  # 0.075% por trade
            
            # Calcula preços considerando direção
            price1_val = float(price1_data[direction1])
            price2_val = float(price2_data[direction2])
            price3_val = float(price3_data[direction3])
            
            # Calcula profit considerando taxas
            profit = (
                (1 / price1_val * (1 - fee)) *
                (1 / price2_val * (1 - fee)) *
                (price3_val * (1 - fee))
            ) - 1
            
            return profit * 100  # Retorna em porcentagem
            
        except Exception as e:
            self.logger.error(f"❌ Erro no cálculo de profit: {e}")
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
                if time.time() - data['timestamp'] < 5
            }
            
            # Base pairs para triangular arbitrage
            base_pairs = ['BTC', 'ETH', 'BNB', 'USDT']
            
            for base in base_pairs:
                base_markets = [p for p in recent_pairs if base in p]
                
                for pair1 in base_markets:
                    for pair2 in base_markets:
                        if pair1 == pair2:
                            continue
                            
                        # Encontra o terceiro par
                        asset1 = pair1.replace(base, '')
                        asset2 = pair2.replace(base, '')
                        
                        pair3 = f"{asset1}{asset2}"
                        if pair3 not in recent_pairs:
                            pair3 = f"{asset2}{asset1}"
                            if pair3 not in recent_pairs:
                                continue
                        
                        # Calcula profit apenas se todos os pares têm latência aceitável
                        max_latency = max(
                            recent_pairs[pair1]['latency'],
                            recent_pairs[pair2]['latency'],
                            recent_pairs[pair3]['latency']
                        )
                        
                        if max_latency > 500:  # Ignora se latência > 500ms
                            continue
                        
                        # Calcula profit
                        profit = self._calculate_triangular_profit(
                            pair1, pair2, pair3,
                            recent_pairs[pair1],
                            recent_pairs[pair2],
                            recent_pairs[pair3]
                        )
                        
                        if profit and profit > 0.1:
                            volume = self._calculate_max_volume(
                                pair1, pair2, pair3,
                                recent_pairs[pair1],
                                recent_pairs[pair2],
                                recent_pairs[pair3]
                            )
                            
                            opportunity = {
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
                                'score': 90 if profit > 1.5 else 70 if profit > 0.5 else 50,
                                'latency': round(max_latency, 2),
                                'status': 'active'
                            }
                            opportunities.append(opportunity)
            
            # Atualiza apenas se encontrou oportunidades
            if opportunities:
                self.opportunities = sorted(
                    opportunities,
                    key=lambda x: float(x['profit']),
                    reverse=True
                )[:10]  # Mantém apenas as 10 melhores
                self.last_update = current_time
                
        except Exception as e:
            self.logger.error(f"❌ Erro na detecção de arbitragem: {e}")
            return

    def _calculate_max_volume(self, pair1, pair2, pair3, price1, price2, price3):
        """Calcula volume máximo possível considerando liquidez"""
        try:
            # Calcula volume baseado na liquidez disponível
            volumes = [
                min(price1['bidVolume'], price1['askVolume']),
                min(price2['bidVolume'], price2['askVolume']),
                min(price3['bidVolume'], price3['askVolume'])
            ]
            
            # Aplica limite conservador
            max_volume = min(volumes) * 0.8  # 80% do volume disponível
            
            # Limita baseado na configuração
            config_limit = TRADING_CONFIG['FUNDS_ALLOCATION'].get('BTC', 0.01)
            
            return round(min(max_volume, config_limit), 6)
            
        except Exception as e:
            self.logger.error(f"❌ Erro no cálculo de volume: {e}")
            return 0.001

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