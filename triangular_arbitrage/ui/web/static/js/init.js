import themeManager from './themes.js';
import opportunitiesManager from './opportunities.js';
import pairsMonitor from './pairs-monitor.js';

class SystemInitializer {
    constructor() {
        this.wsUrl = `ws://${window.location.host}/ws`;
        this.wsManager = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }

    async initialize() {
        // Inicializa tema
        themeManager.initialize();
        
        // Inicializa monitor de pares
        pairsMonitor.initialize();
        
        // Configura WebSocket
        await this.setupWebSocket();
        
        // Configura observadores de tema
        this.setupThemeObservers();
        
        // Configura handlers de erro
        this.setupErrorHandlers();
    }

    async setupWebSocket() {
        try {
            const ws = new WebSocket(this.wsUrl);
            
            ws.onopen = () => {
                console.log('WebSocket conectado');
                this.updateConnectionStatus(true);
                this.reconnectAttempts = 0;
                
                // Solicita dados iniciais
                ws.send(JSON.stringify({
                    type: 'subscribe',
                    topics: ['opportunities', 'top_pairs', 'system_status']
                }));
            };
            
            ws.onmessage = (event) => {
                this.handleMessage(JSON.parse(event.data));
            };
            
            ws.onclose = () => {
                console.log('WebSocket desconectado');
                this.updateConnectionStatus(false);
                this.tryReconnect();
            };
            
            this.wsManager = ws;
            
        } catch (error) {
            console.error('Erro ao conectar WebSocket:', error);
            this.updateConnectionStatus(false);
        }
    }

    handleMessage(data) {
        try {
            switch (data.type) {
                case 'opportunity':
                    opportunitiesManager.updateOpportunities(data.data);
                    break;
                case 'system_status':
                    this.updateSystemStatus(data.data);
                    break;
                case 'top_pairs_update':
                    pairsMonitor.updatePairsData(data.data.pairs);
                    break;
            }
        } catch (e) {
            console.error('Erro ao processar mensagem:', e);
        }
    }

    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        const statusContainer = document.getElementById('status-container');
        
        if (statusElement) {
            statusElement.textContent = connected ? 'Conectado' : 'Desconectado';
            statusElement.className = connected ? 
                'px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800' :
                'px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800';
        }
        
        if (statusContainer) {
            statusContainer.className = connected ? 'text-green-500' : 'text-red-500';
        }
    }

    updateSystemStatus(status) {
        // Atualiza elementos de status do sistema
        const elements = {
            'latency': `${status.performance?.avg_latency?.toFixed(2) || 0} ms`,
            'volume-24h': `${status.performance?.volume_24h?.toFixed(8) || 0} BTC`,
            'pairs-count': status.active_streams || 0,
            'avg-profit': `${status.performance?.avg_profit?.toFixed(2) || 0}%`
        };
        
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });
    }

    async tryReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Número máximo de tentativas de reconexão atingido');
            return;
        }

        this.reconnectAttempts++;
        console.log(`Tentativa de reconexão ${this.reconnectAttempts}...`);
        
        await new Promise(resolve => setTimeout(resolve, 1000 * this.reconnectAttempts));
        await this.setupWebSocket();
    }

    setupThemeObservers() {
        themeManager.addObserver((theme) => {
            console.log(`Tema alterado para: ${theme}`);
        });
    }

    setupErrorHandlers() {
        window.onerror = (msg, url, line, col, error) => {
            console.error('Erro global:', { msg, url, line, col, error });
            return false;
        };

        window.onunhandledrejection = (event) => {
            console.error('Promise rejeitada não tratada:', event.reason);
        };
    }
}

// Inicializa sistema
const systemInitializer = new SystemInitializer();
systemInitializer.initialize().catch(console.error);

export default systemInitializer;
