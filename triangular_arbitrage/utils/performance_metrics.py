"""
Sistema de métricas de performance
"""
import time
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
from collections import deque
import statistics
from dataclasses import dataclass, field
from .debug_logger import debug_logger

@dataclass
class MetricPoint:
    value: float
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)

class MetricsManager:
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics: Dict[str, deque] = {}
        self.start_time = time.time()
        
        # Métricas agregadas
        self.aggregated_metrics: Dict[str, Dict] = {}
        
        debug_logger.log_event(
            'metrics_manager_init',
            'Sistema de métricas inicializado',
            {'window_size': window_size}
        )

    def record_metric(self, 
                     name: str, 
                     value: float, 
                     tags: Optional[Dict[str, str]] = None):
        """Registra uma nova métrica"""
        if name not in self.metrics:
            self.metrics[name] = deque(maxlen=self.window_size)
        
        point = MetricPoint(value=value, timestamp=time.time(), tags=tags or {})
        self.metrics[name].append(point)
        
        # Atualiza métricas agregadas
        self._update_aggregated_metrics(name)
        
        debug_logger.log_event(
            'metric_recorded',
            f'Métrica {name} registrada',
            {
                'value': value,
                'tags': tags,
                'total_points': len(self.metrics[name])
            }
        )

    def _update_aggregated_metrics(self, metric_name: str):
        """Atualiza métricas agregadas para um determinado nome"""
        if not self.metrics[metric_name]:
            return
        
        values = [p.value for p in self.metrics[metric_name]]
        current_time = time.time()
        
        self.aggregated_metrics[metric_name] = {
            'current': values[-1],
            'min': min(values),
            'max': max(values),
            'avg': statistics.mean(values),
            'median': statistics.median(values),
            'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
            'count': len(values),
            'last_update': current_time
        }

    def get_metric_statistics(self, 
                            name: str, 
                            time_window: Optional[float] = None) -> Dict:
        """Retorna estatísticas de uma métrica"""
        if name not in self.metrics:
            return {}
            
        current_time = time.time()
        points = self.metrics[name]
        
        if time_window:
            cutoff = current_time - time_window
            points = [p for p in points if p.timestamp >= cutoff]
            
        if not points:
            return {}
            
        values = [p.value for p in points]
        
        return {
            'name': name,
            'current': values[-1],
            'min': min(values),
            'max': max(values),
            'avg': statistics.mean(values),
            'median': statistics.median(values),
            'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
            'count': len(values),
            'time_window': time_window,
            'last_update': current_time
        }

    def get_all_metrics(self) -> Dict[str, Dict]:
        """Retorna todas as métricas agregadas"""
        return self.aggregated_metrics

    def get_metrics_by_tag(self, tag_name: str, tag_value: str) -> Dict[str, List[MetricPoint]]:
        """Retorna métricas filtradas por tag"""
        filtered_metrics = {}
        
        for name, points in self.metrics.items():
            matching_points = [
                p for p in points 
                if tag_name in p.tags and p.tags[tag_name] == tag_value
            ]
            if matching_points:
                filtered_metrics[name] = matching_points
                
        return filtered_metrics

    def get_performance_summary(self) -> Dict:
        """Gera um resumo geral de performance"""
        current_time = time.time()
        uptime = current_time - self.start_time
        
        metrics_count = {
            name: len(points) for name, points in self.metrics.items()
        }
        
        total_metrics = sum(metrics_count.values())
        metrics_per_second = total_metrics / uptime if uptime > 0 else 0
        
        return {
            'uptime_seconds': uptime,
            'total_metrics': total_metrics,
            'metrics_per_second': metrics_per_second,
            'active_metrics': len(self.metrics),
            'metrics_count': metrics_count,
            'timestamp': datetime.now().isoformat()
        }

    def cleanup_old_metrics(self, max_age: float):
        """Remove métricas antigas"""
        cutoff = time.time() - max_age
        metrics_removed = 0
        
        for name in list(self.metrics.keys()):
            original_size = len(self.metrics[name])
            self.metrics[name] = deque(
                [p for p in self.metrics[name] if p.timestamp >= cutoff],
                maxlen=self.window_size
            )
            metrics_removed += original_size - len(self.metrics[name])
            
            if not self.metrics[name]:
                del self.metrics[name]
                if name in self.aggregated_metrics:
                    del self.aggregated_metrics[name]
        
        debug_logger.log_event(
            'metrics_cleanup',
            'Limpeza de métricas antigas',
            {
                'max_age': max_age,
                'metrics_removed': metrics_removed,
                'remaining_metrics': sum(len(m) for m in self.metrics.values())
            }
        )

# Instância global do gerenciador de métricas
metrics_manager = MetricsManager()