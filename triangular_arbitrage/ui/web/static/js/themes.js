// Configurações de temas
const themes = {
    light: {
        name: 'light',
        colors: {
            background: '#f3f4f6',
            surface: '#ffffff',
            primary: '#2563eb',
            secondary: '#4b5563',
            accent: '#3b82f6',
            text: {
                primary: '#111827',
                secondary: '#4b5563',
                accent: '#2563eb'
            },
            border: '#e5e7eb',
            divider: '#e5e7eb',
            error: '#dc2626',
            success: '#059669',
            warning: '#d97706'
        }
    },
    dark: {
        name: 'dark',
        colors: {
            background: '#111827',
            surface: '#1f2937',
            primary: '#3b82f6',
            secondary: '#9ca3af',
            accent: '#60a5fa',
            text: {
                primary: '#f9fafb',
                secondary: '#d1d5db',
                accent: '#60a5fa'
            },
            border: '#374151',
            divider: '#374151',
            error: '#ef4444',
            success: '#10b981',
            warning: '#f59e0b'
        }
    }
};

class ThemeManager {
    constructor() {
        this.currentTheme = localStorage.getItem('theme') || 'light';
        this.observers = new Set();
    }

    // Inicializa o gerenciador de temas
    initialize() {
        // Aplica tema salvo ou padrão
        this.applyTheme(this.currentTheme);
        
        // Observa preferência do sistema
        this.watchSystemTheme();
        
        // Adiciona controles à interface
        this.addThemeControls();
    }

    // Adiciona controles de tema na interface
    addThemeControls() {
        const header = document.querySelector('header .flex');
        if (!header) return;

        const themeToggle = document.createElement('div');
        themeToggle.className = 'flex items-center space-x-2';
        themeToggle.innerHTML = `
            <button id="theme-toggle" class="p-2 rounded-lg bg-gray-200 dark:bg-gray-700">
                <svg id="theme-icon" class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <!-- Sol -->
                    <path class="sun hidden" fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"/>
                    <!-- Lua -->
                    <path class="moon hidden" fill-rule="evenodd" d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/>
                </svg>
            </button>
        `;

        header.appendChild(themeToggle);

        // Adiciona evento de toggle
        const toggleBtn = document.getElementById('theme-toggle');
        toggleBtn.addEventListener('click', () => {
            this.toggleTheme();
        });

        // Atualiza ícone inicial
        this.updateThemeIcon();
    }

    // Observa mudanças na preferência do sistema
    watchSystemTheme() {
        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addListener((e) => {
                if (this.currentTheme === 'system') {
                    this.applyTheme(e.matches ? 'dark' : 'light');
                }
            });
        }
    }

    // Alterna entre temas
    toggleTheme() {
        const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.applyTheme(newTheme);
    }

    // Aplica um tema
    applyTheme(themeName) {
        if (!themes[themeName]) return;

        const theme = themes[themeName];
        this.currentTheme = themeName;

        // Salva preferência
        localStorage.setItem('theme', themeName);

        // Aplica classes ao HTML
        document.documentElement.classList.remove('light', 'dark');
        document.documentElement.classList.add(themeName);

        // Aplica variáveis CSS
        this.applyThemeColors(theme.colors);

        // Atualiza ícone
        this.updateThemeIcon();

        // Notifica observadores
        this.notifyObservers();
    }

    // Aplica cores do tema como variáveis CSS
    applyThemeColors(colors) {
        const root = document.documentElement;
        Object.entries(colors).forEach(([key, value]) => {
            if (typeof value === 'object') {
                Object.entries(value).forEach(([subKey, subValue]) => {
                    root.style.setProperty(`--${key}-${subKey}`, subValue);
                });
            } else {
                root.style.setProperty(`--${key}`, value);
            }
        });
    }

    // Atualiza ícone do tema
    updateThemeIcon() {
        const sunPath = document.querySelector('.sun');
        const moonPath = document.querySelector('.moon');

        if (sunPath && moonPath) {
            if (this.currentTheme === 'dark') {
                sunPath.classList.add('hidden');
                moonPath.classList.remove('hidden');
            } else {
                sunPath.classList.remove('hidden');
                moonPath.classList.add('hidden');
            }
        }
    }

    // Adiciona observador
    addObserver(callback) {
        this.observers.add(callback);
    }

    // Remove observador
    removeObserver(callback) {
        this.observers.delete(callback);
    }

    // Notifica observadores
    notifyObservers() {
        this.observers.forEach(callback => callback(this.currentTheme));
    }
}

// Exporta instância única
const themeManager = new ThemeManager();
export default themeManager;

// Inicializa quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    themeManager.initialize();
});