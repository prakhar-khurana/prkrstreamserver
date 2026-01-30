# Testing Guide

## Quick Start

```bash
# Terminal 1: Start the server
./run.sh

# Terminal 2: Run tests
chmod +x run_tests.sh
./run_tests.sh
```

## Test Suites

### 1. Stress Tests - Correctness Validation

**Purpose**: Validate system correctness under challenging conditions

**Tests Included:**
1. **Concurrent Subscribers** (50 clients)
   - Validates: Message delivery to all subscribers, ordering preservation
   - Expected: All messages received by all subscribers in order

2. **Backpressure - Slow Consumer**
   - Validates: Drop-oldest policy, publisher never blocked
   - Expected: Messages dropped, publisher completes quickly

3. **Message Replay**
   - Validates: `last_n` parameter, replay ordering
   - Expected: Last N messages replayed before live messages

4. **Topic Deletion with Active Subscribers**
   - Validates: Clean cleanup, no crashes
   - Expected: Topic deleted, subscribers notified

5. **Concurrent Topic Operations**
   - Validates: Thread safety, no race conditions
   - Expected: All operations succeed without conflicts

6. **High Throughput - Single Topic**
   - Validates: System handles concurrent load
   - Expected: All messages delivered, acceptable latency

7. **WebSocket Reconnection**
   - Validates: Clean disconnect/reconnect
   - Expected: Successful reconnection and message delivery

**Run Command:**
```bash
python tests/test_stress.py
```

**Expected Output:**
```
🚀 STARTING COMPREHENSIVE STRESS TEST SUITE
...
📊 TEST SUMMARY
✅ Concurrent Subscribers
✅ Backpressure Handling
✅ Message Replay
✅ Topic Deletion with Subscribers
✅ Concurrent Topic Operations
✅ High Throughput
✅ WebSocket Reconnection

Total: 7/7 tests passed
Success rate: 100.0%
```

### 2. Load Tests - Performance Benchmarking

**Purpose**: Measure system performance under realistic production loads

**Scenarios:**

#### Light Load (Quick Validation)
- 5 topics, 10 publishers, 20 subscribers
- 100 messages per publisher
- Duration: ~30 seconds
- Use case: Quick smoke test

#### Medium Load (Realistic Production)
- 10 topics, 20 publishers, 50 subscribers
- 500 messages per publisher
- Duration: ~60 seconds
- Use case: Typical production workload

#### Heavy Load (Stress Test)
- 20 topics, 50 publishers, 100 subscribers
- 1000 messages per publisher
- Duration: ~120 seconds
- Use case: Peak traffic simulation

#### Extreme Load (Breaking Point)
- 50 topics, 100 publishers, 200 subscribers
- 2000 messages per publisher
- Duration: ~180 seconds
- Use case: Find system limits

**Run Command:**
```bash
python tests/load_test.py
```

**Interactive Menu:**
```
Choose a load test scenario:
1. Light Load (Quick test)
2. Medium Load (Realistic production)
3. Heavy Load (Stress test)
4. Extreme Load (Breaking point)
5. Custom configuration
```

**Expected Output:**
```
📊 LOAD TEST RESULTS
⏱️  Duration: 62.45s
📨 Messages:
  Published: 10,000
  Received: 9,987
  Dropped: 13 (0.13%)
🚀 Throughput:
  Published: 160 msg/s
  Received: 159 msg/s
⚡ Latency:
  Average: 12.34ms
  P50: 8.21ms
  P95: 45.67ms
  P99: 78.90ms
  Max: 123.45ms
❌ Errors:
  Publish errors: 0
  Subscribe errors: 0
  Connection errors: 0
🎯 Overall Performance:
  Message delivery rate: 99.87%
  Error rate: 0.00%
  Verdict: ✅ EXCELLENT - System handled load well
```

## Performance Benchmarks

### Expected Performance (Medium Load)

| Metric | Target | Typical |
|--------|--------|---------|
| Throughput | > 5,000 msg/s | 8,000-10,000 msg/s |
| P50 Latency | < 20ms | 8-15ms |
| P95 Latency | < 50ms | 30-45ms |
| P99 Latency | < 100ms | 60-80ms |
| Delivery Rate | > 95% | 99%+ |
| Error Rate | < 1% | < 0.1% |

