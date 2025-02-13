import themeManager from './themes.js';
import opportunitiesManager from './opportunities.js';
import pairsMonitor from './pairs-monitor.js';
import wsManager from './websocket-manager.js';
import arbitrageTable from './arbitrage-table.js';

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

        // Inicializa notificações
        notificationManager.initialize();
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
                    this.updateSystemMetrics(data.status.performance);
                    break;
                case 'system_status':
                    this.updateSystemStatus(data.data);
                    break;
                case 'pair_monitor_update':
                    realtimeMonitor.handleWebSocketMessage(data);
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
        const uptimeElement = document.getElementById('uptime');
        if (uptimeElement) {
            uptimeElement.textContent = status.uptime;
        }

        const tradesElement = document.getElementById('trades-executed');
        if (tradesElement) {
            tradesElement.textContent = status.trades_executed;
        }

        const oppsFoundElement = document.getElementById('opportunities-found');
        if (oppsFoundElement) {
            oppsFoundElement.textContent = status.opportunities_found;
        }
    }

    updateSystemMetrics(metrics) {
        document.getElementById('total-profit-24h').textContent = `$${metrics.total_profit_24h.toLocaleString('pt-BR')}`;
        document.getElementById('success-rate').textContent = `${metrics.success_rate}%`;
        document.getElementById('average-slippage').textContent = `${metrics.avg_slippage}%`;
        document.getElementById('active-routes').textContent = metrics.active_routes;
    }

    async tryReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            notificationManager.error('Falha na conexão após várias tentativas');
            return;
        }

        this.reconnectAttempts++;
        await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, this.reconnectAttempts)));
        await this.setupWebSocket();
    }

    setupThemeObservers() {
        // Observa mudanças no tema do sistema
        const darkModeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        darkModeMediaQuery.addListener((e) => {
            if (e.matches) {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        });
    }

    setupErrorHandlers() {
        window.onerror = (msg, url, line, col, error) => {
            notificationManager.error(`Erro: ${msg}`);
            console.error('Erro detectado:', { msg, url, line, col, error });
            return false;
        };

        window.onunhandledrejection = (event) => {
            notificationManager.error(`Erro assíncrono: ${event.reason}`);
            console.error('Rejeição não tratada:', event.reason);
        };
    }
}

// Inicializa o sistema
const initializer = new SystemInitializer();
document.addEventListener('DOMContentLoaded', () => {
    initializer.initialize();

    // Limpa dados antigos
    const tables = ['arbitrage-pairs-table', 'recent-operations'];
    tables.forEach(id => {
        const table = document.getElementById(id);
        if (table) table.innerHTML = '';
    });

    // Reseta métricas
    const metrics = {
        'total-profit-24h': '$0.00',
        'success-rate': '0.0%',
        'average-slippage': '0.00%',
        'active-routes': '0',
        'routes-badge': '0 Rotas Ativas'
    };

    Object.entries(metrics).forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    });

    // Inicia conexão WebSocket
    wsManager.subscribe('opportunity', (data) => {
        opportunitiesManager.updateOpportunities(data);
        arbitrageTable.updateOpportunities(data.data);
    });

    wsManager.connect();
});

export default initializer;
