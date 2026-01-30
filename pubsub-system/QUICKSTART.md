# Quick Start Guide

## 🚀 Get Started in 3 Steps

### 1. Start the Server

```bash
cd pubsub-system
./run.sh
```

Server will be available at:
- **API**: http://localhost:8000
- **WebSocket**: ws://localhost:8000/ws
- **Docs**: http://localhost:8000/docs

### 2. Test the System

Open a new terminal:

```bash
cd pubsub-system
chmod +x run_tests.sh
./run_tests.sh
```

Choose option 1 for stress tests or option 2 for load tests.

### 3. Try the Example Client

```bash
cd pubsub-system
source venv/bin/activate
python example_client.py
```

Choose option 1 for a full workflow demonstration.

## 📋 What to Test

### Basic Functionality
```bash
# Create a topic
curl -X POST http://localhost:8000/topics \
  -H "Content-Type: application/json" \
  -d '{"name": "test-topic"}'

# List topics
curl http://localhost:8000/topics

# Check health
curl http://localhost:8000/health

# Get stats
curl http://localhost:8000/stats
```

### WebSocket Test (using wscat)
```bash
# Install wscat if needed
npm install -g wscat

# Connect
wscat -c ws://localhost:8000/ws

# Send commands
> {"type": "subscribe", "topic": "test-topic", "last_n": 0}
> {"type": "publish", "topic": "test-topic", "data": {"hello": "world"}}
> {"type": "ping"}
```

## 🧪 Run Tests

### Stress Tests (Validates Correctness)
```bash
python tests/test_stress.py
```

**Tests:**
- ✅ Concurrent subscribers
- ✅ Backpressure handling
- ✅ Message replay
- ✅ Topic deletion
- ✅ Concurrent operations
- ✅ High throughput
- ✅ Reconnection

### Load Tests (Measures Performance)
```bash
python tests/load_test.py
```

**Scenarios:**
1. Light Load (quick test)
2. Medium Load (realistic)
3. Heavy Load (stress)
4. Extreme Load (breaking point)

## 📊 Expected Performance

| Scenario | Throughput | P99 Latency | Delivery Rate |
|----------|------------|-------------|---------------|
| Light | 2,000 msg/s | < 50ms | > 99% |
| Medium | 8,000 msg/s | < 100ms | > 95% |
| Heavy | 15,000 msg/s | < 200ms | > 90% |

## 🐳 Docker Alternative

```bash
# Build
docker build -t pubsub-system .

# Run
docker run -p 8000:8000 pubsub-system

# Test
curl http://localhost:8000/health
```

## 🔧 Troubleshooting

**Python 3.13 Error?**
```bash
brew install python@3.12
rm -rf venv
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Server Not Starting?**
- Check port 8000 is not in use: `lsof -i :8000`
- Check Python version: `python3 --version`
- Check logs for errors

**Tests Failing?**
- Ensure server is running
- Check server health: `curl http://localhost:8000/health`
- Reduce load test parameters

## 📚 Next Steps

- Read `README.md` for architecture details
- Read `TESTING.md` for comprehensive testing guide
- Check `example_client.py` for usage examples
- View API docs at http://localhost:8000/docs

## 🎯 Key Features Demonstrated

✅ **Concurrency**: Per-topic locking, no global bottlenecks  
✅ **Backpressure**: Drop-oldest policy, bounded queues  
✅ **Message Replay**: Ring buffer with `last_n` parameter  
✅ **Safety**: Thread-safe operations, clean cleanup  
✅ **Performance**: High throughput, low latency  
✅ **Reliability**: Graceful shutdown, error handling  

---

**Need Help?** Check the full documentation in README.md
