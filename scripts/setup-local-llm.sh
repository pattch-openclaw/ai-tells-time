#!/bin/bash
# setup-local-llm.sh
# Script to set up local AI inference on Mac Mini for AI Tells Time
# This script starts Ollama and pulls the default model (qwen2.5vl:7b)

set -e

echo "🚀 Setting up local LLM inference..."

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama is not installed. Please install Ollama first:"
    echo "   curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

echo "✅ Ollama is installed"

# Start Ollama if not running
if ! ollama list &> /dev/null; then
    echo "🚀 Starting Ollama server..."
    # Start Ollama in background
    ollama serve &
    OLLAMA_PID=$!
    
    # Wait for Ollama to be ready (up to 30 seconds)
    echo "⏳ Waiting for Ollama to start..."
    for i in {1..30}; do
        if curl -s http://localhost:11434 > /dev/null 2>&1; then
            echo "✅ Ollama server is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Ollama failed to start within 30 seconds"
            kill $OLLAMA_PID 2>/dev/null || true
            exit 1
        fi
        sleep 1
    done
else
    echo "✅ Ollama is already running"
fi

# Pull the default vision model
echo "⬇️  Pulling qwen2.5vl:7b model..."
ollama pull qwen2.5vl:7b

echo "✅ Local LLM setup complete!"
echo "   Model: qwen2.5vl:7b"
echo "   API: http://localhost:11434"
echo ""
echo "To run the app with local LLM:"
echo "  uv run python main.py --providers ollama"
echo ""
echo "Or with a custom model:"
echo "  uv run python main.py --providers ollama --ollama-model llava:7b"
