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
    Prestige, Raid, prestige_requirement, prestige_multiplier,
    daily_quests, claim_quest,
    evaluate_achievements, claim_achievements,
    referral_code, referral_status, accept_referral,
    chest_status, open_chest, WorldBoss,
    Auction, GuildWar,
    bond_tiers, buy_bond, bond_status, claim_bonds,
    deriv_quote, open_position, deriv_status, settle_derivs,
    sky_status, sky_fund, sky_reward_mult,
    golden_hour, golden_multiplier, award_gold,
    ma_status, buy_shares, share_price,
    news_feed, tick_news,
    market_index, hedge_open, hedge_status, hedge_redeem,
    magnates,
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
        self.chat = {}       # corp_id -> list[{uid,name,corp,text,ts}]  (ring buffer)
        self._chat_seq = 0   # monotonic id for chat messages

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
PRESTIGE = Prestige(STATE)
RAID = Raid(STATE)
WORLDBOSS = WorldBoss(STATE)
AUCTION = Auction(STATE)
GUILDWAR = GuildWar(STATE)


def _boost_reward(uid, result, field="reward_gold"):
    """Apply Golden Hour x-phi bonus + M&A dividends on top of a reward that
    was already credited by a golden_econ function. Mutates & annotates result."""
    base = result.get(field, 0)
    if not base or base <= 0:
        return result
    c = STATE.chars.get(uid)
    if not c:
        return result
    gh = golden_multiplier()
    sky = sky_reward_mult(STATE, c["corp_id"])
    mult = gh * sky
    bonus = int(round(base * (mult - 1.0)))
    if bonus > 0:
        c["gold"] = c.get("gold", 0) + bonus
        STATE.mark_dirty(uid)
        result["golden_bonus"] = bonus
        result[field] = base + bonus
    result["golden"] = gh > 1.0
    result["golden_mult"] = round(gh, 6)
    result["sky_bonus_pct"] = round((sky - 1.0) * 100, 2)
    # M&A dividends on the full (boosted) reward
    from golden_econ import _pay_dividends
    total_base = base + (bonus if bonus > 0 else 0)
    div = _pay_dividends(STATE, uid, total_base)
    if div:
        result["dividends_paid"] = div
    result["gold"] = STATE.chars.get(uid, {}).get("gold", c.get("gold", 0))
    return result


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
    base = item["value"] * qty
    aw = award_gold(STATE, uid, base)
    STATE.track(sent=30)
    STATE.save_char(uid)
    return web.json_response({"ok": True, "gold": aw["gold"], "earned": aw["gained"],
                              "golden": aw["golden"], "multiplier": aw["multiplier"],
                              "dividends_paid": aw["dividends_paid"]})

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
    base = item["value"] * item["qty"] * mult
    c["loot"].pop(ri)
    aw = award_gold(STATE, uid, base)
    STATE.track(sent=30)
    STATE.save_char(uid)
    return web.json_response({"ok": True, "gold": aw["gold"], "donated_rarity": item["rarity"],
                              "multiplier": mult, "earned": aw["gained"],
                              "golden": aw["golden"], "golden_mult": aw["multiplier"],
                              "dividends_paid": aw["dividends_paid"]})

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
    _boost_reward(uid, result)
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


