"""
Metrics Collection
Prometheus-compatible metrics placeholder
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """
    Collects application metrics for observability.
    
    This is a placeholder implementation. In production, integrate with
    Prometheus/OpenTelemetry for metrics collection and export.
    
    Supports:
    - Counters (monotonically increasing values)
    - Gauges (values that can go up or down)
    - Histograms (distributions of values)
    """
    
    def __init__(self, enabled: bool = False) -> None:
        """
        Initialize metrics collector.
        
        Args:
            enabled: Whether to enable metrics collection
        """
        self.enabled = enabled
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        
        if enabled:
            logger.info("Metrics collector initialized (placeholder)")
    
    def increment_counter(self, name: str, value: float = 1.0, **labels: Any) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name (e.g., "messages_sent_total")
            value: Amount to increment by
            **labels: Metric labels (e.g., channel="whatsapp", status="success")
        """
        if not self.enabled:
            return
        
        key = self._make_key(name, labels)
        self._counters[key] += value
        
        logger.debug(
            f"Counter incremented: {name}",
            extra={"value": value, "labels": labels},
        )
    
    def set_gauge(self, name: str, value: float, **labels: Any) -> None:
        """
        Set a gauge metric to a specific value.
        
        Args:
            name: Metric name (e.g., "active_sessions")
            value: Current value
            **labels: Metric labels
        """
        if not self.enabled:
            return
        
        key = self._make_key(name, labels)
        self._gauges[key] = value
        
        logger.debug(
            f"Gauge set: {name}",
            extra={"value": value, "labels": labels},
        )
    
    def observe_histogram(self, name: str, value: float, **labels: Any) -> None:
        """
        Add an observation to a histogram metric.
        
        Args:
            name: Metric name (e.g., "response_time_seconds")
            value: Observed value
            **labels: Metric labels
        """
        if not self.enabled:
            return
        
        key = self._make_key(name, labels)
        self._histograms[key].append(value)
        
        logger.debug(
            f"Histogram observation: {name}",
            extra={"value": value, "labels": labels},
        )
    
    def get_metrics(self) -> dict[str, Any]:
        """
        Get all collected metrics (for debugging/export).
        
        Returns:
            Dictionary of all metrics
        """
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: {
                    "count": len(v),
                    "sum": sum(v),
                    "min": min(v) if v else 0,
                    "max": max(v) if v else 0,
                }
                for k, v in self._histograms.items()
            },
        }
    
    def reset_metrics(self) -> None:
        """Reset all collected metrics (for testing)."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
    
    @staticmethod
    def _make_key(name: str, labels: dict[str, Any]) -> str:
        """Create a unique key from metric name and labels."""
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}" if label_str else name


# Global metrics collector (configured at startup)
_metrics: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    """
    Get the global metrics collector instance.
    
    Returns:
        MetricsCollector instance
    """
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def configure_metrics(enabled: bool = False) -> None:
    """
    Configure the global metrics collector.
    
    Args:
        enabled: Whether to enable metrics collection
    """
    global _metrics
    _metrics = MetricsCollector(enabled=enabled)