from enum import Enum
from typing import Any, Optional, Union
from pydantic import BaseModel, Field, field_validator
from uuid import UUID


class MessageType(str, Enum):
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PUBLISH = "publish"
    PING = "ping"
    ACK = "ack"
    EVENT = "event"
    ERROR = "error"
    PONG = "pong"
    INFO = "info"


class SubscribeMessage(BaseModel):
    type: MessageType = Field(default=MessageType.SUBSCRIBE)
    topic: str = Field(..., min_length=1, max_length=255)
    last_n: Optional[int] = Field(default=0, ge=0, le=1000)


class UnsubscribeMessage(BaseModel):
    type: MessageType = Field(default=MessageType.UNSUBSCRIBE)
    topic: str = Field(..., min_length=1, max_length=255)


class PublishMessage(BaseModel):
    type: MessageType = Field(default=MessageType.PUBLISH)
    topic: str = Field(..., min_length=1, max_length=255)
    data: Any


class PingMessage(BaseModel):
    type: MessageType = Field(default=MessageType.PING)


class AckMessage(BaseModel):
    type: MessageType = Field(default=MessageType.ACK)
    request_type: str
    topic: Optional[str] = None
    message: Optional[str] = None


class EventMessage(BaseModel):
    type: MessageType = Field(default=MessageType.EVENT)
    topic: str
    data: Any
    message_id: str


class ErrorMessage(BaseModel):
    type: MessageType = Field(default=MessageType.ERROR)
    code: str
    message: str
    details: Optional[dict] = None


class PongMessage(BaseModel):
    type: MessageType = Field(default=MessageType.PONG)


class InfoMessage(BaseModel):
    type: MessageType = Field(default=MessageType.INFO)
    message: str
    details: Optional[dict] = None


ClientMessage = Union[SubscribeMessage, UnsubscribeMessage, PublishMessage, PingMessage]
ServerMessage = Union[AckMessage, EventMessage, ErrorMessage, PongMessage, InfoMessage]
