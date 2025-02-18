"""
Cliente WebSocket para Binance
"""
from .binance_init import (
    AsyncClient,
    BinanceSocketManager,
    ThreadedWebsocketManager
)
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
        self._reconnect_delay = 0.5  # Reduzido para 0.5s
        self._connection_lock = asyncio.Lock()
        self._cleanup_event = asyncio.Event()
        self._active_tasks = set()
        self._last_heartbeat = time.time()
        
        # Aumenta tamanho do buffer
        self._stream_buffer = asyncio.Queue(maxsize=50000)
        
        # Configurações otimizadas
        self.ping_interval = 30  # Heartbeat a cada 30s
        self.response_timeout = 10  # Timeout de 10s para respostas
        self.max_message_size = 10 * 1024 * 1024  # 10MB
        self.compression = True  # Habilita compressão

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
        """Inicia socket multiplexado com reconexão automática e buffer otimizado"""
        while self._running:
            try:
                logger.info(f"Iniciando socket multiplexado para {len(streams)} streams")
                
                if not self.twm:
                    logger.error("Socket manager não inicializado")
                    await asyncio.sleep(2)  # Reduzido para 2s
                    continue

                # Configura handler com buffer
                async def handle_socket_message(msg):
                    try:
                        if not self._stream_buffer.full():
                            await self._stream_buffer.put(msg)
                        else:
                            logger.warning("Buffer cheio, descartando mensagem")
                            # Processa mensagens antigas do buffer
                            while not self._stream_buffer.empty():
                                old_msg = await self._stream_buffer.get()
                                await self._process_message(old_msg)
                    except Exception as e:
                        logger.error(f"Erro no handler: {e}")

                # Inicia socket com configurações otimizadas
                self.conn_key = self.twm.start_multiplex_socket(
                    callback=handle_socket_message,
                    streams=streams
                )
                
                logger.info(f"Socket multiplexado iniciado: {len(streams)} streams")
                
                # Inicia processador de buffer em background
                buffer_processor = asyncio.create_task(self._process_buffer())
                self._active_tasks.add(buffer_processor)
                
                while self._running:
                    current_time = time.time()
                    
                    # Heartbeat mais frequente
                    if current_time - self._last_heartbeat >= self.ping_interval:
                        try:
                            if self.client:
                                await asyncio.wait_for(
                                    self.client.ping(),
                                    timeout=self.response_timeout
                                )
                                self._last_heartbeat = current_time
                                logger.debug("Heartbeat enviado com sucesso")
                        except asyncio.TimeoutError:
                            logger.warning("Timeout no heartbeat, reiniciando conexão")
                            break
                        except Exception as e:
                            logger.error(f"Erro no heartbeat: {e}")
                            break
                    
                    await asyncio.sleep(0.1)  # Reduzido para 100ms
                    
            except Exception as e:
                if not self._running:
                    break
                logger.error(f"Erro no socket: {e}")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 1.5, 30)  # Backoff exponencial
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

    async def _process_buffer(self):
        """Processa mensagens do buffer em background"""
        while self._running:
            try:
                if not self._stream_buffer.empty():
                    msg = await self._stream_buffer.get()
                    await self._process_message(msg)
                    self._stream_buffer.task_done()
                else:
                    await asyncio.sleep(0.01)  # Pequena pausa quando buffer vazio
            except Exception as e:
                logger.error(f"Erro no processamento do buffer: {e}")
                await asyncio.sleep(0.1)  # Pausa maior em caso de erro

    def add_callback(self, callback):
        """Adiciona callback para processamento de mensagens"""
        self._callbacks.append(callback)

    async def _cleanup_connections(self):
        """Limpa conexões existentes e recursos"""
        try:
            # Cancela tarefas ativas
            for task in self._active_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self._active_tasks.clear()

            # Limpa buffer
            while not self._stream_buffer.empty():
                try:
                    self._stream_buffer.get_nowait()
                    self._stream_buffer.task_done()
                except asyncio.QueueEmpty:
                    break

            # Para WebSocket Manager
            if self.twm:
                try:
                    self.twm.stop()
                    await asyncio.sleep(0.5)  # Aguarda finalização
                except Exception as e:
                    logger.error(f"Erro ao parar TWM: {e}")

            # Fecha conexão com cliente
            if self.client:
                try:
                    await asyncio.wait_for(
                        self.client.close_connection(),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Timeout ao fechar conexão do cliente")
                except Exception as e:
                    logger.error(f"Erro ao fechar cliente: {e}")

        except Exception as e:
            logger.error(f"Erro na limpeza: {e}")
        finally:
            self.twm = None
            self.client = None
            self.conn_key = None
            logger.info("Conexões e recursos limpos")

    async def close(self):
        """Fecha conexões e limpa recursos"""
        self._running = False
        await self._cleanup_connections()
        self._callbacks.clear()
        self._cleanup_event.set()