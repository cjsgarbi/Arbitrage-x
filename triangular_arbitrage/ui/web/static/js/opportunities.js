// Importa analisador
import analyzer from './analysis.js';

// Gerenciador de oportunidades de arbitragem
class OpportunitiesManager {
    constructor() {
        this.table = document.getElementById('opportunities-body');
        this.countElement = document.getElementById('opportunity-count');
        this.lastUpdateElement = document.getElementById('last-update');
        this.autoRefreshButton = document.getElementById('auto-refresh');
        this.autoRefresh = true;
        this.setupEventListeners();
    }

    setupEventListeners() {
        if (this.autoRefreshButton) {
            this.autoRefreshButton.addEventListener('click', () => {
                this.autoRefresh = !this.autoRefresh;
                this.autoRefreshButton.classList.toggle('bg-indigo-200', this.autoRefresh);
                this.autoRefreshButton.textContent = this.autoRefresh ? 'Auto Refresh On' : 'Auto Refresh Off';
            });
        }
    }

    updateOpportunities(opportunities) {
        if (!this.table || !this.autoRefresh) return;

        // Limpa tabela atual
        this.table.innerHTML = '';
        
        if (!opportunities || opportunities.length === 0) {
            this.showNoDataMessage();
            this.updateCount(0);
            return;
        }

        opportunities.forEach(opp => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors';
            
            const profit = parseFloat(opp.profit);
            const profitClass = profit > 1.0 ? 'text-green-600 dark:text-green-400' : 
                              profit > 0.5 ? 'text-yellow-600 dark:text-yellow-400' : 
                              'text-gray-600 dark:text-gray-400';
            
            const statusClass = opp.status === 'excellent' ? 
                'bg-green-100 text-green-800 dark:bg-green-700 dark:text-green-100' :
                'bg-yellow-100 text-yellow-800 dark:bg-yellow-700 dark:text-yellow-100';

            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                    ${this.formatRoute(opp.route)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm ${profitClass}">
                    ${profit.toFixed(4)}%
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">
                    ${parseFloat(opp.volume).toFixed(8)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${statusClass}">
                        ${opp.status}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">
                    ${this.formatTimestamp(opp.timestamp)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">
                    <button onclick="window.opportunitiesManager.monitorOpportunity('${opp.route}')" 
                            class="text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300 mr-3">
                        Monitor
                    </button>
                    <button onclick="window.opportunitiesManager.analyzeOpportunity('${opp.route}')"
                            class="text-green-600 hover:text-green-900 dark:text-green-400 dark:hover:text-green-300">
                        Analisar
                    </button>
                </td>
            `;
            
            this.table.appendChild(row);
        });

        this.updateCount(opportunities.length);
        this.updateLastUpdate();
    }

    formatRoute(route) {
        return route.replace(/→/g, ' → ');
    }

    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString();
    }

    updateCount(count) {
        if (this.countElement) {
            this.countElement.textContent = `${count} ativa${count !== 1 ? 's' : ''}`;
        }
    }

    updateLastUpdate() {
        if (this.lastUpdateElement) {
            this.lastUpdateElement.textContent = `Última atualização: ${new Date().toLocaleTimeString()}`;
        }
    }

    showNoDataMessage() {
        if (!this.table.querySelector('.no-data-message')) {
            const row = document.createElement('tr');
            row.className = 'no-data-message';
            row.innerHTML = `
                <td colspan="7" class="px-6 py-12 text-center">
                    <div class="flex flex-col items-center justify-center space-y-3">
                        <svg class="w-12 h-12 text-gray-400 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <p class="text-gray-500 dark:text-gray-400">
                            Nenhuma oportunidade encontrada no momento
                        </p>
                    </div>
                </td>
            `;
            this.table.appendChild(row);
        }
    }

    monitorOpportunity(route) {
        window.realtimeMonitor.startMonitoring(route);
    }

    analyzeOpportunity(route) {
        window.opportunityAnalyzer.analyze(route);
    }
}

// Inicializa e exporta o gerenciador
const opportunitiesManager = new OpportunitiesManager();
window.opportunitiesManager = opportunitiesManager; // Para acesso global
export default opportunitiesManager;
