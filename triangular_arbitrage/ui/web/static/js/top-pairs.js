class TopPairsManager {
    constructor() {
        this.table = document.getElementById('top-pairs-body');
        this.lastUpdate = null;
        this.wsManager = window.wsManager;
    }

    initialize() {
        // Inscreve-se no tópico de top pares via WebSocket
        this.wsManager.subscribe('top_pairs', (data) => {
            this.renderPairs(data.pairs);
            this.lastUpdate = data.timestamp;
            
            // Atualiza contador total
            const pairsCount = document.getElementById('pairs-count');
            if (pairsCount) {
                pairsCount.textContent = data.total_monitored;
            }
        });

        // Solicita dados iniciais
        this.wsManager.ws.send(JSON.stringify({
            type: 'subscribe',
            topics: ['top_pairs']
        }));
    }

    renderPairs(pairs) {
        if (!this.table) return;

        // Limpa tabela atual
        this.table.innerHTML = '';

        pairs.forEach(pair => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors';
            
            const statusClass = pair.status === 'active' 
                ? 'bg-green-100 text-green-800 dark:bg-green-700 dark:text-green-100'
                : 'bg-gray-100 text-gray-800 dark:bg-gray-600 dark:text-gray-100';

            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                    ${pair.pair}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm ${pair.avg_profit > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}">
                    ${pair.avg_profit.toFixed(4)}%
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">
                    ${pair.volume_24h.toFixed(8)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">
                    ${pair.opportunity_count}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${statusClass}">
                        ${pair.status === 'active' ? 'Ativo' : 'Inativo'}
                    </span>
                </td>
            `;
            
            this.table.appendChild(row);
        });
    }
}

// Inicializa o gerenciador quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    const topPairsManager = new TopPairsManager();
    topPairsManager.initialize();
});

export default TopPairsManager;
