# How to Test the Pub/Sub System

## Prerequisites

✅ Server is running on http://localhost:8000  
✅ Virtual environment is activated  
✅ All dependencies are installed  

## Step-by-Step Testing Guide

### Step 1: Start the Server

```bash
cd /Users/prakharkhurana/Desktop/all\ projects/assignment-plivo/pubsub-system
./run.sh
```

**Expected output:**
```
✅ Starting server on http://localhost:8000
📡 WebSocket endpoint: ws://localhost:8000/ws
📚 API docs: http://localhost:8000/docs
```

Keep this terminal open. The server must stay running for all tests.

### Step 2: Open a New Terminal for Testing

```bash
cd /Users/prakharkhurana/Desktop/all\ projects/assignment-plivo/pubsub-system
source venv/bin/activate
```

### Step 3: Run Stress Tests

These tests validate **correctness** - that the system works properly under challenging conditions.

```bash
python tests/test_stress.py
```

**What to expect:**
- Tests run for ~3-5 minutes
- Each test shows progress and results
- All 7 tests should pass

**Sample output:**
```
🧪 TEST: Concurrent Subscribers (50 clients)
✅ PASSED: Concurrent Subscribers
   Subscribers: 50/50, Messages per subscriber: 50, Time: 2.34s

🧪 TEST: Backpressure - Slow Consumer
✅ PASSED: Backpressure Handling
   Published: 2000, Received: 856, Dropped: 1144

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

### Step 4: Run Load Tests

These tests measure **performance** - how fast and efficiently the system runs.

```bash
python tests/load_test.py
```

**Interactive menu:**
```
Choose a load test scenario:
1. Light Load (Quick test)        ← Start here
2. Medium Load (Realistic production)
3. Heavy Load (Stress test)
4. Extreme Load (Breaking point)
5. Custom configuration
```

**Recommended progression:**
1. Start with **Light Load** (option 1) - takes ~30 seconds
2. Then try **Medium Load** (option 2) - takes ~60 seconds
3. If system handles well, try **Heavy Load** (option 3)

**Sample output:**
```
📊 LOAD TEST RESULTS
⏱️  Duration: 32.45s
📨 Messages:
  Published: 2,000
  Received: 1,998
  Dropped: 2 (0.10%)
🚀 Throughput:
  Published: 62 msg/s
  Received: 62 msg/s
⚡ Latency:
  Average: 8.34ms
  P50: 6.21ms
  P95: 25.67ms
  P99: 48.90ms
  Max: 89.45ms
🎯 Overall Performance:
  Verdict: ✅ EXCELLENT - System handled load well
```

### Step 5: Try the Example Client (Optional)

```bash
python example_client.py
```

Choose option 1 for a full workflow demonstration.

## What Each Test Validates

### Stress Tests

| Test | What It Checks | Why It Matters |
|------|----------------|----------------|
| Concurrent Subscribers | 50 clients receive all messages | Validates fan-out and ordering |
| Backpressure | Fast publisher + slow consumer | Validates drop-oldest policy works |
| Message Replay | `last_n` parameter works | Validates historical data feature |
| Topic Deletion | Clean cleanup with active subs | Validates no resource leaks |
| Concurrent Operations | Thread-safe topic create/delete | Validates no race conditions |
| High Throughput | Multiple pubs/subs on one topic | Validates system can handle load |
| Reconnection | WebSocket disconnect/reconnect | Validates connection handling |

### Load Tests

| Scenario | Purpose | Duration |
|----------|---------|----------|
| Light | Quick smoke test | ~30s |
| Medium | Realistic production load | ~60s |
| Heavy | Stress test | ~120s |
| Extreme | Find breaking point | ~180s |

## Interpreting Results

### ✅ Good Results

**Stress Tests:**
- All 7 tests pass
- No errors or timeouts

**Load Tests:**
- Throughput > 1,000 msg/s
- P99 latency < 100ms
- Delivery rate > 95%
- Error rate < 1%
- Verdict: EXCELLENT or GOOD

### ⚠️ Acceptable Results

**Load Tests:**
- Throughput > 500 msg/s
- P99 latency < 200ms
- Delivery rate > 90%
- Error rate < 5%
- Verdict: ACCEPTABLE

### ❌ Poor Results

**Stress Tests:**
- Any test fails
- Timeouts or connection errors

**Load Tests:**
- Throughput < 500 msg/s
- P99 latency > 500ms
- Delivery rate < 80%
- Error rate > 10%
- Verdict: POOR

## Common Issues

### Issue: "Connection refused"

**Problem:** Server is not running

**Solution:**
```bash
# In terminal 1
./run.sh
```

### Issue: "Module not found"

**Problem:** Virtual environment not activated or dependencies not installed

**Solution:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: Tests timeout

**Problem:** System is overloaded or slow

**Solution:**
- Close other applications
- Try Light Load instead of Heavy Load
- Check system resources (CPU, memory)

### Issue: High message drop rate

**Problem:** Subscribers can't keep up with publishers

**Expected:** This is normal under backpressure test
**Unexpected:** If it happens in other tests, reduce load

### Issue: High latency

**Problem:** System under heavy load

**Solution:**
- Check network latency
- Reduce concurrent operations
- Try lighter load scenario

## Quick Test Commands

```bash
# Full test suite (recommended)
./run_tests.sh

# Just stress tests
python tests/test_stress.py

# Just load tests - light
python tests/load_test.py
# Then choose option 1

# Example client
python example_client.py
# Then choose option 1
```

## What Success Looks Like

### Stress Tests Success
```
📊 TEST SUMMARY
✅ Concurrent Subscribers
✅ Backpressure Handling
✅ Message Replay
✅ Topic Deletion with Subscribers
✅ Concurrent Topic Operations
✅ High Throughput
✅ WebSocket Reconnection

Total: 7/7 tests passed ← This is what you want
Success rate: 100.0%
```

### Load Tests Success (Medium Load)
```
🎯 Overall Performance:
  Message delivery rate: 99.87%  ← > 95% is good
  Error rate: 0.00%              ← < 1% is good
  Verdict: ✅ EXCELLENT          ← This is what you want
```

## Real-World Scenarios Tested

The tests simulate these real-world situations:

1. **News Feed**: 1 topic, many subscribers (fan-out)
2. **Chat App**: Many topics, moderate activity per topic
3. **IoT Telemetry**: High message rate, few subscribers
4. **Stock Ticker**: Many topics, high fan-out, low latency
5. **Slow Consumer**: Mobile client on poor network
6. **Burst Traffic**: Sudden spike in messages
7. **Connection Issues**: Network interruptions

## Performance Expectations

### Your Machine (M1/M2 Mac)

**Light Load:**
- Throughput: 2,000-5,000 msg/s
- P99 Latency: < 50ms
- Should complete in ~30s

**Medium Load:**
- Throughput: 5,000-10,000 msg/s
- P99 Latency: < 100ms
- Should complete in ~60s

**Heavy Load:**
- Throughput: 10,000-20,000 msg/s
- P99 Latency: < 200ms
- Should complete in ~120s

## Next Steps After Testing

✅ **All tests pass?** System is working correctly!

📊 **Check the results:**
- Review throughput numbers
- Check latency percentiles
- Verify error rates are low

📝 **Document findings:**
- Note any performance bottlenecks
- Record peak throughput achieved
- Save test results for comparison

🚀 **Ready for demo:**
- System validated and tested
- Performance benchmarked
- Ready to show functionality

---

**Questions?** Check README.md or TESTING.md for more details.
