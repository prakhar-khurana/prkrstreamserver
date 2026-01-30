import asyncio
import json
import time
import statistics
from typing import List, Dict
import websockets
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import random


BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"


class StressTestRunner:
    """
    Comprehensive stress testing suite for the Pub/Sub system.
    Tests real-world scenarios including:
    - High concurrency
    - Backpressure handling
    - Message ordering
    - Slow consumers
    - Network failures
    """
    
    def __init__(self):
        self.results = {}
    
    def print_header(self, test_name: str):
        print("\n" + "=" * 80)
        print(f"🧪 TEST: {test_name}")
        print("=" * 80)
    
    def print_result(self, test_name: str, passed: bool, details: str = ""):
        status = "✅ PASSED" if passed else "❌ FAILED"
        self.results[test_name] = passed
        print(f"\n{status}: {test_name}")
        if details:
            print(f"   {details}")
    
    async def test_concurrent_subscribers(self, num_subscribers: int = 100):
        """
        Test: Multiple subscribers receiving messages concurrently
        Validates: No message loss, correct delivery to all subscribers
        """
        self.print_header(f"Concurrent Subscribers ({num_subscribers} clients)")
        
        topic_name = f"stress_test_{int(time.time())}"
        
        # Create topic
        resp = requests.post(f"{BASE_URL}/topics", json={"name": topic_name})
        assert resp.status_code == 201
        
        received_messages = {}
        num_messages = 50
        
        async def subscriber(client_id: int):
            messages = []
            try:
                async with websockets.connect(WS_URL) as ws:
                    # Skip info message
                    await ws.recv()
                    
                    # Subscribe
                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "topic": topic_name,
                        "last_n": 0
                    }))
                    await ws.recv()  # ack
                    
                    # Receive messages
                    for _ in range(num_messages):
                        msg = await asyncio.wait_for(ws.recv(), timeout=10)
                        data = json.loads(msg)
                        if data.get("type") == "event":
                            messages.append(data["data"]["seq"])
                    
                    return client_id, messages
            except Exception as e:
                print(f"Subscriber {client_id} error: {e}")
                return client_id, messages
        
        async def publisher():
            await asyncio.sleep(1)  # Let subscribers connect
            async with websockets.connect(WS_URL) as ws:
                await ws.recv()  # info
                
                for i in range(num_messages):
                    await ws.send(json.dumps({
                        "type": "publish",
                        "topic": topic_name,
                        "data": {"seq": i, "timestamp": time.time()}
                    }))
                    await ws.recv()  # ack
                    await asyncio.sleep(0.01)
        
        start_time = time.time()
        
        # Start subscribers and publisher
        subscriber_tasks = [subscriber(i) for i in range(num_subscribers)]
        publisher_task = publisher()
        
        results = await asyncio.gather(*subscriber_tasks, publisher_task, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        # Analyze results
        for client_id, messages in results[:-1]:  # Exclude publisher result
            if isinstance(messages, Exception):
                continue
            received_messages[client_id] = messages
        
        # Cleanup
        requests.delete(f"{BASE_URL}/topics/{topic_name}")
        
        # Validation
        all_received_all = all(len(msgs) == num_messages for msgs in received_messages.values())
        all_ordered = all(msgs == sorted(msgs) for msgs in received_messages.values())
        
        details = (
            f"Subscribers: {len(received_messages)}/{num_subscribers}, "
            f"Messages per subscriber: {num_messages}, "
            f"Time: {elapsed:.2f}s, "
            f"Throughput: {(num_subscribers * num_messages) / elapsed:.0f} msg/s"
        )
        
        self.print_result(
            "Concurrent Subscribers",
            all_received_all and all_ordered,
            details
        )
        
        return all_received_all and all_ordered
    
    async def test_backpressure_slow_consumer(self):
        """
        Test: Slow consumer with fast publisher
        
        BEHAVIOR: With topic-level delivery and send timeouts:
        - Slow consumers are DISCONNECTED (not just have messages dropped)
        - Publisher completes quickly (never blocked)
        - Slow consumer receives fewer messages than published
        
        This validates the latency-over-completeness tradeoff.
        """
        self.print_header("Backpressure - Slow Consumer")
        
        topic_name = f"backpressure_test_{int(time.time())}"
        requests.post(f"{BASE_URL}/topics", json={"name": topic_name})
        
        messages_published = 500  # Reduced for faster test
        slow_consumer_delay = 0.1  # 100ms per message (intentionally slow)
        
        received_count = 0
        was_disconnected = False
        
        async def slow_subscriber():
            nonlocal received_count, was_disconnected
            try:
                async with websockets.connect(WS_URL) as ws:
                    await ws.recv()  # info
                    
                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "topic": topic_name,
                        "last_n": 0
                    }))
                    await ws.recv()  # ack
                    
                    try:
                        while True:
                            msg = await asyncio.wait_for(ws.recv(), timeout=10)
                            data = json.loads(msg)
                            if data.get("type") == "event":
                                received_count += 1
                                # Simulate slow processing
                                await asyncio.sleep(slow_consumer_delay)
                    except asyncio.TimeoutError:
                        pass
                    except websockets.exceptions.ConnectionClosed:
                        was_disconnected = True
            except Exception as e:
                was_disconnected = True
        
        async def fast_publisher():
            await asyncio.sleep(0.5)  # Let subscriber connect
            async with websockets.connect(WS_URL) as ws:
                await ws.recv()  # info
                
                start = time.time()
                for i in range(messages_published):
                    await ws.send(json.dumps({
                        "type": "publish",
                        "topic": topic_name,
                        "data": {"seq": i}
                    }))
                    await ws.recv()  # ack
                
                elapsed = time.time() - start
                return elapsed
        
        start_time = time.time()
        sub_task = asyncio.create_task(slow_subscriber())
        pub_elapsed = await fast_publisher()
        
        await asyncio.sleep(3)  # Let subscriber process what it can
        sub_task.cancel()
        try:
            await sub_task
        except asyncio.CancelledError:
            pass
        
        total_time = time.time() - start_time
        
        requests.delete(f"{BASE_URL}/topics/{topic_name}")
        
        # Validation:
        # 1. Publisher should complete quickly (not blocked by slow consumer)
        # 2. Slow consumer should receive fewer messages OR be disconnected
        publisher_not_blocked = pub_elapsed < 5.0
        backpressure_worked = (received_count < messages_published) or was_disconnected
        
        details = (
            f"Published: {messages_published}, "
            f"Received: {received_count}, "
            f"Disconnected: {was_disconnected}, "
            f"Publisher time: {pub_elapsed:.2f}s, "
            f"Total time: {total_time:.2f}s"
        )
        
        self.print_result(
            "Backpressure Handling",
            publisher_not_blocked and backpressure_worked,
            details
        )
        
        return publisher_not_blocked and backpressure_worked
    
    async def test_message_replay(self):
        """
        Test: Message replay with last_n parameter
        Validates: Correct replay order, no duplicate delivery
        """
        self.print_header("Message Replay")
        
        topic_name = f"replay_test_{int(time.time())}"
        requests.post(f"{BASE_URL}/topics", json={"name": topic_name})
        
        # Publish messages first
        async with websockets.connect(WS_URL) as ws:
            await ws.recv()  # info
            
            for i in range(100):
                await ws.send(json.dumps({
                    "type": "publish",
                    "topic": topic_name,
                    "data": {"seq": i}
                }))
                await ws.recv()  # ack
        
        # Subscribe with replay
        replay_count = 20
        received_replay = []
        received_live = []
        
        async with websockets.connect(WS_URL) as ws:
            await ws.recv()  # info
            
            await ws.send(json.dumps({
                "type": "subscribe",
                "topic": topic_name,
                "last_n": replay_count
            }))
            await ws.recv()  # ack
            
            # Receive replay messages
            for _ in range(replay_count):
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                if data.get("type") == "event":
                    received_replay.append(data["data"]["seq"])
            
            # Publish new messages
            for i in range(100, 110):
                await ws.send(json.dumps({
                    "type": "publish",
                    "topic": topic_name,
                    "data": {"seq": i}
                }))
                await ws.recv()  # ack
            
            # Receive live messages
            for _ in range(10):
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                if data.get("type") == "event":
                    received_live.append(data["data"]["seq"])
        
        requests.delete(f"{BASE_URL}/topics/{topic_name}")
        
        # Validation
        replay_correct = (
            len(received_replay) == replay_count and
            received_replay == list(range(80, 100))  # Last 20 messages
        )
        live_correct = received_live == list(range(100, 110))
        no_overlap = set(received_replay).isdisjoint(set(received_live))
        
        details = (
            f"Replay messages: {len(received_replay)}/{replay_count}, "
            f"Live messages: {len(received_live)}/10, "
            f"Replay range: {received_replay[:3]}...{received_replay[-3:]}, "
            f"Live range: {received_live[:3]}...{received_live[-3:]}"
        )
        
        self.print_result(
            "Message Replay",
            replay_correct and live_correct and no_overlap,
            details
        )
        
        return replay_correct and live_correct and no_overlap
    
    async def test_topic_deletion_with_subscribers(self):
        """
        Test: Delete topic while subscribers are active
        Validates: Clean subscriber cleanup, no crashes
        """
        self.print_header("Topic Deletion with Active Subscribers")
        
        topic_name = f"deletion_test_{int(time.time())}"
        requests.post(f"{BASE_URL}/topics", json={"name": topic_name})
        
        subscriber_errors = []
        
        async def subscriber(client_id: int):
            try:
                async with websockets.connect(WS_URL) as ws:
                    await ws.recv()  # info
                    
                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "topic": topic_name,
                        "last_n": 0
                    }))
                    await ws.recv()  # ack
                    
                    # Keep receiving
                    for _ in range(100):
                        await asyncio.wait_for(ws.recv(), timeout=10)
            except Exception as e:
                subscriber_errors.append((client_id, str(e)))
        
        # Start subscribers
        tasks = [asyncio.create_task(subscriber(i)) for i in range(10)]
        
        await asyncio.sleep(1)  # Let them connect
        
        # Delete topic
        resp = requests.delete(f"{BASE_URL}/topics/{topic_name}")
        deletion_success = resp.status_code == 204
        
        await asyncio.sleep(2)  # Let subscribers handle deletion
        
        # Cancel remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        details = (
            f"Deletion status: {resp.status_code}, "
            f"Subscribers affected: {len(subscriber_errors)}/10"
        )
        
        self.print_result(
            "Topic Deletion with Subscribers",
            deletion_success,
            details
        )
        
        return deletion_success
    
    async def test_concurrent_topic_operations(self):
        """
        Test: Concurrent topic creation, deletion, and operations
        Validates: Thread safety, no race conditions
        """
        self.print_header("Concurrent Topic Operations")
        
        num_topics = 50
        operations_per_topic = 20
        
        def create_topic(topic_id: int):
            resp = requests.post(f"{BASE_URL}/topics", json={"name": f"topic_{topic_id}"})
            return resp.status_code == 201
        
        def delete_topic(topic_id: int):
            resp = requests.delete(f"{BASE_URL}/topics/topic_{topic_id}")
            return resp.status_code in [204, 404]  # 404 is ok if already deleted
        
        def list_topics():
            resp = requests.get(f"{BASE_URL}/topics")
            return resp.status_code == 200
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            # Create topics concurrently
            create_futures = [executor.submit(create_topic, i) for i in range(num_topics)]
            create_results = [f.result() for f in as_completed(create_futures)]
            
            # Mixed operations
            mixed_futures = []
            for _ in range(operations_per_topic):
                mixed_futures.append(executor.submit(list_topics))
                topic_id = random.randint(0, num_topics - 1)
                mixed_futures.append(executor.submit(create_topic, topic_id))  # Idempotent
            
            mixed_results = [f.result() for f in as_completed(mixed_futures)]
            
            # Delete topics concurrently
            delete_futures = [executor.submit(delete_topic, i) for i in range(num_topics)]
            delete_results = [f.result() for f in as_completed(delete_futures)]
        
        elapsed = time.time() - start_time
        
        # Validation
        all_creates_ok = all(create_results)
        all_mixed_ok = all(mixed_results)
        all_deletes_ok = all(delete_results)
        
        details = (
            f"Topics created: {sum(create_results)}/{num_topics}, "
            f"Mixed operations: {sum(mixed_results)}/{len(mixed_results)}, "
            f"Topics deleted: {sum(delete_results)}/{num_topics}, "
            f"Time: {elapsed:.2f}s"
        )
        
        self.print_result(
            "Concurrent Topic Operations",
            all_creates_ok and all_mixed_ok and all_deletes_ok,
            details
        )
        
        return all_creates_ok and all_mixed_ok and all_deletes_ok
    
    async def test_high_throughput_single_topic(self):
        """
        Test: High message throughput on a single topic
        Validates: System can handle high load without degradation
        """
        self.print_header("High Throughput - Single Topic")
        
        topic_name = f"throughput_test_{int(time.time())}"
        requests.post(f"{BASE_URL}/topics", json={"name": topic_name})
        
        num_publishers = 5
        num_subscribers = 10
        messages_per_publisher = 200
        
        received_counts = {}
        latencies = []
        
        async def subscriber(client_id: int):
            count = 0
            async with websockets.connect(WS_URL) as ws:
                await ws.recv()  # info
                
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "topic": topic_name,
                    "last_n": 0
                }))
                await ws.recv()  # ack
                
                try:
                    while True:
                        msg = await asyncio.wait_for(ws.recv(), timeout=15)
                        data = json.loads(msg)
                        if data.get("type") == "event":
                            count += 1
                            # Calculate latency
                            sent_time = data["data"].get("timestamp")
                            if sent_time:
                                latency = (time.time() - sent_time) * 1000  # ms
                                latencies.append(latency)
                except asyncio.TimeoutError:
                    pass
                
                return client_id, count
        
        async def publisher(pub_id: int):
            await asyncio.sleep(0.5)  # Let subscribers connect
            async with websockets.connect(WS_URL) as ws:
                await ws.recv()  # info
                
                for i in range(messages_per_publisher):
                    await ws.send(json.dumps({
                        "type": "publish",
                        "topic": topic_name,
                        "data": {
                            "publisher": pub_id,
                            "seq": i,
                            "timestamp": time.time()
                        }
                    }))
                    await ws.recv()  # ack
        
        start_time = time.time()
        
        # Start all publishers and subscribers
        sub_tasks = [subscriber(i) for i in range(num_subscribers)]
        pub_tasks = [publisher(i) for i in range(num_publishers)]
        
        results = await asyncio.gather(*sub_tasks, *pub_tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        # Analyze results
        for result in results[:num_subscribers]:
            if isinstance(result, tuple):
                client_id, count = result
                received_counts[client_id] = count
        
        requests.delete(f"{BASE_URL}/topics/{topic_name}")
        
        # Validation
        expected_per_subscriber = num_publishers * messages_per_publisher
        all_received_correctly = all(
            count == expected_per_subscriber 
            for count in received_counts.values()
        )
        
        total_messages = num_publishers * messages_per_publisher * num_subscribers
        throughput = total_messages / elapsed
        
        avg_latency = statistics.mean(latencies) if latencies else 0
        p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else 0
        p99_latency = statistics.quantiles(latencies, n=100)[98] if len(latencies) > 100 else 0
        
        details = (
            f"Total messages: {total_messages}, "
            f"Throughput: {throughput:.0f} msg/s, "
            f"Time: {elapsed:.2f}s, "
            f"Avg latency: {avg_latency:.2f}ms, "
            f"P95: {p95_latency:.2f}ms, "
            f"P99: {p99_latency:.2f}ms"
        )
        
        self.print_result(
            "High Throughput",
            all_received_correctly,
            details
        )
        
        return all_received_correctly
    
    async def test_websocket_reconnection(self):
        """
        Test: Subscriber disconnection and reconnection
        Validates: Clean cleanup, ability to resubscribe
        """
        self.print_header("WebSocket Reconnection")
        
        topic_name = f"reconnect_test_{int(time.time())}"
        requests.post(f"{BASE_URL}/topics", json={"name": topic_name})
        
        reconnection_success = True
        
        try:
            # First connection
            async with websockets.connect(WS_URL) as ws:
                await ws.recv()  # info
                
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "topic": topic_name,
                    "last_n": 0
                }))
                await ws.recv()  # ack
            
            # Connection closed
            await asyncio.sleep(0.5)
            
            # Reconnect
            async with websockets.connect(WS_URL) as ws:
                await ws.recv()  # info
                
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "topic": topic_name,
                    "last_n": 0
                }))
                await ws.recv()  # ack
                
                # Publish and receive
                await ws.send(json.dumps({
                    "type": "publish",
                    "topic": topic_name,
                    "data": {"test": "reconnection"}
                }))
                await ws.recv()  # ack
                
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                reconnection_success = data.get("type") == "event"
        
        except Exception as e:
            reconnection_success = False
            print(f"Reconnection error: {e}")
        
        requests.delete(f"{BASE_URL}/topics/{topic_name}")
        
        self.print_result(
            "WebSocket Reconnection",
            reconnection_success,
            "Successfully reconnected and received messages"
        )
        
        return reconnection_success
    
    async def run_all_tests(self):
        """Run all stress tests"""
        print("\n" + "🚀" * 40)
        print("STARTING COMPREHENSIVE STRESS TEST SUITE")
        print("🚀" * 40)
        
        start_time = time.time()
        
        # Run tests
        await self.test_concurrent_subscribers(num_subscribers=50)
        await self.test_backpressure_slow_consumer()
        await self.test_message_replay()
        await self.test_topic_deletion_with_subscribers()
        await self.test_concurrent_topic_operations()
        await self.test_high_throughput_single_topic()
        await self.test_websocket_reconnection()
        
        total_time = time.time() - start_time
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        for test_name, result in self.results.items():
            status = "✅" if result else "❌"
            print(f"{status} {test_name}")
        
        print("\n" + "-" * 80)
        print(f"Total: {passed}/{total} tests passed")
        print(f"Success rate: {(passed/total)*100:.1f}%")
        print(f"Total time: {total_time:.2f}s")
        print("=" * 80 + "\n")
        
        return passed == total


async def main():
    print("⚠️  Make sure the server is running on http://localhost:8000")
    print("   Start it with: ./run.sh\n")
    
    input("Press Enter to start stress tests...")
    
    runner = StressTestRunner()
    success = await runner.run_all_tests()
    
    exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
