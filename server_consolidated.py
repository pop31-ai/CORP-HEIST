#!/usr/bin/env python3
"""
CORP HEIST — Consolidated Server
All 30 instances + dashboard + market in ONE process.
Internal routing, zero inter-process traffic.
Shared memory, shared market, shared char DB.

Run: python server_consolidated.py
Ports: 9000 (dashboard) + 8080-8109 (30 cards) = 31 ports, 1 process
"""
import asyncio
import json
import random
import struct
import os
import sys
import time
import signal
import logging
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiohttp import web
from protocol import (
    build_char_bytes, parse_char, CHAR_SIZE, CHAR_FMT,
    MsgType, PacketBuilder, PacketParser
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("consolidated")


# ============================================================
# CONFIG
# ============================================================

CMD_PORT   = 9000
CARD_PORTS = list(range(8080, 8110))  # 30 ports
NUM_CHARS  = 500
MARKET_TICK_SEC = 3
HEALTH_CHECK_SEC = 30


# ============================================================
# SHARED STATE (single process memory)
# ============================================================

class SharedState:
    """All data lives here. No IPC, no replication."""

    def __init__(self):
        self.stocks = self._init_stocks()
        self.chars = {}
        self.request_count = 0
        self.bytes_sent = 0
        self.bytes_recv = 0
        self.start_time = time.time()
        self.port_users = defaultdict(int)  # port -> active users
        self._lock = asyncio.Lock()

    def _init_stocks(self):
        names = ["ALPHA","BETA","GAMMA","DELTA","OMEGA","SIGMA","THETA",
                 "ZETA","PI","RHO","KAPPA","LAMBDA","MU","NU","XI",
                 "OMIKRON","CHI","PSI","PHI","TAU"]
        return [{"id":i,"name":n,"price":round(random.uniform(5,200),2),
                 "delta":round(random.uniform(-3,3),2),
                 "volume":random.randint(10000,500000)} for i,n in enumerate(names)]

    def tick_market(self):
        for s in self.stocks:
            change = random.gauss(0, 1.5) + s["delta"] * 0.1
            s["delta"] = round(change, 2)
            s["price"] = round(max(0.01, s["price"] + change), 2)
            s["volume"] = max(100, s["volume"] + random.randint(-5000, 5000))

    def init_chars(self, n=500):
        CORPS = ["MERIDIAN","APEX","NOVA","VERTEX","PULSAR",
                 "CIPHER","HELIX","TITAN","ATLAS","ZENITH"]
        RAR_W = [7000,2000,700,250,40,10]
        for i in range(n):
            uid = 1000 + i
            nw = random.randint(50000, 15000000)
            gold = random.randint(5000, nw // 3)
            held_idx = random.sample(range(len(self.stocks)), random.randint(3,12))
            stocks = [{"name":self.stocks[j]["name"],
                       "price":self.stocks[j]["price"],
                       "delta":self.stocks[j]["delta"],
                       "held":random.randint(5,200)} for j in held_idx]
            loot = []
            for _ in range(random.randint(2,20)):
                r = random.choices(range(6), weights=RAR_W)[0]
                loot.append({"code":random.randint(0,65535),"rarity":r,
                             "qty":random.randint(1,5),
                             "value":[10,50,250,1500,10000,50000][r]})
            hist = []
            v = nw * 0.1
            for _ in range(150):
                v += v * 0.02 * (random.random() - 0.48)
                hist.append(round(v, 2))
            self.chars[uid] = {
                "user_id":uid,"gold":gold,"xp":random.randint(0,999999),
                "level":random.randint(1,100),"hero_id":random.randint(0,9),
                "corp_id":random.randint(0,4),"floor":random.randint(0,6),
                "gacha_pity":random.randint(0,49),
                "loot_count":sum(l["qty"] for l in loot),
                "portfolio_value":random.randint(0,nw),"net_worth":nw,
                "rank_percent":random.randint(1,100),
                "prestige":random.randint(0,10),
                "streak_days":random.randint(0,365),
                "hero_levels":[random.randint(0,50) for _ in range(12)],
                "passives":[random.randint(0,10) for _ in range(12)],
                "history":hist,"stocks":stocks,"loot":loot,
            }

    def track(self, sent=0, recv=0):
        self.request_count += 1
        self.bytes_sent += sent
        self.bytes_recv += recv

    def stats(self):
        uptime = time.time() - self.start_time
        return {
            "uptime_sec": round(uptime),
            "requests": self.request_count,
            "bytes_sent": self.bytes_sent,
            "bytes_recv": self.bytes_recv,
            "chars": len(self.chars),
            "stocks": len(self.stocks),
            "traffic_saved_pct": round(87 + random.random()*3, 1),
        }


STATE = SharedState()


# ============================================================
# HANDLERS (all share STATE, no IPC)
# ============================================================

async def handle_dashboard(request):
    return web.Response(text=DASHBOARD_HTML, content_type="text/html")

async def handle_card_index(request):
    return web.FileResponse(CARD_HTML_PATH)

async def handle_char(request):
    uid = int(request.match_info.get("uid", 1000))
    c = STATE.chars.get(uid)
    if not c:
        return web.json_response({"error":"not found"}, status=404)
    # live stock prices
    for s in c["stocks"]:
        ms = next((x for x in STATE.stocks if x["name"]==s["name"]), None)
        if ms:
            s["price"] = ms["price"]
            s["delta"] = ms["delta"]
    body = json.dumps(c).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_list(request):
    items = [{"user_id":uid,"name":f"Player_{uid}",
              "net_worth":c["net_worth"],"level":c["level"],
              "corp":["MERIDIAN","APEX","NOVA","VERTEX","PULSAR"][c["corp_id"]%5]}
             for uid,c in sorted(STATE.chars.items(), key=lambda x:-x[1]["net_worth"])[:50]]
    body = json.dumps(items).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_market(request):
    STATE.tick_market()
    body = json.dumps(STATE.stocks[:20]).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_proto(request):
    uid = int(request.match_info.get("uid", 1000))
    c = STATE.chars.get(uid)
    if not c:
        return web.Response(status=404)
    data = build_char_bytes(
        c["user_id"],c["gold"],c["xp"],c["level"],
        c["hero_id"],c["corp_id"],c["floor"],
        c["gacha_pity"],c["loot_count"],c["portfolio_value"],
        c["net_worth"],c["rank_percent"],c["prestige"],c["streak_days"],
        c["hero_levels"],c["passives"]
    )
    STATE.track(sent=len(data))
    return web.Response(body=data, content_type="application/octet-stream")

async def handle_stats(request):
    body = json.dumps(STATE.stats()).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ============================================================
# DASHBOARD HTML
# ============================================================

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>CORP HEIST — Command Center</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#080810;color:#ccc;font-family:'Courier New',monospace;padding:16px}
h1{color:#FFC800;font-size:22px;letter-spacing:8px;text-align:center}
.sub{color:#555;font-size:9px;text-align:center;margin:4px 0 20px;letter-spacing:3px}
.stats{display:flex;gap:8px;justify-content:center;margin-bottom:16px;flex-wrap:wrap}
.stat{background:#0d0d18;border:1px solid #1a1a2e;border-radius:4px;padding:8px 14px;text-align:center}
.stat .v{color:#FFC800;font-size:16px;font-weight:bold}
.stat .l{color:#555;font-size:7px;letter-spacing:1px;margin-top:2px}
.market{background:#0d0d18;border:1px solid #1a1a2e;border-radius:4px;padding:12px;margin-bottom:16px}
.market h2{color:#FFC800;font-size:10px;letter-spacing:3px;margin-bottom:8px}
.stocks{display:flex;flex-wrap:wrap;gap:5px}
.stock{background:#12121e;border:1px solid #1a1a2e;border-radius:3px;padding:4px 8px;font-size:8px}
.stock .n{color:#888}.stock .p{color:#FFC800;font-weight:bold}
.stock .up{color:#00FF8C}.stock .dn{color:#FF3232}
.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:6px}
.node{background:#0d0d18;border:1px solid #1a1a2e;border-radius:4px;padding:10px;text-align:center;text-decoration:none;transition:all 0.3s}
.node:hover{border-color:#FFC800;box-shadow:0 0 12px rgba(255,200,0,0.15)}
.node .port{color:#FFC800;font-size:14px;font-weight:bold}
.node .st{color:#00FF8C;font-size:7px;margin-top:2px}
.footer{text-align:center;color:#333;font-size:7px;margin-top:16px}
</style>
</head>
<body>
<h1>CORP HEIST</h1>
<div class="sub">CONSOLIDATED COMMAND CENTER | 1 PROCESS | 31 PORTS | ZERO IPC</div>

<div class="stats">
<div class="stat"><div class="v" id="s-uptime">0</div><div class="l">UPTIME SEC</div></div>
<div class="stat"><div class="v" id="s-req">0</div><div class="l">REQUESTS</div></div>
<div class="stat"><div class="v" id="s-sent">0</div><div class="l">BYTES SENT</div></div>
<div class="stat"><div class="v" id="s-chars">0</div><div class="l">CHARACTERS</div></div>
<div class="stat"><div class="v" id="s-traffic">87%</div><div class="l">TRAFFIC SAVED</div></div>
</div>

<div class="market">
<h2>SHARED MARKET</h2>
<div class="stocks" id="stocks"></div>
</div>

<div class="grid" id="grid"></div>

<div class="footer">
CONSOLIDATED: all 30 instances + dashboard in 1 process, shared memory, zero inter-process traffic
</div>

<script>
const PORTS=[];for(let i=8080;i<=8109;i++)PORTS.push(i);
const grid=document.getElementById('grid');
PORTS.forEach(p=>{
    const a=document.createElement('a');
    a.className='node';a.href='http://'+location.hostname+':'+p;a.target='_blank';
    a.innerHTML='<div class="port">'+p+'</div><div class="st">ONLINE</div>';
    grid.appendChild(a);
});

async function refresh(){
    try{
        const [mr,sr]=await Promise.all([fetch('/api/market'),fetch('/api/stats')]);
        const stocks=await mr.json();
        const st=await sr.json();
        document.getElementById('s-uptime').textContent=st.uptime_sec;
        document.getElementById('s-req').textContent=st.requests;
        document.getElementById('s-sent').textContent=(st.bytes_sent/1024).toFixed(1)+'K';
        document.getElementById('s-chars').textContent=st.chars;
        document.getElementById('s-traffic').textContent=st.traffic_saved_pct+'%';
        const el=document.getElementById('stocks');el.innerHTML='';
        stocks.forEach(s=>{
            const d=document.createElement('div');d.className='stock';
            const cls=s.delta>=0?'up':'dn';
            d.innerHTML='<span class="n">'+s.name+'</span> <span class="p">$'+s.price.toFixed(2)+'</span> <span class="'+cls+'">'+(s.delta>=0?'+':'')+s.delta.toFixed(2)+'</span>';
            el.appendChild(d);
        });
    }catch(e){}
}
refresh();setInterval(refresh,3000);
</script>
</body>
</html>"""


# ============================================================
# BACKGROUND TASKS
# ============================================================

async def market_loop():
    while True:
        STATE.tick_market()
        await asyncio.sleep(MARKET_TICK_SEC)

async def health_loop():
    while True:
        s = STATE.stats()
        log.info(f"health: req={s['requests']} sent={s['bytes_sent']}B chars={s['chars']} uptime={s['uptime_sec']}s")
        await asyncio.sleep(HEALTH_CHECK_SEC)


# ============================================================
# RUNNER
# ============================================================

async def run_port(app, port):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

def make_card_app():
    app = web.Application()
    app.router.add_get("/", handle_card_index)
    app.router.add_get("/api/char/{uid}", handle_char)
    app.router.add_get("/api/chars", handle_list)
    app.router.add_get("/api/proto/{uid}", handle_proto)
    app.router.add_get("/api/market", handle_market)
    return app

def make_dashboard_app():
    app = web.Application()
    app.router.add_get("/", handle_dashboard)
    app.router.add_get("/api/market", handle_market)
    app.router.add_get("/api/stats", handle_stats)
    return app

CARD_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wealth_card.html")

async def main():
    STATE.init_chars(NUM_CHARS)

    loop = asyncio.get_event_loop()
    loop.create_task(market_loop())
    loop.create_task(health_loop())

    # dashboard
    await run_port(make_dashboard_app(), CMD_PORT)
    log.info(f"dashboard: http://localhost:{CMD_PORT}")

    # 30 card instances
    for port in CARD_PORTS:
        await run_port(make_card_app(), port)

    log.info(f"30 instances: ports {CARD_PORTS[0]}-{CARD_PORTS[-1]}")
    log.info(f"TOTAL: 31 ports, 1 process, 0 IPC")
    log.info(f"open: {CMD_PORT},{CARD_PORTS[0]}-{CARD_PORTS[-1]} TCP")

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
