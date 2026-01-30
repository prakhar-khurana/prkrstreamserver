import asyncio
import json
import time
import random
from dataclasses import dataclass
from typing import List, Dict
import websockets
import requests
from collections import defaultdict
import statistics


BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"


@dataclass
class LoadTestConfig:
    """Configuration for load testing scenarios"""
    num_topics: int = 10
    num_publishers: int = 20
    num_subscribers: int = 100
    messages_per_publisher: int = 500
    publish_rate_ms: int = 10  # Delay between publishes
    subscriber_processing_ms: int = 5  # Simulated processing time
    test_duration_seconds: int = 60
    

@dataclass
class LoadTestMetrics:
    """Metrics collected during load testing"""
    messages_published: int = 0
    messages_received: int = 0
    messages_dropped: int = 0
    publish_errors: int = 0
    subscribe_errors: int = 0
    connection_errors: int = 0
    latencies: List[float] = None
    
    def __post_init__(self):
        if self.latencies is None:
            self.latencies = []
    
    def add_latency(self, latency_ms: float):
        self.latencies.append(latency_ms)
    
    def get_stats(self) -> Dict:
        if not self.latencies:
            return {
                "messages_published": self.messages_published,
                "messages_received": self.messages_received,
                "messages_dropped": self.messages_dropped,
                "publish_errors": self.publish_errors,
                "subscribe_errors": self.subscribe_errors,
                "connection_errors": self.connection_errors,
                "latency_avg_ms": 0,
                "latency_p50_ms": 0,
                "latency_p95_ms": 0,
                "latency_p99_ms": 0,
                "latency_max_ms": 0,
            }
        
        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)
        
        return {
            "messages_published": self.messages_published,
            "messages_received": self.messages_received,
            "messages_dropped": self.messages_dropped,
            "publish_errors": self.publish_errors,
            "subscribe_errors": self.subscribe_errors,
            "connection_errors": self.connection_errors,
            "latency_avg_ms": statistics.mean(self.latencies),
            "latency_p50_ms": sorted_latencies[n // 2],
            "latency_p95_ms": sorted_latencies[int(n * 0.95)],
            "latency_p99_ms": sorted_latencies[int(n * 0.99)],
            "latency_max_ms": max(self.latencies),
        }


class LoadTester:
    """
    Realistic load testing scenarios for Pub/Sub system.
    Simulates production workloads with multiple topics, publishers, and subscribers.
    """
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.metrics = LoadTestMetrics()
        self.topics = []
        self.running = True
    
    def setup_topics(self):
        """Create test topics"""
        print(f"📋 Creating {self.config.num_topics} topics...")
        for i in range(self.config.num_topics):
            topic_name = f"load_test_topic_{i}"
            resp = requests.post(f"{BASE_URL}/topics", json={"name": topic_name})
            if resp.status_code == 201:
                self.topics.append(topic_name)
        print(f"✅ Created {len(self.topics)} topics")
    
    def cleanup_topics(self):
        """Delete test topics"""
        print(f"\n🧹 Cleaning up {len(self.topics)} topics...")
        for topic in self.topics:
            requests.delete(f"{BASE_URL}/topics/{topic}")
        print("✅ Cleanup complete")
    
    async def publisher_worker(self, publisher_id: int):
        """
        Publisher that continuously sends messages to random topics
        """
        messages_sent = 0
        errors = 0
        
        try:
            async with websockets.connect(WS_URL) as ws:
                await ws.recv()  # info message
                
                for i in range(self.config.messages_per_publisher):
                    if not self.running:
                        break
                    
                    # Pick random topic
                    topic = random.choice(self.topics)
                    
                    try:
                        message = {
                            "type": "publish",
                            "topic": topic,
                            "data": {
                                "publisher_id": publisher_id,
                                "seq": i,
                                "timestamp": time.time(),
                                "payload": f"Message {i} from publisher {publisher_id}"
                            }
                        }
                        
                        await ws.send(json.dumps(message))
                        ack = await asyncio.wait_for(ws.recv(), timeout=5)
                        
                        messages_sent += 1
                        self.metrics.messages_published += 1
                        
                        # Rate limiting
                        if self.config.publish_rate_ms > 0:
                            await asyncio.sleep(self.config.publish_rate_ms / 1000)
                    
                    except Exception as e:
                        errors += 1
                        self.metrics.publish_errors += 1
        
        except Exception as e:
            self.metrics.connection_errors += 1
            print(f"Publisher {publisher_id} connection error: {e}")
        
        return publisher_id, messages_sent, errors
    
    async def subscriber_worker(self, subscriber_id: int, topics_to_subscribe: List[str]):
        """
        Subscriber that listens to multiple topics and tracks metrics
        """
        messages_received = 0
        errors = 0
        last_seq_per_topic = defaultdict(lambda: -1)
        
        try:
            async with websockets.connect(WS_URL) as ws:
                await ws.recv()  # info message
                
                # Subscribe to assigned topics
                for topic in topics_to_subscribe:
                    try:
                        await ws.send(json.dumps({
                            "type": "subscribe",
                            "topic": topic,
                            "last_n": 0
                        }))
                        await ws.recv()  # ack
                    except Exception as e:
                        errors += 1
                        self.metrics.subscribe_errors += 1
                
                # Receive messages
                while self.running:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1)
                        data = json.loads(msg)
                        
                        if data.get("type") == "event":
                            messages_received += 1
                            self.metrics.messages_received += 1
                            
                            # Calculate latency
                            timestamp = data.get("data", {}).get("timestamp")
                            if timestamp:
                                latency = (time.time() - timestamp) * 1000  # ms
                                self.metrics.add_latency(latency)
                            
                            # Check for dropped messages
                            topic = data.get("topic")
                            seq = data.get("data", {}).get("seq", -1)
                            
                            if topic and seq >= 0:
                                expected_seq = last_seq_per_topic[topic] + 1
                                if seq > expected_seq:
                                    dropped = seq - expected_seq
                                    self.metrics.messages_dropped += dropped
                                last_seq_per_topic[topic] = seq
                            
                            # Simulate processing time
                            if self.config.subscriber_processing_ms > 0:
                                await asyncio.sleep(self.config.subscriber_processing_ms / 1000)
                    
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        errors += 1
        
        except Exception as e:
            self.metrics.connection_errors += 1
            print(f"Subscriber {subscriber_id} connection error: {e}")
        
        return subscriber_id, messages_received, errors
    
    async def monitor_system(self):
        """
        Monitor system health and stats during load test
        """
        print("\n📊 Starting system monitor...\n")
        
        while self.running:
            try:
                # Get health
                health_resp = requests.get(f"{BASE_URL}/health", timeout=2)
                if health_resp.status_code == 200:
                    health = health_resp.json()
                    
                    # Get stats
                    stats_resp = requests.get(f"{BASE_URL}/stats", timeout=2)
                    stats = stats_resp.json() if stats_resp.status_code == 200 else {}
                    
                    # Print status
                    print(f"\r⏱️  Active subscribers: {health.get('active_subscriber_count', 0)} | "
                          f"Published: {self.metrics.messages_published} | "
                          f"Received: {self.metrics.messages_received} | "
                          f"Dropped: {self.metrics.messages_dropped} | "
                          f"Errors: P={self.metrics.publish_errors} S={self.metrics.subscribe_errors} C={self.metrics.connection_errors}",
                          end="", flush=True)
                
                await asyncio.sleep(2)
            
            except Exception as e:
                pass
    
    async def run_load_test(self):
        """
        Execute the load test with configured parameters
        """
        print("\n" + "=" * 80)
        print("🔥 LOAD TEST CONFIGURATION")
        print("=" * 80)
        print(f"Topics: {self.config.num_topics}")
        print(f"Publishers: {self.config.num_publishers}")
        print(f"Subscribers: {self.config.num_subscribers}")
        print(f"Messages per publisher: {self.config.messages_per_publisher}")
        print(f"Publish rate: {self.config.publish_rate_ms}ms")
        print(f"Subscriber processing: {self.config.subscriber_processing_ms}ms")
        print("=" * 80 + "\n")
        
        # Setup
        self.setup_topics()
        
        # Assign topics to subscribers (each subscriber gets 2-3 topics)
        subscriber_topics = []
        for i in range(self.config.num_subscribers):
            num_topics_to_sub = random.randint(2, min(3, len(self.topics)))
            topics = random.sample(self.topics, num_topics_to_sub)
            subscriber_topics.append(topics)
        
        print(f"🚀 Starting load test...")
        start_time = time.time()
        
        # Start monitor
        monitor_task = asyncio.create_task(self.monitor_system())
        
        # Start subscribers first
        print(f"📡 Starting {self.config.num_subscribers} subscribers...")
        subscriber_tasks = [
            asyncio.create_task(self.subscriber_worker(i, subscriber_topics[i]))
            for i in range(self.config.num_subscribers)
        ]
        
        await asyncio.sleep(2)  # Let subscribers connect
        
        # Start publishers
        print(f"📤 Starting {self.config.num_publishers} publishers...")
        publisher_tasks = [
            asyncio.create_task(self.publisher_worker(i))
            for i in range(self.config.num_publishers)
        ]
        
        # Wait for publishers to finish or timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*publisher_tasks, return_exceptions=True),
                timeout=self.config.test_duration_seconds
            )
        except asyncio.TimeoutError:
            print("\n⏰ Test duration reached")
        
        # Let subscribers drain their queues
        print("\n⏳ Draining subscriber queues...")
        await asyncio.sleep(5)
        
        # Stop everything
        self.running = False
        monitor_task.cancel()
        
        for task in subscriber_tasks:
            task.cancel()
        
        await asyncio.gather(*subscriber_tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        # Cleanup
        self.cleanup_topics()
        
        # Print results
        self.print_results(elapsed)
    
    def print_results(self, elapsed_time: float):
        """Print detailed test results"""
        stats = self.metrics.get_stats()
        
        print("\n" + "=" * 80)
        print("📊 LOAD TEST RESULTS")
        print("=" * 80)
        
        print(f"\n⏱️  Duration: {elapsed_time:.2f}s")
        
        print(f"\n📨 Messages:")
        print(f"  Published: {stats['messages_published']:,}")
        print(f"  Received: {stats['messages_received']:,}")
        print(f"  Dropped: {stats['messages_dropped']:,} ({stats['messages_dropped']/max(stats['messages_published'],1)*100:.2f}%)")
        
        print(f"\n🚀 Throughput:")
        pub_throughput = stats['messages_published'] / elapsed_time
        recv_throughput = stats['messages_received'] / elapsed_time
        print(f"  Published: {pub_throughput:,.0f} msg/s")
        print(f"  Received: {recv_throughput:,.0f} msg/s")
        
        print(f"\n⚡ Latency:")
        print(f"  Average: {stats['latency_avg_ms']:.2f}ms")
        print(f"  P50: {stats['latency_p50_ms']:.2f}ms")
        print(f"  P95: {stats['latency_p95_ms']:.2f}ms")
        print(f"  P99: {stats['latency_p99_ms']:.2f}ms")
        print(f"  Max: {stats['latency_max_ms']:.2f}ms")
        
        print(f"\n❌ Errors:")
        print(f"  Publish errors: {stats['publish_errors']}")
        print(f"  Subscribe errors: {stats['subscribe_errors']}")
        print(f"  Connection errors: {stats['connection_errors']}")
        
        # Health check
        print(f"\n🏥 System Health:")
        try:
            health = requests.get(f"{BASE_URL}/health", timeout=5).json()
            print(f"  Status: {health.get('status', 'unknown')}")
            print(f"  Active subscribers: {health.get('active_subscriber_count', 0)}")
            print(f"  Topics: {health.get('topic_count', 0)}")
        except:
            print("  Unable to get health status")
        
        print("\n" + "=" * 80)
        
        # Verdict
        success_rate = (stats['messages_received'] / max(stats['messages_published'], 1)) * 100
        error_rate = (stats['publish_errors'] + stats['subscribe_errors']) / max(stats['messages_published'], 1) * 100
        
        print(f"\n🎯 Overall Performance:")
        print(f"  Message delivery rate: {success_rate:.2f}%")
        print(f"  Error rate: {error_rate:.2f}%")
        
        if success_rate > 95 and error_rate < 1 and stats['latency_p99_ms'] < 100:
            print(f"  Verdict: ✅ EXCELLENT - System handled load well")
        elif success_rate > 90 and error_rate < 5 and stats['latency_p99_ms'] < 200:
            print(f"  Verdict: ✅ GOOD - System performed adequately")
        elif success_rate > 80:
            print(f"  Verdict: ⚠️  ACCEPTABLE - Some performance degradation")
        else:
            print(f"  Verdict: ❌ POOR - System struggled under load")
        
        print("=" * 80 + "\n")


async def run_scenario(name: str, config: LoadTestConfig):
    """Run a specific load test scenario"""
    print("\n" + "🎬" * 40)
    print(f"SCENARIO: {name}")
    print("🎬" * 40)
    
    tester = LoadTester(config)
    await tester.run_load_test()


async def main():
    print("⚠️  Make sure the server is running on http://localhost:8000")
    print("   Start it with: ./run.sh\n")
    
    print("Choose a load test scenario:")
    print("1. Light Load (Quick test)")
    print("2. Medium Load (Realistic production)")
    print("3. Heavy Load (Stress test)")
    print("4. Extreme Load (Breaking point)")
    print("5. Custom configuration")
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    if choice == "1":
        config = LoadTestConfig(
            num_topics=5,
            num_publishers=10,
            num_subscribers=20,
            messages_per_publisher=100,
            publish_rate_ms=20,
            subscriber_processing_ms=5,
            test_duration_seconds=30
        )
        await run_scenario("Light Load", config)
    
    elif choice == "2":
        config = LoadTestConfig(
            num_topics=10,
            num_publishers=20,
            num_subscribers=50,
            messages_per_publisher=500,
            publish_rate_ms=10,
            subscriber_processing_ms=5,
            test_duration_seconds=60
        )
        await run_scenario("Medium Load", config)
    
    elif choice == "3":
        config = LoadTestConfig(
            num_topics=20,
            num_publishers=50,
            num_subscribers=100,
            messages_per_publisher=1000,
            publish_rate_ms=5,
            subscriber_processing_ms=10,
            test_duration_seconds=120
        )
        await run_scenario("Heavy Load", config)
    
    elif choice == "4":
        config = LoadTestConfig(
            num_topics=50,
            num_publishers=100,
            num_subscribers=200,
            messages_per_publisher=2000,
            publish_rate_ms=1,
            subscriber_processing_ms=20,
            test_duration_seconds=180
        )
        await run_scenario("Extreme Load", config)
    
    elif choice == "5":
        print("\nCustom Configuration:")
        config = LoadTestConfig(
            num_topics=int(input("Number of topics: ")),
            num_publishers=int(input("Number of publishers: ")),
            num_subscribers=int(input("Number of subscribers: ")),
            messages_per_publisher=int(input("Messages per publisher: ")),
            publish_rate_ms=int(input("Publish rate (ms): ")),
            subscriber_processing_ms=int(input("Subscriber processing time (ms): ")),
            test_duration_seconds=int(input("Test duration (seconds): "))
        )
        await run_scenario("Custom Load", config)
    
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())
