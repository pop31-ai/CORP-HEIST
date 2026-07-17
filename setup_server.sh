#!/bin/bash
set -e
sudo cp /tmp/corp-heist.service /etc/systemd/system/corp-heist.service
sudo systemctl daemon-reload
sudo systemctl enable corp-heist
sudo systemctl restart corp-heist
sleep 4
echo "=== STATUS ==="
sudo systemctl is-active corp-heist
echo "=== PROC ==="
ps aux | grep server_consolidated | grep -v grep
echo "=== PORTS (local check) ==="
python3 - <<'PY'
import socket
for p in [9000,8080,8081,8109]:
    s=socket.socket(); s.settimeout(2)
    try:
        s.connect(('127.0.0.1',p)); print(f'port {p}: OPEN')
    except Exception as e:
        print(f'port {p}: CLOSED ({e})')
    finally:
        s.close()
PY
