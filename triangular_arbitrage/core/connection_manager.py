"""
Gerenciador de conexões para o bot
"""
from typing import Optional, Dict, List
import asyncio
import logging
from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Gerencia conexões WebSocket e REST com a Binance
    """
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client: Optional[AsyncClient] = None
        self.socket_manager: Optional[BinanceSocketManager] = None
        self.active_socket = None
        self.is_connected = False
        self.message_queue = asyncio.Queue()
        self._running = False
        self.logger = logging.getLogger(__name__)

    async def connect(self) -> bool:
        """
        Estabelece conexão com a Binance
        """
        try:
            if not self.api_key or not self.api_secret:
                raise ValueError("API key e secret são necessários")

            self.client = await AsyncClient.create(self.api_key, self.api_secret)
            if not self.client:
                raise ValueError("Falha ao criar cliente Binance")

            self.socket_manager = BinanceSocketManager(self.client)
            if not self.socket_manager:
                raise ValueError("Falha ao criar socket manager")

            self.is_connected = True
            self._running = True
            return True

        except Exception as e:
            self.logger.error(f"Erro na conexão: {e}")
            await self.disconnect()
            return False

    async def disconnect(self):
        """
        Desconecta de forma segura
        """
        self._running = False
        
        try:
            if self.active_socket:
                # Aguarda um curto período para processamento final
                await asyncio.sleep(0.5)
                self.active_socket = None

            if self.socket_manager:
                self.socket_manager = None

            if self.client:
                await self.client.close_connection()
                self.client = None

            self.is_connected = False
            
        except Exception as e:
            self.logger.error(f"Erro ao desconectar: {e}")
        finally:
            self.is_connected = False

    async def start_market_stream(self, symbols: List[str]) -> bool:
        """
        Inicia stream de dados de mercado
        """
        if not self.is_connected or not self.socket_manager:
            return False

        try:
            streams = [f"{symbol.lower()}@bookTicker" for symbol in symbols]
            self.active_socket = self.socket_manager.multiplex_socket(streams)
            
            return True

        except Exception as e:
            self.logger.error(f"Erro ao iniciar stream: {e}")
            return False

    async def process_socket_messages(self, callback):
        """
        Processa mensagens do socket
        """
        if not self.active_socket:
            return

        try:
            async with self.active_socket as socket:
                while self._running:
                    try:
                        msg = await socket.recv()
                        if msg:
                            await callback(msg)
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        self.logger.error(f"Erro no processamento: {e}")
                        if not self._running:
                            break
                        await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"Erro no socket: {e}")
        finally:
            self._running = False

    async def execute_trades(self, trades: List[Dict]) -> Dict:
        """
        Executa trades de forma segura
        """
        if not self.is_connected or not self.client:
            return {'success': False, 'error': 'Não conectado'}

        results = []
        success = True

        try:
            for trade in trades:
                try:
                    result = await self.client.create_order(**trade)
                    results.append({
                        'success': True,
                        'data': result
                    })
                except BinanceAPIException as e:
                    success = False
                    results.append({
                        'success': False,
                        'error': str(e)
                    })
                    break

            return {
                'success': success,
                'results': results
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }