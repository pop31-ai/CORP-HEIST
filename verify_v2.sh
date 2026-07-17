#!/bin/bash
python3 - <<'PY'
import urllib.request
base='http://127.0.0.1:9000'
def get(path):
    try:
        r=urllib.request.urlopen(base+path, timeout=4)
        return r.status, r.read().decode()[:120]
    except Exception as e:
        return 'ERR', str(e)
for p in ['/', '/api/stats', '/api/chars', '/api/char/1000', '/card/1?uid=1000', '/api/market']:
    s,b=get(p)
    print(f'{p}: {s} | {b[:80]}')
PY
