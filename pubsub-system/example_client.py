import asyncio
import websockets
import json
import requests
from typing import Optional


class PubSubClient:
    """
    Example client for the Pub/Sub system.
    Demonstrates how to interact with the WebSocket API.
    """
    
    def __init__(self, ws_url: str = "ws://localhost:8000/ws", api_url: str = "http://localhost:8000"):
        self.ws_url = ws_url
        self.api_url = api_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
    
    async def connect(self):
        """Connect to the WebSocket server."""
        self.websocket = await websockets.connect(self.ws_url)
        print(f"Connected to {self.ws_url}")
        
        info_msg = await self.websocket.recv()
        print(f"Server info: {info_msg}")
    
    async def subscribe(self, topic: str, last_n: int = 0):
        """Subscribe to a topic."""
        if not self.websocket:
            raise RuntimeError("Not connected")
        
        message = {
            "type": "subscribe",
            "topic": topic,
            "last_n": last_n
        }
        await self.websocket.send(json.dumps(message))
        print(f"Subscribed to topic: {topic}")
        
        response = await self.websocket.recv()
        print(f"Subscribe response: {response}")
    
    async def unsubscribe(self, topic: str):
        """Unsubscribe from a topic."""
        if not self.websocket:
            raise RuntimeError("Not connected")
        
        message = {
            "type": "unsubscribe",
            "topic": topic
        }
        await self.websocket.send(json.dumps(message))
        print(f"Unsubscribed from topic: {topic}")
        
        response = await self.websocket.recv()
        print(f"Unsubscribe response: {response}")
    
    async def publish(self, topic: str, data: any):
        """Publish a message to a topic."""
        if not self.websocket:
            raise RuntimeError("Not connected")
        
        message = {
            "type": "publish",
            "topic": topic,
            "data": data
        }
        await self.websocket.send(json.dumps(message))
        print(f"Published to topic: {topic}")
        
        response = await self.websocket.recv()
        print(f"Publish response: {response}")
    
    async def ping(self):
        """Send a ping to the server."""
        if not self.websocket:
            raise RuntimeError("Not connected")
        
        message = {"type": "ping"}
        await self.websocket.send(json.dumps(message))
        
        response = await self.websocket.recv()
        print(f"Ping response: {response}")
    
    async def listen(self):
        """Listen for incoming messages."""
        if not self.websocket:
            raise RuntimeError("Not connected")
        
        try:
            async for message in self.websocket:
                data = json.loads(message)
                if data.get("type") == "event":
                    print(f"\n📨 Received event:")
                    print(f"   Topic: {data['topic']}")
                    print(f"   Data: {data['data']}")
                    print(f"   Message ID: {data['message_id']}\n")
                else:
                    print(f"Received: {message}")
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")
    
    async def close(self):
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            print("Disconnected")
    
    def create_topic(self, name: str):
        """Create a topic via REST API."""
        response = requests.post(
            f"{self.api_url}/topics",
            json={"name": name}
        )
        if response.status_code == 201:
            print(f"✅ Created topic: {name}")
        else:
            print(f"❌ Failed to create topic: {response.text}")
        return response
    
    def delete_topic(self, name: str):
        """Delete a topic via REST API."""
        response = requests.delete(f"{self.api_url}/topics/{name}")
        if response.status_code == 204:
            print(f"✅ Deleted topic: {name}")
        else:
            print(f"❌ Failed to delete topic: {response.text}")
        return response
    
    def list_topics(self):
        """List all topics via REST API."""
        response = requests.get(f"{self.api_url}/topics")
        if response.status_code == 200:
            topics = response.json()
            print(f"📋 Topics: {topics}")
            return topics
        else:
            print(f"❌ Failed to list topics: {response.text}")
        return []
    
    def get_health(self):
        """Get health status via REST API."""
        response = requests.get(f"{self.api_url}/health")
        if response.status_code == 200:
            health = response.json()
            print(f"💚 Health: {json.dumps(health, indent=2)}")
            return health
        else:
            print(f"❌ Failed to get health: {response.text}")
        return None
    
    def get_stats(self):
        """Get statistics via REST API."""
        response = requests.get(f"{self.api_url}/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"📊 Stats: {json.dumps(stats, indent=2)}")
            return stats
        else:
            print(f"❌ Failed to get stats: {response.text}")
        return None


async def example_publisher():
    """Example: Publisher that sends messages to a topic."""
    client = PubSubClient()
    
    client.create_topic("news")
    
    await client.connect()
    
    for i in range(5):
        await client.publish("news", {
            "headline": f"Breaking News #{i}",
            "content": f"This is news item number {i}"
        })
        await asyncio.sleep(1)
    
    await client.close()


async def example_subscriber():
    """Example: Subscriber that listens to a topic."""
    client = PubSubClient()
    
    client.create_topic("news")
    
    await client.connect()
    
    await client.subscribe("news", last_n=5)
    
    await client.listen()


async def example_full_workflow():
    """Example: Complete workflow with REST API and WebSocket."""
    client = PubSubClient()
    
    print("\n=== Step 1: Create topics ===")
    client.create_topic("events")
    client.create_topic("alerts")
    
    print("\n=== Step 2: List topics ===")
    client.list_topics()
    
    print("\n=== Step 3: Check health ===")
    client.get_health()
    
    print("\n=== Step 4: Connect WebSocket ===")
    await client.connect()
    
    print("\n=== Step 5: Subscribe to topics ===")
    await client.subscribe("events", last_n=0)
    await client.subscribe("alerts", last_n=0)
    
    print("\n=== Step 6: Publish messages ===")
    await client.publish("events", {"type": "user_login", "user_id": 123})
    await client.publish("alerts", {"level": "warning", "message": "High CPU usage"})
    
    print("\n=== Step 7: Ping server ===")
    await client.ping()
    
    print("\n=== Step 8: Get stats ===")
    client.get_stats()
    
    print("\n=== Step 9: Unsubscribe ===")
    await client.unsubscribe("alerts")
    
    print("\n=== Step 10: Publish more messages ===")
    await client.publish("events", {"type": "user_logout", "user_id": 123})
    await client.publish("alerts", {"level": "info", "message": "System normal"})
    
    await asyncio.sleep(1)
    
    print("\n=== Step 11: Close connection ===")
    await client.close()
    
    print("\n=== Step 12: Delete topics ===")
    client.delete_topic("events")
    client.delete_topic("alerts")


async def example_replay():
    """Example: Message replay with last_n."""
    client = PubSubClient()
    
    print("\n=== Setup: Create topic and publish messages ===")
    client.create_topic("history")
    
    await client.connect()
    
    for i in range(10):
        await client.publish("history", {"message": f"Historical message {i}"})
    
    await client.close()
    
    print("\n=== Test: Subscribe with replay ===")
    await client.connect()
    await client.subscribe("history", last_n=5)
    
    await asyncio.sleep(2)
    
    await client.close()
    client.delete_topic("history")


if __name__ == "__main__":
    print("Pub/Sub Client Examples\n")
    print("Choose an example to run:")
    print("1. Full workflow")
    print("2. Publisher")
    print("3. Subscriber")
    print("4. Message replay")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        asyncio.run(example_full_workflow())
    elif choice == "2":
        asyncio.run(example_publisher())
    elif choice == "3":
        asyncio.run(example_subscriber())
    elif choice == "4":
        asyncio.run(example_replay())
    else:
        print("Invalid choice")
