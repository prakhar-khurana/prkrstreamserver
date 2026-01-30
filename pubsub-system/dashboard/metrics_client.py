"""
Metrics HTTP Client for Pub/Sub Observability Dashboard.

This module provides a simple HTTP client to fetch metrics from the backend.
All requests are read-only and do not modify any state.

IMPORTANT: This client does NOT use WebSockets.
"""

import requests
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Backend configuration
DEFAULT_BACKEND_URL = "http://localhost:8000"


class MetricsClient:
    """
    HTTP client for fetching metrics from the Pub/Sub backend.
    
    READ-ONLY: This client never modifies backend state.
    """
    
    def __init__(self, base_url: str = DEFAULT_BACKEND_URL, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
    
    def fetch_health(self) -> Optional[Dict[str, Any]]:
        """
        Fetch health status from GET /health.
        
        Returns:
            Health data dict or None if request fails.
        """
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch health: {e}")
            return None
    
    def fetch_stats(self) -> Optional[Dict[str, Any]]:
        """
        Fetch basic stats from GET /stats.
        
        Returns:
            Stats data dict or None if request fails.
        """
        try:
            response = requests.get(
                f"{self.base_url}/stats",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch stats: {e}")
            return None
    
    def fetch_metrics(self) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed metrics from GET /metrics.
        
        Returns:
            Full metrics data dict or None if request fails.
            
        Expected structure:
        {
            "uptime_seconds": float,
            "topics": {
                "topic_name": {
                    "queue_depth": int,
                    "queue_max_size": int,
                    "batch_size_avg": float,
                    "messages_published": int,
                    "messages_delivered": int,
                    "messages_dropped": int,
                    "subscriber_count": int,
                    "latency_ms": {
                        "avg": float,
                        "p95": float,
                        "p99": float
                    }
                }
            },
            "global": {
                "active_topics": int,
                "active_subscribers": int,
                "total_published": int,
                "total_delivered": int,
                "total_dropped": int
            }
        }
        """
        try:
            response = requests.get(
                f"{self.base_url}/metrics",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch metrics: {e}")
            return None
    
    def fetch_topics(self) -> Optional[list]:
        """
        Fetch list of topics from GET /topics.
        
        Returns:
            List of topic names or None if request fails.
        """
        try:
            response = requests.get(
                f"{self.base_url}/topics",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch topics: {e}")
            return None
    
    def is_available(self) -> bool:
        """
        Check if the backend is available.
        
        Returns:
            True if backend responds to health check.
        """
        health = self.fetch_health()
        return health is not None and health.get("status") == "healthy"
