"""
Configurações para o HuggingFace/Sentence Transformers
"""
import os
from pathlib import Path

def setup_huggingface_env():
    """Configura variáveis de ambiente para o HuggingFace"""
    
    # Define diretório de cache personalizado
    cache_dir = os.path.join(os.path.expanduser('~'), '.cache', 'arbitrage')
    os.makedirs(cache_dir, exist_ok=True)
    
    # Configura variáveis de ambiente
    os.environ['TRANSFORMERS_CACHE'] = os.path.join(cache_dir, 'transformers')
    os.environ['HF_HOME'] = os.path.join(cache_dir, 'hub')
    os.environ['HF_HUB_CACHE'] = os.path.join(cache_dir, 'hub')
    os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
    os.environ['HF_HUB_OFFLINE'] = '1'  # Usa apenas cache local após primeiro download
    
    # Cria diretórios
    Path(os.environ['TRANSFORMERS_CACHE']).mkdir(parents=True, exist_ok=True)
    Path(os.environ['HF_HOME']).mkdir(parents=True, exist_ok=True)
    Path(os.environ['HF_HUB_CACHE']).mkdir(parents=True, exist_ok=True)