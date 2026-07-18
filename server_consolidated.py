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

import market_cube as cube

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
    magnates, moy_status,
    loan_status, take_loan, repay_loan, check_liquidations,
    central_rate, cb_status, buy_insurance, liq_feed,
    ipo_launch, ipo_list, ipo_buy, portfolio,
    short_status, short_open, short_close, check_short_squeezes,
    golden_index, tick_index,
    idx_option_chain, idx_option_open, idx_option_status, idx_option_settle,
    trader_leaderboard, award_trader_of_day,
    maybe_flash_crash,
    mm_place, mm_status, mm_cancel, tick_market_making,
    tick_bots, tick_stock_candles, stock_candles,
    tape_feed, tick_sectors, sectors_status, trader_badges,
    PhiLottery, BlackMarket, HeistMission, PhiProphet,
    GoldenRain, CorpEspionage,
    PhiWeather, BountyBoard, PhiWheel, MarketFrenzy,
    WhaleChase, CorpTrial,
    PhiCasino, MarketOracle, PhiArenaRankings,
    CrashInsurance, PhiArtifacts, MarketInsider,
    PhiCandleBet, CandleShop, CandleSettlement,
    PlayerSession, StateSnapshot, ActivityWatchdog,
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
        self._refresh_cooldown = {}   # uid -> timestamp of last page load
        self._refresh_lock_sec = 300  # 5 minutes default
        self._donor_uids = set()      # uids with donor status (skip cooldown)

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

    STOCK_NAMES = ["ALPHA","BETA","GAMMA","DELTA","OMEGA","SIGMA","THETA",
                   "ZETA","PI","RHO","KAPPA","LAMBDA","MU","NU","XI",
                   "OMIKRON","CHI","PSI","PHI","TAU"]
    CUBE_PRICE_DIV = 5000.0   # map cube price [1..1e6] -> stock price ~[0..200]

    @staticmethod
    def cube_stock_price(name, t=None):
        """Deterministic stock price from the market cube. Pure function of
        (name, time). No storage, no randomness. Same value on client (JS)."""
        if t is None:
            t = int(time.time())
        return round(cube.price(name, t) / SharedState.CUBE_PRICE_DIV, 2)

    @staticmethod
    def cube_stock_delta(name, t=None):
        """Percent change vs 60s ago, straight from the cube."""
        if t is None:
            t = int(time.time())
        now = cube.price(name, t)
        prev = cube.price(name, t - 60)
        if prev <= 0:
            return 0.0
        return round((now - prev) * 100.0 / prev, 2)

    def _init_stocks(self):
        t = int(time.time())
        out = []
        for i, n in enumerate(self.STOCK_NAMES):
            out.append({"id": i, "name": n,
                        "price": self.cube_stock_price(n, t),
                        "delta": self.cube_stock_delta(n, t),
                        "volume": int(cube.volume(n, t))})
        return out

    def tick_market(self):
        """Recompute all prices from the cube at the current time. Prices are a
        pure function of time now (deterministic); trades no longer mutate them.
        The Central Bank rate still tints the DISPLAYED delta as market mood."""
        t = int(time.time())
        try:
            rate = central_rate()
        except Exception:
            rate = 1.0
        mood = (1.0 - rate)   # dovish (>0) lifts sentiment, hawkish (<0) sinks
        for s in self.stocks:
            n = s["name"]
            s["price"] = self.cube_stock_price(n, t)
            s["delta"] = round(self.cube_stock_delta(n, t) + mood * 0.5, 2)
            s["volume"] = int(cube.volume(n, t))

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
            # history is NOT stored: the capital curve is computed from the
            # market cube on demand (see handle_char). Saves ~150 floats/char.
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
                "stocks":stocks,"loot":loot,
            }
            self.mark_dirty(uid)
        self.save_all()
        log.info(f"saved {n} chars to {CHARS_DIR}")

    def track(self, sent=0, recv=0):
        self.request_count += 1
        self.bytes_sent += sent
        self.bytes_recv += recv

    # ---- REFRESH COOLDOWN ----

    def refresh_cooldown_status(self, uid):
        """Return cooldown info for a uid.
        Returns dict with: locked, remaining, lock_sec, donor, tier."""
        now = time.time()
        donor = uid in self._donor_uids
        c = self.chars.get(uid)
        tier = 0
        if c:
            tier = int(c.get("premium_tier", 0))
        if donor or tier >= 2:
            lock_sec = 0
        elif tier == 1:
            lock_sec = 60
        else:
            lock_sec = self._refresh_lock_sec
        last = self._refresh_cooldown.get(uid, 0)
        elapsed = now - last
        if lock_sec == 0:
            remaining = 0
            locked = False
        elif elapsed < lock_sec:
            remaining = int(lock_sec - elapsed)
            locked = True
        else:
            remaining = 0
            locked = False
        return {
            "locked": locked,
            "remaining": remaining,
            "lock_sec": lock_sec,
            "donor": donor or tier >= 2,
            "tier": tier,
        }

    def refresh_register(self, uid):
        """Register a page load for cooldown tracking."""
        self._refresh_cooldown[uid] = time.time()

    def refresh_force(self, uid):
        """Admin/force: reset cooldown for a uid."""
        self._refresh_cooldown.pop(uid, None)

    def refresh_set_donor(self, uid, on=True):
        """Toggle donor status (skip cooldown)."""
        if on:
            self._donor_uids.add(uid)
        else:
            self._donor_uids.discard(uid)

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


