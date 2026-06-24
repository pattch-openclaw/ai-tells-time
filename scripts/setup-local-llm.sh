#!/bin/bash
# setup-local-llm.sh
# Script to set up local AI inference on Mac Mini for AI Tells Time

set -e

echo "🚀 Setting up local LLM inference..."

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "📦 Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "✅ Ollama is already installed"
fi

# Start Ollama service if not running
if ! ollama list &> /dev/null; then
    echo "⚠️  Ollama service not running. Please run: ollama serve &"
    exit 1
fi

# Pull the default vision model
echo "⬇️  Pulling llava:7b model (first time may take a while)..."
ollama pull llava:7b

echo "✅ Local LLM setup complete!"
echo "   Model: llava:7b"
echo "   API: http://localhost:11434"
echo ""
echo "To run the app with local LLM:"
echo "  uv run python main.py --providers ollama"
