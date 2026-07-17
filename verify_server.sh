#!/bin/bash
python3 - <<'PY'
import socket
ports=[9000,8200,8201,8229]
for p in ports:
    s=socket.socket(); s.settimeout(2)
    try:
        s.connect(('127.0.0.1',p)); print(f'port {p}: OPEN')
    except Exception as e:
        print(f'port {p}: CLOSED ({e})')
    finally:
        s.close()
# try HTTP stats on 9000
import urllib.request
try:
    r=urllib.request.urlopen('http://127.0.0.1:9000/api/stats', timeout=3)
    print('STATS:', r.read().decode()[:200])
except Exception as e:
    print('STATS ERR:', e)
PY
