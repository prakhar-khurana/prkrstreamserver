#!/bin/bash

echo "🧪 Pub/Sub System Test Runner"
echo ""

# Check if server is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Server is not running on http://localhost:8000"
    echo "   Please start the server first with: ./run.sh"
    exit 1
fi

echo "✅ Server is running"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Choose test suite:"
echo "1. Stress Tests (Comprehensive validation)"
echo "2. Load Tests (Performance benchmarking)"
echo "3. Both"
echo ""

read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo ""
        echo "🔥 Running Stress Tests..."
        python tests/test_stress.py
        ;;
    2)
        echo ""
        echo "📊 Running Load Tests..."
        python tests/load_test.py
        ;;
    3)
        echo ""
        echo "🔥 Running Stress Tests..."
        python tests/test_stress.py
        echo ""
        echo "📊 Running Load Tests..."
        python tests/load_test.py
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