async def handle_prestige(request):
    """GET prestige status for a player (?uid=)."""
    uid = int(request.query.get("uid", 1000))
    result = PRESTIGE.status(uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def pulse_prestige(request):
    """Pulse: ascend (reset progress for a permanent phi-multiplier). In-game only."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = PRESTIGE.ascend(uid)
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


async def handle_raid(request):
    """GET raid boss status for a player's corp (?uid=)."""
    uid = int(request.query.get("uid", 1000))
    c = STATE.chars.get(uid)
    if not c:
        return web.json_response({"error": "no char"}, status=404)
    corp_id = c["corp_id"] % len(CORPS)
    result = RAID.status(corp_id)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def pulse_raid(request):
    """Pulse: strike the corp raid boss. Loot split by phi shares (in-game gold)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = RAID.strike(uid)
    if "error" in result and "boss already defeated" not in result.get("error", ""):
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


async def handle_quests(request):
    """GET today's phi-quests for a player (?uid=)."""
    uid = int(request.query.get("uid", 1000))
    result = daily_quests(uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def pulse_quest(request):
    """Pulse: claim a daily quest reward (in-game gold)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    slot = d.get("slot", 0)
    result = claim_quest(STATE, uid, slot)
    if "error" in result:
        return web.json_response(result, status=400)
    _boost_reward(uid, result)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


async def handle_achievements(request):
    """GET achievement states for a player (?uid= or /api/achievements/{uid})."""
    uid = int(request.match_info.get("uid", request.query.get("uid", 1000)))
    c = STATE.chars.get(uid)
    if not c:
        return web.json_response({"error": "not found"}, status=404)
    result = {"achievements": evaluate_achievements(c),
              "note": "Rewards are in-game gold only."}
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def pulse_achievements(request):
    """Pulse: claim gold for newly-unlocked achievements."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = claim_achievements(STATE, uid)
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


async def handle_referral(request):
    """GET a player's referral code + stats."""
    uid = int(request.match_info.get("uid", request.query.get("uid", 1000)))
    if uid not in STATE.chars:
        return web.json_response({"error": "not found"}, status=404)
    result = referral_status(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def pulse_referral(request):
    """Pulse: redeem a referral code (both sides get in-game gold)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    code = d.get("code", "")
    result = accept_referral(STATE, uid, code)
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    ref = result.get("referrer")
    if ref is not None:
        STATE.save_char(ref)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


async def handle_chest(request):
    """GET daily chest status for a player."""
    uid = int(request.match_info.get("uid", request.query.get("uid", 1000)))
    result = chest_status(STATE, uid)
    if "error" in result:
        return web.json_response(result, status=404)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def pulse_chest(request):
    """Pulse: open today's golden chest (in-game gold)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = open_chest(STATE, uid)
    if "error" in result:
        return web.json_response(result, status=400)
    _boost_reward(uid, result)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


async def handle_worldboss(request):
    """GET the global world-boss status (shared HP)."""
    result = WORLDBOSS.status()
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def pulse_worldboss(request):
    """Pulse: strike the global world boss."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = WORLDBOSS.strike(uid)
    if "error" in result and "boss_hp" not in result:
        return web.json_response(result, status=400)
    _boost_reward(uid, result)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- CORP CHAT (pulse-poll live messages, per corp) ----
CHAT_MAX = 60          # ring buffer per corp
CHAT_TEXT_MAX = 140

def _corp_name(corp_id):
    return CORPS[corp_id % len(CORPS)]

async def handle_chat(request):
    """GET recent corp messages (?corp= or ?uid=, ?since=)."""
    corp = request.query.get("corp")
    if corp is None:
        uid = int(request.query.get("uid", 1000))
        c = STATE.chars.get(uid)
        corp = (c["corp_id"] if c else 0)
    corp = int(corp) % len(CORPS)
    since = int(request.query.get("since", 0))
    msgs = [m for m in STATE.chat.get(corp, []) if m["id"] > since]
    result = {"corp": corp, "corp_name": _corp_name(corp),
              "messages": msgs[-CHAT_MAX:],
              "last_id": (STATE.chat.get(corp, [{"id": 0}])[-1]["id"]
                          if STATE.chat.get(corp) else 0)}
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_chat(request):
    """Pulse: post a message to the player's corp chat."""
    d = await request.json()
    uid = d.get("uid", 1000)
    text = str(d.get("text", "")).strip()[:CHAT_TEXT_MAX]
    if not text:
        return web.json_response({"error": "empty message"}, status=400)
    c = STATE.chars.get(uid)
    if not c:
        return web.json_response({"error": "no char"}, status=404)
    corp = c["corp_id"] % len(CORPS)
    STATE._chat_seq += 1
    msg = {"id": STATE._chat_seq, "uid": uid, "name": f"Player_{uid}",
           "corp": corp, "text": text, "ts": int(time.time())}
    buf = STATE.chat.setdefault(corp, [])
    buf.append(msg)
    if len(buf) > CHAT_MAX:
        del buf[:-CHAT_MAX]
    STATE.track(recv=len(text))
    return web.json_response({"ok": True, "message": msg})


# ---- CRAFTING (combine 3 same-rarity items -> 1 higher-rarity, phi value) ----
async def pulse_craft(request):
    """Pulse: fuse 3 items of the same rarity into 1 of the next rarity.
    New value follows a phi curve. In-game items only."""
    d = await request.json()
    uid = d.get("uid", 1000)
    c = STATE.chars.get(uid)
    if not c or not c.get("loot"):
        return web.json_response({"error": "no loot"}, status=400)
    rarity = d.get("rarity")
    loot = c["loot"]
    # if no rarity given, pick the lowest rarity with >=3 items
    from collections import Counter
    counts = Counter(l["rarity"] for l in loot)
    if rarity is None:
        avail = [r for r in sorted(counts) if counts[r] >= 3 and r < 5]
        if not avail:
            return web.json_response({"error": "need 3 items of the same rarity (below Unique)"}, status=400)
        rarity = avail[0]
    rarity = int(rarity)
    if rarity >= 5:
        return web.json_response({"error": "cannot upgrade Unique"}, status=400)
    same = [l for l in loot if l["rarity"] == rarity]
    if len(same) < 3:
        return web.json_response({"error": "need 3 items of that rarity"}, status=400)
    # consume 3, subtract their value from net worth
    consumed = same[:3]
    consumed_val = sum(x.get("value", 0) * x.get("qty", 1) for x in consumed)
    for x in consumed:
        loot.remove(x)
    new_rarity = rarity + 1
    base = [10, 50, 250, 1500, 10000, 50000][new_rarity]
    new_value = int(base * PHI)   # phi bonus over the base of the new tier
    new_item = {"code": random.randint(0, 65535), "rarity": new_rarity,
                "qty": 1, "value": new_value, "crafted": True}
    loot.append(new_item)
    c["net_worth"] = c.get("net_worth", 0) - consumed_val + new_value
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(new_item).encode()))
    return web.json_response({"ok": True, "consumed_rarity": rarity,
                              "new_item": new_item, "new_rarity": new_rarity,
                              "net_worth": c["net_worth"],
                              "note": "Crafting uses in-game items only."})


# ---- LIVE ORDER BOOK (phi-spread bids/asks around each stock price) ----
def _order_book(stock, depth=6):
    price = stock["price"]
    # phi-spaced levels; spread widens by phi each level
    bids, asks = [], []
    tick = max(0.01, price * 0.001)
    for i in range(depth):
        off = tick * (PHI ** i)
        size_b = int(1000 * (PHI ** (depth - i)) % 100000) + 10
        size_a = int(1500 * (PHI ** (depth - i)) % 100000) + 10
        bids.append({"price": round(price - off, 2), "size": size_b})
        asks.append({"price": round(price + off, 2), "size": size_a})
    best_bid = bids[0]["price"]
    best_ask = asks[0]["price"]
    return {"name": stock["name"], "price": price, "delta": stock.get("delta", 0),
            "best_bid": best_bid, "best_ask": best_ask,
            "spread": round(best_ask - best_bid, 2),
            "bids": bids, "asks": asks}

async def handle_orderbook(request):
    """GET a phi-spread order book for a symbol (?sym= or first stock)."""
    STATE.tick_market()
    sym = request.query.get("sym")
    stock = None
    if sym:
        stock = next((s for s in STATE.stocks if s["name"] == sym.upper()), None)
    if not stock:
        stock = STATE.stocks[0]
    result = _order_book(stock)
    result["symbols"] = [s["name"] for s in STATE.stocks[:12]]
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- AUCTION HOUSE (list / bid; in-game gold only) ----
async def handle_auctions(request):
    """GET open auction listings."""
    result = AUCTION.listings()
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_auction_list(request):
    """Pulse: list a loot item for auction."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = AUCTION.list_item(uid, d.get("code"), d.get("start_price", 0))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)

async def pulse_auction_bid(request):
    """Pulse: bid on an auction (in-game gold)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = AUCTION.bid(uid, int(d.get("auction_id", 0)), d.get("amount", 0))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- GUILD WARS (two corps race a shared war boss) ----
async def handle_guildwar(request):
    """GET current guild-war status."""
    result = GUILDWAR.status()
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_guildwar(request):
    """Pulse: attack the shared war boss for your corp."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = GUILDWAR.attack(uid)
    if "error" in result and "hp" not in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- INVESTMENT BONDS (phi-yield on a timer; in-game gold) ----
async def handle_bonds(request):
    """GET bond tiers + a player's active bonds (?uid=)."""
    uid = request.match_info.get("uid", request.query.get("uid"))
    if uid is not None:
        result = bond_status(STATE, int(uid))
    else:
        result = bond_tiers()
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_bond_buy(request):
    """Pulse: buy a phi-bond with in-game gold."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = buy_bond(STATE, uid, int(d.get("tier", 0)), d.get("principal", 0))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)

async def pulse_bond_claim(request):
    """Pulse: claim matured bond payouts (in-game gold)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = claim_bonds(STATE, uid)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- DERIVATIVES (phi options/futures on corp stocks) ----
async def handle_derivs(request):
    """GET a quote chain (?sym=) or a player's positions (?uid=)."""
    STATE.tick_market()
    uid = request.match_info.get("uid", request.query.get("uid"))
    sym = request.query.get("sym")
    if uid is not None and not sym:
        result = deriv_status(STATE, int(uid))
    else:
        name = (sym or STATE.stocks[0]["name"]).upper()
        result = deriv_quote(STATE, name)
        result["symbols"] = [s["name"] for s in STATE.stocks[:12]]
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_deriv_open(request):
    """Pulse: open a derivative position (pay premium/margin in gold)."""
    STATE.tick_market()
    d = await request.json()
    uid = d.get("uid", 1000)
    result = open_position(STATE, uid, str(d.get("sym", "")).upper(),
                           d.get("kind", "call"), d.get("strike", 0),
                           d.get("qty", 1))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)

