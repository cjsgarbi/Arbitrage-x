from typing import Optional, Dict, List
import logging
import asyncio
import time
import random
import json
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
    def __init__(self, db=None, display=None, config=None):
        self.db = db
        self.display = display
        self.config = {} if config is None else config
        self.logger = logging.getLogger(__name__)
        
        # Configurações da API
        self.api_key = self.config.get('BINANCE_API_KEY', '')
        self.api_secret = self.config.get('BINANCE_API_SECRET', '')
        
        if not self.api_key or not self.api_secret:
            self.logger.error("❌ Credenciais da Binance não encontradas. Verifique o arquivo .env")
            raise ValueError("Credenciais da Binance não configuradas")
        
        # Estado do bot
        self.client = None
        self.bsm = None
        self.is_connected = False
        self.opportunities = []
        self.trades = []
        self.start_time = datetime.now()
        self.last_update = None
        self.running = True
        self.is_ai_connected = False  # Flag simples para status da IA
        self.is_ai_initialized = False
        
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
        self.active_tasks = set()
        self._cleanup_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False
        self._stream_buffer = asyncio.Queue(maxsize=10000)
        self._buffer_processor_task = None
        self._last_stream_time = time.time()
        
        # Modo de operação
        self.test_mode = self.config.get('test_mode', True)

        if self.test_mode:
            self.logger.info("🔬 Bot iniciado em modo de monitoramento (sem execução de ordens)")
        else:
            self.logger.warning("⚠️ Bot iniciado em modo de execução - Ordens serão enviadas!")

        # Inicializa componentes
        self.currency_core = CurrencyCore(
            exchange=None,
            config={'test_mode': self.test_mode}
        )
        
        self.backup_manager = BackupManager(
            db_path=DB_CONFIG['DB_FILE'],
            backup_dir=DB_CONFIG['BACKUP_DIR'],
            config_dir='data/backups/config',
            logs_dir='data/backups/logs'
        )
        
        self.trading_core = None
        self.events_core = EventsCore()

    def get_performance_metrics(self):
        """Retorna métricas de performance do bot"""
        try:
            now = datetime.now()
            time_running = (now - self.start_time).total_seconds()
            
            metrics = {
                'uptime': time_running,
                'active_pairs': len(self.symbol_pairs),
                'latency': self.last_latency,
                'opportunities_found': len(self.opportunities),
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'status': 'active' if self.running else 'stopped',
                'buffer_size': self._stream_buffer.qsize(),
                'active_streams': len(self.active_streams)
            }
            
            return metrics
        except Exception as e:
            self.logger.error(f"Erro ao gerar métricas: {e}")
            return {}

    def get_ai_status(self) -> bool:
        """Retorna status atual da IA"""
        # Retorna True apenas se a IA foi inicializada E está conectada
        return self.is_ai_initialized and self.is_ai_connected

    async def _load_top_pairs(self):
        """Carrega os pares mais promissores usando IA"""
        try:
            if not self.client:
                self.client = await AsyncClient.create(self.api_key, self.api_secret)

            # Usa o AIPairFinder existente para selecionar pares
            from .ai_pair_finder import AIPairFinder
            ai_finder = AIPairFinder()
            selected_pairs = await ai_finder.get_potential_pairs()

            if not selected_pairs:
                self.logger.warning("IA não retornou pares, usando fallback")
                return ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ETHBTC', 'BNBBTC']

            self.logger.info(f"Pares selecionados pela IA: {', '.join(selected_pairs)}")
            return selected_pairs

        except Exception as e:
            self.logger.error(f"Erro ao carregar pares com IA: {e}")
            return ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ETHBTC', 'BNBBTC']  # Fallback para pares padrão

    async def initialize(self):
        """Inicializa o bot e estabelece conexões"""
        try:
            self.client = await AsyncClient.create(self.api_key, self.api_secret)
            self.bsm = BinanceSocketManager(self.client)
            self.is_connected = True
            self.logger.info("✅ Conexão estabelecida com a Binance")
            
            # Atualiza status da IA
            self.is_ai_initialized = True
            self.is_ai_connected = True
            self.logger.info("✅ Status da IA: Conectada")
            
            return True
        except Exception as e:
            self.logger.error(f"❌ Erro ao inicializar bot: {e}")
            return False

    async def start(self):
        """Inicia o monitoramento dos pares e processamento de oportunidades"""
        try:
            
            # Inicializa registro de histórico de oportunidades
            self.opportunities_history = []
            self.max_history_size = 1000  # Mantém as últimas 1000 oportunidades
            
            # Carrega os pares mais negociados
            initial_pairs = await self._load_top_pairs()
            self.symbol_pairs.update(initial_pairs)
            
            # Inicia stream dos pares iniciais
            self._active_tasks.add(
                asyncio.create_task(self._handle_batch_stream(initial_pairs))
            )
            
            # Mantém o bot rodando
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Erro ao iniciar bot: {e}")
        finally:
            await self._cleanup()

    async def _handle_batch_stream(self, symbols):
        """Gerencia um batch de streams com reconexão inteligente"""
        retry_count = 0
        max_retries = 10  # Aumentado para 10 tentativas
        base_delay = 3    # Aumentado para 3 segundos

        while self.running:
            try:
                if not self.client:
                    self.logger.error("Cliente Binance não inicializado")
                    await asyncio.sleep(5)
                    continue
                
                streams = [f"{pair.lower()}@bookTicker" for pair in symbols]
                if not self.bsm:
                    self.bsm = BinanceSocketManager(self.client)
                
                ws = self.bsm.multiplex_socket(streams)
                async with ws as stream:
                    try:
                        self.active_streams.append(stream)
                        self._last_stream_time = time.time()
                        
                        while self.running:
                            try:
                                data = await asyncio.wait_for(stream.recv(), timeout=15.0)
                                
                                if data:
                                    self._last_stream_time = time.time()
                                    if not self._stream_buffer.full():
                                        await self._stream_buffer.put(data)
                                        retry_count = 0
                                    else:
                                        self.logger.warning("Buffer cheio, ignorando mensagem")
                                
                                if time.time() - self._last_stream_time > 30:
                                    break
                                
                            except asyncio.TimeoutError:
                                if not self.running:
                                    break
                                self.logger.warning(f"Timeout no stream de {symbols[0]}")
                                break
                            except Exception as e:
                                if not self.running:
                                    break
                                self.logger.error(f"Erro no processamento do stream: {e}")
                                await asyncio.sleep(1)
                                continue
                    except Exception as e:
                        self.logger.error(f"Erro no stream: {e}")
                    finally:
                        if stream in self.active_streams:
                            self.active_streams.remove(stream)
                
                if not self.running:
                    break
                    
                if retry_count < max_retries:
                    retry_count += 1
                    delay = min(
                        base_delay * (2 ** (retry_count - 1)) + (random.random() * 2),
                        60
                    )
                    self.logger.info(f"Tentando reconectar em {delay:.1f}s... (tentativa {retry_count}/{max_retries})")
                    await asyncio.sleep(delay)
                else:
                    self.logger.warning("Máximo de tentativas alcançado, reiniciando conexão...")
                    retry_count = 0
                    await asyncio.sleep(10)
                    
            except Exception as e:
                if not self.running:
                    break
                self.logger.error(f"Erro no batch {symbols[0]}...: {e}")
                await asyncio.sleep(5)

    async def _process_stream_message(self, msg):
        """Processa mensagem do stream"""
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
                
                latency = (time.time() * 1000) - event_time
                self.last_latency = latency
                
                if latency < 2000:  # Aumentado para 2000ms
                    price_data = {
                        'bid': bid,
                        'ask': ask,
                        'bidVolume': bid_qty,
                        'askVolume': ask_qty,
                        'timestamp': time.time(),
                        'latency': latency
                    }
                    
                    async with self._price_cache_lock:
                        self.price_cache[symbol] = price_data
                    
                    current_time = time.time()
                    if current_time - self.last_process_time >= 0.1:
                        await self._detect_arbitrage_opportunities()
                        self.last_process_time = current_time
                    
        except Exception as e:
            self.logger.error(f"❌ Erro no processamento da mensagem: {e}")

    async def _process_stream_buffer(self):
        """Processa mensagens do buffer de stream"""
        while self.running:
            try:
                if not self._stream_buffer.empty():
                    msg = await self._stream_buffer.get()
                    await self._process_stream_message(msg)
                else:
                    await asyncio.sleep(0.01)
            except Exception as e:
                self.logger.error(f"Erro no processamento do buffer: {e}")
                await asyncio.sleep(1)

    async def _cleanup(self):
        """Limpa recursos e fecha conexões"""
        self.running = False
        
        if self._buffer_processor_task:
            self._buffer_processor_task.cancel()
            
        for task in self._active_tasks:
            try:
                task.cancel()
                await task
            except:
                pass
            
        if self.client:
            try:
                await self.client.close_connection()
                self.client = None
            except:
                pass
            
        # Salva histórico de oportunidades em arquivo antes de fechar
        if hasattr(self, 'opportunities_history') and self.opportunities_history:
            try:
                self.logger.info("Salvando histórico de oportunidades...")
                with open('data/opportunities_history.json', 'w') as f:
                    json.dump(self.opportunities_history, f, indent=2)
                self.logger.info("Histórico salvo com sucesso")
            except Exception as e:
                self.logger.error(f"Erro ao salvar histórico: {e}")
            
    async def _detect_arbitrage_opportunities(self):
        """Detecta oportunidades de arbitragem triangular"""
        try:
            start_time = time.time()
            opportunities = []
            current_time = datetime.now()
            
            async with self._price_cache_lock:
                price_cache = self.price_cache.copy()
            
            # Filtra pares recentes
            recent_pairs = {
                symbol: data for symbol, data in price_cache.items()
                if isinstance(data, dict) and 'timestamp' in data and time.time() - data['timestamp'] < 10  # Aumentado para 10s
            }
            
            if not recent_pairs:
                return
            
            # Base pairs para triangular arbitrage (expandido)
            base_pairs = ['BTC', 'ETH', 'BNB', 'USDT', 'BUSD', 'USDC', 'DAI']
            
            for base in base_pairs:
                base_markets = [p for p in recent_pairs if base in p]
                
                for pair1 in base_markets:
                    for pair2 in base_markets:
                        if pair1 == pair2:
                            continue
                            
                        try:
                            asset1 = pair1.replace(base, '')
                            asset2 = pair2.replace(base, '')
                            
                            if not asset1 or not asset2:
                                continue
                            
                            pair3 = f"{asset1}{asset2}"
                            if pair3 not in recent_pairs:
                                pair3 = f"{asset2}{asset1}"
                                if pair3 not in recent_pairs:
                                    continue
                            
                            price1_data = recent_pairs[pair1]
                            price2_data = recent_pairs[pair2]
                            price3_data = recent_pairs[pair3]
                            
                            if not all(isinstance(d, dict) and all(field in d for field in ['ask', 'bid'])
                                     for d in [price1_data, price2_data, price3_data]):
                                continue
                            
                            # Verifica liquidez mínima (1000 USDT ou equivalente)
                            min_volume = 1000.0
                            volumes = [
                                price1_data['bidVolume'] * price1_data['bid'],
                                price2_data['bidVolume'] * price2_data['bid'],
                                price3_data['bidVolume'] * price3_data['bid']
                            ]
                            
                            if any(volume < min_volume for volume in volumes):
                                continue

                            # Taxa de trading (0.1% por operação)
                            fee_rate = 0.001
                            
                            # Cálculo considerando taxas
                            profit1 = ((1 / float(price1_data['ask'])) * float(price2_data['bid']) * float(price3_data['bid'])) * (1 - fee_rate)**3 - 1
                            profit2 = ((1 / float(price3_data['ask'])) * (1 / float(price2_data['ask'])) * float(price1_data['bid'])) * (1 - fee_rate)**3 - 1
                            
                            profit = max(profit1, profit2)
                            if profit > -0.001:  # Ajustado para mostrar oportunidades > -0.1%
                                # Log detalhado da oportunidade
                                self.logger.info(f"""
Oportunidade detectada:
Path: {base}->{asset1}->{asset2}->{base}
Profit: {round(profit * 100, 3)}%
Volumes: {volumes}
Taxas consideradas: {round(fee_rate * 100, 3)}% por trade
Latências: {[price1_data['latency'], price2_data['latency'], price3_data['latency']]}ms
""")
                                opportunity = {
                                    'id': str(len(opportunities) + 1),
                                    'profit': round(profit * 100, 3),
                                    'path': f"{base}->{asset1}->{asset2}->{base}",
                                    'timestamp': current_time.isoformat(),
                                    'market_metrics': {
                                        'volumes': {
                                            pair1: round(price1_data['bidVolume'] * price1_data['bid'], 2),
                                            pair2: round(price2_data['bidVolume'] * price2_data['bid'], 2),
                                            pair3: round(price3_data['bidVolume'] * price3_data['bid'], 2)
                                        },
                                        'spreads': {
                                            pair1: round(price1_data['ask'] - price1_data['bid'], 8),
                                            pair2: round(price2_data['ask'] - price2_data['bid'], 8),
                                            pair3: round(price3_data['ask'] - price3_data['bid'], 8)
                                        },
                                        'latencies': {
                                            pair1: round(price1_data['latency'], 2),
                                            pair2: round(price2_data['latency'], 2),
                                            pair3: round(price3_data['latency'], 2)
                                        },
                                        'fees': round(fee_rate * 100, 3)
                                    }
                                }
                                opportunities.append(opportunity)
                                
                                # Adiciona ao histórico
                                if hasattr(self, 'opportunities_history'):
                                    self.opportunities_history.append(opportunity)
                                    if len(self.opportunities_history) > self.max_history_size:
                                        self.opportunities_history = self.opportunities_history[-self.max_history_size:]
                                        
                                    # Salva a cada 100 novas oportunidades
                                    if len(self.opportunities_history) % 100 == 0:
                                        try:
                                            with open('data/opportunities_history.json', 'w') as f:
                                                json.dump(self.opportunities_history, f, indent=2)
                                        except Exception as e:
                                            self.logger.error(f"Erro ao salvar histórico: {e}")
                                
                        except Exception as e:
                            self.logger.error(f"Erro ao processar par {pair1}-{pair2}: {e}")
                            continue
            
            if opportunities:
                self.opportunities = sorted(
                    opportunities,
                    key=lambda x: float(x['profit']),
                    reverse=True
                )
                self.last_update = current_time
            
        except Exception as e:
            self.logger.error(f"Erro na detecção de arbitragem: {e}")
