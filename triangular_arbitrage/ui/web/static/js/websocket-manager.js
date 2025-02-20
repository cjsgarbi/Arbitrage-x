class WebSocketManager {
    constructor() {
        this.ws = null;
        this.subscribers = new Map();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 8;   // Ajustado para 8 tentativas
        this.reconnectDelay = 2500;      // Aumentado para 2500ms
        this.maxReconnectDelay = 25000;  // Ajustado para 25s entre tentativas
        this.isConnecting = false;
        this.binanceSubscriptions = new Set(['opportunities', 'system_status', 'top_pairs']);
        this.messageBuffer = [];
        this.bufferInterval = 150;       // Ajustado para 150ms para processamento mais suave
        this.maxBufferSize = 2000;       // Limite máximo do buffer
        this.bufferProcessor = null;
        this.isShuttingDown = false;
        this.lastMessageTime = Date.now();
        this.connectionStatus = {
            isConnected: false,
            isBinanceConnected: false,
            lastActivity: null,
            state: 'DISCONNECTED'  // Novo: controle de estado
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
                const isActive = timeSinceActivity < 10000; // Aumentado de 5s para 10s

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
        }, 2000);  // Aumentado de 1s para 2s
    }

    _setupConnectionMonitor() {
        setInterval(() => {
            if (this.isShuttingDown) return;

            const now = Date.now();
            const timeSinceLastMessage = now - this.lastMessageTime;

            // Ajuste mais conservador do timeout de inatividade
            if (timeSinceLastMessage > 15000 && !this.isConnecting) {  // Reduzido para 15s para verificação mais rápida
                this.checkConnection();
            }

            const timeSinceLastActivity = now - (this.connectionStatus.lastActivity || 0);
            if (timeSinceLastActivity > 25000) {  // Reduzido para 25s para ação mais rápida
                console.log('Sem atividade por 25s, verificando conexão...');
                this._updateConnectionStatus(false);
                this.checkConnection();
            }
        }, 7500);  // Ajustado para 7.5s para equilíbrio entre resposta e overhead
    }

    _setupShutdown() {
        window.addEventListener('beforeunload', (event) => {
            this.shutdown();
        });

        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.shutdown();
            } else {
                // Reconecta ao voltar para a página
                this.checkConnection();
            }
        });
    }

    shutdown() {
        try {
            this.isShuttingDown = true;
            
            if (this.bufferProcessor) {
                clearInterval(this.bufferProcessor);
                this.bufferProcessor = null;
            }

            this.messageBuffer = [];

            if (this.ws) {
                this.ws.close();
                this.ws = null;
            }

            this.subscribers.clear();
            this.binanceSubscriptions.clear();
            
            console.log('WebSocket finalizado com sucesso');
            this._updateConnectionStatus(false);
            
        } catch (error) {
            console.error('Erro ao finalizar WebSocket:', error);
        }
    }

    _setupBufferProcessor() {
        this.bufferProcessor = setInterval(() => {
            if (this.isShuttingDown) return;
            
            if (this.messageBuffer.length > 0) {
                // Processa em lotes de até 100 mensagens
                const batchSize = Math.min(100, this.messageBuffer.length);
                const messages = this.messageBuffer.splice(0, batchSize);
                
                // Verifica overflow do buffer
                if (this.messageBuffer.length > this.maxBufferSize) {
                    console.warn(`Buffer overflow, removendo ${this.messageBuffer.length - this.maxBufferSize} mensagens`);
                    this.messageBuffer = this.messageBuffer.slice(-this.maxBufferSize);
                }
                
                messages.forEach(msg => this._processMessage(msg));
            }
        }, this.bufferInterval);
    }

    initialize() {
        this.connect();
        setInterval(() => this.checkConnection(), 7500);  // Ajustado para mesmo intervalo do monitor
    }

    connect() {
        if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) {
            console.log('WebSocket: Já conectado ou tentando conectar');
            return;
        }
        
        this.isConnecting = true;
        this.connectionStatus.state = 'CONNECTING';
        
        // Usa protocolo correto baseado no protocolo da página
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            console.log('WebSocket: Iniciando conexão com', wsUrl);
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket: Conexão estabelecida');
                this.isConnecting = false;
                this.reconnectAttempts = 0;
                this._updateConnectionStatus(true);
                this.connectionStatus.lastActivity = Date.now();
                this.connectionStatus.state = 'CONNECTED';
                
                // Reinscreve em todos os tópicos
                console.log('WebSocket: Reinscrevendo em tópicos...');
                this._resubscribeAll();
            };
            
            this.ws.onmessage = (event) => {
                try {
                    console.log('WebSocket mensagem recebida:', event.data);
                    const data = JSON.parse(event.data);
                    console.log('Dados parseados:', data);
                    this._handleMessage(data);
                } catch (error) {
                    console.error('Erro ao processar mensagem:', error);
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('Conexão WebSocket fechada:', event.code, event.reason);
                this.isConnecting = false;
                this._updateConnectionStatus(false);
                this.connectionStatus.state = 'DISCONNECTED';
                
                if (event.code !== 1000) {
                    this.handleDisconnect();
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('Erro na conexão WebSocket:', error);
                this.isConnecting = false;
                this._updateConnectionStatus(false);
                this.connectionStatus.state = 'DISCONNECTED';
            };
            
        } catch (error) {
            console.error('Erro ao criar conexão WebSocket:', error);
            this.isConnecting = false;
            this._updateConnectionStatus(false);
            this.connectionStatus.state = 'DISCONNECTED';
        }
    }

    _resubscribeAll() {
        if (this.ws?.readyState === WebSocket.OPEN) {
            const topics = Array.from(this.binanceSubscriptions);
            if (topics.length > 0) {
                this.ws.send(JSON.stringify({
                    type: 'subscribe',
                    topics: topics
                }));
            }
        }
    }

    calculateReconnectDelay() {
        // Exponential backoff com jitter mais suave
        const jitter = Math.random() * 500;  // Reduzido para 500ms de jitter
        const baseDelay = this.reconnectDelay * Math.pow(1.3, this.reconnectAttempts);  // Fator reduzido para 1.3
        return Math.min(baseDelay + jitter, this.maxReconnectDelay);
    }

    subscribe(topic, callback) {
        if (!this.subscribers.has(topic)) {
            this.subscribers.set(topic, new Set());
            if (!topic.startsWith('_')) {
                this.binanceSubscriptions.add(topic);
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
        console.log('WebSocket: Mensagem recebida', { type: data.type });
        this.lastMessageTime = Date.now();
        this.connectionStatus.lastActivity = Date.now();
        
        if (data.type === 'ping') {
            if (this.ws?.readyState === WebSocket.OPEN) {
                console.log('WebSocket: Respondendo ping');
                this.ws.send(JSON.stringify({
                    type: 'pong',
                    timestamp: Date.now()
                }));
            }
            return;
        }

        if (!this.isShuttingDown) {
            console.log('WebSocket: Adicionando mensagem ao buffer', {
                type: data.type,
                dataLength: data.data?.length || 0
            });
            this.messageBuffer.push(data);
            this._updateConnectionStatus(true);
        }
    }

    _processMessage(data) {
        const type = data.type;
        
        if (type === 'pong') {
            this._updateConnectionStatus(true);
            return;
        }

        if (type === 'opportunities' && data.data) {
            console.log('Oportunidades recebidas:', data.data);
            console.log('Total de oportunidades:', data.data.length);
            
            // Amostra da primeira oportunidade para debug
            if (data.data.length > 0) {
                console.log('Exemplo de oportunidade:', data.data[0]);
            }
            
            this._updateOpportunities(data.data);
            
            if (data.metadata) {
                console.log('Metadata recebido:', data.metadata);
                this._updateMetrics(data.metadata);
            }
        }

        if (type === 'system_status' && data.data) {
            console.log('Status do sistema recebido:', data.data);
            // Garantindo que o status da IA seja um booleano
            const aiStatus = data.data.ai_status === true;
            console.log('Status da IA:', aiStatus);
            this._updateAIStatus(aiStatus);
            this.connectionStatus.isBinanceConnected = data.data.connected || false;
        }

        const subscribers = this.subscribers.get(type);
        if (subscribers) {
            subscribers.forEach(callback => {
                try {
                    callback(data.data);
                } catch (error) {
                    console.error('Erro ao executar callback:', error);
                }
            });
        }
    }

    _processMessage(data) {
        const type = data.type;
        console.log('Processando mensagem do tipo:', type);

        if (type === 'pong') {
            this._updateConnectionStatus(true);
            return;
        }

        try {
            // Log detalhado das oportunidades recebidas
            if (type === 'opportunities' && data.data) {
                console.log('Oportunidades recebidas:', data.data.length);
                if (data.data.length > 0) {
                    console.log('Primeira oportunidade:', JSON.stringify(data.data[0], null, 2));
                }
            }

            // Encaminha dados para subscribers
            const subscribers = this.subscribers.get(type);
            if (subscribers) {
                subscribers.forEach(callback => {
                    try {
                        callback(data.data);
                    } catch (error) {
                        console.error('Erro ao executar callback:', error);
                    }
                });
            }
        } catch (error) {
            console.error('Erro ao processar mensagem:', error);
        }

            // Processa e encaminha dados para arbitrage-table.js
            const subscribers = this.subscribers.get(type);
            if (subscribers) {
                subscribers.forEach(callback => {
                    try {
                        callback(data.data);
                    } catch (error) {
                        console.error('Erro ao processar dados em arbitrage-table:', error);
                    }
                });
            }
    }

    _updateMetrics(metrics) {
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

    _updateAIStatus(isConnected) {
        const aiStatusEl = document.getElementById('ai-status');
        if (!aiStatusEl) return;

        if (isConnected === undefined || isConnected === null) {
            // Estado de verificação
            const statusHtml = `
            <div class="flex items-center gap-2">
                <span class="flex h-3 w-3">
                    <span class="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-yellow-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-3 w-3 bg-yellow-500"></span>
                </span>
                <span class="text-yellow-500 font-medium">IA: Verificando conexão...</span>
            </div>
            `;
            aiStatusEl.innerHTML = statusHtml;
            return;
        }

        const statusHtml = isConnected ? `
            <div class="flex items-center gap-2">
                <span class="flex h-3 w-3">
                    <span class="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                </span>
                <span class="text-green-500 font-medium">IA: Conectada</span>
            </div>
        ` : `
            <div class="flex items-center gap-2">
                <span class="flex h-3 w-3">
                    <span class="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                </span>
                <span class="text-red-500 font-medium">IA: Desconectada</span>
            </div>
        `;

        aiStatusEl.innerHTML = statusHtml;
    }

    _updateConnectionStatus(isConnected) {
        const statusEl = document.getElementById('exchange-status');
        if (!statusEl) return;

        this.connectionStatus.isConnected = isConnected;
        
        const statusHtml = isConnected ? `
            <div class="flex items-center gap-2">
                <span class="flex h-3 w-3">
                    <span class="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                </span>
                <span class="text-green-500 font-medium">Conectado</span>
            </div>
        ` : `
            <div class="flex items-center gap-2">
                <span class="flex h-3 w-3">
                    <span class="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                </span>
                <span class="text-red-500 font-medium">Desconectado</span>
            </div>
        `;

        statusEl.innerHTML = statusHtml;
    }

    _attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Máximo de tentativas de reconexão atingido');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.calculateReconnectDelay();
        
        console.log(`Tentando reconectar em ${delay}ms (tentativa ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            if (!this.ws || this.ws.readyState === WebSocket.CLOSED) {
                this.connect();
            }
        }, delay);
    }

    handleDisconnect() {
        if (this._isShuttingDown) return;

        if (!this.isConnecting && this.reconnectAttempts < this.maxReconnectAttempts) {
            const delay = this.calculateReconnectDelay();
            console.log(`Reconectando em ${delay}ms... (tentativa ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);
            
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

const wsManager = new WebSocketManager();
window.wsManager = wsManager;
export default wsManager;