### What Each Metric Means

**Throughput**: Messages processed per second
- Higher is better
- Measures system capacity

**Latency**: Time from publish to receive
- Lower is better
- P50 = median, P95/P99 = tail latency

**Delivery Rate**: % of messages successfully delivered
- Should be > 95% under normal load
- Drops under extreme backpressure (by design)

**Error Rate**: % of operations that failed
- Should be near 0% under normal conditions
- Indicates system stability

## Real-World Test Scenarios

### Scenario 1: News Feed
```python
# 1 topic, 5 publishers (news sources), 100 subscribers (users)
# High fan-out, moderate throughput
```

### Scenario 2: Chat Application
```python
# 50 topics (chat rooms), 100 publishers (users), 100 subscribers
# Many topics, moderate messages per topic
```

### Scenario 3: IoT Telemetry
```python
# 10 topics (device types), 200 publishers (devices), 20 subscribers (monitors)
# High throughput, few subscribers
```

### Scenario 4: Stock Ticker
```python
# 100 topics (stocks), 10 publishers (exchanges), 500 subscribers (traders)
# Many topics, high fan-out, low latency required
```

## Troubleshooting

### Test Failures

**"Connection refused"**
- Server is not running
- Solution: Start server with `./run.sh`

**"Timeout waiting for message"**
- System overloaded or slow
- Solution: Reduce load parameters or check system resources

**"Messages dropped"**
- Expected under backpressure test
- Unexpected in other tests: Check subscriber processing speed

**"Latency too high"**
- System under heavy load
- Check: CPU usage, network latency, concurrent operations

### Performance Issues

**Low Throughput**
- Check: System resources (CPU, memory)
- Reduce: Number of concurrent operations
- Increase: Publish rate delay

**High Latency**
- Check: Network conditions
- Reduce: Subscriber processing time
- Check: Queue sizes and backpressure

**High Error Rate**
- Check: Server logs for errors
- Reduce: Load intensity
- Check: Network stability

## Custom Testing

### Create Your Own Test

```python
import asyncio
import websockets
import json

async def custom_test():
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        await ws.recv()  # info
        
        # Subscribe
        await ws.send(json.dumps({
            "type": "subscribe",
            "topic": "my-topic",
            "last_n": 0
        }))
        await ws.recv()  # ack
        
        # Publish
        await ws.send(json.dumps({
            "type": "publish",
            "topic": "my-topic",
            "data": {"test": "data"}
        }))
        await ws.recv()  # ack
        
        # Receive
        msg = await ws.recv()
        print(f"Received: {msg}")

asyncio.run(custom_test())
```

## Continuous Testing

### Pre-Deployment Checklist

- [ ] All stress tests pass
- [ ] Medium load test shows acceptable performance
- [ ] Heavy load test completes without crashes
- [ ] Error rate < 1%
- [ ] P99 latency < 100ms
- [ ] Message delivery rate > 95%

### Regression Testing

Run after any code changes:
```bash
./run_tests.sh
```

Should complete in < 5 minutes with all tests passing.

## Interpreting Failures

### Stress Test Failures

**Concurrent Subscribers Failed**
- Issue: Message loss or ordering problems
- Impact: Core functionality broken
- Severity: CRITICAL

**Backpressure Failed**
- Issue: Publisher blocked or no messages dropped
- Impact: System can't handle slow consumers
- Severity: HIGH

**Message Replay Failed**
- Issue: Replay ordering or delivery problems
- Impact: Historical data feature broken
- Severity: MEDIUM

### Load Test Failures

**Throughput < 1,000 msg/s**
- Issue: System bottleneck
- Severity: HIGH

**P99 Latency > 500ms**
- Issue: Performance degradation
- Severity: MEDIUM

**Delivery Rate < 90%**
- Issue: Message loss under load
- Severity: HIGH

**Error Rate > 5%**
- Issue: System instability
- Severity: CRITICAL

---

**For more details, see README.md**