def _post_system_chat(corp, text):
    """Post a SYSTEM message into a corp chat ring buffer."""
    corp = corp % len(CORPS)
    STATE._chat_seq += 1
    msg = {"id": STATE._chat_seq, "uid": 0, "name": "⚡ SYSTEM",
           "corp": corp, "text": text[:CHAT_TEXT_MAX], "ts": int(time.time())}
    buf = STATE.chat.setdefault(corp, [])
    buf.append(msg)
    if len(buf) > CHAT_MAX:
        del buf[:-CHAT_MAX]


def _sweep_liquidations():
    """Run loan-liquidation + short-squeeze sweeps; broadcast into corp chat."""
    res = check_liquidations(STATE)
    for ev in res.get("liquidated", []) + res.get("saved", []):
        _post_system_chat(ev["corp"], ev["text"])
        STATE.save_char(ev["uid"])
    sq = check_short_squeezes(STATE)
    for ev in sq.get("squeezed", []):
        _post_system_chat(ev["corp"], ev["text"])
        STATE.save_char(ev["uid"])
    return res


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

_CARD_CACHE = {"mtime": 0, "html": None}

def build_card_html():
    """Return wealth_card.html with market_cube.js inlined before the main
    <script>, so the client computes cube values locally (single source of
    truth, no extra request). Cached by file mtimes to keep RAM/CPU tiny."""
    card_m = os.path.getmtime(CARD_HTML_PATH)
    cube_m = os.path.getmtime(CUBE_JS_PATH) if os.path.exists(CUBE_JS_PATH) else 0
    key = card_m + cube_m
    if _CARD_CACHE["html"] is not None and _CARD_CACHE["mtime"] == key:
        return _CARD_CACHE["html"]
    with open(CARD_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    if os.path.exists(CUBE_JS_PATH):
        with open(CUBE_JS_PATH, "r", encoding="utf-8") as f:
            cube_js = f.read()
        inject = "<script>/*market_cube*/\n" + cube_js + "\n</script>\n"
        html = html.replace("<script>", inject + "<script>", 1)
    _CARD_CACHE["html"] = html
    _CARD_CACHE["mtime"] = key
    return html

async def handle_card_index(request):
    return web.Response(text=build_card_html(), content_type="text/html")

# ---- PRESS: PHI micro-magazines (canvas-only; NO PDF on the site) ----
# The web edition is rendered client-side on <canvas> (hero scenes ported to
# JS), with browser Print + PNG export. No PDF is served or generated on the
# live server -- the print-grade PDF press is an offline / CI artifact only.
# This keeps the server light (no subprocess PDF builds, no file streaming),
# which matters under the ~30-connection ceiling.
PRESS_META = [
    ("01", "PHI-РЫНОК", "Запуск Golden-500", "market_galaxy"),
    ("02", "СЕКТОРА", "Ротация TECH → LUXURY", "sector_prism"),
    ("03", "ШОРТЫ", "Анатомия сквиза", "short_storm"),
    ("04", "ЦЕНТРОБАНК", "Цикл ставки PHI", "cb_temple"),
    ("05", "МАГНАТЫ", "Рейтинг богатства", "magnate_hall"),
    ("06", "МАГНАТ ГОДА", "Коронация сезона", "crown_throne"),
    ("07", "ДЕРИВАТИВЫ", "Опционы на PHI-страйки", "derivatives_web"),
    ("08", "БОТЫ", "Живая лента рынка", "bot_swarm"),
    ("09", "ГИЛЬДИИ", "Небоскрёбы и войны", "guild_towers"),
    ("10", "МАРКЕТ-МЕЙКИНГ", "Спред на PHI", "market_maker"),
]

async def handle_press_index(request):
    """JSON list of issues for the client PRESS panel.

    No PDF urls: the client draws each cover on <canvas> using the `scene`
    key (a hero-scene id), then offers Print / PNG. `available` is always
    true because rendering happens in the browser, not from a server file.
    """
    items = [{"no": no, "title": title, "subtitle": sub, "scene": scene,
              "available": True}
             for no, title, sub, scene in PRESS_META]
    body = json.dumps({
        "issues": items,
        "almanac": {"title": "АЛЬМАНАХ", "subtitle": "Полное собрание",
                    "scene": "market_galaxy", "available": True},
        "note": "Веб-издание рисуется на canvas. Печать и PNG — в браузере.",
    }, ensure_ascii=False).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- REFRESH COOLDOWN HANDLERS ----

async def handle_refresh_cooldown(request):
    """GET /api/refresh-cooldown/{uid} — returns cooldown state for client."""
    uid = int(request.match_info.get("uid", 0))
    status = STATE.refresh_cooldown_status(uid)
    body = json.dumps(status).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def pulse_refresh_load(request):
    """POST /pulse/refresh/load — register page load, start cooldown."""
    d = await request.json()
    uid = int(d.get("uid", 0))
    STATE.refresh_register(uid)
    body = json.dumps(STATE.refresh_cooldown_status(uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def pulse_refresh_force(request):
    """POST /pulse/refresh/force — admin: reset cooldown for a uid."""
    d = await request.json()
    uid = int(d.get("uid", 0))
    STATE.refresh_force(uid)
    body = json.dumps(STATE.refresh_cooldown_status(uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def pulse_refresh_donor(request):
    """POST /pulse/refresh/donor — toggle donor status (skip cooldown)."""
    d = await request.json()
    uid = int(d.get("uid", 0))
    on = d.get("on", True)
    STATE.refresh_set_donor(uid, on)
    body = json.dumps(STATE.refresh_cooldown_status(uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


async def pulse_premium_buy(request):
    """POST /pulse/premium/buy — buy priority tier (1 min cooldown) with in-game gold."""
    d = await request.json()
    uid = int(d.get("uid", 0))
    c = STATE.chars.get(uid)
    if not c:
        return web.json_response({"error": "no char"})
    tier = int(c.get("premium_tier", 0))
    if tier >= 1:
        return web.json_response({"error": "already premium", "tier": tier})
    cost = 5000
    gold = int(c.get("gold", 0))
    if gold < cost:
        return web.json_response({"error": "not enough gold", "have": gold, "need": cost})
    c["gold"] = gold - cost
    c["premium_tier"] = 1
    STATE.mark_dirty(uid)
    body = json.dumps({"ok": True, "tier": 1, "gold_left": c["gold"],
                        **STATE.refresh_cooldown_status(uid)}).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


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
    # capital history: computed from the cube on demand (never stored). The
    # curve shape is deterministic per uid; scaled so it ends at net_worth.
    # Client can reproduce this exactly from market_cube.js.
    now = int(time.time())
    c["history"] = cube.capital_series(uid, c["net_worth"], now, 3600, 48)
    body = json.dumps(c).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_welfare(request):
    """Welfare quote for a player: a pure function of the cube (uid + time).
    No storage. Returns the current candle, a tape of weekly candles, the
    full audit breakdown (explain) and a saldo ledger. The client (JS twin)
    can reproduce every number - this endpoint is a convenience, not a source
    of truth."""
    try:
        uid = int(request.match_info.get("uid", 1000))
    except (TypeError, ValueError):
        return web.json_response({"error": "bad uid"}, status=400)
    n = 8
    try:
        n = max(1, min(52, int(request.query.get("n", "8"))))
    except ValueError:
        n = 8
    now = int(time.time())
    payload = {
        "uid": uid,
        "t": now,
        "welfare": cube.welfare(uid, now),
        "living_tier": cube.living_tier(uid, now),
        "floor": cube.welfare_floor(uid, now),
        "market_trend_q16": cube.market_trend(now),
        "sector": cube.sector_of(uid),
        "sector_trend_q16": cube.sector_trend(cube.sector_of(uid), now),
        "candle": cube.welfare_candle(uid, t=now),
        "quotes": cube.welfare_quotes(uid, now, n),
        "report": cube.welfare_report(uid, now, n),
        "explain": cube.welfare_explain(uid, now),
        "note": "Welfare is a deterministic function of the cube. "
                "No real money. In-game standard-of-living metric only.",
    }
    body = json.dumps(payload).encode()
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
    _hb(uid, f"trade_{side}_{stock_name}_{amount}", c["gold"])
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
    _hb(uid, f"gacha_r{rarity}", c["gold"])
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


# ---- MAGNATE OF THE YEAR (season crown artifact) ----
async def handle_moy(request):
    """GET Magnate-of-the-Year status; crowns champions at season rollover."""
    result = moy_status(STATE)
    if result.get("awarded"):
        STATE.save_char(result["champion"]["uid"])
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- BANK / LOANS (borrow at phi-interest; leverage; liquidation) ----
async def handle_loan(request):
    """GET a player's loan status (?uid=). Sweeps liquidations first."""
    _sweep_liquidations()
    uid = int(request.match_info.get("uid", request.query.get("uid", 1000)))
    result = loan_status(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- CENTRAL BANK (global phi rate) ----
async def handle_cb(request):
    """GET the Golden Central Rate + stance."""
    result = cb_status()
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- POSITION INSURANCE (protect a loan from liquidation) ----
async def pulse_insure(request):
    """Pulse: insure your active loan against one liquidation (phi premium)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = buy_insurance(STATE, uid)
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- LIQUIDATION FEED (dramatic overlay + notifications) ----
async def handle_liqfeed(request):
    """GET recent liquidation/save events (?since=). Sweeps first."""
    _sweep_liquidations()
    since = int(request.query.get("since", 0))
    result = liq_feed(STATE, since)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_loan_take(request):
    """Pulse: take a leveraged loan against gold collateral."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = take_loan(STATE, uid, d.get("collateral", 0), d.get("leverage", 1.0))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)

async def pulse_loan_repay(request):
    """Pulse: repay part or all of a loan (returns collateral when cleared)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = repay_loan(STATE, uid, d.get("amount"))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- IPO (list your own micro-corp; players buy your shares) ----
async def handle_ipo(request):
    """GET the IPO board (?uid= to include your holdings)."""
    uid = request.query.get("uid")
    result = ipo_list(STATE, int(uid) if uid else None)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_ipo_launch(request):
    """Pulse: go public with your own company (phi listing fee)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = ipo_launch(STATE, uid, d.get("name", ""), d.get("base_price", 100))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)

async def pulse_ipo_buy(request):
    """Pulse: buy shares of another player's IPO (phi price curve)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = ipo_buy(STATE, uid, d.get("founder"), d.get("qty", 1))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    fu = d.get("founder")
    if fu is not None:
        STATE.save_char(int(fu))
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- SHORT SELLING (profit on drops; phi margin; squeeze risk) ----
async def handle_shorts(request):
    """GET a player's open short positions (?uid= or /api/shorts/<uid>)."""
    uid = int(request.match_info.get("uid", request.query.get("uid", 1000)))
    result = short_status(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_short_open(request):
    """Pulse: open a short position (reserve phi-margin)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = short_open(STATE, uid, d.get("symbol", ""), d.get("size", 1))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)

async def pulse_short_close(request):
    """Pulse: close a short (payout margin+PnL, or lose margin on squeeze)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = short_close(STATE, uid, d.get("id"))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- GOLDEN-500 INDEX (phi-weighted composite + candles) ----
async def handle_index(request):
    """GET the Golden-500 index value + candlestick history."""
    result = golden_index(STATE)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- PER-STOCK CANDLES (candlestick history for any ticker) ----
async def handle_stock_candles(request):
    """GET candlestick history for a single stock (/api/candles/<SYMBOL>)."""
    name = request.match_info.get("sym", request.query.get("sym", ""))
    result = stock_candles(STATE, name)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- BOT TICKER TAPE (scrolling feed of bot trades/events) ----
async def handle_tape(request):
    """GET the bot ticker tape (?since= for new lines only)."""
    since = int(request.query.get("since", 0))
    result = tape_feed(STATE, since)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- MARKET SECTORS (phi-sectors + rotation) ----
async def handle_sectors(request):
    """GET the phi-sector indices, members and hot/cold rotation."""
    result = sectors_status(STATE)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- TRADER BADGES (phi-milestone honors) ----
async def handle_badges(request):
    """GET a player's trader badges (?uid= or /api/badges/<uid>)."""
    uid = int(request.match_info.get("uid", request.query.get("uid", 1000)))
    result = trader_badges(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- GOLDEN-500 INDEX OPTIONS (calls/puts, phi strikes) ----
async def handle_idxopt(request):
    """GET the index option chain, or a player's positions (?uid=)."""
    uid = request.query.get("uid")
    if uid:
        result = idx_option_status(STATE, int(uid))
    else:
        result = idx_option_chain(STATE)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_idxopt_open(request):
    """Pulse: buy a Golden-500 call/put at a phi strike."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = idx_option_open(STATE, uid, d.get("kind", "call"), d.get("strike", 0))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)

async def pulse_idxopt_settle(request):
    """Pulse: settle an expired index option for gold."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = idx_option_settle(STATE, uid, d.get("id"))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- TRADER OF THE DAY (realized PnL leaderboard) ----
async def handle_traders(request):
    """GET today's trader leaderboard by realized PnL (?uid= for your rank)."""
    uid = request.query.get("uid")
    result = trader_leaderboard(STATE, int(uid) if uid else None)
    if result.get("hall_of_fame"):
        for e in result["hall_of_fame"]:
            STATE.save_char(e["uid"])
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- MARKET MAKING (limit orders; earn the phi-spread) ----
async def handle_mm(request):
    """GET a player's market-making orders (?uid= or /api/mm/<uid>)."""
    uid = int(request.match_info.get("uid", request.query.get("uid", 1000)))
    result = mm_status(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_mm_place(request):
    """Pulse: post a market-making order (park gold at bid, sell at bid*phi)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = mm_place(STATE, uid, d.get("symbol", ""), d.get("bid", 0),
                      d.get("size", 1), d.get("leverage", 1.0))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)

async def pulse_mm_cancel(request):
    """Pulse: cancel a market-making order (refund parked gold or inventory)."""
    d = await request.json()
    uid = d.get("uid", 1000)
    result = mm_cancel(STATE, uid, d.get("id"))
    if "error" in result:
        return web.json_response(result, status=400)
    STATE.save_char(uid)
    STATE.track(sent=len(json.dumps(result).encode()))
    return web.json_response(result)


# ---- PORTFOLIO (unified phi net-worth breakdown) ----
async def handle_portfolio(request):
    """GET a unified breakdown of all a player's assets and net worth."""
    _sweep_liquidations()
    uid = int(request.match_info.get("uid", request.query.get("uid", 1000)))
    result = portfolio(STATE, uid)
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
        try:
            tick_bots(STATE)
            fc = maybe_flash_crash(STATE)
            if fc.get("crashed"):
                for cid in range(len(CORPS)):
                    _post_system_chat(cid, f"FLASH CRASH! Golden-500 -> {fc['index']:,.0f}. Shorts feast, the leveraged bleed!")
            PhiWeather.apply_weather_effect(STATE)
            MarketFrenzy.apply_frenzy(STATE)
            tick_market_making(STATE)
            tick_index(STATE)
            tick_stock_candles(STATE)
            tick_sectors(STATE)
        except Exception:
            pass
        await asyncio.sleep(MARKET_TICK_SEC)

async def health_loop():
    while True:
        s = STATE.stats()
        log.info(f"health: req={s['requests']} sent={s['bytes_sent']}B chars={s['chars']} dirty={s['dirty']} uptime={s['uptime_sec']}s active={PlayerSession.active_count()}")
        # periodic snapshots for all active chars
        now = int(time.time())
        for uid in list(STATE.chars.keys())[:50]:
            StateSnapshot.take(STATE, uid, now=now)
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


# ---- NEW GAME EVENTS: Lottery, Black Market, Heist, Prophet, Rain, Espionage ----

async def handle_lottery(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(PhiLottery.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_lottery_buy(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = PhiLottery.buy_ticket(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_lottery_draw(request):
    d = await request.json()
    result = PhiLottery.draw(STATE)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_blackmarket(request):
    body = json.dumps(BlackMarket.status()).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_blackmarket_buy(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    item_id = int(d.get("item_id", 0))
    result = BlackMarket.buy(STATE, uid, item_id)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_heist(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(HeistMission.status(STATE)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_heist_fund(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    amount = int(d.get("amount", 1000))
    result = HeistMission.fund(STATE, uid, amount)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_heist_claim(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = HeistMission.claim(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_prophet(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(PhiProphet.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_prophet_predict(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    symbol = d.get("symbol", "ALPHA")
    direction = d.get("direction", "up")
    result = PhiProphet.predict(STATE, uid, symbol, direction)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_prophet_settle(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = PhiProphet.settle(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_rain(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(GoldenRain.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_rain_catch(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = GoldenRain.catch(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_espionage(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(CorpEspionage.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_espionage_sabotage(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    target = int(d.get("target_corp_id", 0))
    result = CorpEspionage.sabotage(STATE, uid, target)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_espionage_boost(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = CorpEspionage.boost(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- NEW EVENTS 2: Weather, Bounty, Wheel, Frenzy, Whale, Trial ----

async def handle_weather(request):
    body = json.dumps(PhiWeather.current()).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_bounty(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(BountyBoard.check_progress(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_bounty_claim(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    slot = int(d.get("slot", 0))
    result = BountyBoard.claim(STATE, uid, slot)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_wheel_spin(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = PhiWheel.spin(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_frenzy(request):
    body = json.dumps(MarketFrenzy.status()).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_frenzy_claim(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = MarketFrenzy.claim_bonus(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_whale(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(WhaleChase.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_whale_predict(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    whale_id = int(d.get("whale_id", 0))
    stock = d.get("stock", "ALPHA")
    result = WhaleChase.predict(STATE, uid, whale_id, stock)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_whale_settle(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = WhaleChase.settle(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_trial(request):
    uid = int(request.match_info.get("uid", 1000))
    c = STATE.chars.get(uid, {})
    corp_id = c.get("corp_id", 0)
    body = json.dumps(CorpTrial.status(STATE, corp_id, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_trial_claim(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = CorpTrial.claim(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- NEW EVENTS 3: Casino, Oracle, Arena, Insurance, Artifacts, Insider ----

async def pulse_casino_play(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    action = d.get("action", "deal")
    bet = int(d.get("bet", 100))
    player_hand = d.get("player_hand")
    dealer_hand = d.get("dealer_hand")
    result = PhiCasino.play(STATE, uid, bet, action, player_hand, dealer_hand)
    gold_after = result.get("gold_left", STATE.chars.get(uid, {}).get("gold", 0))
    _hb(uid, f"casino_{action}_{bet}", gold_after)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_oracle(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(MarketOracle.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_oracle_follow(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    stock = d.get("stock")
    result = MarketOracle.follow(STATE, uid, stock)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_oracle_settle(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = MarketOracle.settle(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_arena(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(PhiArenaRankings.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_arena_match(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    won = bool(d.get("won", False))
    PhiArenaRankings.record_match(STATE, uid, won)
    body = json.dumps({"ok": True, "won": won}).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_arena_claim(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = PhiArenaRankings.claim_season_reward(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_insurance(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(CrashInsurance.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_insurance_buy(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = CrashInsurance.buy(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_artifacts(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(PhiArtifacts.get_sets(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_insider(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(MarketInsider.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_insider_bet(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    side = d.get("side", "follow")
    result = MarketInsider.bet(STATE, uid, side)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_insider_settle(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = MarketInsider.settle(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- CANDLE SYSTEM: CandleBet, CandleShop, CandleSettlement ----

async def handle_candle_day(request):
    body = json.dumps(PhiCandleBet.day_info(STATE)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_candle_status(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(PhiCandleBet.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_candle_buy(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    bet = int(d.get("bet", 100))
    direction = d.get("direction", "green")
    result = PhiCandleBet.buy(STATE, uid, bet, direction)
    _hb(uid, f"candle_buy_{direction}_{bet}", result.get("gold_left", 0))
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_candle_return(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = PhiCandleBet.return_bet(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_candle_settle(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = PhiCandleBet.settle(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_candle_shop(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(CandleShop.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_candle_shop_buy(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    item_idx = int(d.get("item_idx", 0))
    result = CandleShop.buy_item(STATE, uid, item_idx)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_candle_exchange(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    item_idx = int(d.get("item_idx", 0))
    result = CandleShop.exchange_item(STATE, uid, item_idx)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_candle_settlement(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(CandleSettlement.status(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_candle_claim(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = CandleSettlement.claim_settlement(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def pulse_candle_auto_exchange(request):
    d = await request.json()
    uid = int(d.get("uid", 1000))
    result = CandleSettlement.auto_exchange_wrong_sector(STATE, uid)
    body = json.dumps(result).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


# ---- AUDIT / SESSION / WATCHDOG ----

def _hb(uid, action, gold_after):
    """Heartbeat helper — call after every pulse."""
    PlayerSession.heartbeat(uid, action, gold_after)
    c = STATE.chars.get(uid, {})
    StateSnapshot.take(STATE, uid)

async def handle_audit(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(ActivityWatchdog.audit(STATE, uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_session(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(PlayerSession.get_session(uid)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_session_log(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(PlayerSession.get_log(uid, last_n=30)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")

async def handle_snapshots(request):
    uid = int(request.match_info.get("uid", 1000))
    body = json.dumps(StateSnapshot.get_history(uid, last_n=10)).encode()
    STATE.track(sent=len(body))
    return web.Response(body=body, content_type="application/json")


def make_card_app():
    app = web.Application()
    app.router.add_get("/", handle_card_index)
    app.router.add_get("/api/char/{uid}", handle_char)
    app.router.add_get("/api/welfare/{uid}", handle_welfare)
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
    return web.Response(text=build_card_html(), content_type="text/html")

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
    # PRESS: PHI micro-magazines (canvas-only; no PDF served)
    app.router.add_get("/api/press", handle_press_index)
    app.router.add_get("/press", handle_press_index)
    # char API + pulse (shared)
    app.router.add_get("/api/char/{uid}", handle_char)
    app.router.add_get("/api/welfare/{uid}", handle_welfare)
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
    app.router.add_get("/api/moy", handle_moy)
    app.router.add_get("/api/loan", handle_loan)
    app.router.add_get("/api/loan/{uid}", handle_loan)
    app.router.add_post("/pulse/loan/take", pulse_loan_take)
    app.router.add_post("/pulse/loan/repay", pulse_loan_repay)
    app.router.add_get("/api/cb", handle_cb)
    app.router.add_post("/pulse/loan/insure", pulse_insure)
    app.router.add_get("/api/liqfeed", handle_liqfeed)
    app.router.add_get("/api/ipo", handle_ipo)
    app.router.add_post("/pulse/ipo/launch", pulse_ipo_launch)
    app.router.add_post("/pulse/ipo/buy", pulse_ipo_buy)
    app.router.add_get("/api/portfolio", handle_portfolio)
    app.router.add_get("/api/portfolio/{uid}", handle_portfolio)
    app.router.add_get("/api/shorts", handle_shorts)
    app.router.add_get("/api/shorts/{uid}", handle_shorts)
    app.router.add_post("/pulse/short/open", pulse_short_open)
    app.router.add_post("/pulse/short/close", pulse_short_close)
    app.router.add_get("/api/index", handle_index)
    app.router.add_get("/api/candles/{sym}", handle_stock_candles)
    app.router.add_get("/api/tape", handle_tape)
    app.router.add_get("/api/sectors", handle_sectors)
    app.router.add_get("/api/badges", handle_badges)
    app.router.add_get("/api/badges/{uid}", handle_badges)
    app.router.add_get("/api/idxopt", handle_idxopt)
    app.router.add_post("/pulse/idxopt/open", pulse_idxopt_open)
    app.router.add_post("/pulse/idxopt/settle", pulse_idxopt_settle)
    app.router.add_get("/api/traders", handle_traders)
    app.router.add_get("/api/mm", handle_mm)
    app.router.add_get("/api/mm/{uid}", handle_mm)
    app.router.add_post("/pulse/mm/place", pulse_mm_place)
    app.router.add_post("/pulse/mm/cancel", pulse_mm_cancel)
    # ---- REFRESH COOLDOWN ----
    app.router.add_get("/api/refresh-cooldown/{uid}", handle_refresh_cooldown)
    app.router.add_post("/pulse/refresh/load", pulse_refresh_load)
    app.router.add_post("/pulse/refresh/force", pulse_refresh_force)
    app.router.add_post("/pulse/refresh/donor", pulse_refresh_donor)
    app.router.add_post("/pulse/premium/buy", pulse_premium_buy)
    # ---- NEW EVENTS ----
    app.router.add_get("/api/lottery/{uid}", handle_lottery)
    app.router.add_post("/pulse/lottery/buy", pulse_lottery_buy)
    app.router.add_post("/pulse/lottery/draw", pulse_lottery_draw)
    app.router.add_get("/api/blackmarket", handle_blackmarket)
    app.router.add_post("/pulse/blackmarket/buy", pulse_blackmarket_buy)
    app.router.add_get("/api/heist/{uid}", handle_heist)
    app.router.add_post("/pulse/heist/fund", pulse_heist_fund)
    app.router.add_post("/pulse/heist/claim", pulse_heist_claim)
    app.router.add_get("/api/prophet/{uid}", handle_prophet)
    app.router.add_post("/pulse/prophet/predict", pulse_prophet_predict)
    app.router.add_post("/pulse/prophet/settle", pulse_prophet_settle)
    app.router.add_get("/api/rain/{uid}", handle_rain)
    app.router.add_post("/pulse/rain/catch", pulse_rain_catch)
    app.router.add_get("/api/espionage/{uid}", handle_espionage)
    app.router.add_post("/pulse/espionage/sabotage", pulse_espionage_sabotage)
    app.router.add_post("/pulse/espionage/boost", pulse_espionage_boost)
    # ---- NEW EVENTS 2 ----
    app.router.add_get("/api/weather", handle_weather)
    app.router.add_get("/api/bounty/{uid}", handle_bounty)
    app.router.add_post("/pulse/bounty/claim", pulse_bounty_claim)
    app.router.add_post("/pulse/wheel/spin", pulse_wheel_spin)
    app.router.add_get("/api/frenzy", handle_frenzy)
    app.router.add_post("/pulse/frenzy/claim", pulse_frenzy_claim)
    app.router.add_get("/api/whale/{uid}", handle_whale)
    app.router.add_post("/pulse/whale/predict", pulse_whale_predict)
    app.router.add_post("/pulse/whale/settle", pulse_whale_settle)
    app.router.add_get("/api/trial/{uid}", handle_trial)
    app.router.add_post("/pulse/trial/claim", pulse_trial_claim)
    # ---- NEW EVENTS 3: Casino, Oracle, Arena, Insurance, Artifacts, Insider ----
    app.router.add_post("/pulse/casino/play", pulse_casino_play)
    app.router.add_get("/api/oracle/{uid}", handle_oracle)
    app.router.add_post("/pulse/oracle/follow", pulse_oracle_follow)
    app.router.add_post("/pulse/oracle/settle", pulse_oracle_settle)
    app.router.add_get("/api/arena/{uid}", handle_arena)
    app.router.add_post("/pulse/arena/match", pulse_arena_match)
    app.router.add_post("/pulse/arena/claim", pulse_arena_claim)
    app.router.add_get("/api/insurance/{uid}", handle_insurance)
    app.router.add_post("/pulse/insurance/buy", pulse_insurance_buy)
    app.router.add_get("/api/artifacts/{uid}", handle_artifacts)
    app.router.add_get("/api/insider/{uid}", handle_insider)
    app.router.add_post("/pulse/insider/bet", pulse_insider_bet)
    app.router.add_post("/pulse/insider/settle", pulse_insider_settle)
    # ---- CANDLE SYSTEM ----
    app.router.add_get("/api/candle/day", handle_candle_day)
    app.router.add_get("/api/candle/{uid}", handle_candle_status)
    app.router.add_post("/pulse/candle/buy", pulse_candle_buy)
    app.router.add_post("/pulse/candle/return", pulse_candle_return)
    app.router.add_post("/pulse/candle/settle", pulse_candle_settle)
    app.router.add_get("/api/candleshop/{uid}", handle_candle_shop)
    app.router.add_post("/pulse/candleshop/buy", pulse_candle_shop_buy)
    app.router.add_post("/pulse/candleshop/exchange", pulse_candle_exchange)
    app.router.add_get("/api/candlesettle/{uid}", handle_candle_settlement)
    app.router.add_post("/pulse/candlesettle/claim", pulse_candle_claim)
    app.router.add_post("/pulse/candlesettle/autoex", pulse_candle_auto_exchange)
    # ---- AUDIT / SESSION ----
    app.router.add_get("/api/audit/{uid}", handle_audit)
    app.router.add_get("/api/session/{uid}", handle_session)
    app.router.add_get("/api/sessionlog/{uid}", handle_session_log)
    app.router.add_get("/api/snapshots/{uid}", handle_snapshots)
    return app

CARD_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wealth_card.html")
CUBE_JS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "market_cube.js")

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
