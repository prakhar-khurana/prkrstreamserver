import asyncio
import json
from typing import Optional
from uuid import UUID, uuid4
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError
import logging

from ..models.messages import (
    SubscribeMessage,
    UnsubscribeMessage,
    PublishMessage,
    PingMessage,
    MessageType,
)
from ..topics.topic_manager import TopicManager

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """
    Handles WebSocket connections and message routing.
    
    Each WebSocket connection gets:
    - A unique client_id
    - A message processing loop
    - A message delivery loop (for queued messages)
    """
    
    def __init__(self, topic_manager: TopicManager):
        self.topic_manager = topic_manager
    
    async def handle_connection(self, websocket: WebSocket) -> None:
        """
        Main entry point for WebSocket connections.
        """
        await websocket.accept()
        client_id = uuid4()
        
        logger.info(f"WebSocket connected: {client_id}")
        
        try:
            await self._send_info(
                websocket,
                f"Connected with client_id: {client_id}"
            )
            
            # Only need receive loop now - topic workers handle delivery
            await self._receive_loop(websocket, client_id)
        
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {client_id}")
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {e}")
        finally:
            self.topic_manager.cleanup_subscriber(client_id)
            try:
                await websocket.close()
            except:
                pass
    
    async def _receive_loop(self, websocket: WebSocket, client_id: UUID) -> None:
        """
        Receive and process messages from the client.
        """
        while True:
            try:
                data = await websocket.receive_text()
                await self._handle_message(websocket, client_id, data)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in receive loop for {client_id}: {e}")
                await self._send_error(
                    websocket,
                    "INTERNAL",
                    "Internal server error"
                )
    
    # REMOVED: Per-subscriber send loop no longer needed.
    # Topic-level delivery workers now handle batching and fan-out.
    
    async def _handle_message(
        self,
        websocket: WebSocket,
        client_id: UUID,
        raw_message: str
    ) -> None:
        """
        Parse and route incoming messages.
        """
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send_error(
                websocket,
                "INVALID_JSON",
                "Message must be valid JSON"
            )
            return
        
        if not isinstance(data, dict) or "type" not in data:
            await self._send_error(
                websocket,
                "INVALID_MESSAGE",
                "Message must have a 'type' field"
            )
            return
        
        message_type = data.get("type")
        
        try:
            if message_type == MessageType.SUBSCRIBE:
                await self._handle_subscribe(websocket, client_id, data)
            elif message_type == MessageType.UNSUBSCRIBE:
                await self._handle_unsubscribe(websocket, client_id, data)
            elif message_type == MessageType.PUBLISH:
                await self._handle_publish(websocket, client_id, data)
            elif message_type == MessageType.PING:
                await self._handle_ping(websocket, client_id, data)
            else:
                await self._send_error(
                    websocket,
                    "UNKNOWN_MESSAGE_TYPE",
                    f"Unknown message type: {message_type}"
                )
        except ValidationError as e:
            await self._send_error(
                websocket,
                "VALIDATION_ERROR",
                "Invalid message format",
                {"errors": e.errors()}
            )
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await self._send_error(
                websocket,
                "INTERNAL",
                "Internal server error"
            )
    
    async def _handle_subscribe(
        self,
        websocket: WebSocket,
        client_id: UUID,
        data: dict
    ) -> None:
        """
        Handle subscribe message.
        """
        msg = SubscribeMessage(**data)
        
        if not self.topic_manager.topic_exists(msg.topic):
            await self._send_error(
                websocket,
                "TOPIC_NOT_FOUND",
                f"Topic '{msg.topic}' does not exist"
            )
            return
        
        replay_messages = self.topic_manager.subscribe(
            msg.topic,
            client_id,
            websocket,
            msg.last_n or 0
        )
        
        if replay_messages is None:
            await self._send_error(
                websocket,
                "SUBSCRIBE_FAILED",
                f"Failed to subscribe to topic '{msg.topic}'"
            )
            return
        
        await self._send_ack(
            websocket,
            "subscribe",
            msg.topic,
            f"Subscribed to topic '{msg.topic}'"
        )
        
        if replay_messages:
            for replay_msg in replay_messages:
                await websocket.send_json(replay_msg)
    
    async def _handle_unsubscribe(
        self,
        websocket: WebSocket,
        client_id: UUID,
        data: dict
    ) -> None:
        """
        Handle unsubscribe message.
        """
        msg = UnsubscribeMessage(**data)
        
        success = self.topic_manager.unsubscribe(msg.topic, client_id)
        
        if success:
            await self._send_ack(
                websocket,
                "unsubscribe",
                msg.topic,
                f"Unsubscribed from topic '{msg.topic}'"
            )
        else:
            await self._send_error(
                websocket,
                "NOT_SUBSCRIBED",
                f"Not subscribed to topic '{msg.topic}'"
            )
    
    async def _handle_publish(
        self,
        websocket: WebSocket,
        client_id: UUID,
        data: dict
    ) -> None:
        """
        Handle publish message.
        """
        msg = PublishMessage(**data)
        
        subscriber_count = self.topic_manager.publish(msg.topic, msg.data)
        
        if subscriber_count is None:
            await self._send_error(
                websocket,
                "TOPIC_NOT_FOUND",
                f"Topic '{msg.topic}' does not exist"
            )
            return
        
        await self._send_ack(
            websocket,
            "publish",
            msg.topic,
            f"Published to {subscriber_count} subscriber(s)"
        )
    
    async def _handle_ping(
        self,
        websocket: WebSocket,
        client_id: UUID,
        data: dict
    ) -> None:
        """
        Handle ping message.
        """
        msg = PingMessage(**data)
        await websocket.send_json({"type": "pong"})
    
    async def _send_ack(
        self,
        websocket: WebSocket,
        request_type: str,
        topic: Optional[str],
        message: str
    ) -> None:
        """
        Send acknowledgment message.
        """
        await websocket.send_json({
            "type": "ack",
            "request_type": request_type,
            "topic": topic,
            "message": message
        })
    
    async def _send_error(
        self,
        websocket: WebSocket,
        code: str,
        message: str,
        details: Optional[dict] = None
    ) -> None:
        """
        Send error message.
        """
        error_msg = {
            "type": "error",
            "code": code,
            "message": message
        }
        if details:
            error_msg["details"] = details
        
        await websocket.send_json(error_msg)
    
    async def _send_info(
        self,
        websocket: WebSocket,
        message: str,
        details: Optional[dict] = None
    ) -> None:
        """
        Send info message.
        """
        info_msg = {
            "type": "info",
            "message": message
        }
        if details:
            info_msg["details"] = details
        
        await websocket.send_json(info_msg)
