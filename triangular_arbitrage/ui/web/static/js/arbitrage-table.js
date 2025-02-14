import wsManager from './websocket-manager.js';

class ArbitrageTableManager {
    constructor() {
        this.table = document.getElementById('arbitrage-pairs-table');
        this.opportunities = new Map();
        this.lastUpdate = null;
        this.setupWebSocket();
    }

    setupWebSocket() {
        this.wsManager = window.wsManager;
        if (!this.wsManager) {
            console.error('WebSocket manager não encontrado');
            return;
        }

        // Inscreve para receber atualizações de oportunidades em tempo real
        this.wsManager.subscribe('opportunities', (data) => {
            this.updateOpportunities(data);
            // Atualiza todos os elementos relacionados
            this.updateTableData(data);
            this.updateMetrics(data);
            this.updateRouteIndicators(data);
        });

        this.wsManager.subscribe('system_status', (data) => this.updateMetrics(data));
    }

    updateTableData(data) {
        // Atualiza todos os elementos da tabela
        if (Array.isArray(data)) {
            data.forEach(opp => {
                // Atualiza profit esperado e real
                const profitExpected = parseFloat(opp.profit);
                const profitReal = profitExpected * (1 - parseFloat(opp.slippage));
                
                // Atualiza slippage e tempo de execução
                const slippage = parseFloat(opp.slippage) * 100;
                const execTime = parseFloat(opp.executionTime);
                
                // Atualiza liquidez e risco
                const liquidity = opp.liquidity;
                const risk = opp.risk;
                
                // Atualiza spread e volatilidade
                const spread = parseFloat(opp.spread);
                const volatility = opp.volatility;
                
                // Atualiza confiança
                const confidence = parseInt(opp.confidence);
                
                // Atualiza rota
                this.updateRouteDisplay(opp.route, profitReal > 0.5);
            });
        }
    }

    updateRouteIndicators(data) {
        if (!Array.isArray(data)) return;

        // Atualiza badges de rotas ativas
        const activeRoutes = data.filter(opp => parseFloat(opp.profit) > 0).length;
        document.getElementById('routes-badge').textContent = `${activeRoutes} Rotas Ativas`;
    }

    updateOpportunities(data) {
        if (!Array.isArray(data)) return;
        
        // Limpa estado atual
        this.opportunities.clear();
        this.table.innerHTML = '';

        // Inicializa com -- se não houver dados
        if (data.length === 0) {
            const emptyRow = document.createElement('tr');
            emptyRow.innerHTML = `
                <td colspan="10" class="p-6 text-center">
                    <div class="flex flex-col items-center space-y-3">
                        <div class="animate-pulse text-blue-500">
                            <svg class="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                    d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                        </div>
                        <div class="text-gray-600 dark:text-gray-300">
                            Conectado à Binance, aguardando oportunidades de arbitragem...
                        </div>
                        <div class="text-sm text-gray-500">
                            Monitorando pares de trading em tempo real
                        </div>
                    </div>
                </td>
            `;
            this.table.appendChild(emptyRow);
            return;
        }

        // Ordena oportunidades por lucro
        const sortedOpportunities = data.sort((a, b) => 
            parseFloat(b.profit || 0) - parseFloat(a.profit || 0)
        );

        // Atualiza status do exchange
        const statusEl = document.getElementById('exchange-status');
        if (statusEl) {
            statusEl.innerHTML = `
                <svg class="h-4 w-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="text-green-500 font-medium">Conectado à Binance</span>
            `;
        }

        // Atualiza tabela com novos dados
        sortedOpportunities.forEach(opp => {
            const row = document.createElement('tr');
            row.className = 'border-b hover:bg-gray-50 dark:hover:bg-gray-700';
            
            const profitExpected = parseFloat(opp.profit);
            const profitReal = profitExpected * (1 - parseFloat(opp.slippage));
            const profitClass = this.getProfitClass(profitReal);

            row.innerHTML = `
                <td class="p-3">
                    <div class="flex items-center space-x-2">
                        ${this.formatRoute(opp.route)}
                    </div>
                </td>
                <td class="p-3 text-center">
                    <span class="px-2 py-1 text-xs font-semibold rounded ${profitClass}">
                        ${profitExpected.toFixed(4)}%
                    </span>
                </td>
                <td class="p-3 text-center">
                    <span class="px-2 py-1 text-xs font-semibold rounded ${profitClass}">
                        ${profitReal.toFixed(4)}%
                    </span>
                </td>
                <td class="p-3 text-center">
                    <span class="text-orange-600 font-medium">
                        ${(parseFloat(opp.slippage) * 100).toFixed(2)}%
                    </span>
                </td>
                <td class="p-3 text-center">
                    <span class="text-gray-600 dark:text-gray-300">
                        ${opp.executionTime.toFixed(1)}s
                    </span>
                </td>
                <td class="p-3 text-center">
                    <span class="px-2 py-1 text-xs font-semibold rounded ${this.getLiquidityClass(opp.liquidity)}">
                        ${opp.liquidity}
                    </span>
                </td>
                <td class="p-3 text-center">
                    <span class="px-2 py-1 text-xs font-semibold rounded ${this.getRiskClass(opp.risk)}">
                        ${opp.risk}
                    </span>
                </td>
                <td class="p-3 text-center">
                    <span class="text-gray-600 dark:text-gray-300">
                        ${parseFloat(opp.spread).toFixed(4)}%
                    </span>
                </td>
                <td class="p-3 text-center">
                    <span class="px-2 py-1 text-xs font-semibold rounded ${this.getVolatilityClass(opp.volatility)}">
                        ${opp.volatility}
                    </span>
                </td>
                <td class="p-3 text-center">
                    <span class="px-2 py-1 text-xs font-semibold rounded ${this.getConfidenceClass(opp.confidence)}">
                        ${opp.confidence}%
                    </span>
                </td>
            `;
            
            this.table.appendChild(row);
            this.opportunities.set(opp.id, opp);
        });

        this.updateMetrics();
        this.updateLastUpdate();
    }

