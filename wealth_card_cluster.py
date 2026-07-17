#!/usr/bin/env python3
"""
CORP HEIST — 30 Wealth Card Instances
Each on its own port, shared traffic pool, unique portfolios.
Run: python wealth_card_cluster.py
Ports: 8080-8109 (30 instances)
"""
import asyncio
import json
import random
import sys
import os
import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiohttp import web
from protocol import build_char_bytes, parse_char, CHAR_SIZE

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wealth_card.html")

# ============================================================
# SHARED TRAFFIC POOL (one stock market, all 30 see it)
# ============================================================

STOCK_NAMES = [
    "ALPHA", "BETA", "GAMMA", "DELTA", "OMEGA",
    "SIGMA", "THETA", "ZETA", "PI", "RHO",
    "KAPPA", "LAMBDA", "MU", "NU", "XI",
    "OMIKRON", "CHI", "PSI", "PHI", "TAU",
]

STOCKS = []
for i, name in enumerate(STOCK_NAMES):
    STOCKS.append({
        "id": i,
        "name": name,
        "price": round(random.uniform(5, 200), 2),
        "delta": round(random.uniform(-3, 3), 2),
        "volume": random.randint(10000, 500000),
    })

def tick_market():
    """Shared market tick — all instances see same prices."""
    for s in STOCKS:
        change = random.gauss(0, 1.5) + s["delta"] * 0.1
        s["delta"] = round(change, 2)
        s["price"] = round(max(0.01, s["price"] + change), 2)
        s["volume"] = max(100, s["volume"] + random.randint(-5000, 5000))


# ============================================================
# CHARACTER GENERATOR
# ============================================================

CORP_NAMES = ["MERIDIAN", "APEX", "NOVA", "VERTEX", "PULSAR",
              "CIPHER", "HELIX", "TITAN", "ATLAS", "ZENITH"]

LOOT_CATS = ["watches", "cars", "realestate", "yachts", "jewelry",
             "art", "restaurants", "fashion", "tech", "jets"]

RARITY_WEIGHTS = [7000, 2000, 700, 250, 40, 10]

