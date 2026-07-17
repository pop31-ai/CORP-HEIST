#!/usr/bin/env python3
"""
CORP HEIST — Wealth Card Bridge
Converts binary protocol char data -> JSON for Canvas wealth card renderer.
Run: python wealth_card_bridge.py [port]
Serves wealth_card.html with live data from binary protocol.
"""
import json
import struct
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocol import parse_char, build_char_bytes, CHAR_FMT, CHAR_SIZE

try:
    import websockets
    import websockets.server
except ImportError:
    websockets = None

try:
    from aiohttp import web
except ImportError:
    web = None


# ============================================================
# Char -> JSON converter
# ============================================================

def char_bytes_to_json(data: bytes) -> dict:
    """Convert 68-byte char struct to JSON for wealth card renderer."""
    if len(data) < CHAR_SIZE:
        return {"error": "short data"}
    c = parse_char(data[:CHAR_SIZE])
    # add computed fields
    c["history"] = [c["net_worth"] * 0.1]  # placeholder history
    c["stocks"] = []  # will be filled by market data
    c["loot"] = []    # will be filled by loot inventory
    return c


def char_from_params(user_id=1, gold=500000, xp=120000, level=42,
                     hero_id=0, corp_id=0, floor=0, gacha_pity=25,
                     loot_count=0, portfolio_value=750000, net_worth=1250000,
                     rank_percent=50, prestige=0, streak_days=0,
                     hero_levels=None, passives=None) -> dict:
    """Build char dict from params (for testing/demo)."""
    hl = (hero_levels or [0]*12)[:12]
    pa = (passives or [0]*12)[:12]
    return {
        "user_id": user_id, "gold": gold, "xp": xp, "level": level,
        "hero_id": hero_id, "corp_id": corp_id, "floor": floor,
        "gacha_pity": gacha_pity, "loot_count": loot_count,
        "portfolio_value": portfolio_value, "net_worth": net_worth,
        "rank_percent": rank_percent, "prestige": prestige,
        "streak_days": streak_days, "hero_levels": hl, "passives": pa,
        "history": [], "stocks": [], "loot": [],
    }


# ============================================================
# HTTP server (aiohttp)
# ============================================================

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wealth_card.html")

CHARS_DB = {}  # uid -> char dict (in-memory demo)


def generate_demo_chars(count=50):
    """Generate demo characters with varied stats."""
    import random
    names = ["Alexey", "Dmitry", "Sergey", "Andrey", "Nikolay",
             "Mikhail", "Ivan", "Pavel", "Vladimir", "Konstantin"]
    corps = ["MERIDIAN", "APEX", "NOVA", "VERTEX", "PULSAR"]
    for i in range(count):
        uid = 1000 + i
        nw = random.randint(10000, 9999999)
        gold = random.randint(1000, nw // 2)
        hl = [random.randint(0, 30) for _ in range(12)]
        pa = [random.randint(0, 5) for _ in range(12)]
        CHARS_DB[uid] = char_from_params(
            user_id=uid, gold=gold, xp=random.randint(0, 999999),
            level=random.randint(1, 100), hero_id=random.randint(0, 9),
            corp_id=random.randint(0, 4), floor=random.randint(0, 6),
            gacha_pity=random.randint(0, 49), loot_count=random.randint(0, 500),
            portfolio_value=random.randint(0, nw),
            net_worth=nw, rank_percent=random.randint(1, 100),
            prestige=random.randint(0, 10), streak_days=random.randint(0, 365),
            hero_levels=hl, passives=pa
        )
        # add random loot
        CHARS_DB[uid]["loot"] = [
            {"code": random.randint(0, 65535), "rarity": random.randint(0, 5),
             "qty": random.randint(1, 5), "value": random.randint(10, 50000)}
            for _ in range(random.randint(0, 15))
        ]
        # add random stocks
        stock_names = ["ALPHA", "BETA", "GAMMA", "DELTA", "OMEGA",
                       "SIGMA", "THETA", "ZETA", "PI", "RHO"]
        CHARS_DB[uid]["stocks"] = [
            {"name": stock_names[j % len(stock_names)],
             "price": round(random.uniform(1, 200), 2),
             "delta": round(random.uniform(-5, 5), 2),
             "held": random.randint(0, 200)}
            for j in range(random.randint(3, 10))
        ]
        # generate history
        hist = []
        v = nw * 0.1
        for _ in range(150):
            v += v * 0.02 * (random.random() - 0.48)
            hist.append(round(v, 2))
        CHARS_DB[uid]["history"] = hist


async def handle_index(request):
    return web.FileResponse(HTML_PATH)


async def handle_char(request):
    uid = int(request.match_info.get("uid", 1000))
    if uid not in CHARS_DB:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(CHARS_DB[uid])


async def handle_list(request):
    items = [{"user_id": uid, "name": f"Player_{uid}",
              "net_worth": c["net_worth"], "level": c["level"]}
             for uid, c in sorted(CHARS_DB.items(), key=lambda x: -x[1]["net_worth"])[:20]]
    return web.json_response(items)


async def handle_proto(request):
    """Serve binary char data for a uid (for protocol parser testing)."""
    uid = int(request.match_info.get("uid", 1000))
    if uid not in CHARS_DB:
        return web.Response(status=404)
    c = CHARS_DB[uid]
    data = build_char_bytes(
        c["user_id"], c["gold"], c["xp"], c["level"],
        c["hero_id"], c["corp_id"], c["floor"],
        c["gacha_pity"], c["loot_count"], c["portfolio_value"],
        c["net_worth"], c["rank_percent"], c["prestige"], c["streak_days"],
        c["hero_levels"], c["passives"]
    )
    return web.Response(body=data, content_type="application/octet-stream")


def start_http(port=8080):
    generate_demo_chars()
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/char/{uid}", handle_char)
    app.router.add_get("/api/chars", handle_list)
    app.router.add_get("/api/proto/{uid}", handle_proto)
    print(f"Wealth Card server: http://localhost:{port}")
    print(f"  /             - Wealth card (select player)")
    print(f"  /api/chars    - Top 20 players")
    print(f"  /api/char/UID - Player data (JSON)")
    print(f"  /api/proto/UID - Player data (binary)")
    web.run_app(app, port=port)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    start_http(port)
