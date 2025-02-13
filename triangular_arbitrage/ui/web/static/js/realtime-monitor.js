class RealtimeMonitor {
    constructor() {
        this.activePairs = new Set();
        this.updateCallbacks = new Map();
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }

    startMonitoring(pair, onUpdate) {
        if (this.activePairs.has(pair)) return;
        
        this.activePairs.add(pair);
        if (onUpdate) {
            this.updateCallbacks.set(pair, onUpdate);
        }

        // Cria elemento flutuante para monitoramento
        this.createMonitorElement(pair);

        // Inicia conexão WebSocket se não existir
        if (!this.ws) {
            this.connectWebSocket();
        } else {
            // Envia mensagem para subscrever ao par
            this.ws.send(JSON.stringify({
                type: 'monitor_pair',
                pair: pair
            }));
        }
    }

    createMonitorElement(pair) {
        const monitorId = `monitor-${pair.replace('/', '-')}`;
        
        // Remove monitor existente se houver
        const existingMonitor = document.getElementById(monitorId);
        if (existingMonitor) {
            existingMonitor.remove();
        }

        const monitorHtml = `
            <div id="${monitorId}" class="fixed bottom-4 right-4 w-80 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-4 cursor-move">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-sm font-medium text-gray-900 dark:text-white">Monitor: ${pair}</h3>
                    <button onclick="window.realtimeMonitor.stopMonitoring('${pair}')" class="text-gray-400 hover:text-gray-500">
                        <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                <div class="space-y-2">
                    <div class="flex justify-between items-center">
                        <span class="text-xs text-gray-500 dark:text-gray-400">Lucro Atual:</span>
                        <span id="${monitorId}-profit" class="text-sm font-medium">--</span>
                    </div>
                    <div class="flex justify-between items-center">
                        <span class="text-xs text-gray-500 dark:text-gray-400">Volume:</span>
                        <span id="${monitorId}-volume" class="text-sm text-gray-900 dark:text-white">--</span>
                    </div>
                    <div class="flex justify-between items-center">
                        <span class="text-xs text-gray-500 dark:text-gray-400">Oportunidades:</span>
                        <span id="${monitorId}-opportunities" class="text-sm text-gray-900 dark:text-white">--</span>
                    </div>
                </div>
                <div class="mt-4">
                    <div class="text-xs text-gray-500 dark:text-gray-400 mb-2">Rotas Ativas:</div>
                    <div id="${monitorId}-routes" class="space-y-1 text-sm"></div>
                </div>
                <div class="mt-3 text-right">
                    <span id="${monitorId}-timestamp" class="text-xs text-gray-400"></span>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', monitorHtml);

        // Adiciona drag and drop
        this.makeMonitorDraggable(monitorId);
    }

    makeMonitorDraggable(monitorId) {
        const monitor = document.getElementById(monitorId);
        if (!monitor) return;

        let isDragging = false;
        let currentX;
        let currentY;
        let initialX;
        let initialY;
        let xOffset = 0;
        let yOffset = 0;

        monitor.addEventListener('mousedown', startDragging);
        document.addEventListener('mousemove', drag);
        document.addEventListener('mouseup', stopDragging);

        function startDragging(e) {
            initialX = e.clientX - xOffset;
            initialY = e.clientY - yOffset;

            if (e.target === monitor) {
                isDragging = true;
            }
        }

        function drag(e) {
            if (isDragging) {
                e.preventDefault();
                
                currentX = e.clientX - initialX;
                currentY = e.clientY - initialY;

                xOffset = currentX;
                yOffset = currentY;

                setTranslate(currentX, currentY, monitor);
            }
        }

        function stopDragging() {
            initialX = currentX;
            initialY = currentY;
            isDragging = false;
        }

        function setTranslate(xPos, yPos, el) {
            el.style.transform = `translate3d(${xPos}px, ${yPos}px, 0)`;
        }
    }

    updateMonitorData(pair, data) {
        const monitorId = `monitor-${pair.replace('/', '-')}`;
        const monitor = document.getElementById(monitorId);
        if (!monitor) return;

        // Atualiza elementos
        const profitElement = document.getElementById(`${monitorId}-profit`);
        if (profitElement) {
            const profitValue = data.metrics.current_profit;
            profitElement.textContent = `${profitValue.toFixed(4)}%`;
            profitElement.className = this.getProfitClass(profitValue);
        }

        const volumeElement = document.getElementById(`${monitorId}-volume`);
        if (volumeElement) {
            volumeElement.textContent = `${data.metrics.volume_now.toFixed(8)} BTC`;
        }

        const oppsElement = document.getElementById(`${monitorId}-opportunities`);
        if (oppsElement) {
            oppsElement.textContent = data.metrics.opportunity_count;
        }

        const routesElement = document.getElementById(`${monitorId}-routes`);
        if (routesElement) {
            routesElement.innerHTML = data.metrics.active_routes
                .map(route => `<div class="py-1 px-2 bg-gray-50 dark:bg-gray-700 rounded">${route}</div>`)
                .join('');
        }

        const timestampElement = document.getElementById(`${monitorId}-timestamp`);
        if (timestampElement) {
            const date = new Date(data.timestamp);
            timestampElement.textContent = `Atualizado: ${date.toLocaleTimeString()}`;
        }

        // Chama callback de atualização se existir
        const callback = this.updateCallbacks.get(pair);
        if (callback) {
            callback(data);
        }
    }

    getProfitClass(profit) {
        if (profit > 1.0) return 'text-sm font-medium text-green-600 dark:text-green-400';
        if (profit > 0.5) return 'text-sm font-medium text-yellow-600 dark:text-yellow-400';
        return 'text-sm font-medium text-gray-600 dark:text-gray-400';
    }

    stopMonitoring(pair) {
        const monitorId = `monitor-${pair.replace('/', '-')}`;
        const monitor = document.getElementById(monitorId);
        if (monitor) {
            monitor.remove();
        }

        this.activePairs.delete(pair);
        this.updateCallbacks.delete(pair);
    }

    handleWebSocketMessage(data) {
        if (data.type === 'pair_monitor_update' && data.data.pair) {
            this.updateMonitorData(data.data.pair, data.data);
        }
    }
}

// Exporta instância única
const realtimeMonitor = new RealtimeMonitor();
window.realtimeMonitor = realtimeMonitor;
export default realtimeMonitor;