    getProfitClass(profit) {
        const value = parseFloat(profit);
        if (!value || isNaN(value)) return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-100';
        if (value >= 1.0) return 'bg-green-100 text-green-800 dark:bg-green-700 dark:text-green-100';
        if (value >= 0.5) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-700 dark:text-yellow-100';
        if (value > 0) return 'bg-blue-100 text-blue-800 dark:bg-blue-700 dark:text-blue-100';
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-100';
    }

    refresh() {
        // Força atualização dos dados
        if (this.wsManager && this.wsManager.ws?.readyState === WebSocket.OPEN) {
            this.wsManager.ws.send(JSON.stringify({ type: 'request_update' }));
        }

        // Notifica que os dados estão sendo atualizados
        this.table.innerHTML = `
            <tr>
                <td colspan="10" class="p-3 text-center">
                    <div class="animate-pulse text-gray-500">
                        Atualizando dados...
                    </div>
                </td>
            </tr>
        `;
    }

    getLiquidityClass(liquidity) {
        const classes = {
            'Alta': 'bg-green-100 text-green-800 dark:bg-green-700 dark:text-green-100',
            'Média': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-700 dark:text-yellow-100',
            'Baixa': 'bg-red-100 text-red-800 dark:bg-red-700 dark:text-red-100'
        };
        return classes[liquidity] || classes['Média'];
    }

    getRiskClass(risk) {
        const classes = {
            'Baixo': 'bg-green-100 text-green-800 dark:bg-green-700 dark:text-green-100',
            'Médio': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-700 dark:text-yellow-100',
            'Alto': 'bg-red-100 text-red-800 dark:bg-red-700 dark:text-red-100'
        };
        return classes[risk] || classes['Médio'];
    }

    getVolatilityClass(volatility) {
        const classes = {
            'Baixa': 'bg-green-100 text-green-800 dark:bg-green-700 dark:text-green-100',
            'Média': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-700 dark:text-yellow-100',
            'Alta': 'bg-red-100 text-red-800 dark:bg-red-700 dark:text-red-100'
        };
        return classes[volatility] || classes['Média'];
    }

    getConfidenceClass(confidence) {
        if (confidence >= 90) return 'bg-green-100 text-green-800 dark:bg-green-700 dark:text-green-100';
        if (confidence >= 70) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-700 dark:text-yellow-100';
        return 'bg-red-100 text-red-800 dark:bg-red-700 dark:text-red-100';
    }

    formatRoute(route) {
        const steps = route.split('→');
        return steps.map((step, index) => `
            <span class="text-sm font-medium text-gray-900 dark:text-white">${step}</span>
            ${index < steps.length - 1 ? `
                <svg class="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
            ` : ''}
        `).join('');
    }

    updateMetrics() {
        const opportunities = Array.from(this.opportunities.values());
        
        // Atualiza contadores
        document.getElementById('active-routes').textContent = opportunities.length;
        document.getElementById('routes-badge').textContent = `${opportunities.length} Rotas Ativas`;

        // Calcula métricas
        if (opportunities.length > 0) {
            const profits = opportunities.map(opp => parseFloat(opp.profit));
            const avgProfit = profits.reduce((a, b) => a + b, 0) / profits.length;
            const totalProfit = profits.reduce((a, b) => a + b, 0);
            const successRate = (profits.filter(p => p > 0).length / profits.length * 100) || 0;
            const avgSlippage = opportunities.reduce((a, b) => a + parseFloat(b.slippage), 0) / opportunities.length;

            // Atualiza display com animação
            this.updateValueWithAnimation('total-profit-24h', `$${totalProfit.toFixed(2)}`);
            this.updateValueWithAnimation('success-rate', `${successRate.toFixed(1)}%`);
            this.updateValueWithAnimation('average-slippage', `${(avgSlippage * 100).toFixed(2)}%`);
        }
    }

    updateValueWithAnimation(elementId, newValue) {
        const element = document.getElementById(elementId);
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
        const now = new Date();
        this.lastUpdate = now;
        const element = document.getElementById('last-update');
        if (element) {
            element.textContent = `Atualizado: ${now.toLocaleTimeString()}`;
        }
    }
}

// Inicializa e exporta
const arbitrageTable = new ArbitrageTableManager();
window.arbitrageTable = arbitrageTable; // Torna acessível globalmente
export default arbitrageTable;
