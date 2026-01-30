import asyncio
from typing import Any, List
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class Subscriber:
    """
    Represents a single subscriber connection.
    
    ARCHITECTURE CHANGE: Subscribers no longer manage their own queues.
    Instead, the topic-level delivery worker handles batching and delivery.
    
    Subscribers only manage:
    - WebSocket connection lifecycle
    - Batch message sending
    """
    
    def __init__(
        self,
        client_id: UUID,
        topic: str,
        websocket: Any
    ):
        self.client_id = client_id
        self.topic = topic
        self.websocket = websocket
        self._closed = False
    
    def close(self) -> None:
        """Mark subscriber as closed."""
        self._closed = True
    
    def is_closed(self) -> bool:
        """Check if subscriber is closed."""
        return self._closed
    
    async def send_batch(self, messages: List[dict]) -> bool:
        """
        Send a batch of messages to the WebSocket.
        
        Messages are sent in order within the batch.
        Returns True if all messages sent successfully, False otherwise.
        
        BACKPRESSURE: If send fails, subscriber is marked as closed
        and the topic worker will remove it.
        """
        if self._closed:
            return False
        
        try:
            # Send all messages in the batch sequentially to preserve order
            for message in messages:
                await self.websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send batch to {self.client_id}: {e}")
            self._closed = True
            return False
