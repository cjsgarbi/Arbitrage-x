// Importa monitor em tempo real
import realtimeMonitor from './realtime-monitor.js';

class PairsMonitor {
    constructor() {
        this.table = document.getElementById('arbitrage-pairs-table');
        this.updateTimeElement = document.getElementById('pairs-update-time');
        this.lastData = new Map();
        this.btcPrice = 0; // Preço do BTC em USD para conversões
        this.autoRefreshButton = document.getElementById('auto-refresh');
        this.autoRefreshEnabled = true;
    }

    initialize() {
        this.connectWebSocket();
        this.fetchBTCPrice();
        // Atualiza preço do BTC a cada 1 minuto
        setInterval(() => this.fetchBTCPrice(), 60000);
        this.setupAutoRefresh();
    }

    setupAutoRefresh() {
        if (this.autoRefreshButton) {
            this.autoRefreshButton.addEventListener('click', () => {
                this.autoRefreshEnabled = !this.autoRefreshEnabled;
                this.autoRefreshButton.classList.toggle('bg-indigo-200', this.autoRefreshEnabled);
                this.autoRefreshButton.textContent = this.autoRefreshEnabled ? 'Auto Refresh ON' : 'Auto Refresh OFF';
            });
        }
    }

    async fetchBTCPrice() {
        try {
            const response = await fetch('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT');
            const data = await response.json();
            this.btcPrice = parseFloat(data.price);
        } catch (error) {
            console.error('Erro ao buscar preço do BTC:', error);
        }
    }

