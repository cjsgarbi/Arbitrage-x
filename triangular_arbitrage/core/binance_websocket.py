from binance.websockets import BinanceWebsocketClient as BinanceWS
from binance.client import AsyncClient
from binance import ThreadedWebsocketManager
import asyncio
import json
import logging
import time
from contextlib import AsyncExitStack

logger = logging.getLogger(__name__)

class BinanceWebsocketClient:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None
        self.twm = None  # ThreadedWebsocketManager
        self.conn_key = None
        self._callbacks = []
        self._running = True
        self._reconnect_delay = 1
        self._connection_lock = asyncio.Lock()
        self._cleanup_event = asyncio.Event()
        self._active_tasks = set()
        self._last_heartbeat = time.time()

    async def connect(self, max_retries=3):
        """Estabelece conexão com Binance Websocket com retentativas"""
        async with self._connection_lock:
            retry_count = 0
            
            while retry_count < max_retries and self._running:
                try:
                    logger.info(f"Tentativa {retry_count + 1} de conexão com Binance WebSocket")
                    
                    await self._cleanup_connections()
                    
                    self.client = await AsyncClient.create(
                        self.api_key,
                        self.api_secret,
                        requests_params={'timeout': 30}
                    )
                    
                    self.twm = ThreadedWebsocketManager(
                        api_key=self.api_key,
                        api_secret=self.api_secret
                    )
                    self.twm.start()
                    
                    # Testa conexão
                    for _ in range(3):
                        try:
                            if self.client:
                                await self.client.ping()
                                logger.info("Binance WebSocket Client conectado com sucesso")
                                self._reconnect_delay = 1
                                self._last_heartbeat = time.time()
                                return True
                        except Exception as e:
                            if _ < 2:
                                await asyncio.sleep(1)
                                continue
                            raise
                                
                except Exception as e:
                    retry_count += 1
                    logger.error(f"Falha na tentativa {retry_count}: {e}")
                    
                    if retry_count < max_retries and self._running:
                        await asyncio.sleep(self._reconnect_delay)
                        self._reconnect_delay = min(self._reconnect_delay * 2, 60)
                        continue
                    
                    logger.error(f"Falha ao conectar após {max_retries} tentativas")
                    return False
            
            return False

    async def start_multiplex_socket(self, streams):
        """Inicia socket multiplexado com reconexão automática"""
        while self._running:
            try:
                logger.info(f"Iniciando socket multiplexado para {len(streams)} streams")
                
                if not self.twm:
                    logger.error("Socket manager não inicializado")
                    await asyncio.sleep(5)
                    continue

                def handle_socket_message(msg):
                    asyncio.create_task(self._process_message(msg))
                
                self.conn_key = self.twm.start_multiplex_socket(
                    callback=handle_socket_message,
                    streams=streams
                )
                
                logger.info(f"Socket multiplexado iniciado: {len(streams)} streams")
                
                while self._running:
                    await asyncio.sleep(1)
                    current_time = time.time()
                    
                    # Verifica heartbeat
                    if current_time - self._last_heartbeat >= 55:
                        if self.client:
                            await self.client.ping()
                            self._last_heartbeat = current_time
                    
            except Exception as e:
                if not self._running:
                    break
                logger.error(f"Erro no socket: {e}")
                await asyncio.sleep(5)
                continue

    async def _process_message(self, msg):
        """Processa mensagens recebidas do WebSocket"""
        try:
            if msg.get('e') == 'error':
                logger.error(f"Erro no WebSocket: {msg.get('m')}")
                return
            
            for callback in self._callbacks:
                try:
                    await callback(msg)
                except Exception as e:
                    logger.error(f"Erro no callback: {e}")
                    
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")

    def add_callback(self, callback):
        """Adiciona callback para processamento de mensagens"""
        self._callbacks.append(callback)

    async def _cleanup_connections(self):
        """Limpa conexões existentes"""
        try:
            if self.twm:
                self.twm.stop()
            if self.client:
                await self.client.close_connection()
        except Exception as e:
            logger.error(f"Erro na limpeza: {e}")
        finally:
            self.twm = None
            self.client = None
            self.conn_key = None

    async def close(self):
        """Fecha conexões e limpa recursos"""
        self._running = False
        await self._cleanup_connections()
        self._callbacks.clear()
        self._cleanup_event.set()