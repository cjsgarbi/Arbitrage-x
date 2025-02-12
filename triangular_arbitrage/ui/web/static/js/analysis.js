import notificationManager from './notifications.js';

class OpportunityAnalyzer {
    constructor() {
        this.modalTemplate = `
            <div id="analysis-modal" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full">
                <div class="relative top-20 mx-auto p-5 border w-11/12 max-w-2xl shadow-lg rounded-md bg-white dark:bg-gray-800">
                    <div class="mt-3">
                        <div class="flex justify-between items-center pb-3">
                            <h3 class="text-lg font-medium text-gray-900 dark:text-white" id="modal-title">
                                Análise de Oportunidade
                            </h3>
                            <button id="close-modal" class="text-gray-400 hover:text-gray-500">
                                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div class="mt-2" id="analysis-content">
                            <!-- Conteúdo dinâmico será inserido aqui -->
                        </div>
                        <div class="mt-4 flex justify-end space-x-3">
                            <button id="monitor-btn" class="px-4 py-2 bg-blue-500 text-white text-base font-medium rounded-md shadow-sm hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-300">
                                Monitorar
                            </button>
                            <button id="close-btn" class="px-4 py-2 bg-gray-200 text-gray-800 text-base font-medium rounded-md shadow-sm hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400">
                                Fechar
                            </button>
                        </div>
                    </div>
                </div>
            </div>`;
    }

    async analyze(route) {
        try {
            // Busca dados detalhados da rota
            const response = await fetch(`/api/analyze-route?route=${encodeURIComponent(route)}`);
            const data = await response.json();
            
            // Cria e mostra modal
            this.showAnalysisModal(data);
            notificationManager.success('Análise carregada com sucesso');
        } catch (error) {
            console.error('Erro ao analisar rota:', error);
            this.showError('Não foi possível analisar esta oportunidade');
        }
    }

    showAnalysisModal(data) {
        // Remove modal existente se houver
        const existingModal = document.getElementById('analysis-modal');
        if (existingModal) {
            existingModal.remove();
        }

        // Adiciona novo modal ao DOM
        document.body.insertAdjacentHTML('beforeend', this.modalTemplate);

        // Configura conteúdo
        const content = document.getElementById('analysis-content');
        content.innerHTML = this.generateAnalysisContent(data);

        // Configura event listeners
        this.setupModalEventListeners(data);
    }

    generateAnalysisContent(data) {
        return `
            <div class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                        <div class="text-sm text-gray-500 dark:text-gray-400">Volume Total</div>
                        <div class="text-lg font-semibold text-gray-900 dark:text-white">
                            ${data.volume.toFixed(8)} BTC
                        </div>
                    </div>
                    <div class="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                        <div class="text-sm text-gray-500 dark:text-gray-400">Lucro Estimado</div>
                        <div class="text-lg font-semibold text-green-600 dark:text-green-400">
                            ${data.profit.toFixed(4)}%
                        </div>
                    </div>
                </div>

                <div class="mt-4">
                    <h4 class="text-sm font-medium text-gray-900 dark:text-white mb-2">Detalhes da Rota</h4>
                    <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                        <div class="space-y-2">
                            ${this.generateRouteSteps(data.steps)}
                        </div>
                    </div>
                </div>

                <div class="mt-4">
                    <h4 class="text-sm font-medium text-gray-900 dark:text-white mb-2">Análise de Risco</h4>
                    <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                        <div class="space-y-2">
                            <div class="flex justify-between items-center">
                                <span class="text-sm text-gray-500 dark:text-gray-400">Volatilidade</span>
                                <span class="text-sm font-medium ${this.getRiskClass(data.risk.volatility)}">
                                    ${this.getRiskLabel(data.risk.volatility)}
                                </span>
                            </div>
                            <div class="flex justify-between items-center">
                                <span class="text-sm text-gray-500 dark:text-gray-400">Liquidez</span>
                                <span class="text-sm font-medium ${this.getRiskClass(data.risk.liquidity)}">
                                    ${this.getRiskLabel(data.risk.liquidity)}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
    }

    generateRouteSteps(steps) {
        return steps.map((step, index) => `
            <div class="flex items-center">
                <div class="flex-1">
                    <div class="text-sm font-medium text-gray-900 dark:text-white">
                        ${step.from} → ${step.to}
                    </div>
                    <div class="text-xs text-gray-500 dark:text-gray-400">
                        Volume: ${step.volume.toFixed(8)} | Preço: ${step.price.toFixed(8)}
                    </div>
                </div>
                ${index < steps.length - 1 ? `
                    <svg class="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                ` : ''}
            </div>
        `).join('');
    }

    getRiskClass(risk) {
        const classes = {
            low: 'text-green-600 dark:text-green-400',
            medium: 'text-yellow-600 dark:text-yellow-400',
            high: 'text-red-600 dark:text-red-400'
        };
        return classes[risk] || classes.medium;
    }

    getRiskLabel(risk) {
        const labels = {
            low: 'Baixo',
            medium: 'Médio',
            high: 'Alto'
        };
        return labels[risk] || 'Desconhecido';
    }

    setupModalEventListeners(data) {
        const modal = document.getElementById('analysis-modal');
        const closeBtn = document.getElementById('close-btn');
        const closeIcon = document.getElementById('close-modal');
        const monitorBtn = document.getElementById('monitor-btn');

        const closeModal = () => modal.remove();

        closeBtn?.addEventListener('click', closeModal);
        closeIcon?.addEventListener('click', closeModal);
        modal?.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        monitorBtn?.addEventListener('click', () => {
            this.startMonitoring(data);
            closeModal();
        });
    }

    startMonitoring(data) {
        notificationManager.info(`Iniciando monitoramento da rota ${data.steps[0].from} → ${data.steps[data.steps.length-1].to}`);
        // TODO: Implementar lógica de monitoramento
    }

    showError(message) {
        notificationManager.error(message);
    }
}

// Exporta instância única
const analyzer = new OpportunityAnalyzer();
export default analyzer;