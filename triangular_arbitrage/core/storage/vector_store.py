"""
VectorStore para armazenamento e busca de oportunidades de arbitragem
"""
from typing import Dict, List, Optional, Tuple, Any
import faiss
import numpy as np
from numpy.typing import NDArray
from sentence_transformers import SentenceTransformer
import json
import logging
import os
from pathlib import Path
import time
import torch

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, model_name: str = 'paraphrase-MiniLM-L3-v2'):
        """
        Inicializa o VectorStore
        
        Args:
            model_name: Nome do modelo de embeddings
        """
        # Configura cache do modelo
        cache_dir = os.path.join(os.path.expanduser('~'), '.cache', 'arbitrage', 'models')
        os.makedirs(cache_dir, exist_ok=True)
        
        try:
            logger.info(f"Carregando modelo {model_name}")
            self.model = SentenceTransformer(
                model_name,
                cache_folder=cache_dir
            )
            self.dimension = self.model.get_sentence_embedding_dimension()
            self.index: Any = faiss.IndexFlatL2(self.dimension)
            self.items: List[Dict] = []  # armazena os itens originais
            self.cache: Dict[str, Tuple[NDArray[np.float32], float]] = {}  # cache de embeddings
            self.cache_ttl = 500  # 500ms TTL para cache
            logger.info(f"Modelo carregado com dimensão {self.dimension}")
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            raise
        
    def add_item(self, item: Dict) -> bool:
        """
        Adiciona um item ao store
        
        Args:
            item: Dicionário com dados da oportunidade
            
        Returns:
            bool: True se adicionado com sucesso
        """
        try:
            # Converte item para string JSON para embedding
            item_str = json.dumps(item, sort_keys=True)
            
            # Gera embedding
            embedding = self._get_embedding(item_str)
            
            # Converte para o formato correto e adiciona ao índice
            embedding_array = np.array([embedding], dtype=np.float32)
            self.index.add_with_ids(embedding_array, np.array([len(self.items)], dtype=np.int64))
            self.items.append(item)
            
            return True
        except Exception as e:
            logger.error(f"Erro ao adicionar item: {e}")
            return False
            
    def search_similar(self, query: Dict, k: int = 5) -> List[Dict]:
        """
        Busca itens similares
        
        Args:
            query: Dicionário com dados para busca
            k: Número de resultados
            
        Returns:
            List[Dict]: Lista de itens similares
        """
        try:
            # Converte query para embedding
            query_str = json.dumps(query, sort_keys=True)
            query_vector = self._get_embedding(query_str)
            
            # Prepara array para busca
            query_array = np.array([query_vector], dtype=np.float32)
            k = min(k, len(self.items))
            
            # Realiza a busca
            if k > 0:
                distances = np.empty((1, k), dtype=np.float32)
                labels = np.empty((1, k), dtype=np.int64)
                self.index.search(query_array, k, distances, labels)
                
                # Retorna itens encontrados com scores
                results = []
                for i, idx in enumerate(labels[0]):
                    if idx < len(self.items):
                        item = self.items[idx].copy()
                        item['similarity_score'] = float(distances[0][i])
                        results.append(item)
                        
                return results
            return []
            
        except Exception as e:
            logger.error(f"Erro na busca: {e}")
            return []
            
    def _get_embedding(self, text: str) -> NDArray[np.float32]:
        """
        Gera ou recupera embedding do cache
        
        Args:
            text: Texto para gerar embedding
            
        Returns:
            NDArray[np.float32]: Embedding do texto
        """
        # Verifica cache
        now = time.time()
        if text in self.cache:
            embedding, timestamp = self.cache[text]
            if now - timestamp <= self.cache_ttl/1000:
                return embedding
                
        # Gera novo embedding
        with torch.no_grad():
            embedding = self.model.encode(text, show_progress_bar=False)
            if isinstance(embedding, torch.Tensor):
                embedding = embedding.cpu().numpy().astype(np.float32)
            elif isinstance(embedding, np.ndarray):
                embedding = embedding.astype(np.float32)
            
        # Atualiza cache
        self.cache[text] = (embedding, now)
        
        return embedding
        
    def clear(self):
        """Limpa todos os dados"""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.items = []
        self.cache = {}