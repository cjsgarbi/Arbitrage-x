function updateAIStatus() {
    fetch('/api/ai_status')
        .then(response => response.json())
        .then(data => {
            const statusElement = document.getElementById('ai-status');
            if (data.connected) {
                statusElement.textContent = 'IA: Conectada';
                statusElement.style.color = '#28a745'; // Verde
            } else {
                statusElement.textContent = 'IA: Desconectada';
                statusElement.style.color = '#dc3545'; // Vermelho
            }
        })
        .catch(error => {
            console.error('Erro ao atualizar status da IA:', error);
        });
}

// Atualiza o status a cada 5 segundos
setInterval(updateAIStatus, 5000);

// Atualiza assim que a página carrega
window.onload = updateAIStatus;
