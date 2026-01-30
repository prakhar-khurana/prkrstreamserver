import asyncio
from typing import Dict, List, Optional
from uuid import UUID, uuid4
from threading import Lock
import logging
import time
from .subscriber import Subscriber
from ..utils.ring_buffer import RingBuffer

logger = logging.getLogger(__name__)


class Topic:
    """
    Represents a single topic with its own delivery worker.
    
    ARCHITECTURE CHANGE: Topic-level delivery instead of per-subscriber queues.
    
    Each topic maintains:
    - A set of subscribers
    - A ring buffer for message replay
    - An async queue for incoming messages
    - A background delivery worker that batches and fans out messages
    - Statistics (message count)
    
    BATCHING STRATEGY:
    - Messages are accumulated up to batch_size (default 10)
    - Batch is flushed when full OR after batch_timeout_ms (default 20ms)
    - Batching reduces per-message overhead and improves throughput
    
    ORDERING GUARANTEE:
    - Messages are delivered in publish order within a topic
    - Batches preserve message order
    """
    
    def __init__(self, name: str, replay_buffer_size: int = 100, 
                 batch_size: int = 10, batch_timeout_ms: int = 20,
                 send_timeout_ms: int = 500):
        self.name = name
        self._subscribers: Dict[UUID, Subscriber] = {}
        self._lock = Lock()
        self._message_buffer = RingBuffer[dict](replay_buffer_size)
        self._message_count = 0
        
        # Topic-level delivery infrastructure
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._delivery_task: Optional[asyncio.Task] = None
        self._running = False
        self._batch_size = batch_size
        self._batch_timeout_ms = batch_timeout_ms
        self._send_timeout_ms = send_timeout_ms  # Timeout for slow subscribers
        
        # Metrics tracking for observability dashboard
        self._messages_published = 0
        self._messages_delivered = 0
        self._messages_dropped = 0
        self._latencies: list = []  # Rolling window of recent latencies
        self._batch_sizes: list = []  # Rolling window of batch sizes
        self._max_metrics_samples = 1000  # Keep last N samples
    
    def add_subscriber(self, subscriber: Subscriber) -> None:
        with self._lock:
            self._subscribers[subscriber.client_id] = subscriber
            logger.info(f"Added subscriber {subscriber.client_id} to topic {self.name}")
    
    def remove_subscriber(self, client_id: UUID) -> bool:
        with self._lock:
            if client_id in self._subscribers:
                subscriber = self._subscribers.pop(client_id)
                subscriber.close()
                logger.info(f"Removed subscriber {client_id} from topic {self.name}")
                return True
            return False
    
    def get_subscriber(self, client_id: UUID) -> Optional[Subscriber]:
        with self._lock:
            return self._subscribers.get(client_id)
    
    def get_all_subscribers(self) -> List[Subscriber]:
        with self._lock:
            return list(self._subscribers.values())
    
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)
    
    def start_delivery_worker(self) -> None:
        """
        Start the topic-level delivery worker.
        Should be called after topic creation.
        """
        if not self._running:
            self._running = True
            self._delivery_task = asyncio.create_task(self._delivery_worker())
            logger.info(f"Started delivery worker for topic {self.name}")
    
    async def stop_delivery_worker(self) -> None:
        """
        Stop the delivery worker gracefully.
        Flushes pending batches before stopping.
        """
        if self._running:
            self._running = False
            if self._delivery_task:
                self._delivery_task.cancel()
                try:
                    await self._delivery_task
                except asyncio.CancelledError:
                    pass
            logger.info(f"Stopped delivery worker for topic {self.name}")
    
    async def _delivery_worker(self) -> None:
        """
        Topic-level delivery worker with batching.
        
        ALGORITHM:
        1. Accumulate messages into a batch
        2. Flush batch when:
           - Batch size reaches limit (10 messages), OR
           - Timeout expires (20ms), OR
           - Queue is empty and batch has messages
        3. Fan out batch to all subscribers concurrently
        4. Remove failed subscribers
        
        LATENCY OPTIMIZATION:
        - Batching reduces per-message overhead
        - Concurrent fan-out to all subscribers
        - No locks held during WebSocket sends
        """
        batch = []
        last_flush_time = time.time()
        
        while self._running:
            try:
                # Calculate timeout for next message
                elapsed_ms = (time.time() - last_flush_time) * 1000
                timeout = max(0.001, (self._batch_timeout_ms - elapsed_ms) / 1000)
                
                try:
                    # Try to get a message with timeout
                    message = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=timeout
                    )
                    batch.append(message)
                except asyncio.TimeoutError:
                    # Timeout expired, flush if we have messages
                    if batch:
                        await self._flush_batch(batch)
                        batch = []
                        last_flush_time = time.time()
                    continue
                
                # Check if batch is full
                if len(batch) >= self._batch_size:
                    await self._flush_batch(batch)
                    batch = []
                    last_flush_time = time.time()
            
            except asyncio.CancelledError:
                # Flush remaining messages on shutdown
                if batch:
                    await self._flush_batch(batch)
                break
            except Exception as e:
                logger.error(f"Error in delivery worker for {self.name}: {e}")
                await asyncio.sleep(0.1)
    
    async def _flush_batch(self, batch: List[dict]) -> None:
        """
        Flush a batch of messages to all subscribers CONCURRENTLY.
        
        CRITICAL FIX: Use asyncio.gather for TRUE concurrent fan-out.
        Previous implementation awaited tasks sequentially which blocked.
        
        CONCURRENCY:
        - Get subscriber snapshot without holding lock during sends
        - Fan out to ALL subscribers in parallel using asyncio.gather
        - Each send has a timeout to detect slow subscribers
        - Remove failed/slow subscribers after delivery
        
        BACKPRESSURE:
        - If subscriber send fails or times out, it's disconnected
        - Slow subscribers don't block other subscribers
        - Publishers are never blocked
        """
        if not batch:
            return
        
        # Track batch size for metrics
        with self._lock:
            self._batch_sizes.append(len(batch))
            if len(self._batch_sizes) > self._max_metrics_samples:
                self._batch_sizes = self._batch_sizes[-self._max_metrics_samples:]
        
        # Get subscriber snapshot (quick lock)
        with self._lock:
            subscribers = list(self._subscribers.values())
        
        if not subscribers:
            return
        
        # Create send tasks for all active subscribers
        active_subscribers = [s for s in subscribers if not s.is_closed()]
        if not active_subscribers:
            return
        
        # Fan out CONCURRENTLY to all subscribers using asyncio.gather
        # Each send has a timeout to detect slow subscribers
        tasks = [
            self._send_with_timeout(subscriber, batch)
            for subscriber in active_subscribers
        ]
        
        # Wait for ALL sends to complete concurrently (not sequentially!)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calculate latency for this batch
        delivery_time = time.time()
        for msg in batch:
            publish_time = msg.get("_publish_time")
            if publish_time:
                latency_ms = (delivery_time - publish_time) * 1000
                with self._lock:
                    self._latencies.append(latency_ms)
                    if len(self._latencies) > self._max_metrics_samples:
                        self._latencies = self._latencies[-self._max_metrics_samples:]
        
        # Process results and remove failed subscribers
        successful_deliveries = 0
        for subscriber, result in zip(active_subscribers, results):
            if isinstance(result, Exception):
                logger.warning(f"Subscriber {subscriber.client_id} failed: {result}")
                self.remove_subscriber(subscriber.client_id)
            elif result is False:
                # Send failed or timed out
                self.remove_subscriber(subscriber.client_id)
            else:
                successful_deliveries += 1
        
        # Update delivered count (messages * successful subscribers)
        with self._lock:
            self._messages_delivered += len(batch) * successful_deliveries
    
    async def _send_with_timeout(self, subscriber: Subscriber, batch: List[dict]) -> bool:
        """
        Send a batch to a subscriber with timeout.
        
        SLOW CONSUMER DETECTION:
        - If send takes longer than send_timeout_ms, subscriber is considered slow
        - Slow subscribers are disconnected to prevent blocking
        - This ensures low latency for healthy subscribers
        
        Returns True on success, False on failure/timeout.
        """
        try:
            return await asyncio.wait_for(
                subscriber.send_batch(batch),
                timeout=self._send_timeout_ms / 1000.0
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Subscriber {subscriber.client_id} too slow, disconnecting "
                f"(timeout: {self._send_timeout_ms}ms)"
            )
            subscriber.close()
            return False
        except Exception as e:
            logger.error(f"Error sending to {subscriber.client_id}: {e}")
            subscriber.close()
            return False
    
    def publish_message(self, data: any, message_id: str) -> int:
        """
        Publish a message to the topic.
        
        IMPORTANT: Publishers are never blocked.
        Messages are enqueued to the topic's async queue.
        The delivery worker handles batching and fan-out.
        
        Returns the current subscriber count (not delivery count,
        since delivery is now async).
        """
        message = {
            "type": "event",
            "topic": self.name,
            "data": data,
            "message_id": message_id,
            "_publish_time": time.time()  # For latency tracking
        }
        
        # Add to replay buffer and update stats
        with self._lock:
            self._message_buffer.append(message)
            self._message_count += 1
            self._messages_published += 1
            subscriber_count = len(self._subscribers)
        
        # Enqueue for async delivery (non-blocking)
        try:
            self._message_queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning(f"Topic {self.name} message queue full, dropping message")
            with self._lock:
                self._messages_dropped += 1
        
        return subscriber_count
    
    def get_replay_messages(self, last_n: int) -> List[dict]:
        return self._message_buffer.get_last_n(last_n)
    
    def get_message_count(self) -> int:
        with self._lock:
            return self._message_count
    
    def get_metrics(self) -> dict:
        """
        Get detailed metrics for this topic.
        Used by the observability dashboard via /metrics endpoint.
        
        Returns:
            Dict with queue_depth, batch_size_avg, message counts, and latency percentiles.
        """
        with self._lock:
            # Calculate latency percentiles
            latencies = self._latencies[-self._max_metrics_samples:]
            if latencies:
                sorted_latencies = sorted(latencies)
                avg_latency = sum(latencies) / len(latencies)
                p95_idx = min(int(len(sorted_latencies) * 0.95), len(sorted_latencies) - 1)
                p99_idx = min(int(len(sorted_latencies) * 0.99), len(sorted_latencies) - 1)
                p95_latency = sorted_latencies[p95_idx]
                p99_latency = sorted_latencies[p99_idx]
            else:
                avg_latency = 0.0
                p95_latency = 0.0
                p99_latency = 0.0
            
            # Calculate batch size average
            batch_sizes = self._batch_sizes[-self._max_metrics_samples:]
            batch_size_avg = sum(batch_sizes) / len(batch_sizes) if batch_sizes else 0.0
            
            return {
                "queue_depth": self._message_queue.qsize(),
                "queue_max_size": self._message_queue.maxsize,
                "batch_size_avg": round(batch_size_avg, 2),
                "messages_published": self._messages_published,
                "messages_delivered": self._messages_delivered,
                "messages_dropped": self._messages_dropped,
                "subscriber_count": len(self._subscribers),
                "latency_ms": {
                    "avg": round(avg_latency, 2),
                    "p95": round(p95_latency, 2),
                    "p99": round(p99_latency, 2)
                }
            }
    
    async def close_all_subscribers(self) -> None:
        """Called when topic is being deleted."""
        # Stop delivery worker first
        await self.stop_delivery_worker()
        
        # Close all subscribers
        with self._lock:
            for subscriber in self._subscribers.values():
                subscriber.close()
            self._subscribers.clear()


