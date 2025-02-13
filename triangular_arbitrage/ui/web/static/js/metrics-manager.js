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

        // Inscreve para receber atualizações do sistema
        this.wsManager.subscribe('system_status', (data) => this.updateSystemMetrics(data));
        this.wsManager.subscribe('opportunities', (data) => this.updateOpportunityMetrics(data));
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