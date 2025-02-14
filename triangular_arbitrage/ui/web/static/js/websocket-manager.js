class WebSocketManager {
    constructor() {
        this.ws = null;
        this.subscribers = new Map();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.isConnecting = false;
        this.binanceSubscriptions = new Set(['opportunities', 'system_status', 'top_pairs']);
        this.messageBuffer = [];
        this.bufferInterval = 50;
        this.bufferProcessor = null;
        this.isShuttingDown = false;
        this.lastMessageTime = Date.now();
        this.connectionStatus = {
            isConnected: false,
            isBinanceConnected: false,
            lastActivity: null
        };
        
        this.initialize();
        this._setupBufferProcessor();
        this._setupConnectionMonitor();
        this._setupShutdown();
        this._startActivityIndicator();
    }

    _startActivityIndicator() {
        const statusEl = document.getElementById('exchange-status');
        if (!statusEl) return;

        setInterval(() => {
            if (this.connectionStatus.isBinanceConnected) {
                const timeSinceActivity = Date.now() - (this.connectionStatus.lastActivity || 0);
                const isActive = timeSinceActivity < 5000; // Considera ativo se recebeu dados nos últimos 5s

                statusEl.innerHTML = `
                    <div class="flex items-center gap-2">
                        <span class="flex h-3 w-3">
                            <span class="animate-ping absolute inline-flex h-3 w-3 rounded-full ${isActive ? 'bg-green-400' : 'bg-yellow-400'} opacity-75"></span>
                            <span class="relative inline-flex rounded-full h-3 w-3 ${isActive ? 'bg-green-500' : 'bg-yellow-500'}"></span>
                        </span>
                        <span class="${isActive ? 'text-green-500' : 'text-yellow-500'} font-medium">
                            ${isActive ? 'Monitorando Binance' : 'Conectado à Binance'}
                        </span>
                    </div>
                `;
            }
        }, 1000);
    }

    _setupConnectionMonitor() {
        // Monitora estado da conexão a cada 3 segundos
        setInterval(() => {
            if (this.isShuttingDown) return;

            const now = Date.now();
            const timeSinceLastMessage = now - this.lastMessageTime;
            const timeSinceLastActivity = now - (this.connectionStatus.lastActivity || 0);

            // Se não receber mensagens por 10 segundos, tenta reconectar
            if (timeSinceLastMessage > 10000) {
                console.log('Sem mensagens por 10s, verificando conexão...');
                this.checkConnection();
            }

            // Se não houver atividade por 15 segundos, força reconexão
            if (timeSinceLastActivity > 15000) {
                console.log('Sem atividade por 15s, forçando reconexão...');
                this._updateConnectionStatus(false);
                this._attemptReconnect();
            }

        }, 3000);
    }

    _setupShutdown() {
        // Adiciona handler para SIGINT (Ctrl+C)
        window.addEventListener('beforeunload', (event) => {
            this.shutdown();
        });

        // Adiciona handler para fechamento da página
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.shutdown();
            }
        });
    }

    shutdown() {
        try {
            this.isShuttingDown = true;
            
            // Para o processador de buffer
            if (this.bufferProcessor) {
                clearInterval(this.bufferProcessor);
                this.bufferProcessor = null;
            }

            // Limpa o buffer
            this.messageBuffer = [];

            // Fecha conexão WebSocket
            if (this.ws) {
                this.ws.close();
                this.ws = null;
            }

            // Limpa subscribers
            this.subscribers.clear();
            
            // Limpa binanceSubscriptions
            this.binanceSubscriptions.clear();

            console.log('WebSocket finalizado com sucesso');
            
            // Atualiza status visual
            this._updateConnectionStatus(false);
            
        } catch (error) {
            console.error('Erro ao finalizar WebSocket:', error);
        }
    }

    _setupBufferProcessor() {
        // Processa mensagens em lote para melhor performance
        this.bufferProcessor = setInterval(() => {
            if (this.isShuttingDown) return;
            
            if (this.messageBuffer.length > 0) {
                const messages = this.messageBuffer.splice(0);
                messages.forEach(msg => this._processMessage(msg));
            }
        }, this.bufferInterval);
    }

    initialize() {
        this.connect();
        // Monitora status da conexão
        setInterval(() => this.checkConnection(), 5000);
    }

    connect() {
        if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) return;
        
        this.isConnecting = true;
        const wsUrl = `ws://${window.location.host}/ws`;
        
        try {
            console.log('Tentando conectar ao WebSocket:', wsUrl);
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket conectado com sucesso');
                this.isConnecting = false;
                this.reconnectAttempts = 0;
                this._updateConnectionStatus(true);
                this.connectionStatus.lastActivity = Date.now();
                
                // Solicita atualização inicial de dados
                this.ws.send(JSON.stringify({ 
                    type: 'request_update',
                    timestamp: Date.now()
                }));
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this._handleMessage(data);
                } catch (error) {
                    console.error('Erro ao processar mensagem:', error);
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('Conexão WebSocket fechada:', event.code, event.reason);
                this.isConnecting = false;
                this._updateConnectionStatus(false);
                
                // Só tenta reconectar se não foi um fechamento limpo
                if (event.code !== 1000) {
                    this.handleDisconnect();
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('Erro na conexão WebSocket:', error);
                this.isConnecting = false;
                this._updateConnectionStatus(false);
            };
            
        } catch (error) {
            console.error('Erro ao criar conexão WebSocket:', error);
            this.isConnecting = false;
            this._updateConnectionStatus(false);
        }
    }

    subscribe(topic, callback) {
        if (!this.subscribers.has(topic)) {
            this.subscribers.set(topic, new Set());
            // Adiciona à lista de inscrições da Binance se não for um tópico interno
            if (!topic.startsWith('_')) {
                this.binanceSubscriptions.add(topic);
                // Se já estiver conectado, envia inscrição
                if (this.ws?.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        type: 'subscribe',
                        topics: [topic]
                    }));
                }
            }
        }
        this.subscribers.get(topic).add(callback);
    }

    unsubscribe(topic, callback) {
        if (this.subscribers.has(topic)) {
            this.subscribers.get(topic).delete(callback);
            // Se não houver mais callbacks, remove a inscrição
            if (this.subscribers.get(topic).size === 0) {
                this.subscribers.delete(topic);
                this.binanceSubscriptions.delete(topic);
                if (this.ws?.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        type: 'unsubscribe',
                        topics: [topic]
                    }));
                }
            }
        }
    }

    checkConnection() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            if (!this.isConnecting) {
                this._attemptReconnect();
            }
            return;
        }

        // Envia ping para verificar conexão
        try {
            this.ws.send(JSON.stringify({ 
                type: 'ping',
                timestamp: Date.now()
            }));
        } catch (error) {
            console.error('Erro ao enviar ping:', error);
            this._attemptReconnect();
        }
    }

    _handleMessage(data) {
        // Atualiza timestamp da última mensagem
        this.lastMessageTime = Date.now();
        
        // Atualiza status de conexão
        this.connectionStatus.lastActivity = Date.now();
        
        if (data.type === 'ping') {
            // Responde imediatamente ao ping
            if (this.ws?.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ 
                    type: 'pong',
                    timestamp: Date.now()
                }));
            }
            return;
        }

        // Adiciona ao buffer para processamento em lote
        if (!this.isShuttingDown) {
            this.messageBuffer.push(data);
            this._updateConnectionStatus(true);
        }
    }

    _processMessage(data) {
        const type = data.type;
        
        // Trata pong separadamente
        if (type === 'pong') {
            this._updateConnectionStatus(true);
            return;
        }

        // Trata dados de oportunidades
        if (type === 'opportunities' && data.data) {
            this._updateOpportunities(data.data);
            
            // Atualiza métricas se disponíveis
            if (data.metrics) {
                this._updateMetrics(data.metrics);
            }
        }

        // Distribui para subscribers
        const subscribers = this.subscribers.get(type);
        if (subscribers) {
            subscribers.forEach(callback => callback(data.data));
        }
    }

    _updateOpportunities(opportunities) {
        if (!Array.isArray(opportunities)) return;
        
        const tableBody = document.getElementById('arbitrage-pairs-table');
        if (!tableBody) return;

        // Limpa tabela
        tableBody.innerHTML = '';

        // Adiciona novas oportunidades (incluindo negativas)
        opportunities.forEach(opp => {
            const row = document.createElement('tr');
            const profitColor = parseFloat(opp.profit) > 0 ? 'text-green-500' : 'text-red-500';
            const status = parseFloat(opp.profit) > 0 ? 'active' : 'inactive';

            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="flex items-center">
                        <div class="text-sm font-medium text-gray-900">
                            ${opp.a_step_from} → ${opp.b_step_from} → ${opp.c_step_from}
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm ${profitColor}">${parseFloat(opp.profit).toFixed(3)}%</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${parseFloat(opp.a_volume).toFixed(8)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        status === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }">
                        ${status}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${opp.latency}ms
                </td>
            `;
            
            tableBody.appendChild(row);
        });

        // Atualiza contador de oportunidades
        const countEl = document.getElementById('opportunities-count');
        if (countEl) {
            const activeCount = opportunities.filter(o => parseFloat(o.profit) > 0).length;
            countEl.textContent = `${activeCount}/${opportunities.length}`;
        }
    }

    _updateMetrics(metrics) {
        // Atualiza métricas
        const elements = {
            'total-profit-24h': metrics.profit_24h ? `$${metrics.profit_24h.toFixed(2)}` : '--',
            'success-rate': metrics.success_rate ? `${metrics.success_rate.toFixed(1)}%` : '--',
            'average-slippage': metrics.avg_slippage ? `${(metrics.avg_slippage * 100).toFixed(2)}%` : '--',
            'active-routes': metrics.active_routes || '--'
        };

        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });
    }

    _updateSystemStatus(status) {
        const statusEl = document.getElementById('exchange-status');
        if (!statusEl) return;

        statusEl.innerHTML = status.is_connected ? `
            <svg class="h-4 w-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="text-green-500 font-medium">Conectado</span>
        ` : `
            <svg class="h-4 w-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span class="text-red-500 font-medium">Desconectado</span>
        `;

        // Atualiza timestamp
        const timeEl = document.getElementById('last-update');
        if (timeEl) {
            timeEl.textContent = `Atualizado: ${new Date().toLocaleTimeString()}`;
        }
    }

    _updateConnectionStatus(isConnected) {
        const statusEl = document.getElementById('exchange-status');
        if (!statusEl) return;

        if (isConnected) {
            statusEl.innerHTML = `
                <svg class="h-4 w-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="text-green-500 font-medium">Conectado</span>
            `;
        } else {
            statusEl.innerHTML = `
                <svg class="h-4 w-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span class="text-red-500 font-medium">Desconectado</span>
            `;
        }
    }

    _attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Máximo de tentativas de reconexão atingido');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`Tentando reconectar em ${delay}ms (tentativa ${this.reconnectAttempts})`);
        
        setTimeout(() => {
            if (this.ws?.readyState === WebSocket.CLOSED) {
                this.connect();
            }
        }, delay);
    }

    handleDisconnect() {
        // Limpa heartbeat existente
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
        
        // Tenta reconectar se não ultrapassou o limite de tentativas
        if (!this.isReconnecting && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.isReconnecting = true;
            const delay = this.calculateReconnectDelay();
            console.log(`Tentando reconectar em ${delay}ms...`);
            
            setTimeout(() => {
                this.reconnectAttempts++;
                this.connect();
            }, delay);
        } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Máximo de tentativas de reconexão atingido');
            this.shutdown();
        }
    }
}

// Cria e exporta instância única
const wsManager = new WebSocketManager();
window.wsManager = wsManager; // Torna acessível globalmente
export default wsManager;