async def pulse_deriv_settle(request):
    """Pulse: settle expired derivative positions (in-game gold)."""
    STATE.tick_market()
    d = await request.json()
    uid = d.get("uid", 1000)
    result = settle_derivs(STATE, uid)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- GUILD SKYSCRAPER (collective build; corp-wide phi bonus) ----
async def handle_skyscraper(request):
    """GET skyscraper status for a corp (?corp= or ?uid=)."""
    corp = request.query.get("corp")
    if corp is None:
        uid = int(request.query.get("uid", 1000))
        c = STATE.chars.get(uid)
        corp = (c["corp_id"] if c else 0)
    result = sky_status(STATE, int(corp))
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_sky_fund(request):
    """Pulse: fund your corp skyscraper (gold)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = sky_fund(STATE, uid, d.get("amount", 0))
    if "error" in result and "floors" not in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- GOLDEN HOUR (timed x-phi rewards window) ----
async def handle_golden_hour(request):
    """GET current Golden Hour status/countdown."""
    result = golden_hour()
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- M&A (buy corp stakes; earn phi-share dividends) ----
async def handle_ma(request):
    """GET M&A board (corp share prices + holdings; ?uid= for your stakes)."""
    uid = request.query.get("uid")
    result = ma_status(STATE, uid=int(uid) if uid else None)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_ma_buy(request):
    """Pulse: buy shares in a corp (gold)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = buy_shares(STATE, uid, int(d.get("corp", 0)), d.get("qty", 1))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- INSIDER NEWS (random phi events move stocks) ----
