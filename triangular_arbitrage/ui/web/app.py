from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from typing import Dict, List
from datetime import datetime, timedelta
import logging
from pathlib import Path
import sys
import time

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()
        self._last_cleanup = datetime.now()
        self._connection_tasks = set()
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'errors': 0,
            'reconnections': 0
        }
        self.performance_metrics = {
            'avg_latency': 0,
            'message_count': 0,
            'last_latencies': [],
            'last_error': None,
            'error_count': 0
        }
        
        # Inicia task de manutenção
        self._maintenance_task = asyncio.create_task(self._connection_maintenance())

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
            self.connection_stats['total_connections'] += 1
            self.connection_stats['active_connections'] = len(self.active_connections)
            logger.info(f"Nova conexão WebSocket. Total ativo: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                self.connection_stats['active_connections'] = len(self.active_connections)
                logger.info(f"Conexão WebSocket fechada. Total ativo: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        async with self._lock:
            start_time = time.time()
            disconnected = []
            
            for connection in self.active_connections:
                try:
                    await connection.send_text(json.dumps(message))
                    self.connection_stats['messages_sent'] += 1
                except Exception as e:
                    logger.error(f"Erro ao enviar mensagem: {e}")
                    self.connection_stats['errors'] += 1
                    disconnected.append(connection)
                    self.performance_metrics['error_count'] += 1
                    self.performance_metrics['last_error'] = str(e)
            
            # Remove conexões com erro
            for conn in disconnected:
                await self.disconnect(conn)
            
            # Atualiza métricas de performance
            latency = (time.time() - start_time) * 1000
            self.update_performance_metrics(latency)

    async def _connection_maintenance(self):
        """Mantém conexões saudáveis e recupera de falhas"""
        while True:
            try:
                # Limpa conexões inativas
                inactive = []
                async with self._lock:
                    for conn in self.active_connections:
                        try:
                            await conn.send_text(json.dumps({"type": "ping"}))
                        except Exception as e:
                            logger.debug(f"Conexão inativa detectada: {str(e)}")
                            inactive.append(conn)
                            self.connection_stats['errors'] += 1
                            self.performance_metrics['error_count'] += 1
                            self.performance_metrics['last_error'] = str(e)
                    
                    # Remove conexões inativas
                    for conn in inactive:
                        await self.disconnect(conn)
                        self.connection_stats['reconnections'] += 1
                    
                    if inactive:
                        logger.info(f"Manutenção: {len(inactive)} conexões removidas")
                
                # Verifica saúde das tasks
                dead_tasks = {task for task in self._connection_tasks if task.done()}
                self._connection_tasks -= dead_tasks
                
                for task in dead_tasks:
                    try:
                        exc = task.exception()
                        if exc:
                            logger.error(f"Task morta com erro: {exc}")
                    except asyncio.CancelledError:
                        pass
                
                await asyncio.sleep(5)  # Verifica a cada 5 segundos
                
            except Exception as e:
                logger.error(f"Erro na manutenção de conexões: {str(e)}")
                import traceback
                logger.error(f"Detalhes: {traceback.format_exc()}")
                await asyncio.sleep(1)

    def get_stats(self):
        """Retorna estatísticas das conexões"""
        return self.connection_stats

    def update_performance_metrics(self, latency):
        """Atualiza métricas de performance"""
        self.performance_metrics['message_count'] += 1
        self.performance_metrics['last_latencies'].append(latency)
        
        # Mantém apenas as últimas 100 medições
        if len(self.performance_metrics['last_latencies']) > 100:
            self.performance_metrics['last_latencies'].pop(0)
        
        # Calcula média móvel
        self.performance_metrics['avg_latency'] = sum(self.performance_metrics['last_latencies']) / len(self.performance_metrics['last_latencies'])

    def get_performance_metrics(self):
        """Retorna métricas de performance"""
        return {
            **self.performance_metrics,
            'current_connections': len(self.active_connections),
            'stats': self.connection_stats
        }

class WebDashboard:
    def __init__(self, bot_core):
        self.app = FastAPI(
            title="Arbitrage Dashboard",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        self.bot_core = bot_core
        self.manager = ConnectionManager()
        self._broadcast_task = None
        self._initialized = False
        self._cleanup_event = asyncio.Event()
        self._tasks = set()
        
        # CORS configuration
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Mount static folder
        static_path = Path(__file__).parent / "static"
        self.app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
        
        # Setup routes
        self.setup_routes()

    async def initialize(self):
        """Inicializa o WebDashboard"""
        if self._initialized:
            return
            
        try:
            # Inicia task de broadcast em background
            self._broadcast_task = asyncio.create_task(self._broadcast_data())
            self._tasks.add(self._broadcast_task)
            self._initialized = True
            logger.info("✅ WebDashboard inicializado")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar WebDashboard: {e}")
            raise

    async def _broadcast_data(self):
        """Broadcast data para clientes WebSocket com otimizações"""
        last_opportunities = None
        last_broadcast = 0
        min_interval = 0.1  # Intervalo mínimo entre broadcasts
        
        while not self._cleanup_event.is_set():
            try:
                current_time = time.time()
                
                # Verifica se tem conexões ativas
                if not self.manager.active_connections:
                    await asyncio.sleep(min_interval)
                    continue

                # Obtém dados atualizados
                opportunities = getattr(self.bot_core, 'opportunities', [])
                performance = self.bot_core.get_performance_metrics()
                
                # Verifica se dados mudaram e se passou tempo mínimo
                if (opportunities != last_opportunities and 
                    current_time - last_broadcast >= min_interval):
                    
                    # Formata oportunidades para o formato esperado pelo frontend
                    formatted_opportunities = []
                    for opp in opportunities:
                        formatted_opp = {
                            'route': f"{opp.get('a_step_from')}→{opp.get('b_step_from')}→{opp.get('c_step_from')}",
                            'profit': float(opp.get('profit', 0)),
                            'volume': float(opp.get('a_volume', 0)),
                            'confidence': 'high' if float(opp.get('score', 0)) > 80 else 'medium',
                            'timestamp': opp.get('timestamp', datetime.now().isoformat())
                        }
                        formatted_opportunities.append(formatted_opp)
                    
                    message = {
                        'type': 'opportunity',
                        'data': formatted_opportunities,
                        'timestamp': datetime.now().isoformat(),
                        'status': {
                            'connected': self.bot_core.is_connected,
                            'hasData': bool(opportunities),
                            'lastUpdate': getattr(self.bot_core, 'last_update', datetime.now()).isoformat(),
                            'performance': {
                                'opportunities_found': len(opportunities),
                                'trades_executed': len(getattr(self.bot_core, 'trades', [])),
                                'volume_24h': sum(float(opp.get('a_volume', 0)) for opp in opportunities),
                                **performance
                            }
                        }
                    }
                    
                    logger.debug(f"Enviando update com {len(opportunities)} oportunidades")
                    await self.manager.broadcast(message)
                    
                    last_opportunities = opportunities
                    last_broadcast = current_time
                
                await asyncio.sleep(min_interval)
                
            except asyncio.CancelledError:
                logger.info("Broadcast task cancelada")
                break
            except Exception as e:
                logger.error(f"Erro no broadcast: {str(e)}")
                import traceback
                logger.error(f"Detalhes: {traceback.format_exc()}")
                await asyncio.sleep(1)

    async def _handle_websocket(self, websocket: WebSocket):
        """Gerencia conexão WebSocket individual"""
        await self.manager.connect(websocket)
        try:
            while not self._cleanup_event.is_set():
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)

                    if message.get('type') == 'ping':
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        }))

                    elif message.get('type') == 'monitor_pair':
                        # Monitora par específico em tempo real
                        await self._monitor_pair(websocket, message.get('pair'))

                    elif message.get('type') == 'subscribe':
                        # Permite que o cliente se inscreva em diferentes tipos de updates
                        topics = message.get('topics', [])
                        for topic in topics:
                            if topic == 'opportunities':
                                await self._send_opportunities_update(websocket)
                            elif topic == 'top_pairs':
                                await self._send_top_pairs_update(websocket)
                            elif topic == 'system_status':
                                await self._send_system_status(websocket)

                    elif message.get('type') == 'request_update':
                        # Envia todas as atualizações disponíveis
                        await self._send_full_update(websocket)

                except WebSocketDisconnect:
                    logger.info("Cliente WebSocket desconectado")
                    break
                except Exception as e:
                    logger.error(f"Erro no WebSocket: {str(e)}")
                    await asyncio.sleep(1)
                    continue

        finally:
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
        """Envia atualização de oportunidades"""
        opportunities = getattr(self.bot_core, 'opportunities', [])
        formatted_opportunities = [{
            'route': f"{opp.get('a_step_from')}→{opp.get('b_step_from')}→{opp.get('c_step_from')}",
            'profit': float(opp.get('profit', 0)),
            'volume': float(opp.get('a_volume', 0)),
            'status': 'excellent' if float(opp.get('profit', 0)) > 1.0 else 'good',
            'timestamp': opp.get('timestamp', datetime.now().isoformat())
        } for opp in opportunities]

        await websocket.send_text(json.dumps({
            'type': 'opportunities_update',
            'data': formatted_opportunities
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
        status = {
            'connected': self.bot_core.is_connected,
            'uptime': str(datetime.now() - self.bot_core.start_time),
            'opportunities_found': len(getattr(self.bot_core, 'opportunities', [])),
            'trades_executed': len(getattr(self.bot_core, 'trades', [])),
            'performance': self.bot_core.get_performance_metrics()
        }

        await websocket.send_text(json.dumps({
            'type': 'system_status',
            'data': status
        }))

    async def _send_full_update(self, websocket: WebSocket):
        """Envia todas as atualizações disponíveis"""
        await self._send_system_status(websocket)
        await self._send_opportunities_update(websocket)
        await self._send_top_pairs_update(websocket)

    async def cleanup(self):
        """Limpa recursos e fecha conexões"""
        try:
            # Sinaliza para tasks pararem
            self._cleanup_event.set()
            
            # Cancela todas as tasks
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            
            # Aguarda tasks terminarem
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
            
            # Fecha conexões WebSocket
            for conn in self.manager.active_connections:
                await self.manager.disconnect(conn)
            
            logger.info("✅ WebDashboard finalizado com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao finalizar WebDashboard: {e}")
            import traceback
            logger.error(f"Detalhes: {traceback.format_exc()}")

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
                'ws_connections': len(self.manager.active_connections)
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
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Erro ao analisar rota: {e}")
                raise HTTPException(status_code=500, detail=str(e))
                
    def _calculate_volatility_risk(self, opportunity: Dict) -> str:
        """Calcula risco de volatilidade baseado no histórico"""
        profit = float(opportunity.get('profit', 0))
        volume = float(opportunity.get('a_volume', 0))
        
        if profit > 1.5 and volume > 0.1:
            return 'low'
        elif profit > 0.8 and volume > 0.05:
            return 'medium'
        else:
            return 'high'
            
    def _calculate_liquidity_risk(self, opportunity: Dict) -> str:
        """Calcula risco de liquidez baseado no volume"""
        volume = float(opportunity.get('a_volume', 0))
        
        if volume > 0.5:  # Volume maior que 0.5 BTC
            return 'low'
        elif volume > 0.1:  # Volume maior que 0.1 BTC
            return 'medium'
        else:
            return 'high'

# Exporta apenas a classe WebDashboard
__all__ = ['WebDashboard']