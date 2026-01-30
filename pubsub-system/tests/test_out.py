⚠️  Make sure the server is running on http://localhost:8000
   Start it with: ./run.sh

Press Enter to start stress tests...
🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀
STARTING COMPREHENSIVE STRESS TEST SUITE
🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀

================================================================================
🧪 TEST: Concurrent Subscribers (50 clients)
================================================================================

✅ PASSED: Concurrent Subscribers
   Subscribers: 50/50, Messages per subscriber: 50, Time: 1.62s, Throughput: 1544 msg/s

================================================================================
🧪 TEST: Backpressure - Slow Consumer
================================================================================

✅ PASSED: Backpressure Handling
   Published: 500, Received: 31, Disconnected: False, Publisher time: 0.12s, Total time: 13.64s

================================================================================
🧪 TEST: Message Replay
================================================================================

✅ PASSED: Message Replay
   Replay messages: 20/20, Live messages: 10/10, Replay range: [80, 81, 82]...[97, 98, 99], Live range: [100, 101, 102]...[107, 108, 109]

================================================================================
🧪 TEST: Topic Deletion with Active Subscribers
================================================================================

✅ PASSED: Topic Deletion with Subscribers
   Deletion status: 204, Subscribers affected: 0/10

================================================================================
🧪 TEST: Concurrent Topic Operations
================================================================================

✅ PASSED: Concurrent Topic Operations
   Topics created: 50/50, Mixed operations: 40/40, Topics deleted: 50/50, Time: 0.14s

================================================================================
🧪 TEST: High Throughput - Single Topic
================================================================================

✅ PASSED: High Throughput
   Total messages: 10000, Throughput: 627 msg/s, Time: 15.95s, Avg latency: 6.19ms, P95: 10.98ms, P99: 18.68ms

================================================================================
🧪 TEST: WebSocket Reconnection
================================================================================

✅ PASSED: WebSocket Reconnection
   Successfully reconnected and received messages

================================================================================
📊 TEST SUMMARY
================================================================================
✅ Concurrent Subscribers
✅ Backpressure Handling
✅ Message Replay
✅ Topic Deletion with Subscribers
✅ Concurrent Topic Operations
✅ High Throughput
✅ WebSocket Reconnection

--------------------------------------------------------------------------------
Total: 7/7 tests passed
Success rate: 100.0%
Total time: 35.02s
================================================================================