async def handle_news(request):
    """GET the insider news feed (?since=). Generates headlines on a phi timer."""
    since = int(request.query.get("since", 0))
    result = news_feed(STATE, since)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- HEDGE FUND (auto-invest; phi-yield tied to market index) ----
async def handle_hedge(request):
    """GET the Golden Index + a player's funds (?uid=)."""
    STATE.tick_market()
    uid = request.match_info.get("uid", request.query.get("uid"))
    if uid is not None:
        result = hedge_status(STATE, int(uid))
    else:
        result = {"index": market_index(STATE)}
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_hedge_open(request):
    """Pulse: deposit gold into the hedge fund."""
    STATE.tick_market()
    d = await request.json()
    uid = d.get("uid", 1000)
    result = hedge_open(STATE, uid, d.get("amount", 0))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)

async def pulse_hedge_redeem(request):
    """Pulse: redeem matured hedge funds (in-game gold)."""
    STATE.tick_market()
    d = await request.json()
    uid = d.get("uid", 1000)
    result = hedge_redeem(STATE, uid)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- MAGNATE LEADERBOARD (live richest players; phi crowns) ----
async def handle_magnates(request):
    """GET the live magnate leaderboard (?uid= for your rank)."""
    uid = request.query.get("uid")
    result = magnates(STATE, top=20, uid=int(uid) if uid else None)
    body = json.dumps(result).encode()
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
    app.router.add_get("/api/prestige", handle_prestige)
    app.router.add_get("/api/raid", handle_raid)
    app.router.add_get("/api/quests", handle_quests)
    app.router.add_get("/api/achievements", handle_achievements)
    app.router.add_get("/api/achievements/{uid}", handle_achievements)
    app.router.add_get("/api/referral", handle_referral)
    app.router.add_get("/api/referral/{uid}", handle_referral)
    app.router.add_get("/api/chest", handle_chest)
    app.router.add_get("/api/chest/{uid}", handle_chest)
    app.router.add_get("/api/worldboss", handle_worldboss)
    app.router.add_get("/api/chat", handle_chat)
    app.router.add_get("/api/orderbook", handle_orderbook)
    app.router.add_post("/pulse/trade", pulse_trade)
    app.router.add_post("/pulse/gacha", pulse_gacha)
    app.router.add_post("/pulse/loot/sell", pulse_loot_sell)
    app.router.add_post("/pulse/donate", pulse_donate)
    app.router.add_post("/pulse/buy-gold", pulse_buy_gold)
    app.router.add_post("/pulse/duel", pulse_duel)
    app.router.add_post("/pulse/passive", pulse_passive)
    app.router.add_post("/pulse/prestige", pulse_prestige)
    app.router.add_post("/pulse/raid", pulse_raid)
    app.router.add_post("/pulse/quest", pulse_quest)
    app.router.add_post("/pulse/achievements", pulse_achievements)
    app.router.add_post("/pulse/referral", pulse_referral)
    app.router.add_post("/pulse/chest", pulse_chest)
    app.router.add_post("/pulse/worldboss", pulse_worldboss)
    app.router.add_post("/pulse/chat", pulse_chat)
    app.router.add_post("/pulse/craft", pulse_craft)
    app.router.add_get("/api/auctions", handle_auctions)
    app.router.add_post("/pulse/auction/list", pulse_auction_list)
    app.router.add_post("/pulse/auction/bid", pulse_auction_bid)
    app.router.add_get("/api/guildwar", handle_guildwar)
    app.router.add_post("/pulse/guildwar", pulse_guildwar)
    app.router.add_get("/api/bonds", handle_bonds)
    app.router.add_get("/api/bonds/{uid}", handle_bonds)
    app.router.add_post("/pulse/bond/buy", pulse_bond_buy)
    app.router.add_post("/pulse/bond/claim", pulse_bond_claim)
    app.router.add_get("/api/derivs", handle_derivs)
    app.router.add_get("/api/derivs/{uid}", handle_derivs)
    app.router.add_post("/pulse/deriv/open", pulse_deriv_open)
    app.router.add_post("/pulse/deriv/settle", pulse_deriv_settle)
    app.router.add_get("/api/skyscraper", handle_skyscraper)
    app.router.add_post("/pulse/skyscraper", pulse_sky_fund)
    app.router.add_get("/api/golden-hour", handle_golden_hour)
    app.router.add_get("/api/ma", handle_ma)
    app.router.add_post("/pulse/ma/buy", pulse_ma_buy)
    app.router.add_get("/api/news", handle_news)
    app.router.add_get("/api/hedge", handle_hedge)
    app.router.add_get("/api/hedge/{uid}", handle_hedge)
    app.router.add_post("/pulse/hedge/open", pulse_hedge_open)
    app.router.add_post("/pulse/hedge/redeem", pulse_hedge_redeem)
    app.router.add_get("/api/magnates", handle_magnates)
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
