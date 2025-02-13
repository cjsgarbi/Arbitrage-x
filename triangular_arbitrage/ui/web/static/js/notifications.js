class NotificationManager {
    constructor() {
        this.container = document.createElement('div');
        this.container.className = 'fixed top-4 right-4 z-50 space-y-2';
        document.body.appendChild(this.container);
        this.queue = [];
        this.processing = false;
    }

    initialize() {
        // Processa fila de notificações a cada 100ms
        setInterval(() => this.processQueue(), 100);
    }

    show(message, type = 'info') {
        this.queue.push({ message, type });
    }

    async processQueue() {
        if (this.processing || this.queue.length === 0) return;
        
        this.processing = true;
        const { message, type } = this.queue.shift();
        
        const notification = this.createNotificationElement(message, type);
        this.container.appendChild(notification);

        // Inicia animação de entrada
        await new Promise(resolve => setTimeout(resolve, 100));
        notification.classList.remove('opacity-0', 'translate-x-full');

        // Remove após 5 segundos
        setTimeout(() => {
            notification.classList.add('opacity-0', 'translate-x-full');
            setTimeout(() => notification.remove(), 300);
        }, 5000);

        this.processing = false;
    }

    createNotificationElement(message, type) {
        const div = document.createElement('div');
        div.className = `flex items-center p-4 mb-4 w-full max-w-xs rounded-lg shadow text-white ${this.getColorClass(type)} transition-all duration-300 transform opacity-0 translate-x-full`;
        div.innerHTML = `
            <div class="inline-flex flex-shrink-0 justify-center items-center w-8 h-8 rounded-lg bg-white/25">
                ${this.getIconForType(type)}
            </div>
            <div class="ml-3 text-sm font-normal">${message}</div>
            <button type="button" class="ml-auto -mx-1.5 -my-1.5 rounded-lg focus:ring-2 focus:ring-gray-300 p-1.5 inline-flex h-8 w-8 text-white hover:text-gray-200 hover:bg-white/25" onclick="this.parentElement.remove()">
                <span class="sr-only">Fechar</span>
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"></path>
                </svg>
            </button>
        `;

        return div;
    }

    getColorClass(type) {
        const colors = {
            success: 'bg-green-500 dark:bg-green-600',
            error: 'bg-red-500 dark:bg-red-600',
            info: 'bg-blue-500 dark:bg-blue-600',
            warning: 'bg-yellow-500 dark:bg-yellow-600'
        };
        return colors[type] || colors.info;
    }

    getIconForType(type) {
        const icons = {
            success: '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"></path></svg>',
            error: '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"></path></svg>',
            info: '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"></path></svg>',
            warning: '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"></path></svg>'
        };
        return icons[type] || icons.info;
    }

    success(message) {
        this.show(message, 'success');
    }

    error(message) {
        this.show(message, 'error');
    }

    info(message) {
        this.show(message, 'info');
    }

    warning(message) {
        this.show(message, 'warning');
    }
}

// Exporta instância única
const notificationManager = new NotificationManager();
export default notificationManager;