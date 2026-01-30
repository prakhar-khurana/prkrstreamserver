#!/bin/bash

echo "🚀 Starting Pub/Sub System..."
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

# Check Python version (need 3.11 or 3.12, not 3.13)
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "📍 Detected Python version: $PYTHON_VERSION"

if [[ "$PYTHON_VERSION" == "3.13" ]]; then
    echo "⚠️  Python 3.13 detected. Checking for Python 3.11 or 3.12..."
    
    if command -v python3.12 &> /dev/null; then
        PYTHON_CMD=python3.12
        echo "✅ Using Python 3.12"
    elif command -v python3.11 &> /dev/null; then
        PYTHON_CMD=python3.11
        echo "✅ Using Python 3.11"
    else
        echo "❌ Python 3.11 or 3.12 is required (Python 3.13 has compatibility issues)"
        echo "   Please install Python 3.11 or 3.12:"
        echo "   - macOS: brew install python@3.12"
        echo "   - Or use pyenv: pyenv install 3.12"
        exit 1
    fi
else
    PYTHON_CMD=python3
fi

# Remove old venv if it exists with wrong Python version
if [ -d "venv" ]; then
    VENV_PYTHON_VERSION=$(venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "unknown")
    if [[ "$VENV_PYTHON_VERSION" == "3.13" ]]; then
        echo "🗑️  Removing old venv with Python 3.13..."
        rm -rf venv
    fi
fi

if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment with $PYTHON_CMD..."
    $PYTHON_CMD -m venv venv
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✅ Starting server on http://localhost:8000"
echo "📡 WebSocket endpoint: ws://localhost:8000/ws"
echo "📚 API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python -m src.main