class TopicManager:
    """
    Manages all topics in the system.
    
    CONCURRENCY STRATEGY:
    - Global lock only for topic creation/deletion
    - Each topic has its own lock for subscriber operations
    - No global locks during message publishing
    """
    
    def __init__(self, replay_buffer_size: int = 100):
        self._topics: Dict[str, Topic] = {}
        self._global_lock = Lock()
        self._replay_buffer_size = replay_buffer_size
        logger.info("TopicManager initialized")
    
    def create_topic(self, name: str) -> bool:
        """
        Create a new topic and start its delivery worker.
        Idempotent - returns True even if topic exists.
        """
        with self._global_lock:
            if name not in self._topics:
                topic = Topic(name, self._replay_buffer_size)
                self._topics[name] = topic
                # Start the topic's delivery worker
                topic.start_delivery_worker()
                logger.info(f"Created topic: {name}")
                return True
            return True
    
    async def delete_topic(self, name: str) -> bool:
        """
        Delete a topic and notify all subscribers.
        
        RACE CONDITION PREVENTION:
        1. Remove topic from registry first
        2. Stop delivery worker and close all subscribers
        3. Clean up resources
        """
        with self._global_lock:
            if name not in self._topics:
                return False
            
            topic = self._topics.pop(name)
        
        # Stop delivery worker and close subscribers (async)
        await topic.close_all_subscribers()
        logger.info(f"Deleted topic: {name}")
        return True
    
    def get_topic(self, name: str) -> Optional[Topic]:
        with self._global_lock:
            return self._topics.get(name)
    
    def topic_exists(self, name: str) -> bool:
        with self._global_lock:
            return name in self._topics
    
    def list_topics(self) -> List[str]:
        with self._global_lock:
            return list(self._topics.keys())
    
    def get_all_topics(self) -> Dict[str, Topic]:
        with self._global_lock:
            return dict(self._topics)
    
    def subscribe(
        self,
        topic_name: str,
        client_id: UUID,
        websocket: any,
        last_n: int = 0
    ) -> Optional[List[dict]]:
        """
        Subscribe a client to a topic.
        
        Returns replay messages if last_n > 0, None if topic doesn't exist.
        """
        topic = self.get_topic(topic_name)
        if not topic:
            return None
        
        subscriber = Subscriber(client_id, topic_name, websocket)
        topic.add_subscriber(subscriber)
        
        if last_n > 0:
            return topic.get_replay_messages(last_n)
        return []
    
    def unsubscribe(self, topic_name: str, client_id: UUID) -> bool:
        """
        Unsubscribe a client from a topic.
        """
        topic = self.get_topic(topic_name)
        if not topic:
            return False
        
        return topic.remove_subscriber(client_id)
    
    def publish(self, topic_name: str, data: any) -> Optional[int]:
        """
        Publish a message to a topic.
        
        Returns number of subscribers that received the message,
        or None if topic doesn't exist.
        """
        topic = self.get_topic(topic_name)
        if not topic:
            return None
        
        message_id = str(uuid4())
        return topic.publish_message(data, message_id)
    
    def get_stats(self) -> Dict[str, dict]:
        """
        Get statistics for all topics.
        Thread-safe snapshot of current state.
        """
        with self._global_lock:
            topics_snapshot = dict(self._topics)
        
        stats = {}
        for name, topic in topics_snapshot.items():
            stats[name] = {
                "message_count": topic.get_message_count(),
                "subscriber_count": topic.subscriber_count()
            }
        
        return stats
    
    def get_all_metrics(self) -> Dict[str, any]:
        """
        Get detailed metrics for all topics and global aggregates.
        Used by the observability dashboard.
        
        Returns a structure suitable for the /metrics endpoint:
        {
            "topics": { topic_name: topic_metrics, ... },
            "global": { aggregated stats }
        }
        """
        with self._global_lock:
            topics_snapshot = dict(self._topics)
        
        topics_metrics = {}
        total_published = 0
        total_delivered = 0
        total_dropped = 0
        total_subscribers = 0
        
        for name, topic in topics_snapshot.items():
            metrics = topic.get_metrics()
            topics_metrics[name] = metrics
            
            # Aggregate global stats
            total_published += metrics.get("messages_published", 0)
            total_delivered += metrics.get("messages_delivered", 0)
            total_dropped += metrics.get("messages_dropped", 0)
            total_subscribers += metrics.get("subscriber_count", 0)
        
        return {
            "topics": topics_metrics,
            "global": {
                "active_topics": len(topics_snapshot),
                "active_subscribers": total_subscribers,
                "total_published": total_published,
                "total_delivered": total_delivered,
                "total_dropped": total_dropped
            }
        }
    
    def get_total_subscriber_count(self) -> int:
        """
        Get total number of active subscribers across all topics.
        """
        with self._global_lock:
            topics_snapshot = list(self._topics.values())
        
        return sum(topic.subscriber_count() for topic in topics_snapshot)
    
    def cleanup_subscriber(self, client_id: UUID) -> None:
        """
        Remove a subscriber from all topics.
        Called on WebSocket disconnect.
        """
        with self._global_lock:
            topics_snapshot = list(self._topics.values())
        
        for topic in topics_snapshot:
            topic.remove_subscriber(client_id)
        
        logger.info(f"Cleaned up subscriber {client_id} from all topics")
    
    async def shutdown_all_topics(self) -> None:
        """
        Shutdown all topic delivery workers.
        Called during graceful shutdown.
        """
        with self._global_lock:
            topics_snapshot = list(self._topics.values())
        
        # Stop all delivery workers concurrently
        tasks = [topic.stop_delivery_worker() for topic in topics_snapshot]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("All topic delivery workers stopped")
