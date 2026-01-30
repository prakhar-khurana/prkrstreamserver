from pydantic import BaseModel, Field
from typing import Dict


class TopicCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TopicResponse(BaseModel):
    name: str
    created: bool = True


class TopicStats(BaseModel):
    message_count: int
    subscriber_count: int


class StatsResponse(BaseModel):
    topics: Dict[str, TopicStats]


class HealthResponse(BaseModel):
    status: str = "healthy"
    uptime_seconds: float
    topic_count: int
    active_subscriber_count: int


# Metrics models for observability dashboard
class LatencyMetrics(BaseModel):
    avg: float = 0.0
    p95: float = 0.0
    p99: float = 0.0


class TopicMetrics(BaseModel):
    queue_depth: int = 0
    queue_max_size: int = 10000
    batch_size_avg: float = 0.0
    messages_published: int = 0
    messages_delivered: int = 0
    messages_dropped: int = 0
    subscriber_count: int = 0
    latency_ms: LatencyMetrics = LatencyMetrics()


class GlobalMetrics(BaseModel):
    active_topics: int = 0
    active_subscribers: int = 0
    total_published: int = 0
    total_delivered: int = 0
    total_dropped: int = 0


class MetricsResponse(BaseModel):
    uptime_seconds: float
    topics: Dict[str, TopicMetrics]
    global_metrics: GlobalMetrics = Field(alias="global")
    
    class Config:
        populate_by_name = True