def gen_char(uid):
    nw = random.randint(50000, 15000000)
    gold = random.randint(5000, nw // 3)
    hl = [random.randint(0, 50) for _ in range(12)]
    pa = [random.randint(0, 10) for _ in range(12)]
    num_stocks = random.randint(3, 12)
    held = random.sample(range(len(STOCK_NAMES)), num_stocks)
    stocks = [{"name": STOCK_NAMES[i], "price": STOCKS[i]["price"],
               "delta": STOCKS[i]["delta"],
               "held": random.randint(5, 200)} for i in held]
    loot = []
    for _ in range(random.randint(2, 20)):
        r = random.choices(range(6), weights=RARITY_WEIGHTS)[0]
        loot.append({
            "code": random.randint(0, 65535),
            "rarity": r,
            "qty": random.randint(1, 5),
            "value": [10, 50, 250, 1500, 10000, 50000][r],
        })
    hist = []
    v = nw * 0.1
    for _ in range(150):
        v += v * 0.02 * (random.random() - 0.48)
        hist.append(round(v, 2))
    return {
        "user_id": uid, "gold": gold,
        "xp": random.randint(0, 999999),
        "level": random.randint(1, 100),
        "hero_id": random.randint(0, 9),
        "corp_id": random.randint(0, 4),
        "floor": random.randint(0, 6),
        "gacha_pity": random.randint(0, 49),
        "loot_count": sum(l["qty"] for l in loot),
        "portfolio_value": random.randint(0, nw),
        "net_worth": nw,
        "rank_percent": random.randint(1, 100),
        "prestige": random.randint(0, 10),
        "streak_days": random.randint(0, 365),
        "hero_levels": hl, "passives": pa,
        "history": hist, "stocks": stocks, "loot": loot,
    }


# ============================================================
# CHARACTERS DB (shared across all 30 instances)
# ============================================================

CHARS = {}
def init_chars(count=500):
    for i in range(count):
        uid = 1000 + i
        CHARS[uid] = gen_char(uid)


# ============================================================
# HTTP HANDLERS (shared, port doesn't matter)
# ============================================================

async def handle_index(request):
    return web.FileResponse(HTML_PATH)

async def handle_char(request):
    uid = int(request.match_info.get("uid", 1000))
    if uid not in CHARS:
        return web.json_response({"error": "not found"}, status=404)
    # update stock prices from shared market
    c = CHARS[uid]
    for s in c["stocks"]:
        ms = next((x for x in STOCKS if x["name"] == s["name"]), None)
        if ms:
            s["price"] = ms["price"]
            s["delta"] = ms["delta"]
    return web.json_response(c)

async def handle_list(request):
    items = [{"user_id": uid, "name": f"Player_{uid}",
              "net_worth": c["net_worth"], "level": c["level"],
              "corp": CORP_NAMES[c["corp_id"] % len(CORP_NAMES)]}
             for uid, c in sorted(CHARS.items(), key=lambda x: -x[1]["net_worth"])[:50]]
    return web.json_response(items)

async def handle_proto(request):
    uid = int(request.match_info.get("uid", 1000))
    if uid not in CHARS:
        return web.Response(status=404)
    c = CHARS[uid]
    data = build_char_bytes(
        c["user_id"], c["gold"], c["xp"], c["level"],
        c["hero_id"], c["corp_id"], c["floor"],
        c["gacha_pity"], c["loot_count"], c["portfolio_value"],
        c["net_worth"], c["rank_percent"], c["prestige"], c["streak_days"],
        c["hero_levels"], c["passives"]
    )
    return web.Response(body=data, content_type="application/octet-stream")

async def handle_market(request):
    """Shared market data — same for all 30 instances."""
    tick_market()
    return web.json_response(STOCKS[:20])


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>CORP HEIST — Command Center</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#080810;color:#ccc;font-family:'Courier New',monospace;padding:20px}
h1{color:#FFC800;font-size:20px;letter-spacing:6px;text-align:center;margin-bottom:4px}
.sub{color:#555;font-size:9px;text-align:center;margin-bottom:24px;letter-spacing:3px}
.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;max-width:1100px;margin:0 auto}
.node{background:#0d0d18;border:1px solid #1a1a2e;border-radius:4px;padding:12px;text-align:center;text-decoration:none;transition:all 0.3s}
.node:hover{border-color:#FFC800;box-shadow:0 0 12px rgba(255,200,0,0.15)}
.node .port{color:#FFC800;font-size:16px;font-weight:bold}
.node .status{font-size:8px;margin-top:4px}
.node .online{color:#00FF8C}
.market{background:#0d0d18;border:1px solid #1a1a2e;border-radius:4px;padding:16px;margin:20px auto;max-width:1100px}
.market h2{color:#FFC800;font-size:11px;letter-spacing:3px;margin-bottom:10px}
.stocks{display:flex;flex-wrap:wrap;gap:6px}
.stock{background:#12121e;border:1px solid #1a1a2e;border-radius:3px;padding:6px 10px;font-size:8px}
.stock .name{color:#888}
.stock .price{color:#FFC800;font-weight:bold}
.stock .up{color:#00FF8C}
.stock .down{color:#FF3232}
.footer{text-align:center;color:#333;font-size:8px;margin-top:20px}
</style>
</head>
<body>
<h1>CORP HEIST</h1>
<div class="sub">COMMAND CENTER | 30 INSTANCES | 500 PLAYERS</div>

<div class="market">
<h2>SHARED MARKET</h2>
<div class="stocks" id="stocks"></div>
</div>

<div class="grid" id="grid"></div>

<div class="footer">
CORP HEIST Command Center | Binary Protocol v2 | 1200 render algorithms | All ports 8080-8109
</div>

<script>
const PORTS=[];for(let i=8080;i<=8109;i++)PORTS.push(i);
const grid=document.getElementById('grid');
PORTS.forEach(p=>{
    const a=document.createElement('a');
    a.className='node';a.href='http://'+location.hostname+':'+p;a.target='_blank';
    a.innerHTML='<div class="port">'+p+'</div><div class="status online">ONLINE</div>';
    grid.appendChild(a);
});

async function refreshMarket(){
    try{
        const r=await fetch('/api/market');
        const stocks=await r.json();
        const el=document.getElementById('stocks');
        el.innerHTML='';
        stocks.forEach(s=>{
            const d=document.createElement('div');d.className='stock';
            const cls=s.delta>=0?'up':'down';
            d.innerHTML='<span class="name">'+s.name+'</span> <span class="price">$'+s.price.toFixed(2)+'</span> <span class="'+cls+'">'+(s.delta>=0?'+':'')+s.delta.toFixed(2)+'</span>';
            el.appendChild(d);
        });
    }catch(e){}
}
refreshMarket();
setInterval(refreshMarket,3000);
</script>
</body>
</html>"""


async def handle_dashboard(request):
    return web.Response(text=DASHBOARD_HTML, content_type="text/html")


# ============================================================
# MARKET TICKER (shared background task)
# ============================================================

async def market_ticker():
    while True:
        tick_market()
        await asyncio.sleep(2)


# ============================================================
# CLUSTER RUNNER
# ============================================================

PORTS = list(range(8080, 8110))  # 8080-8109 = 30 ports
CMD_PORT = 9000  # command dashboard

async def run_instance(app, port):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    init_chars(500)

    # shared app routes
    def make_app():
        app = web.Application()
        app.router.add_get("/", handle_index)
        app.router.add_get("/api/char/{uid}", handle_char)
        app.router.add_get("/api/chars", handle_list)
        app.router.add_get("/api/proto/{uid}", handle_proto)
        app.router.add_get("/api/market", handle_market)
        return app

    # start market ticker
    loop = asyncio.get_event_loop()
    loop.create_task(market_ticker())

    # command dashboard on port 9000
    dash_app = web.Application()
    dash_app.router.add_get("/", handle_dashboard)
    dash_app.router.add_get("/api/market", handle_market)
    dash_runner = web.AppRunner(dash_app)
    await dash_runner.setup()
    dash_site = web.TCPSite(dash_runner, "0.0.0.0", CMD_PORT)
    await dash_site.start()

    # start 30 instances
    tasks = []
    for port in PORTS:
        app = make_app()
        tasks.append(run_instance(app, port))

    await asyncio.gather(*tasks)

    print(f"\n{'='*50}")
    print(f"  CORP HEIST — 30 Wealth Card Instances")
    print(f"{'='*50}")
    print(f"  COMMAND CENTER:  http://localhost:{CMD_PORT}")
    print(f"  30 INSTANCES:    ports {PORTS[0]}-{PORTS[-1]}")
    print(f"  500 players | Shared market | 1200 render algorithms")
    print(f"{'='*50}")
    print(f"  Open ports: {CMD_PORT}, {PORTS[0]}-{PORTS[-1]} TCP")
    print(f"{'='*50}\n")

    # keep alive
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
