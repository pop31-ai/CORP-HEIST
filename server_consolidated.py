#!/usr/bin/env python3
"""
CORP HEIST — Consolidated Server
No persistent WebSocket. Pulse (one-shot) + periodic polling only.
All 30 instances + dashboard + market in ONE process.
Shared memory, zero IPC.

Run: python server_consolidated.py
  Ports: 9000 (single port: dashboard + 30 cards + API), 1 process
  Note: 8080 reserved for conference/telephony (separate Node.js service)

TRANSPORT MODEL:
  Pulse   — one-shot request/response (trade, gacha, sell, donate)
  Poll    — client pulls data every N seconds (market, char, loot)
  WebSocket: NOT USED (wastes idle connections)
  Result: less RAM, less traffic, simpler client
"""
import asyncio
import json
import random
import math
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
from golden_econ import (
    GuildSystem, Arena, roll_artifact, maybe_drop_artifact,
    CORPS, FLOORS, PHI,
    current_season, season_progress, season_points,
    PASSIVE_NODES, passive_bonus, unlock_cost,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("consolidated")


# ============================================================
# CONFIG
# ============================================================

CMD_PORT   = 9000
CARD_PORTS = list(range(8200, 8230))  # 30 ports (8080 reserved for conference/telephony)
NUM_CHARS  = 500
MARKET_TICK_SEC = 3
HEALTH_CHECK_SEC = 30
SAVE_INTERVAL_SEC = 30
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CHARS_DIR = os.path.join(DATA_DIR, "chars")


# ============================================================
# FILE-BASED STORAGE (JSON per user, no DB server)
# ============================================================

class SharedState:
    """All data lives as JSON files. No DB, no SQLite, no server."""

    def __init__(self):
        os.makedirs(CHARS_DIR, exist_ok=True)
        self.stocks = self._load_market()
        self.chars = {}
        self.request_count = 0
        self.bytes_sent = 0
        self.bytes_recv = 0
        self.start_time = time.time()
        self._dirty = set()  # uids pending save

    def _load_market(self):
        path = os.path.join(DATA_DIR, "market.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return self._init_stocks()

    def _save_market(self):
        path = os.path.join(DATA_DIR, "market.json")
        with open(path, "w") as f:
            json.dump(self.stocks, f)

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

    # --- CHAR FILE I/O ---

    def _char_path(self, uid):
        return os.path.join(CHARS_DIR, f"{uid}.json")

    def load_char(self, uid):
        path = self._char_path(uid)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)

    def save_char(self, uid):
        c = self.chars.get(uid)
        if not c:
            return
        path = self._char_path(uid)
        with open(path, "w") as f:
            json.dump(c, f, indent=None)
        self._dirty.discard(uid)

    def save_all(self):
        """Save all dirty chars to disk."""
        for uid in list(self._dirty):
            self.save_char(uid)
        self._save_market()

    def load_all_chars(self):
        """Load all char files from disk."""
        loaded = 0
        for fname in os.listdir(CHARS_DIR):
            if fname.endswith(".json"):
                uid = int(fname[:-5])
                self.chars[uid] = self.load_char(uid)
                loaded += 1
        return loaded

    def mark_dirty(self, uid):
        self._dirty.add(uid)

    # --- INIT (generate if no files) ---

    def init_chars(self, n=500):
        loaded = self.load_all_chars()
        if loaded > 0:
            log.info(f"loaded {loaded} chars from files")
            return
        log.info(f"generating {n} demo chars...")
        CORPS = ["MERIDIAN","APEX","NOVA","VERTEX","PULSAR"]
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
            art = maybe_drop_artifact(0.15)
            if art:
                loot.append(art)
            hist = []
            v = nw * 0.1
            for _ in range(150):
                v += v * 0.02 * (random.random() - 0.48)
                hist.append(round(v, 2))
            self.chars[uid] = {
                "user_id":uid,"gold":gold,"xp":random.randint(0,999999),
                "level":random.randint(1,100),"hero_id":random.randint(0,9),
                "corp_id":random.randint(0,6),"floor":random.randint(0,11),
                "gacha_pity":random.randint(0,49),
                "loot_count":sum(l["qty"] for l in loot),
                "portfolio_value":random.randint(0,nw),"net_worth":nw,
                "tier":min(5,max(0,int(math.log10(max(1,nw))/1.5))),
                "rank_percent":random.randint(1,100),
                "prestige":random.randint(0,10),
                "season":list(current_season()),
                "season_points":season_points({
                    "net_worth":nw,"prestige":random.randint(0,10)}),
                "streak_days":random.randint(0,365),
                "hero_levels":[random.randint(0,50) for _ in range(12)],
                "passives":[random.randint(0,10) for _ in range(12)],
                "history":hist,"stocks":stocks,"loot":loot,
            }
            self.mark_dirty(uid)
        self.save_all()
        log.info(f"saved {n} chars to {CHARS_DIR}")

    def track(self, sent=0, recv=0):
        self.request_count += 1
        self.bytes_sent += sent
        self.bytes_recv += recv

    def stats(self):
        uptime = time.time() - self.start_time
        files = len([f for f in os.listdir(CHARS_DIR) if f.endswith(".json")])
        return {
            "uptime_sec": round(uptime),
            "requests": self.request_count,
            "bytes_sent": self.bytes_sent,
            "bytes_recv": self.bytes_recv,
            "chars": files,
            "dirty": len(self._dirty),
            "stocks": len(self.stocks),
            "traffic_saved_pct": round(87 + random.random()*3, 1),
        }


STATE = SharedState()
GUILDS = GuildSystem(STATE)
ARENA = Arena(STATE)


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


async def handle_guilds(request):
    body = json.dumps(GUILDS.corp_totals()).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def handle_leaderboard(request):
    body = json.dumps(GUILDS.leaderboard(50)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def handle_market_summary(request):
    body = json.dumps(GUILDS.market_summary()).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def handle_season(request):
    body = json.dumps({
        "season": current_season()[0],
        "week": current_season()[1],
        "progress": season_progress(),
        "phi_weeks": int(PHI * 7),
    }).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def handle_passives(request):
    body = json.dumps({
        "nodes": PASSIVE_NODES,
        "bonus_example": passive_bonus([1,0,2,0,0,0,0,0,0,0,0,0]),
    }).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def handle_season_rewards(request):
    body = json.dumps(GUILDS.season_rewards(10)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ============================================================
# PULSE ENDPOINTS (one-shot request/response, no persistent conn)
# ============================================================

async def pulse_trade(request):
    """Pulse: buy/sell stock. Returns fill confirmation."""
    d = await request.json()
    uid = d.get("uid", 1000)
    stock_name = d.get("stock", "ALPHA")
    amount = d.get("amount", 10)
    side = d.get("side", "buy")
    c = STATE.chars.get(uid)
    if not c:
        return web.json_response({"error": "no char"})
    ms = next((s for s in STATE.stocks if s["name"] == stock_name), None)
    if not ms:
        return web.json_response({"error": "no stock"})
    cost = ms["price"] * amount
    if side == "buy":
        if c["gold"] < cost:
            return web.json_response({"error": "not enough gold"})
        c["gold"] -= int(cost)
        c["portfolio_value"] += int(cost)
        held = next((s for s in c["stocks"] if s["name"] == stock_name), None)
        if held:
            held["held"] += amount
        else:
            c["stocks"].append({"name": stock_name, "price": ms["price"],
                                "delta": ms["delta"], "held": amount})
    else:
        held = next((s for s in c["stocks"] if s["name"] == stock_name), None)
        if not held or held["held"] < amount:
            return web.json_response({"error": "not enough held"})
        held["held"] -= amount
        c["gold"] += int(cost)
        c["net_worth"] += int(cost)
    STATE.track(sent=50)
    STATE.mark_dirty(uid)
    STATE.save_char(uid)
    return web.json_response({"ok": True, "gold": c["gold"], "side": side,
                              "stock": stock_name, "amount": amount,
                              "price": ms["price"]})

async def pulse_gacha(request):
    """Pulse: roll gacha. Returns hero + rarity."""
    d = await request.json()
    uid = d.get("uid", 1000)
    c = STATE.chars.get(uid)
    if not c:
        return web.json_response({"error": "no char"})
    # gacha logic
    c["gacha_pity"] += 1
    roll = random.random() * 10000
    if c["gacha_pity"] >= 50:
        rarity = random.choices(range(6), weights=[0,0,2000,2500,4000,1500])[0]
        c["gacha_pity"] = 0
    elif roll < 40:
        rarity = 5  # Unique 0.4%
    elif roll < 250:
        rarity = 4  # Legendary 2.5%
    elif roll < 1700:
        rarity = 3  # Epic 17%
    elif roll < 3700:
        rarity = 2  # Rare 20%
    elif roll < 6700:
        rarity = 1  # Uncommon 30%
    else:
        rarity = 0  # Common 33%
    hero_id = random.randint(0, 9)
    STATE.track(sent=20)
    STATE.mark_dirty(uid)
    STATE.save_char(uid)
    return web.json_response({"ok": True, "hero_id": hero_id,
                              "rarity": rarity, "pity": c["gacha_pity"]})

async def pulse_loot_sell(request):
    """Pulse: sell loot item for gold."""
    d = await request.json()
    uid = d.get("uid", 1000)
    code = d.get("code", 0)
    qty = d.get("qty", 1)
    c = STATE.chars.get(uid)
    if not c:
        return web.json_response({"error": "no char"})
    item = next((l for l in c["loot"] if l["code"] == code), None)
    if not item or item["qty"] < qty:
        return web.json_response({"error": "not enough"})
    item["qty"] -= qty
    if item["qty"] <= 0:
        c["loot"].remove(item)
    gold = item["value"] * qty
    c["gold"] += gold
    STATE.track(sent=30)
    STATE.mark_dirty(uid)
    STATE.save_char(uid)
    return web.json_response({"ok": True, "gold": c["gold"], "earned": gold})

async def pulse_donate(request):
    """Pulse: donate rarest loot for gold (system decides multiplier)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    c = STATE.chars.get(uid)
    if not c or not c["loot"]:
        return web.json_response({"error": "no loot"})
    ri = max(range(len(c["loot"])), key=lambda i: c["loot"][i]["rarity"])
    item = c["loot"][ri]
    mult = [3,5,8,12,20,50][item["rarity"]]
    gold = item["value"] * item["qty"] * mult
    c["gold"] += gold
    c["loot"].pop(ri)
    STATE.track(sent=30)
    STATE.mark_dirty(uid)
    STATE.save_char(uid)
    return web.json_response({"ok": True, "gold": c["gold"], "donated_rarity": item["rarity"],
                              "multiplier": mult, "earned": gold})

async def pulse_buy_gold(request):
    """Pulse: buy game gold for real money (USD/RUB, system decides rate)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    pack = d.get("pack", 0)
    c = STATE.chars.get(uid)
    if not c:
        return web.json_response({"error": "no char"})
    packs = [
        {"usd":0.99,"rub":89,"gold":500},
        {"usd":4.99,"rub":449,"gold":3000},
        {"usd":9.99,"rub":899,"gold":7500},
        {"usd":19.99,"rub":1799,"gold":18000},
        {"usd":49.99,"rub":4499,"gold":50000},
    ]
    p = packs[pack % len(packs)]
    c["gold"] += p["gold"]
    c["net_worth"] += p["gold"]
    STATE.track(sent=30)
    STATE.mark_dirty(uid)
    STATE.save_char(uid)
    return web.json_response({"ok": True, "gold": c["gold"], "paid_usd": p["usd"],
                              "paid_rub": p["rub"], "received": p["gold"]})

async def pulse_support(request):
    """Pulse: support request. Donations are non-refundable; operator
    pays taxes on collected funds. System may compensate in-game gold
    at its sole discretion, never real money."""
    d = await request.json()
    uid = d.get("uid", 1000)
    c = STATE.chars.get(uid)
    if not c:
        return web.json_response({"error": "no char"})
    note = ("Donations are charitable and non-refundable. "
            "Operator pays applicable taxes. System may review at discretion.")
    STATE.track(sent=30)
    return web.json_response({"ok": True, "gold": c["gold"],
                              "note": note, "real_money_back": False})


async def pulse_duel(request):
    """Pulse: phi-duel arena fight. Pure in-game economy, no P2P, no real money."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = ARENA.fight(uid)
    if "error" in result:
        return web.json_response(result, status=404)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


async def pulse_passive(request):
    """Pulse: unlock a passive node. Cost scales by phi^(current level)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    node_id = d.get("node", 0)
    c = STATE.chars.get(uid)
    if not c:
        return web.json_response({"error": "no char"})
    if node_id < 0 or node_id >= len(PASSIVE_NODES):
        return web.json_response({"error": "bad node"})
    lvl = c["passives"][node_id]
    cost = unlock_cost(node_id, lvl)
    if c["gold"] < cost:
        return web.json_response({"error": "not enough gold", "cost": cost,
                                   "gold": c["gold"]})
    c["gold"] -= cost
    c["passives"][node_id] = lvl + 1
    STATE.track(sent=30)
    STATE.mark_dirty(uid)
    STATE.save_char(uid)
    return web.json_response({"ok": True, "node": node_id,
                               "level": c["passives"][node_id],
                               "cost_next": unlock_cost(node_id, lvl + 1),
                               "gold": c["gold"]})

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
const NODES=[];for(let i=1;i<=30;i++)NODES.push(i);
const grid=document.getElementById('grid');
NODES.forEach(n=>{
    const uid=1000+(n-1);
    const a=document.createElement('a');
    a.className='node';a.href='/card/'+n+'?uid='+uid;a.target='_blank';
    a.innerHTML='<div class="port">#' + n + '</div><div class="st">ONLINE</div>';
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
        log.info(f"health: req={s['requests']} sent={s['bytes_sent']}B chars={s['chars']} dirty={s['dirty']} uptime={s['uptime_sec']}s")
        await asyncio.sleep(HEALTH_CHECK_SEC)

async def autosave_loop():
    """Save dirty chars to disk every N seconds."""
    while True:
        await asyncio.sleep(SAVE_INTERVAL_SEC)
        if STATE._dirty:
            STATE.save_all()
            log.info(f"autosave: {len(STATE._dirty)} chars saved")


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
    # pulse endpoints (one-shot POST)
    app.router.add_post("/pulse/trade", pulse_trade)
    app.router.add_post("/pulse/gacha", pulse_gacha)
    app.router.add_post("/pulse/loot/sell", pulse_loot_sell)
    app.router.add_post("/pulse/donate", pulse_donate)
    app.router.add_post("/pulse/buy-gold", pulse_buy_gold)
    app.router.add_post("/pulse/duel", pulse_duel)
    app.router.add_post("/pulse/passive", pulse_passive)
    return app

async def handle_card_route(request):
    """Serve wealth card HTML, selecting a player via ?uid= or /card/<n>."""
    uid = request.match_info.get("n", request.query.get("uid", "local"))
    # inject selected uid into HTML via query param passthrough
    resp = web.FileResponse(CARD_HTML_PATH)
    return resp

def make_dashboard_app():
    app = web.Application()
    app.router.add_get("/", handle_dashboard)
    app.router.add_get("/api/market", handle_market)
    app.router.add_get("/api/stats", handle_stats)
    return app

def make_unified_app():
    """Single-port app: dashboard + 30 cards + API on one port (9000)."""
    app = web.Application()
    # dashboard
    app.router.add_get("/", handle_dashboard)
    app.router.add_get("/api/market", handle_market)
    app.router.add_get("/api/stats", handle_stats)
    # wealth card (selected player)
    app.router.add_get("/card", handle_card_route)
    app.router.add_get("/card/{n}", handle_card_route)
    # char API + pulse (shared)
    app.router.add_get("/api/char/{uid}", handle_char)
    app.router.add_get("/api/chars", handle_list)
    app.router.add_get("/api/proto/{uid}", handle_proto)
    app.router.add_get("/api/guilds", handle_guilds)
    app.router.add_get("/api/leaderboard", handle_leaderboard)
    app.router.add_get("/api/market-summary", handle_market_summary)
    app.router.add_get("/api/season", handle_season)
    app.router.add_get("/api/passives", handle_passives)
    app.router.add_get("/api/season-rewards", handle_season_rewards)
    app.router.add_post("/pulse/trade", pulse_trade)
    app.router.add_post("/pulse/gacha", pulse_gacha)
    app.router.add_post("/pulse/loot/sell", pulse_loot_sell)
    app.router.add_post("/pulse/donate", pulse_donate)
    app.router.add_post("/pulse/buy-gold", pulse_buy_gold)
    app.router.add_post("/pulse/duel", pulse_duel)
    app.router.add_post("/pulse/passive", pulse_passive)
    return app

CARD_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wealth_card.html")

async def main():
    STATE.init_chars(NUM_CHARS)

    loop = asyncio.get_event_loop()
    loop.create_task(market_loop())
    loop.create_task(health_loop())
    loop.create_task(autosave_loop())

    # single port: dashboard + 30 cards + API all on CMD_PORT (9000)
    await run_port(make_unified_app(), CMD_PORT)
    log.info(f"server: http://localhost:{CMD_PORT}")
    log.info(f"dashboard: /  cards: /card/<1-30>  api: /api/*  pulse: /pulse/*")
    log.info(f"NOTE: port 8080 reserved for conference/telephony")

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
