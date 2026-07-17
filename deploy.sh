#!/bin/bash
# CORP HEIST — Deploy Script
# Usage: bash deploy.sh user@host
# Example: bash deploy.sh root@123.45.67.89

set -e

REMOTE=${1:-"root@localhost"}
REPO="https://github.com/pop31-ai/CORP-HEIST.git"
DIR="CORP-HEIST"

echo "=========================================="
echo "  CORP HEIST — Deploy to $REMOTE"
echo "=========================================="

echo ""
echo "[1/7] Connecting to $REMOTE..."
ssh $REMOTE "echo connected"

echo "[2/7] Installing Python + git..."
ssh $REMOTE "apt update && apt install -y python3 python3-pip git" 2>/dev/null || true

echo "[3/7] Cloning repo..."
ssh $REMOTE "rm -rf $DIR && git clone $REPO && cd $DIR && pip3 install -r requirements.txt aiohttp"

echo "[4/7] Running tests..."
ssh $REMOTE "cd $DIR && python3 tests/test_protocol.py && python3 tests/test_bridge.py"

echo "[5/7] Starting server..."
ssh $REMOTE "cd $DIR && pkill -f server_consolidated || true; nohup python3 server_consolidated.py > /var/log/corp-heist.log 2>&1 &"

echo "[6/7] Waiting for startup..."
sleep 3

echo "[7/7] Verifying..."
ssh $REMOTE "curl -s http://localhost:9000/api/stats"

echo ""
echo "=========================================="
echo "  DEPLOYED!"
echo "=========================================="
echo "  Dashboard: http://$REMOTE:9000"
echo "  Cards:     http://$REMOTE:8080-8109"
echo "  Logs:      ssh $REMOTE 'tail -f /var/log/corp-heist.log'"
echo "  Stats:     curl http://$REMOTE:9000/api/stats"
echo "=========================================="
