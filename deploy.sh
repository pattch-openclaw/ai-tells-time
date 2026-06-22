#!/bin/bash
# Deployment script for Mac Mini
# Run this after pulling changes to sync dependencies and restart the app

set -e

echo "=== AI Tells Time Deployment ==="

cd ~/Coding/ai-tells-time

echo "Cleaning up any stale git state..."
git stash -q || true
git pull origin main -q

echo "Syncing dependencies with uv..."
uv sync -q

echo "Restarting application..."
# Replace 'ai-tells-time' with your actual process name/service
# Example: sudo systemctl restart ai-tells-time
# Or if running manually: nohup uv run main.py > /dev/null 2>&1 &

echo "=== Deployment complete ==="
