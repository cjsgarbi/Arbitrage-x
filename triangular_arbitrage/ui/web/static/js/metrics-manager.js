class MetricsManager {
    constructor() {
        this.metricsElements = {
            profit24h: document.getElementById('total-profit-24h'),
            successRate: document.getElementById('success-rate'),
            avgSlippage: document.getElementById('average-slippage'),
            activeRoutes: document.getElementById('active-routes'),
            routesBadge: document.getElementById('routes-badge'),
            lastUpdate: document.getElementById('last-update')
        };
        this.lastMetrics = {
            profit24h: 0,
            successRate: 0,
            avgSlippage: 0,
            activeRoutes: 0
        };
        this.setupWebSocket();
    }

    setupWebSocket() {
        this.wsManager = window.wsManager;
        if (!this.wsManager) {
            console.error('WebSocket manager não encontrado');
            return;
        }

        // Inicializa campos com --
        this.updateInitialState();

        // Inscreve para receber atualizações em tempo real
        this.wsManager.subscribe('opportunities', (data) => {
            if (data && data.metrics) {
                const metrics = this._formatMetrics(data.metrics);
                this.updateMetricsDisplay(metrics);
            }
        });

        // Solicita atualização inicial
        this.wsManager.ws.send(JSON.stringify({
            type: 'request_update'
        }));
    }
    
    updateInitialState() {
        // Inicializa todos os campos com --
        Object.keys(this.metricsElements).forEach(key => {
            if (this.metricsElements[key] && key !== 'lastUpdate') {
                this.metricsElements[key].textContent = '--';
            }
        });
    }

    _formatMetrics(metrics) {
        return {
            profit24h: metrics.profit_24h || 0,
            successRate: metrics.success_rate || 0,
            avgSlippage: metrics.avg_slippage || 0,
            activeRoutes: metrics.active_routes || 0,
            monitoredPairs: metrics.monitored_pairs || 0
        };
    }

    calculateMetrics(opportunities) {
        if (!opportunities || opportunities.length === 0) {
            return {
                profit24h: 0,
                successRate: 0,
                avgSlippage: 0,
                activeRoutes: 0
            };
        }

        const profits = opportunities.map(opp => parseFloat(opp.profit) || 0);
        const successfulTrades = profits.filter(p => p > 0).length;

        return {
            profit24h: profits.reduce((a, b) => a + b, 0),
            successRate: (successfulTrades / profits.length) * 100,
            avgSlippage: opportunities.reduce((acc, opp) => acc + (parseFloat(opp.slippage) || 0), 0) / opportunities.length,
            activeRoutes: opportunities.length
        };
    }

    updateAllElements() {
        // Atualiza todos os elementos com os dados mais recentes
        const elements = {
            'profit24h': this.lastMetrics.profit24h,
            'successRate': this.lastMetrics.successRate,
            'avgSlippage': this.lastMetrics.avgSlippage,
            'activeRoutes': this.lastMetrics.activeRoutes
        };

        for (const [key, value] of Object.entries(this.metricsElements)) {
            if (value) {
                this.updateValueWithAnimation(key, this.formatValue(key, elements[key]));
            }
        }
        
        // Atualiza timestamp
        this.updateLastUpdate();
    }

    formatValue(key, value) {
        switch(key) {
            case 'profit24h':
                return new Intl.NumberFormat('pt-BR', {
                    style: 'currency',
                    currency: 'USD'
                }).format(value);
            case 'successRate':
            case 'avgSlippage':
                return `${value.toFixed(2)}%`;
            case 'activeRoutes':
                return value.toString();
            default:
                return value;
        }
    }

    updateSystemMetrics(data) {
        if (!data || !data.performance) return;

        const { performance } = data;
        const metrics = {
            profit24h: performance.profit_24h || 0,
            successRate: performance.success_rate || 0,
            avgSlippage: performance.avg_slippage || 0,
            activeRoutes: performance.active_routes || 0
        };

        this.updateMetricsDisplay(metrics);
    }

    updateOpportunityMetrics(data) {
        if (!Array.isArray(data)) return;

        const metrics = {
            activeRoutes: data.length,
            profit24h: 0,
            successRate: 0,
            avgSlippage: 0
        };

        if (data.length > 0) {
            const profits = data.map(opp => parseFloat(opp.profit));
            metrics.profit24h = profits.reduce((a, b) => a + b, 0);
            metrics.successRate = (profits.filter(p => p > 0).length / profits.length * 100);
            metrics.avgSlippage = data.reduce((a, opp) => a + parseFloat(opp.slippage), 0) / data.length;
        }

        this.updateMetricsDisplay(metrics);
    }

    updateMetricsDisplay(metrics) {
        // Formata e atualiza lucro 24h
        if (this.metricsElements.profit24h) {
            const formattedProfit = new Intl.NumberFormat('pt-BR', {
                style: 'currency',
                currency: 'USD'
            }).format(metrics.profit24h);
            this.updateValueWithAnimation('profit24h', formattedProfit);
        }

        // Atualiza taxa de sucesso
        if (this.metricsElements.successRate) {
            this.updateValueWithAnimation('successRate', `${metrics.successRate.toFixed(1)}%`);
        }

        // Atualiza slippage médio
        if (this.metricsElements.avgSlippage) {
            this.updateValueWithAnimation('avgSlippage', `${(metrics.avgSlippage * 100).toFixed(2)}%`);
        }

        // Atualiza rotas ativas
        if (this.metricsElements.activeRoutes) {
            this.updateValueWithAnimation('activeRoutes', metrics.activeRoutes.toString());
        }
        if (this.metricsElements.routesBadge) {
            this.metricsElements.routesBadge.textContent = `${metrics.activeRoutes} Rotas Ativas`;
        }

        // Atualiza timestamp
        this.updateLastUpdate();
        
        // Armazena últimas métricas
        this.lastMetrics = metrics;
    }

    updateValueWithAnimation(metricKey, newValue) {
        const element = this.metricsElements[metricKey];
        if (!element) return;

        const oldValue = element.textContent;
        element.textContent = newValue;

        if (oldValue !== newValue) {
            element.classList.add('value-changed');
            setTimeout(() => {
                element.classList.remove('value-changed');
            }, 1000);
        }
    }

    updateLastUpdate() {
        if (this.metricsElements.lastUpdate) {
            const now = new Date();
            this.metricsElements.lastUpdate.textContent = `Atualizado: ${now.toLocaleTimeString()}`;
        }
    }
}

// Inicializa e exporta
const metricsManager = new MetricsManager();
window.metricsManager = metricsManager; // Torna acessível globalmente
export default metricsManager;
