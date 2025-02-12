// Estado global
let currentConfig = {};

// Funções auxiliares
function showMessage(message, isError = false) {
    const status = document.getElementById('save-status');
    if (status) {
        status.textContent = message;
        status.className = `text-sm ${isError ? 'text-red-600' : 'text-green-600'}`;
        setTimeout(() => status.textContent = '', 3000);
    }
}

// Gerenciamento de tabs
function setupTabs() {
    const tabs = document.querySelectorAll('.nav-tab');
    const sections = document.querySelectorAll('.config-section');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove seleção anterior
            tabs.forEach(t => t.classList.remove('active'));
            sections.forEach(s => s.classList.add('hidden'));
            
            // Seleciona nova tab
            tab.classList.add('active');
            const section = document.getElementById(`${tab.dataset.tab}-section`);
            if (section) section.classList.remove('hidden');
        });
    });
}

// Carrega configurações
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        if (!response.ok) throw new Error('Falha ao carregar configurações');
        
        currentConfig = await response.json();
        
        // Preenche campos
        document.querySelectorAll('[data-config]').forEach(input => {
            const [category, key] = input.dataset.config.split('.');
            const value = currentConfig[category]?.[key];
            
            if (input.type === 'checkbox') {
                input.checked = value === 'true';
            } else {
                input.value = value || '';
            }
        });
        
    } catch (error) {
        console.error('Erro ao carregar configurações:', error);
        showMessage('Erro ao carregar configurações', true);
    }
}

// Salva configurações
async function saveConfig() {
    try {
        // Coleta valores alterados
        const updates = {};
        document.querySelectorAll('[data-config]').forEach(input => {
            const [category, key] = input.dataset.config.split('.');
            const value = input.type === 'checkbox' ? input.checked.toString() : input.value;
            
            if (!updates[category]) updates[category] = {};
            updates[category][key] = value;
        });
        
        // Envia atualizações
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updates)
        });
        
        if (!response.ok) throw new Error('Falha ao salvar configurações');
        
        showMessage('Configurações salvas com sucesso');
        await loadConfig();  // Recarrega configurações
        
    } catch (error) {
        console.error('Erro ao salvar configurações:', error);
        showMessage('Erro ao salvar configurações', true);
    }
}

// Exporta configurações
function exportConfig() {
    const config = JSON.stringify(currentConfig, null, 2);
    const blob = new Blob([config], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bot_config_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    loadConfig();
    
    // Event listeners
    const saveBtn = document.getElementById('btn-save');
    if (saveBtn) saveBtn.addEventListener('click', saveConfig);
    
    const exportBtn = document.getElementById('btn-export');
    if (exportBtn) exportBtn.addEventListener('click', exportConfig);
});