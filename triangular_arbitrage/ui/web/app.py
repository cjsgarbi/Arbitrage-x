from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
import logging
from pathlib import Path
import sys
import time
import statistics
import traceback

# Ajuste dos imports relativos para absolutos
from triangular_arbitrage.utils.log_config import setup_logging, JsonFormatter
from triangular_arbitrage.utils.dashboard_logger import DashboardLogger

# Configuração inicial dos loggers
loggers = setup_logging()
logger = logging.getLogger(__name__)
debug_logger = logging.getLogger('debug')
error_logger = logging.getLogger('error')
dashboard_logger = DashboardLogger()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()
        self._cleanup_event = asyncio.Event()
        self._heartbeat_interval = 5  # Reduzido para 5 segundos
        self._connection_timeouts = {}
        self._last_activity = {}
        self._ping_tasks = {}
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'errors': 0,
            'reconnections': 0
        }

    async def connect(self, websocket: WebSocket):
        """Gerencia conexão de um novo WebSocket"""
        try:
            await websocket.accept()
            async with self._lock:
                self.active_connections.append(websocket)
                self.connection_stats['total_connections'] += 1
                self.connection_stats['active_connections'] = len(self.active_connections)
                self._last_activity[id(websocket)] = time.time()
                
                # Inicia monitoramento de heartbeat para esta conexão
                self._ping_tasks[id(websocket)] = asyncio.create_task(
                    self._monitor_connection(websocket)
                )
                
            logger.info(f"Nova conexão WebSocket estabelecida. Total ativo: {len(self.active_connections)}")
            
            # Envia configuração inicial
            await websocket.send_text(json.dumps({
                "type": "connection_config",
                "data": {
                    "heartbeat_interval": self._heartbeat_interval,
                    "reconnect_delay": 1000,
                    "connection_id": id(websocket)
                }
            }))
            
        except Exception as e:
            logger.error(f"Erro ao estabelecer conexão WebSocket: {e}")
            if websocket in self.active_connections:
                await self.disconnect(websocket)

    async def disconnect(self, websocket: WebSocket):
        """Desconecta um WebSocket de forma segura"""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                self.connection_stats['active_connections'] = len(self.active_connections)
                
                # Limpa dados de monitoramento
                conn_id = id(websocket)
                self._last_activity.pop(conn_id, None)
                
                # Cancela task de ping
                if conn_id in self._ping_tasks:
                    self._ping_tasks[conn_id].cancel()
                    self._ping_tasks.pop(conn_id)
                
                try:
                    await websocket.close()
                except Exception:
                    pass
                
                logger.info(f"Conexão WebSocket fechada. Total ativo: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Envia mensagem para todos os clientes conectados"""
        if not self.active_connections:
            logger.debug("Nenhuma conexão ativa para broadcast")
            return
            
        async with self._lock:
            logger.debug(f"Iniciando broadcast para {len(self.active_connections)} conexões")
            start_time = time.time()
            
            disconnected = []
            success_count = 0
            
            for connection in self.active_connections:
                try:
                    # Serializa a mensagem uma vez para cada conexão
                    message_text = json.dumps(message)
                    await connection.send_text(message_text)
                    self.connection_stats['messages_sent'] += 1
                    self._last_activity[id(connection)] = time.time()
                    success_count += 1
                except Exception as e:
                    logger.error(f"Erro ao enviar mensagem para conexão {id(connection)}: {e}")
                    self.connection_stats['errors'] += 1
                    disconnected.append(connection)

            # Remove conexões com erro
            for conn in disconnected:
                logger.warning(f"Removendo conexão com erro: {id(conn)}")
                await self.disconnect(conn)

            # Log do resultado do broadcast
            duration = (time.time() - start_time) * 1000
            logger.debug(f"""
                Broadcast concluído:
                - Tempo total: {duration:.2f}ms
                - Envios com sucesso: {success_count}
                - Falhas: {len(disconnected)}
                - Conexões restantes: {len(self.active_connections)}
            """)

    async def _monitor_connection(self, websocket: WebSocket):
        """Monitora uma conexão específica e mantém heartbeat"""
        conn_id = id(websocket)
        ping_interval = self._heartbeat_interval / 2  # Envia ping na metade do intervalo
        
        while not self._cleanup_event.is_set() and websocket in self.active_connections:
            try:
                await asyncio.sleep(ping_interval)
                
                # Verifica última atividade
                if time.time() - self._last_activity.get(conn_id, 0) > self._heartbeat_interval:
                    # Envia ping
                    await websocket.send_text(json.dumps({"type": "ping", "timestamp": time.time()}))
                    
                    # Aguarda pong com timeout
                    try:
                        response = await asyncio.wait_for(
                            websocket.receive_text(),
                            timeout=3.0
                        )
                        if json.loads(response).get("type") == "pong":
                            self._last_activity[conn_id] = time.time()
                            continue
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout no heartbeat da conexão {conn_id}")
                        break
                    except Exception as e:
                        logger.error(f"Erro no heartbeat: {e}")
                        break
                
            except Exception as e:
                logger.error(f"Erro no monitoramento da conexão {conn_id}: {e}")
                break
        
        # Se saiu do loop, desconecta
        if websocket in self.active_connections:
            await self.disconnect(websocket)

    async def cleanup(self):
        """Limpa todas as conexões"""
        self._cleanup_event.set()
        async with self._lock:
            for connection in self.active_connections[:]:
                await self.disconnect(connection)
            self.active_connections.clear()
            self._last_activity.clear()
            
            for timeout in self._connection_timeouts.values():
                timeout.cancel()
            self._connection_timeouts.clear()

    async def get_stats(self):
        """Retorna estatísticas da conexão"""
        return {
            'active_connections': len(self.active_connections),
            'total_connections': self.connection_stats['total_connections'],
            'messages_sent': self.connection_stats['messages_sent'],
            'errors': self.connection_stats['errors'],
            'reconnections': self.connection_stats['reconnections']
        }
        
    async def get_performance_metrics(self):
        """Retorna métricas de performance das conexões"""
        return {
            'connection_stats': self.connection_stats,
            'active_connections': len(self.active_connections),
            'messages_sent': self.connection_stats['messages_sent'],
            'errors': self.connection_stats['errors'],
            'reconnections': self.connection_stats['reconnections']
        }

class WebDashboard:
    def __init__(self, bot_core):
        self.app = FastAPI(
            title="Arbitrage Dashboard",
            docs_url="/docs",
            redoc_url="/redoc",
            on_shutdown=[self.cleanup]  # Registra cleanup para ser chamado no shutdown
        )
        self.bot_core = bot_core
        self.manager = ConnectionManager()
        self._broadcast_task = None
        self._initialized = False
        self._cleanup_event = asyncio.Event()
        self._tasks = set()
        self._shutdown_started = False
        
        # Configuração de logging
        self.logger = logger
        self.debug_logger = debug_logger
        self.error_logger = error_logger
        self.dashboard_logger = dashboard_logger
        
        # Setup inicial de métricas
        self._last_metrics_update = datetime.now()
        self._broadcast_metrics = {
            'latency': [],
            'errors': 0,
            'messages_sent': 0
        }
        
        # CORS configuration com logs detalhados
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
        )
        
        # Log todas as origens das requisições
        @self.app.middleware("http")
        async def log_requests(request, call_next):
            self.logger.debug(f"Request recebida de: {request.client.host}, método: {request.method}, path: {request.url.path}")
            response = await call_next(request)
            return response
        
        # Mount static folder
        static_path = Path(__file__).parent / "static"
        self.app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
        
        # Setup routes
        self.setup_routes()

    async def initialize(self):
        """Inicializa o WebDashboard garantindo que todos os componentes estejam prontos"""
        if self._initialized:
            return
            
        try:
            # Verifica se o bot está pronto
            if not self.bot_core or not self.bot_core.is_connected:
                logger.warning("Aguardando bot estar pronto...")
                await asyncio.sleep(1)
                
            # Prepara estruturas de dados
            self._broadcast_metrics = {
                'latency': [],
                'errors': 0,
                'messages_sent': 0
            }
            
            # Limpa tasks antigas se houver
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            self._tasks.clear()
            
            # Inicia task de broadcast em background
            self._broadcast_task = asyncio.create_task(self._broadcast_data())
            self._tasks.add(self._broadcast_task)
            
            # Aguarda primeira execução do broadcast
            try:
                await asyncio.wait_for(self._wait_first_broadcast(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout aguardando primeiro broadcast, continuando mesmo assim")
            
            self._initialized = True
            logger.info("✅ WebDashboard inicializado com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar WebDashboard: {e}")
            import traceback
            logger.error(f"Detalhes: {traceback.format_exc()}")
            self._initialized = False
            raise

    async def _wait_first_broadcast(self):
        """Aguarda primeira execução do broadcast"""
        while not self._broadcast_metrics['messages_sent']:
            await asyncio.sleep(0.1)

    def _adjust_broadcast_interval(self, latency: float, current_interval: float) -> float:
        """Ajusta intervalo de broadcast baseado na latência"""
        target_latency = 50  # 50ms alvo
        min_interval = 0.05  # 50ms mínimo
        max_interval = 0.2   # 200ms máximo
        
        if latency > 100:  # Latência muito alta
            return min(max_interval, current_interval * 1.2)
        elif latency < target_latency:  # Latência boa
            return max(min_interval, current_interval * 0.9)
        return current_interval

    async def _broadcast_data(self):
        """Broadcast data para clientes WebSocket com otimizações e ajuste dinâmico"""
        broadcast_interval = 1.0  # 1 segundo inicial
        min_interval = 0.5  # Mínimo de 500ms
        max_interval = 2.0  # Máximo de 2 segundos
        
        while not self._cleanup_event.is_set():
            try:
                if not self.manager.active_connections:
                    self.logger.debug("Sem conexões ativas para broadcast")
                    await asyncio.sleep(broadcast_interval)
                    continue

                start_time = time.time()
                
                # Verifica se bot_core existe e está conectado
                if not self.bot_core:
                    self.logger.error("bot_core não está disponível")
                    await asyncio.sleep(1)
                    continue
                    
                if not self.bot_core.is_connected:
                    self.logger.warning("bot_core não está conectado")
                    await asyncio.sleep(1)
                    continue

                try:
                    # Obtém e valida oportunidades
                    opportunities = getattr(self.bot_core, 'opportunities', [])
                    self.logger.info(f"Oportunidades detectadas: {len(opportunities)}")
                    
                    # Log detalhado para debug do formato dos dados
                    if opportunities:
                        self.logger.debug("Exemplo de estrutura das oportunidades:")
                        self.logger.debug(json.dumps(opportunities[0], indent=2))
                        self.logger.debug("Status do bot_core:")
                        self.logger.debug(f"is_connected: {self.bot_core.is_connected}")
                        self.logger.debug(f"ai_status: {self.bot_core.get_ai_status()}")
                    
                    if not opportunities:
                        self.logger.debug("Nenhuma oportunidade disponível para broadcast")
                        # Envia mensagem vazia para manter o frontend atualizado
                        await self.manager.broadcast({
                            'type': 'opportunities',
                            'data': [],
                            'metadata': {
                                'total_pairs': len(getattr(self.bot_core, 'symbol_pairs', set())),
                                'active_pairs': 0,
                                'monitored_pairs': 0,
                                'update_timestamp': datetime.now().isoformat()
                            }
                        })
                        await asyncio.sleep(broadcast_interval)
                        continue

                    # Log detalhado para debug
                    self.logger.debug("Detalhes das oportunidades detectadas:")
                    for opp in opportunities[:5]:
                        self.logger.debug(f"""
                            ID: {opp.get('id')}
                            Rota: {opp.get('route')}
                            Profit: {opp.get('profit')}%
                            Volume: {opp.get('a_volume')}
                            Latência: {opp.get('latency')}ms
                        """)

                    # Formata oportunidades antes do envio
                except Exception as e:
                    self.logger.error(f"Erro ao processar oportunidades: {e}")
                    self.logger.error(f"Detalhes do erro: {traceback.format_exc()}")
                    await asyncio.sleep(1)
                    continue

                all_pairs = list(self.bot_core.symbol_pairs)[:10]  # Limita a 10 grupos
                formatted_opportunities = []
                
                # Processa cada par dos 10 selecionados
                for pair in all_pairs:
                    # Encontra oportunidades relacionadas ao par
                    pair_opportunities = [opp for opp in opportunities
                                      if pair in [opp.get('a_step_from'), opp.get('b_step_from'), opp.get('c_step_from')]]
                    
                    try:
                        latest_price = self.bot_core.price_cache.get(pair, {}).get('price', 0)
                        latest_volume = self.bot_core.price_cache.get(pair, {}).get('volume', 0)
                        latest_timestamp = self.bot_core.price_cache.get(pair, {}).get('timestamp', time.time())
                        
                        if pair_opportunities:
                            for opp in pair_opportunities:
                                try:
                                    # Extrai dados da oportunidade com valores padrão
                                    profit = float(opp.get('profit', 0))
                                    volume = float(opp.get('a_volume', 0))
                                    latency = float(opp.get('latency', 0))
                                    
                                    # Formata a oportunidade com todos os campos necessários
                                    formatted_opp: Dict[str, Union[str, float, int]] = {
                                        'id': opp.get('id', str(time.time())),
                                        'route': f"{opp.get('a_step_from')}→{opp.get('b_step_from')}→{opp.get('c_step_from')}",
                                        'profit': profit,
                                        'volume': volume,
                                        'price': float(opp.get('a_rate', 0)),
                                        'slippage': 0.005,
                                        'executionTime': latency / 1000,
                                        'liquidity': self._calculate_liquidity_level(volume),
                                        'risk': self._calculate_risk_level(profit, volume),
                                        'spread': 0.0,
                                        'volatility': self._calculate_volatility_risk(opp),
                                        'confidence': self._calculate_confidence(profit),
                                        'timestamp': opp.get('timestamp', datetime.now().isoformat()),
                                        'status': 'active' if profit > 0 else 'inactive'
                                    }
                                    
                                    formatted_opportunities.append(formatted_opp)
                                    
                                except Exception as e:
                                    self.logger.error(f"Erro ao formatar oportunidade: {e}")
                                    continue
                    except (ValueError, TypeError) as e:
                        self.logger.error(f"❌ Erro ao processar par {pair}: {e}")
                        continue

                # Prepara mensagem com metadados atualizados
                message: Dict[str, Any] = {
                    'type': 'opportunities',
                    'data': formatted_opportunities,
                    'metadata': {
                        'total_pairs': len(all_pairs),
                        'active_pairs': len([opp for opp in formatted_opportunities if opp['status'] == 'active']),
                        'monitored_pairs': len(formatted_opportunities),
                        'update_timestamp': datetime.now().isoformat()
                    }
                }
                
                self.logger.debug(f"Preparando broadcast para {len(self.manager.active_connections)} conexões")
                self.logger.debug(f"Dados a serem enviados: {len(formatted_opportunities)} oportunidades")
                if formatted_opportunities:
                    self.logger.debug(f"Primeira oportunidade: {json.dumps(formatted_opportunities[0], indent=2)}")

                # Verifica conexões ativas antes do broadcast
                if not self.manager.active_connections:
                    self.logger.warning("Nenhuma conexão WebSocket ativa. Pulando broadcast.")
                    await asyncio.sleep(broadcast_interval)
                    continue

                try:
                    start_broadcast = time.time()
                    # Broadcast para todos os clientes
                    await self.manager.broadcast(message)
                    broadcast_duration = (time.time() - start_broadcast) * 1000

                    # Ajusta intervalo baseado no tempo de processamento
                    if broadcast_duration > 500:  # Se demorou mais de 500ms
                        broadcast_interval = min(broadcast_interval * 1.2, max_interval)
                        self.logger.warning(f"Aumentando intervalo para {broadcast_interval:.2f}s devido à latência alta")
                    elif broadcast_duration < 100:  # Se foi rápido (<100ms)
                        broadcast_interval = max(broadcast_interval * 0.8, min_interval)
                        self.logger.debug(f"Reduzindo intervalo para {broadcast_interval:.2f}s")

                    # Log detalhado do broadcast
                    self.logger.info(f"""
                        Broadcast realizado:
                        - Total de oportunidades: {len(formatted_opportunities)}
                        - Oportunidades ativas: {message['metadata']['active_pairs']}
                        - Conexões ativas: {len(self.manager.active_connections)}
                        - Tempo de broadcast: {broadcast_duration:.2f}ms
                        - Próximo intervalo: {broadcast_interval:.2f}s
                    """)
                    
                    # Atualiza métricas
                    self._broadcast_metrics['latency'].append(broadcast_duration / 1000)
                    if len(self._broadcast_metrics['latency']) > 100:
                        self._broadcast_metrics['latency'] = self._broadcast_metrics['latency'][-100:]
                except Exception as e:
                    self.logger.error(f"Erro durante broadcast: {e}")
                    self.logger.error(traceback.format_exc())
                
                # Log de performance
                broadcast_time = (time.time() - start_time) * 1000
                self.logger.debug(f"Broadcast completado em {broadcast_time:.2f}ms")
                
                await asyncio.sleep(broadcast_interval)
                
            except Exception as e:
                self.logger.error(f"Erro no broadcast: {e}")
                self.logger.error(f"Detalhes: {traceback.format_exc()}")
                await asyncio.sleep(1)

    def _calculate_status(self, profit: float) -> str:
        if profit > 1.0:
            return 'excellent'
        elif profit > 0.5:
            return 'good'
        return 'viable'

    def _calculate_confidence(self, profit: float) -> int:
        if profit > 1.5:
            return 90
        elif profit > 0.5:
            return 70
        return 50

    def _calculate_cache_health(self) -> float:
        """Calcula saúde do cache baseado em dados recentes"""
        try:
            if not hasattr(self.bot_core, 'price_cache'):
                return 0.0
                
            current_time = time.time()
            recent_prices = [
                1 for timestamp in (
                    data.get('timestamp', 0) 
                    for data in self.bot_core.price_cache.values()
                )
                if current_time - timestamp < 5
            ]
            
            if not self.bot_core.price_cache:
                return 0.0
                
            return round((len(recent_prices) / len(self.bot_core.price_cache)) * 100, 2)
        except Exception as e:
            logger.error(f"Erro ao calcular saúde do cache: {e}")
            return 0.0

    def _calculate_volatility_risk(self, opportunity: Dict) -> str:
        """Calcula risco de volatilidade baseado no histórico"""
        try:
            # Tenta calcular baseado no histórico de preços
            recent_prices = self.bot_core.price_cache.get(
                opportunity.get('a_step_from'), 
                {}
            ).get('recent_prices', [])

            if recent_prices and len(recent_prices) >= 10:
                # Calcula volatilidade usando desvio padrão dos últimos preços
                std_dev = statistics.stdev(recent_prices[-10:])
                mean_price = statistics.mean(recent_prices[-10:])
                volatility = (std_dev / mean_price) * 100 if mean_price > 0 else 0
                
                if volatility < 0.5:
                    return "Baixa"
                elif volatility < 1.5:
                    return "Média"
                return "Alta"
            
            # Se não tiver dados suficientes, calcula baseado no profit e volume
            profit = float(opportunity.get('profit', 0))
            volume = float(opportunity.get('a_volume', 0))
            
            if profit > 1.5 and volume > 0.1:
                return "Baixa"
            elif profit > 0.8 and volume > 0.05:
                return "Média"
            return "Alta"
            
        except (ValueError, TypeError, Exception):
            return "Média"  # Valor padrão em caso de erro

    def _calculate_liquidity_risk(self, opportunity: Dict) -> str:
        """Calcula risco de liquidez baseado no volume"""
        try:
            volume = float(opportunity.get('a_volume', 0))
            
            if volume > 0.5:  # Volume maior que 0.5 BTC
                return 'low'
            elif volume > 0.1:  # Volume maior que 0.1 BTC
                return 'medium'
            return 'high'
        except (ValueError, TypeError):
            return 'high'

    def _calculate_liquidity_level(self, volume: float) -> str:
        """Calcula nível de liquidez baseado no volume"""
        try:
            if volume >= 1.0:  # Volume maior que 1 BTC
                return "Alta"
            elif volume >= 0.1:  # Volume maior que 0.1 BTC
                return "Média"
            return "Baixa"
        except (ValueError, TypeError):
            return "Baixa"

    def _calculate_risk_level(self, profit: float, volume: float) -> str:
        """Calcula nível de risco baseado no profit e volume"""
        try:
            # Considera tanto profit positivo quanto negativo
            abs_profit = abs(profit)
            if abs_profit > 1.0 and volume > 1.0:
                return "Baixo"
            elif abs_profit > 0.5 and volume > 0.1:
                return "Médio"
            return "Alto"
        except (ValueError, TypeError):
            return "Alto"

    async def _handle_websocket(self, websocket: WebSocket):
        """Gerencia conexão WebSocket individual"""
        client_id = f"client_{id(websocket)}"
        
        try:
            await self.manager.connect(websocket)
            self.logger.info(f"Nova conexão WebSocket estabelecida: {client_id}")
            
            # Envia estado inicial
            await self._send_full_update(websocket)
            
            while not self._cleanup_event.is_set():
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    self.logger.debug(f"Mensagem recebida de {client_id}: {message}")
                    
                    if message.get('type') == 'ping':
                        await websocket.send_text(json.dumps({
                            'type': 'pong',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue
                    
                    # Processa outras mensagens normalmente
                    await self._process_websocket_message(websocket, message)
                    
                except WebSocketDisconnect:
                    self.logger.info(f"Cliente desconectado: {client_id}")
                    break
                except json.JSONDecodeError:
                    self.logger.warning(f"Mensagem inválida recebida de {client_id}")
                    continue
                except Exception as e:
                    self.logger.error(f"Erro no processamento de mensagem WebSocket: {e}")
                    if "Connection reset by peer" in str(e):
                        break
                    await asyncio.sleep(1)
                    continue
                    
        except Exception as e:
            self.logger.error(f"Erro na conexão WebSocket {client_id}: {e}")
        finally:
            self.logger.info(f"Finalizando conexão {client_id}")
            await self.manager.disconnect(websocket)

    async def _monitor_pair(self, websocket: WebSocket, pair: str):
        """Monitora um par específico em tempo real"""
        try:
            # Obtém dados do par
            opportunities = [opp for opp in getattr(self.bot_core, 'opportunities', [])
                           if pair in [opp.get('a_step_from'), opp.get('b_step_from'), opp.get('c_step_from')]]
            
            # Calcula métricas em tempo real
            metrics = {
                'pair': pair,
                'metrics': {
                    'current_profit': max([float(opp.get('profit', 0)) for opp in opportunities], default=0),
                    'volume_now': sum(float(opp.get('a_volume', 0)) for opp in opportunities),
                    'opportunity_count': len(opportunities),
                    'active_routes': list(set(
                        f"{opp.get('a_step_from')}→{opp.get('b_step_from')}→{opp.get('c_step_from')}"
                        for opp in opportunities
                    )),
                },
                'timestamp': datetime.now().isoformat()
            }
            
            await websocket.send_text(json.dumps({
                'type': 'pair_monitor_update',
                'data': metrics
            }))
            
        except Exception as e:
            logger.error(f"Erro ao monitorar par {pair}: {e}")
            await websocket.send_text(json.dumps({
                'type': 'error',
                'message': f'Erro ao monitorar par: {str(e)}'
            }))

    async def _send_opportunities_update(self, websocket: WebSocket):
        """Envia atualização de oportunidades incluindo todos os dados reais"""
        try:
            # Obtém todos os pares monitorados
            all_pairs = list(self.bot_core.symbol_pairs)[:10]  # Limita a 10 grupos
            opportunities = getattr(self.bot_core, 'opportunities', [])
            
            formatted_opportunities = []
            
            # Processa cada par dos 10 selecionados
            for pair in all_pairs:
                # Encontra oportunidades relacionadas ao par
                pair_opportunities = [opp for opp in opportunities 
                                   if pair in [opp.get('a_step_from'), opp.get('b_step_from'), opp.get('c_step_from')]]
                
                try:
                    # Obtém dados reais do par
                    latest_price = self.bot_core.price_cache.get(pair, {}).get('price', 0)
                    latest_volume = self.bot_core.price_cache.get(pair, {}).get('volume', 0)
                    latest_timestamp = self.bot_core.price_cache.get(pair, {}).get('timestamp', time.time())
                    
                    # Calcula dados reais mesmo sem oportunidades ativas
                    base_opp = {
                        'id': f"{pair}_{str(time.time())}",
                        'route': f"{pair}→{pair}→{pair}",
                        'profit': 0.0,
                        'volume': latest_volume,
                        'price': latest_price,
                        'slippage': 0.005,
                        'executionTime': 0,
                        'liquidity': self._calculate_liquidity_level(latest_volume),
                        'risk': self._calculate_risk_level(0, latest_volume),
                        'spread': 0.0,
                        'volatility': self._calculate_volatility_risk({'a_step_from': pair, 'volume': latest_volume}),
                        'confidence': 50,
                        'timestamp': datetime.fromtimestamp(latest_timestamp).isoformat(),
                        'status': 'monitored'
                    }
                    
                    # Se houver oportunidades ativas, atualiza com dados reais
                    if pair_opportunities:
                        for opp in pair_opportunities:
                            profit = float(opp.get('profit', 0))
                            volume = float(opp.get('a_volume', 0))
                            
                            formatted_opp = {
                                'id': opp.get('id', str(time.time())),
                                'route': f"{opp.get('a_step_from')}→{opp.get('b_step_from')}→{opp.get('c_step_from')}",
                                'profit': profit,  # Mantém valor real mesmo se negativo
                                'volume': volume,
                                'price': float(opp.get('a_rate', 0)),
                                'slippage': float(opp.get('slippage', 0.005)),
                                'executionTime': float(opp.get('latency', 0)) / 1000,
                                'liquidity': self._calculate_liquidity_level(volume),
                                'risk': self._calculate_risk_level(profit, volume),
                                'spread': float(opp.get('spread', 0)),
                                'volatility': self._calculate_volatility_risk(opp),
                                'confidence': self._calculate_confidence(profit),
                                'timestamp': opp.get('timestamp', datetime.now().isoformat()),
                                'status': 'active'
                            }
                            formatted_opportunities.append(formatted_opp)
                    else:
                        # Adiciona o par mesmo sem oportunidades ativas
                        formatted_opportunities.append(base_opp)
                        
                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Erro ao processar par {pair}: {e}")
                    continue

            # Envia dados com metadata adicional
            await websocket.send_text(json.dumps({
                'type': 'opportunities',
                'data': formatted_opportunities,
                'metadata': {
                    'total_pairs': len(all_pairs),
                    'active_pairs': len([opp for opp in formatted_opportunities if opp['status'] == 'active']),
                    'monitored_pairs': len(formatted_opportunities),
                    'update_timestamp': datetime.now().isoformat()
                }
            }))

        except Exception as e:
            logger.error(f"❌ Erro ao enviar atualizações: {e}")
            await websocket.send_text(json.dumps({
                'type': 'error',
                'message': 'Erro ao atualizar oportunidades'
            }))

    async def _send_top_pairs_update(self, websocket: WebSocket):
        """Envia atualização dos top pares com métricas detalhadas"""
        try:
            pairs = list(self.bot_core.symbol_pairs)
            pair_metrics = []

            # Obtém dados de 24h atrás para cálculo de variação
            yesterday = datetime.now() - timedelta(days=1)
            
            for pair in pairs:
                opportunities = [opp for opp in getattr(self.bot_core, 'opportunities', [])
                               if pair in [opp.get('a_step_from'), opp.get('b_step_from'), opp.get('c_step_from')]]
                
                if opportunities:
                    # Calcula métricas atuais
                    current_profits = [float(opp.get('profit', 0)) for opp in opportunities]
                    volume_24h = sum(float(opp.get('a_volume', 0)) for opp in opportunities)
                    
                    # Obtém rota mais lucrativa
                    best_opportunity = max(opportunities, key=lambda x: float(x.get('profit', 0)))
                    best_route = f"{best_opportunity.get('a_step_from')}→{best_opportunity.get('b_step_from')}→{best_opportunity.get('c_step_from')}"
                    
                    # Calcula média de lucro das últimas 24h
                    profits_24h = [float(opp.get('profit', 0)) for opp in opportunities 
                                 if datetime.fromisoformat(opp.get('timestamp', '')) > yesterday]
                    
                    metrics = {
                        'pair': pair,
                        'route': best_route,
                        'avg_profit': round(sum(current_profits) / len(current_profits), 4),
                        'profit_24h': round(sum(profits_24h) / len(profits_24h), 4) if profits_24h else None,
                        'volume_24h': round(volume_24h, 8),
                        'opportunity_count': len(opportunities),
                        'last_update': max(opp.get('timestamp', datetime.now().isoformat()) for opp in opportunities),
                        'status': 'active' if (datetime.now() - datetime.fromisoformat(
                            max(opp.get('timestamp', datetime.now().isoformat()) for opp in opportunities)
                        )).seconds < 300 else 'inactive'
                    }
                    pair_metrics.append(metrics)

            # Ordena por lucro médio e pega os top 10
            top_pairs = sorted(pair_metrics, key=lambda x: x['avg_profit'], reverse=True)[:10]
            
            await websocket.send_text(json.dumps({
                'type': 'top_pairs_update',
                'data': {
                    'pairs': top_pairs,
                    'total_monitored': len(pairs),
                    'timestamp': datetime.now().isoformat()
                }
            }))
            
        except Exception as e:
            logger.error(f"Erro ao enviar atualização dos pares: {e}")
            await websocket.send_text(json.dumps({
                'type': 'error',
                'message': 'Erro ao atualizar dados dos pares'
            }))

    async def _send_system_status(self, websocket: WebSocket):
        """Envia status do sistema"""
        try:
            status = {
                'connected': self.bot_core.is_connected,
                'uptime': str(datetime.now() - self.bot_core.start_time),
                'opportunities_found': len(getattr(self.bot_core, 'opportunities', [])),
                'trades_executed': len(getattr(self.bot_core, 'trades', [])),
                'performance': self.bot_core.get_performance_metrics(),
                'ai_status': self.bot_core.get_ai_status()  # Usa o método get_ai_status atualizado
            }

            await websocket.send_text(json.dumps({
                'type': 'system_status',
                'data': status
            }))
            
            # Envia status a cada 5 segundos
            await asyncio.sleep(5)
            
        except Exception as e:
            self.logger.error(f"Erro ao enviar status do sistema: {e}")

    async def _send_full_update(self, websocket: WebSocket):
        """Envia todas as atualizações disponíveis"""
        await self._send_system_status(websocket)
        await self._send_opportunities_update(websocket)
        await self._send_top_pairs_update(websocket)

    async def _process_websocket_message(self, websocket: WebSocket, message: dict):
        """Processa mensagens recebidas via WebSocket"""
        try:
            message_type = message.get('type')
            
            if message_type == 'request_update':
                await self._send_full_update(websocket)
            elif message_type == 'monitor_pair':
                pair = message.get('pair')
                if pair:
                    await self._monitor_pair(websocket, pair)
            elif message_type == 'get_top_pairs':
                await self._send_top_pairs_update(websocket)
            else:
                logger.warning(f"Tipo de mensagem desconhecido: {message_type}")
                
        except Exception as e:
            logger.error(f"Erro ao processar mensagem WebSocket: {e}")
            await websocket.send_text(json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def stop(self):
        """Para o WebDashboard de forma segura"""
        if self._shutdown_started:
            return
            
        self._shutdown_started = True
        print("Parando WebDashboard...")
        
        try:
            self._cleanup_event.set()
            
            # Para broadcast primeiro
            if self._broadcast_task and not self._broadcast_task.done():
                self._broadcast_task.cancel()
                
            # Fecha todas as conexões WebSocket imediatamente
            await asyncio.gather(*[
                self.manager.disconnect(conn) 
                for conn in self.manager.active_connections
            ], return_exceptions=True)
            
            # Limpa recursos
            await self.manager.cleanup()
            
            print("WebDashboard parado com sucesso")
            
        except Exception as e:
            print(f"Erro ao parar WebDashboard: {e}")
        finally:
            self._shutdown_started = False

    async def cleanup(self):
        """Limpa recursos e fecha conexões"""
        await self.stop()  # Garante que o stop seja chamado

    def _log_metrics(self):
        """Registra métricas de performance periodicamente"""
        try:
            avg_latency = sum(self._broadcast_metrics['latency']) / len(self._broadcast_metrics['latency']) if self._broadcast_metrics['latency'] else 0
            
            metrics = {
                'broadcast': {
                    'avg_latency_ms': round(avg_latency * 1000, 2),
                    'errors_count': self._broadcast_metrics['errors'],
                    'messages_sent': self._broadcast_metrics['messages_sent']
                },
                'websocket': {
                    'active_connections': len(self.manager.active_connections),
                    'total_messages': self.manager.connection_stats['messages_sent'],
                    'total_errors': self.manager.connection_stats['errors']
                },
                'cache': {
                    'health': self._calculate_cache_health(),
                    'size': len(getattr(self.bot_core, 'price_cache', {}))
                }
            }
            
            debug_logger.info(f"Performance metrics: {json.dumps(metrics, indent=2)}")
            
            # Alerta sobre problemas potenciais
            if avg_latency > 1.0:  # Latência média > 1s
                error_logger.warning(f"Alta latência média no broadcast: {avg_latency:.2f}s")
            
            if self._broadcast_metrics['errors'] > 0:
                error_logger.warning(f"Erros acumulados no broadcast: {self._broadcast_metrics['errors']}")
            
            # Reseta contadores
            self._broadcast_metrics['errors'] = 0
            self._broadcast_metrics['messages_sent'] = 0
            
            self.dashboard_logger.log_performance(metrics)
            
        except Exception as e:
            logger.error(f"Erro ao registrar métricas: {e}")
            self.dashboard_logger.log_error('metrics_logging_failed', str(e))

    def _calculate_avg_latency(self) -> float:
        """Calcula latência média do broadcast"""
        if not self._broadcast_metrics['latency']:
            return 0.0
        return sum(self._broadcast_metrics['latency']) / len(self._broadcast_metrics['latency']) * 1000  # em ms

    def setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def get_dashboard(request: Request):
            try:
                html_path = Path(__file__).parent / "static" / "index.html"
                return HTMLResponse(content=html_path.read_text(encoding='utf-8'), status_code=200)
            except Exception as e:
                logger.error(f"Error serving page: {e}")
                return HTMLResponse(content="Error loading page", status_code=500)

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            ws_task = asyncio.create_task(self._handle_websocket(websocket))
            self._tasks.add(ws_task)
            try:
                await ws_task
            except Exception as e:
                self.logger.error(f"Erro no WebSocket: {e}")
            finally:
                self._tasks.remove(ws_task)

        @self.app.get("/api/status")
        async def get_status():
            return {
                'status': 'running',
                'uptime': str(datetime.now() - self.bot_core.start_time),
                'opportunities_found': len(getattr(self.bot_core, 'opportunities', [])),
                'trades_executed': len(getattr(self.bot_core, 'trades', [])),
                'last_update': self.bot_core.last_update.isoformat() if hasattr(self.bot_core, 'last_update') and self.bot_core.last_update else None,
                'ws_connections': len(self.manager.active_connections),
                'ai_status': self.bot_core.get_ai_status()  # Usando o novo método
            }

        @self.app.get("/api/diagnostics")
        async def get_diagnostics():
            """Endpoint de diagnóstico do sistema"""
            current_time = datetime.now()
            return {
                'system_status': {
                    'uptime': str(current_time - self.bot_core.start_time),
                    'last_update': getattr(self.bot_core, 'last_update', current_time).isoformat(),
                    'is_connected': self.bot_core.is_connected,
                    'running': self.bot_core.running,
                    'ws_stats': self.manager.get_stats()
                },
                'websocket_stats': self.manager.get_stats(),
                'memory_usage': {
                    'active_opportunities': len(getattr(self.bot_core, 'opportunities', [])),
                    'active_trades': len(getattr(self.bot_core, 'trades', [])),
                    'websocket_connections': len(self.manager.active_connections)
                },
                'timestamp': current_time.isoformat()
            }

        @self.app.get("/api/performance")
        async def get_performance():
            """Endpoint de monitoramento de performance"""
            bot_metrics = self.bot_core.get_performance_metrics()
            ws_metrics = self.manager.get_performance_metrics()
            
            return {
                'bot_metrics': bot_metrics,
                'websocket_metrics': ws_metrics,
                'system_health': {
                    'is_connected': self.bot_core.is_connected,
                    'active_streams': len(self.bot_core.active_streams),
                    'cache_freshness': len([
                        k for k, v in self.bot_core.price_cache.items()
                        if time.time() - v['timestamp'] < 5
                    ]),
                    'last_update': self.bot_core.last_update.isoformat() if self.bot_core.last_update else None
                },
                'timestamp': datetime.now().isoformat()
            }

        @self.app.get("/api/top-pairs")
        async def get_top_pairs():
            """Retorna os 10 pares mais ativos com suas métricas"""
            try:
                # Obtém todos os pares monitorados
                pairs = list(self.bot_core.symbol_pairs)
                pair_metrics = []

                for pair in pairs:
                    # Obtém métricas do par dos últimos trades/oportunidades
                    opportunities = [opp for opp in getattr(self.bot_core, 'opportunities', [])
                                if pair in [opp.get('a_step_from'), opp.get('b_step_from'), opp.get('c_step_from')]]
                    
                    if opportunities:
                        avg_profit = sum(float(opp.get('profit', 0)) for opp in opportunities) / len(opportunities)
                        volume_24h = sum(float(opp.get('a_volume', 0)) for opp in opportunities)
                        last_update = max(opp.get('timestamp', datetime.now().isoformat()) for opp in opportunities)
                        
                        pair_metrics.append({
                            'pair': pair,
                            'avg_profit': round(avg_profit, 4),
                            'volume_24h': round(volume_24h, 8),
                            'opportunity_count': len(opportunities),
                            'last_update': last_update,
                            'status': 'active' if datetime.now().timestamp() - datetime.fromisoformat(last_update).timestamp() < 300 else 'inactive'
                        })

                # Ordena por volume e retorna top 10
                top_pairs = sorted(pair_metrics, key=lambda x: x['volume_24h'], reverse=True)[:10]
                
                return {
                    'pairs': top_pairs,
                    'timestamp': datetime.now().isoformat(),
                    'total_monitored': len(pairs)
                }
                
            except Exception as e:
                logger.error(f"Erro ao obter top pares: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/analyze-route")
        async def analyze_route(route: str):
            """Endpoint para análise detalhada de uma rota específica"""
            try:
                # Encontra a oportunidade específica
                opportunities = getattr(self.bot_core, 'opportunities', [])
                opportunity = next(
                    (opp for opp in opportunities 
                     if f"{opp.get('a_step_from')}→{opp.get('b_step_from')}→{opp.get('c_step_from')}" == route),
                    None
                )
                
                if not opportunity:
                    raise HTTPException(status_code=404, detail="Rota não encontrada")
                
                # Calcula métricas detalhadas
                volume = float(opportunity.get('a_volume', 0))
                profit = float(opportunity.get('profit', 0))
                
                # Obtém detalhes dos passos da rota
                steps = [
                    {
                        'from': opportunity.get('a_step_from'),
                        'to': opportunity.get('a_step_to'),
                        'volume': volume,
                        'price': float(opportunity.get('a_rate', 0))
                    },
                    {
                        'from': opportunity.get('b_step_from'),
                        'to': opportunity.get('b_step_to'),
                        'volume': volume * float(opportunity.get('a_rate', 1)),
                        'price': float(opportunity.get('b_rate', 0))
                    },
                    {
                        'from': opportunity.get('c_step_from'),
                        'to': opportunity.get('c_step_to'),
                        'volume': volume * float(opportunity.get('b_rate', 1)),
                        'price': float(opportunity.get('c_rate', 0))
                    }
                ]
                
                # Calcula análise de risco
                risk = {
                    'volatility': self._calculate_volatility_risk(opportunity),
                    'liquidity': self._calculate_liquidity_risk(opportunity)
                }
                
                return {
                    'volume': volume,
                    'profit': profit,
                    'steps': steps,
                    'risk': risk,
                    'timestamp': opportunity.get('timestamp', datetime.now().isoformat())
                }
                
            except HTTPException as he:
                raise he
            except Exception as e:
                logger.error(f"Erro ao analisar rota: {e}")
                raise HTTPException(status_code=500, detail=str(e))

# Exporta apenas a classe WebDashboard
__all__ = ['WebDashboard']
