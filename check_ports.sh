#!/bin/bash
echo "=== who uses 8080 ==="
sudo ss -tlnp 2>/dev/null | grep ':8080' || echo "ss unavailable, trying lsof"
sudo lsof -i :8080 2>/dev/null || echo "lsof n/a"
echo "=== free ports test ==="
python3 - <<'PY'
import socket
candidates=[8200,8201,8210,8300,8400,9000,9001]
for p in candidates:
    s=socket.socket(); s.settimeout(1)
    try:
        s.connect(('127.0.0.1',p)); print(f'{p}: USED')
    except:
        print(f'{p}: FREE')
    finally:
        s.close()
PY
