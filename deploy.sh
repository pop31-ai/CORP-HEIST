#!/bin/bash
# CORP HEIST — Deploy Script
# Usage: bash deploy.sh
# Server: user1@87.242.117.240

set -e

REMOTE="user1@87.242.117.240"
KEY="id_rsa"
REPO="https://github.com/pop31-ai/CORP-HEIST.git"
DIR="CORP-HEIST"

SSH="ssh -i $KEY $REMOTE"

echo "=========================================="
echo "  CORP HEIST — Deploy to $REMOTE"
echo "=========================================="

echo ""
echo "[1/7] Connecting..."
$SSH "echo connected"

echo "[2/7] Installing Python + git..."
$SSH "sudo apt update && sudo apt install -y python3 python3-pip git" 2>/dev/null || true

echo "[3/7] Cloning repo..."
$SSH "rm -rf $DIR && git clone $REPO && cd $DIR && pip3 install -r requirements.txt aiohttp"

echo "[4/7] Running tests..."
$SSH "cd $DIR && python3 tests/test_protocol.py && python3 tests/test_bridge.py"

echo "[5/7] Starting server..."
$SSH "cd $DIR && pkill -f server_consolidated || true; nohup python3 server_consolidated.py > /tmp/corp-heist.log 2>&1 &"

echo "[6/7] Waiting for startup..."
sleep 3

echo "[7/7] Verifying..."
$SSH "curl -s http://localhost:9000/api/stats"

echo ""
echo "=========================================="
echo "  DEPLOYED!"
echo "=========================================="
echo "  Dashboard: http://87.242.117.240:9000"
echo "  Cards:     http://87.242.117.240:8080-8109"
echo "  SSH:       ssh -i $KEY $REMOTE"
echo "  Logs:      $SSH 'tail -f /tmp/corp-heist.log'"
echo "  Stats:     curl http://87.242.117.240:9000/api/stats"
echo "=========================================="