    connectWebSocket() {
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'top_pairs_update') {
                this.updatePairsData(data.data.pairs);
            }
        };

        ws.onclose = () => {
            console.log('WebSocket desconectado, tentando reconectar...');
            setTimeout(() => this.connectWebSocket(), 5000);
        };
    }

    async fetchPairsData() {
        try {
            const response = await fetch('/api/top-pairs');
            const data = await response.json();
            this.updatePairsData(data.pairs);
            this.updateTimestamp(data.timestamp);
        } catch (error) {
            console.error('Erro ao buscar dados dos pares:', error);
        }
    }

    updatePairsData(pairs) {
        if (!this.table || !this.autoRefreshEnabled) return;

        this.table.innerHTML = '';
        pairs.forEach(pair => {
            const previousData = this.lastData.get(pair.pair);
            const row = this.createPairRow(pair, previousData);
            this.table.appendChild(row);
            this.lastData.set(pair.pair, pair);
        });

        this.updateTimestamp();
    }

    createPairRow(pair, previousData) {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors';
        row.setAttribute('data-pair', pair.pair);

        const profitChange = previousData ? pair.avg_profit - previousData.avg_profit : 0;
        const profitDirection = profitChange > 0 ? '↑' : profitChange < 0 ? '↓' : '–';
        const profitClass = this.getProfitClass(pair.avg_profit);
        const volumeUSD = this.btcPrice * pair.volume_24h;

        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                ${pair.pair}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">
                ${this.formatRoute(pair.route)}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm ${profitClass}">
                ${profitDirection} ${pair.avg_profit.toFixed(2)}%
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm ${this.get24hProfitClass(pair.profit_24h)}">
                ${pair.profit_24h ? pair.profit_24h.toFixed(2) + '%' : '---'}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">
                <div class="flex flex-col">
                    <span>${pair.volume_24h.toFixed(8)}</span>
                    <span class="text-xs text-gray-400">≈ $${volumeUSD.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                ${this.getVariationIndicator(pair, previousData)}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                ${this.getStatusBadge(pair.status)}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">
                <button onclick="window.pairsMonitor.monitorPair('${pair.pair}')"
                        class="text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300 font-medium">
                    Monitorar
                </button>
            </td>
        `;

        return row;
    }

    getProfitClass(profit) {
        if (profit >= 2.0) return 'text-green-600 dark:text-green-400 font-bold animate-pulse';
        if (profit >= 1.0) return 'text-green-600 dark:text-green-400 font-medium';
        if (profit >= 0.5) return 'text-yellow-600 dark:text-yellow-400';
        return 'text-gray-600 dark:text-gray-400';
    }

    get24hProfitClass(profit) {
        if (!profit) return 'text-gray-400';
        if (profit >= 10) return 'text-blue-600 dark:text-blue-400 font-bold';
        if (profit >= 5) return 'text-blue-600 dark:text-blue-400';
        return 'text-gray-600 dark:text-gray-400';
    }

    getStatusBadge(status) {
        const classes = status === 'active' 
            ? 'bg-green-100 text-green-800 dark:bg-green-700 dark:text-green-100'
            : 'bg-gray-100 text-gray-800 dark:bg-gray-600 dark:text-gray-100';
        
        return `
            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${classes}">
                ${status === 'active' ? 'Ativo' : 'Inativo'}
            </span>
        `;
    }

    getVariationIndicator(pair, previousData) {
        if (!previousData) return '---';

        const change = ((pair.avg_profit - previousData.avg_profit) / previousData.avg_profit) * 100;
        if (Math.abs(change) < 0.01) return '–';

        const changeClass = change > 0 ? 'text-green-500 dark:text-green-400' : 'text-red-500 dark:text-red-400';
        const arrow = change > 0 ? '↑' : '↓';
        
        return `<span class="${changeClass}">${arrow} ${Math.abs(change).toFixed(2)}%</span>`;
    }

    formatRoute(route) {
        if (!route) return '---';
        return route.split('→').map(coin => `<span class="font-medium">${coin}</span>`).join(' → ');
    }

    updateTimestamp() {
        if (this.updateTimeElement) {
            const now = new Date();
            this.updateTimeElement.textContent = `Última atualização: ${now.toLocaleTimeString()}`;
        }
    }

    monitorPair(pair) {
        const pairData = this.lastData.get(pair);
        if (!pairData) return;

        // Cria modal para detalhes do par
        const modalHtml = `
            <div id="pair-details-modal" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
                <div class="relative top-20 mx-auto p-5 border w-11/12 max-w-4xl shadow-lg rounded-md bg-white dark:bg-gray-800">
                    <div class="flex justify-between items-center pb-3">
                        <h3 class="text-xl font-medium text-gray-900 dark:text-white">
                            Detalhes do Par ${pair}
                        </h3>
                        <button id="close-pair-modal" class="text-gray-400 hover:text-gray-500">
                            <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>

                    <div class="mt-4">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                            <div class="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                                <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Métricas de Trading</h4>
                                <dl class="space-y-2">
                                    <div class="flex justify-between">
                                        <dt class="text-sm text-gray-600 dark:text-gray-300">Volume 24h:</dt>
                                        <dd class="text-sm font-medium text-gray-900 dark:text-white">${this.formatVolume(pairData.volume_24h)}</dd>
                                    </div>
                                    <div class="flex justify-between">
                                        <dt class="text-sm text-gray-600 dark:text-gray-300">Lucro Médio:</dt>
                                        <dd class="text-sm font-medium ${this.getProfitClass(pairData.avg_profit)}">${pairData.avg_profit.toFixed(4)}%</dd>
                                    </div>
                                    <div class="flex justify-between">
                                        <dt class="text-sm text-gray-600 dark:text-gray-300">Oportunidades:</dt>
                                        <dd class="text-sm font-medium text-gray-900 dark:text-white">${pairData.opportunity_count}</dd>
                                    </div>
                                </dl>
                            </div>

                            <div class="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                                <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Status do Par</h4>
                                <dl class="space-y-2">
                                    <div class="flex justify-between">
                                        <dt class="text-sm text-gray-600 dark:text-gray-300">Estado:</dt>
                                        <dd class="text-sm">
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                                                pairData.status === 'active' 
                                                    ? 'bg-green-100 text-green-800 dark:bg-green-700 dark:text-green-100'
                                                    : 'bg-gray-100 text-gray-800 dark:bg-gray-600 dark:text-gray-100'
                                            }">
                                                ${pairData.status === 'active' ? 'Ativo' : 'Inativo'}
                                            </span>
                                        </dd>
                                    </div>
                                    <div class="flex justify-between">
                                        <dt class="text-sm text-gray-600 dark:text-gray-300">Última Execução:</dt>
                                        <dd class="text-sm font-medium text-gray-900 dark:text-white">${this.formatTimestamp(pairData.last_update)}</dd>
                                    </div>
                                </dl>
                            </div>
                        </div>

                        <div class="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg mt-4">
                            <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Rota de Arbitragem</h4>
                            <div class="flex items-center justify-center space-x-4 py-4">
                                <span class="text-sm font-medium text-gray-900 dark:text-white">${pair}</span>
                                <svg class="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                                </svg>
                                <span class="text-sm font-medium text-gray-900 dark:text-white">${this.formatRoute(pairData.route)}</span>
                            </div>
                        </div>

                        <div class="mt-6 flex justify-end space-x-3">
                            <button id="monitor-pair-btn" class="px-4 py-2 bg-indigo-600 text-white text-base font-medium rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                                Monitorar em Tempo Real
                            </button>
                            <button id="close-pair-details" class="px-4 py-2 bg-gray-200 text-gray-800 text-base font-medium rounded-md shadow-sm hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400">
                                Fechar
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Adiciona modal ao DOM
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Configura event listeners
        const modal = document.getElementById('pair-details-modal');
        const closeBtn = document.getElementById('close-pair-details');
        const closeIcon = document.getElementById('close-pair-modal');
        const monitorBtn = document.getElementById('monitor-pair-btn');

        const closeModal = () => modal.remove();

        closeBtn?.addEventListener('click', closeModal);
        closeIcon?.addEventListener('click', closeModal);
        modal?.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        monitorBtn?.addEventListener('click', () => {
            this.startRealtimeMonitoring(pair);
            closeModal();
        });
    }

    startRealtimeMonitoring(pair) {
        realtimeMonitor.startMonitoring(pair, (data) => {
            // Callback para atualizar dados na tabela quando houver atualizações
            const row = this.table.querySelector(`tr[data-pair="${pair}"]`);
            if (row) {
                const profitCell = row.querySelector('.profit-value');
                if (profitCell) {
                    const profit = data.metrics.current_profit;
                    profitCell.textContent = `${profit.toFixed(4)}%`;
                    profitCell.className = this.getProfitClass(profit);
                }

                const opportunitiesCell = row.querySelector('.opportunities-value');
                if (opportunitiesCell) {
                    opportunitiesCell.textContent = data.metrics.opportunity_count;
                }
            }
        });
    }
}

// Inicializa e exporta
const pairsMonitor = new PairsMonitor();
window.pairsMonitor = pairsMonitor;
export default pairsMonitor;