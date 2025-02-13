class WebSocketManager {
    constructor() {
        this.ws = null;
        this.subscribers = new Map();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.isConnecting = false;
        this.binanceSubscriptions = new Set(['opportunities', 'system_status', 'top_pairs']);
        this.initialize();
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
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket conectado');
                this.isConnecting = false;
                this.reconnectAttempts = 0;
                this._updateConnectionStatus(true);
                
                // Solicita dados iniciais
                this.ws.send(JSON.stringify({
                    type: 'subscribe',
                    topics: Array.from(this.binanceSubscriptions)
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
            
            this.ws.onclose = () => {
                console.log('WebSocket desconectado');
                this.isConnecting = false;
                this._updateConnectionStatus(false);
                this._attemptReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('Erro no WebSocket:', error);
                this.isConnecting = false;
                this._updateConnectionStatus(false);
            };
            
        } catch (error) {
            console.error('Erro ao conectar WebSocket:', error);
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
        if (this.ws?.readyState === WebSocket.OPEN) {
            // Envia ping para manter conexão ativa
            this.ws.send(JSON.stringify({ type: 'ping' }));
        } else if (!this.isConnecting) {
            this._attemptReconnect();
        }
    }

    _handleMessage(data) {
        const type = data.type;
        
        // Trata pong separadamente
        if (type === 'pong') {
            this._updateConnectionStatus(true);
            return;
        }

        const subscribers = this.subscribers.get(type);
        if (subscribers) {
            subscribers.forEach(callback => {
                try {
                    callback(data.data);
                } catch (error) {
                    console.error(`Erro no callback para ${type}:`, error);
                }
            });
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
}

// Cria e exporta instância única
const wsManager = new WebSocketManager();
window.wsManager = wsManager; // Torna acessível globalmente
export default wsManager;