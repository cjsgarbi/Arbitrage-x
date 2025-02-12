from binance.websocket.spot.websocket_client import SpotWebsocketClient
from binance.client import AsyncClient
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
        self.bm = None
        self.conn_key = None
        self._callbacks = []
        self._running = True
        self._reconnect_delay = 1
        self._connection_lock = asyncio.Lock()
        self._cleanup_event = asyncio.Event()
        self._active_tasks = set()

    async def connect(self, max_retries=3):
        """Estabelece conexão com Binance Websocket com retentativas"""
        async with self._connection_lock:
            retry_count = 0
            
            while retry_count < max_retries and self._running:
                try:
                    logger.info(f"Tentativa {retry_count + 1} de conexão com Binance WebSocket")
                    
                    # Fecha conexões existentes antes de reconectar
                    await self._cleanup_connections()
                    
                    # Configura client com timeout mais longo
                    self.client = await AsyncClient.create(
                        self.api_key,
                        self.api_secret,
                        requests_params={'timeout': 30}
                    )
                    
                    # Configura websocket client
                    self.bm = SpotWebsocketClient()
                    await self.bm.connect()
                    
                    # Testa conexão
                    for _ in range(3):
                        try:
                            await self.client.ping()
                            logger.info("Binance WebSocket Client conectado com sucesso")
                            self._reconnect_delay = 1  # Reset delay após sucesso
                            return True
                        except Exception as e:
                            if _ < 2:  # Tenta mais 2 vezes antes de desistir
                                await asyncio.sleep(1)
                                continue
                            raise
                                
                except Exception as e:
                    retry_count += 1
                    logger.error(f"Falha na tentativa {retry_count}/{max_retries}: {str(e)}", exc_info=True)
                    
                    if retry_count < max_retries and self._running:
                        logger.info(f"Aguardando {self._reconnect_delay}s antes da próxima tentativa")
                        await asyncio.sleep(self._reconnect_delay)
                        self._reconnect_delay = min(self._reconnect_delay * 2, 60)  # Exponential backoff até 60s
                        continue
                    
                    logger.error(f"Falha ao conectar após {max_retries} tentativas")
                    return False
            
            return False

    def add_callback(self, callback):
        """Adiciona callback para processamento de mensagens"""
        self._callbacks.append(callback)

    async def start_multiplex_socket(self, streams):
        """Inicia socket multiplexado com reconexão automática"""
        while self._running:
            try:
                logger.info(f"Iniciando socket multiplexado para {len(streams)} streams")
                
                if not self.bm:
                    logger.error("Socket client não inicializado")
                    await asyncio.sleep(5)
                    continue
                    
                # Subscribe to streams
                await self.bm.multiplex_subscribe(
                    callbacks=self._callbacks,
                    streams=streams
                )
                
                logger.info(f"Socket iniciado para {len(streams)} streams")
                
                # Inicia heartbeat
                last_heartbeat = time.time()
                message_count = 0
                error_count = 0
                
                while self._running:
                    try:
                        current_time = time.time()
                        
                        # Atualiza heartbeat com maior intervalo
                        if current_time - last_heartbeat >= 55:  # 55s para estar dentro do timeout de 60s
                            if self.client:
                                await self.client.ping()
                                last_heartbeat = current_time
                                logger.debug("Heartbeat atualizado")
                        
                        # Aguarda um pouco para não sobrecarregar
                        await asyncio.sleep(0.1)
                                
                    except Exception as e:
                        if not self._running:
                            break
                        error_count += 1
                        logger.error(f"Erro no processamento: {e}", exc_info=True)
                        await asyncio.sleep(1)
                        continue
                                
            except Exception as e:
                if not self._running:
                    break
                logger.error(f"Erro fatal no socket: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _cleanup_connections(self):
        """Limpa conexões existentes"""
        try:
            if self.bm:
                try:
                    await self.bm.stop()
                except Exception as e:
                    logger.error(f"Erro ao parar socket: {e}")

            if self.client:
                try:
                    await self.client.close_connection()
                except Exception as e:
                    logger.error(f"Erro ao fechar cliente: {e}")
                    
        except Exception as e:
            logger.error(f"Erro na limpeza de conexões: {e}")
        finally:
            self.bm = None
            self.client = None
            self.conn_key = None

    async def close(self):
        """Fecha conexões e limpa recursos de forma segura"""
        try:
            logger.info("Iniciando fechamento do WebSocket Client...")
            
            # Sinaliza para parar
            self._running = False
            
            # Aguarda tasks ativas finalizarem
            if self._active_tasks:
                logger.info(f"Aguardando {len(self._active_tasks)} tasks finalizarem...")
                await asyncio.gather(*self._active_tasks, return_exceptions=True)
            
            # Limpa conexões
            await self._cleanup_connections()
            
            # Limpa recursos
            self._callbacks.clear()
            self._active_tasks.clear()
            
            # Sinaliza cleanup completo
            self._cleanup_event.set()
            
            logger.info("Binance WebSocket Client finalizado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao finalizar recursos: {e}", exc_info=True)
            raise