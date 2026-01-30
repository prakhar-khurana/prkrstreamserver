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
