"""
Gerenciador de métricas para monitoramento do sistema
"""
import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)

class MetricsManager:
    def __init__(self):
        self.analysis_count = 0
        self.success_count = 0
        self.total_response_time = 0
        self.total_cost = 0
        self.start_time = time.time()

    def start_analysis(self):
        self.analysis_count += 1
        return time.time()

    def end_analysis(self, start_time, success: bool, cost: float = 0):
        response_time = time.time() - start_time
        self.total_response_time += response_time
        self.total_cost += cost
        
        if success:
            self.success_count += 1

    def get_metrics(self) -> Dict:
        elapsed_time = time.time() - self.start_time
        
        success_rate = (self.success_count / self.analysis_count) * 100 \
            if self.analysis_count > 0 else 0
        
        avg_response_time = self.total_response_time / self.analysis_count \
            if self.analysis_count > 0 else 0
        
        return {
            "analysis_count": self.analysis_count,
            "success_count": self.success_count,
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "total_cost": self.total_cost,
            "elapsed_time": elapsed_time
        }

    def log_metrics(self):
        metrics = self.get_metrics()
        logger.info(f"Métricas do Sistema: {metrics}")

metrics_manager = MetricsManager()