import asyncio
import signal
import logging
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, WebSocket, HTTPException, status
from fastapi.responses import JSONResponse

from .models.api import (
    TopicCreate,
    TopicResponse,
    HealthResponse,
    StatsResponse,
    TopicStats,
)
from .topics.topic_manager import TopicManager
from .ws.handler import WebSocketHandler
from .utils.time_utils import get_current_timestamp
from .utils.validation import validate_topic_name

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PubSubApplication:
    """
    Main application state container.
    Handles graceful shutdown and lifecycle management.
    """
    
    def __init__(self):
        self.topic_manager = TopicManager(replay_buffer_size=100)
        self.ws_handler = WebSocketHandler(self.topic_manager)
        self.start_time = get_current_timestamp()
        self.shutdown_event = asyncio.Event()
        self.accepting_connections = True
        
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """
        Setup signal handlers for graceful shutdown.
        """
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self.accepting_connections = False
            asyncio.create_task(self._graceful_shutdown())
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    async def _graceful_shutdown(self) -> None:
        """
        Graceful shutdown procedure:
        1. Stop accepting new connections
        2. Stop accepting new REST operations
        3. Stop all topic delivery workers (flushes pending batches)
        4. Close all WebSockets cleanly
        """
        logger.info("Starting graceful shutdown...")
        
        self.accepting_connections = False
        
        await asyncio.sleep(0.5)
        
        # Stop all topic delivery workers (they flush pending batches)
        await self.topic_manager.shutdown_all_topics()
        
        logger.info("Graceful shutdown complete")
        self.shutdown_event.set()


app_state = PubSubApplication()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up")
    yield
    logger.info("Application shutting down")
    if not app_state.shutdown_event.is_set():
        await app_state._graceful_shutdown()


app = FastAPI(
    title="In-Memory Pub/Sub System",
    description="Production-grade in-memory Pub/Sub with WebSocket support",
    version="1.0.0",
    lifespan=lifespan
)


@app.post("/topics", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(topic: TopicCreate) -> TopicResponse:
    """
    Create a new topic.
    Idempotent - returns success even if topic already exists.
    """
    if not app_state.accepting_connections:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is shutting down"
        )
    
    if not validate_topic_name(topic.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid topic name. Use alphanumeric, underscore, hyphen, or dot only."
        )
    
    app_state.topic_manager.create_topic(topic.name)
    
    return TopicResponse(name=topic.name, created=True)


@app.delete("/topics/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(name: str) -> None:
    """
    Delete a topic and notify all subscribers.
    """
    if not app_state.accepting_connections:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is shutting down"
        )
    
    success = await app_state.topic_manager.delete_topic(name)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic '{name}' not found"
        )


@app.get("/topics", response_model=list[str])
async def list_topics() -> list[str]:
    """
    List all topics.
    """
    return app_state.topic_manager.list_topics()


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    Returns uptime, topic count, and active subscriber count.
    """
    uptime = get_current_timestamp() - app_state.start_time
    topic_count = len(app_state.topic_manager.list_topics())
    subscriber_count = app_state.topic_manager.get_total_subscriber_count()
    
    return HealthResponse(
        status="healthy",
        uptime_seconds=uptime,
        topic_count=topic_count,
        active_subscriber_count=subscriber_count
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """
    Get statistics for all topics.
    Returns per-topic message count and subscriber count.
    """
    stats_data = app_state.topic_manager.get_stats()
    
    topics_stats: Dict[str, TopicStats] = {}
    for topic_name, stats in stats_data.items():
        topics_stats[topic_name] = TopicStats(
            message_count=stats["message_count"],
            subscriber_count=stats["subscriber_count"]
        )
    
    return StatsResponse(topics=topics_stats)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Pub/Sub operations.
    
    Supported message types:
    - subscribe: Subscribe to a topic
    - unsubscribe: Unsubscribe from a topic
    - publish: Publish a message to a topic
    - ping: Ping the server
    """
    if not app_state.accepting_connections:
        await websocket.close(code=1001, reason="Server is shutting down")
        return
    
    await app_state.ws_handler.handle_connection(websocket)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler to prevent server crashes.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
