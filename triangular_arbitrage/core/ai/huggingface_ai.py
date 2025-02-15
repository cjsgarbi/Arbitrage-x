from langchain.embeddings import HuggingFaceEmbeddings
from .base_ai import BaseAI

class HuggingFaceAI(BaseAI):
    def __init__(self):
        self.model = None
        
    def setup(self, config: dict) -> bool:
        try:
            self.model = HuggingFaceEmbeddings()
            return True
        except Exception as e:
            print(f"Erro ao configurar Hugging Face: {e}")
            return False
            
    def analyze(self, data: dict) -> dict:
        if self.model is not None:
            return self.model.embed_documents(data)
        else:
            raise ValueError("Model is not set up. Please call setup() first.")
