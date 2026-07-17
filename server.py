#!/usr/bin/env python3
"""
CORP HEIST — Серверная архитектура v0.1
Цель: 2M пользователей на 1 сервере (4GB RAM, 32GB disk)

Архитектура:
  - WebSocket для реалтайма (10K соединений max)
  - HTTP REST для остальных (stateless)
  - Redis-like in-memory кэш (или sqlite)
  - Stock market: in-memory, бродкаст через pub/sub
  - Отрисовка: батчи по 10 элементов

Бюджет памяти (4GB):
  - Python overhead:        ~300 MB
  - Active users (10K):     ~10 MB  (1KB × 10K)
  - Stock market state:     ~50 MB  (10K акций × 5KB)
  - Message queue:          ~200 MB (1M сообщений × 200B)
  - Connection pool:        ~50 MB  (10K × 5KB per conn)
  - SQLite WAL cache:       ~100 MB
  - Остаток на overhead:    ~3.3 GB
  ИТОГО: ~710 MB из 4GB. Запас 5.6x.

Бюджет диска (32GB):
  - 2M users × 1KB:        ~2 GB
  - Stock history:          ~5 GB (10K акций × 365 дней)
  - Message logs:           ~10 GB (90 дней)
  - SQLite + WAL:           ~1 GB
  - Логи:                  ~2 GB
  ИТОГО: ~20 GB из 32GB. Запас 1.6x.
"""

import asyncio
import json
import time
import struct
import sqlite3
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

HOST = "0.0.0.0"
WS_PORT = 8765
HTTP_PORT = 8080
DB_PATH = "corpheist.db"

MAX_ACTIVE_USERS = 10_000
MAX_MESSAGE_BUFFER = 1_000_000
BATCH_RENDER_SIZE = 10
STOCK_UPDATE_INTERVAL = 2.0
HEARTBEAT_INTERVAL = 30.0
USER_DATA_SIZE_BYTES = 1024


# ============================================================
# МОДЕЛЬ ДАННЫХ ПОЛЬЗОВАТЕЛЯ (1KB = 1024 байт)
# ============================================================
# Структура бинарного формата (упаковка):
#   user_id:      uint32   (4 байта)
#   level:        uint16   (2 байта)
#   gold:         uint32   (4 байта)
#   xp:           uint32   (4 байта)
#   active_hero:  uint8    (1 байт)  — индекс героя (0-255)
#   hero_count:   uint8    (1 байт)
#   hero_tiers:   10 × uint8 (10 байт) — тиры героев (0=B,1=A,2=S,3=SSR)
#   hero_stars:   10 × uint8 (10 байт)
#   hero_levels:  10 × uint16 (20 байт)
#   portfolio:    20 × (uint32 stock_id + uint16 amount) (120 байт)
#   passives:     8 × uint8 (8 байт) — уровни пассивок
#   corporation:  uint8    (1 байт)  — выбранная корпорация
#   floor:        uint8    (1 байт)  — текущий этаж
#   last_active:  uint32   (4 байта) — timestamp
#   reserved:     остальное до 1024 байт
#
#   Итого: ~180 байт использовано / 1024 выделено

USER_STRUCT = struct.Struct("<IHHHBB10B10B10HB8BBBI532x")
# Проверка: I(4) + H(2) + H(2) + H(2) + B(1) + B(1) + 10B(10) + 10B(10) + 10H(20) + 120(B*60) + 8B(8) + B(1) + B(1) + I(4) + 532x = 724 + 532 = 1256
# Пересчитаем точно:
# I=4, H=2, H=2, H=2, B=1, B=1 = 12
# 10B=10, 10B=10, 10H=20 = 40
# 20×(I+H) = 20×6 = 120
# 8B=8, B=1, B=1, I=4 = 14
# Итого data: 12+40+120+14 = 186 байт
# Reserved: 1024-186 = 838 байт


# ============================================================
# СТРУКТУРЫ СЕТИ
# ============================================================

# Протокол: WebSocket (text JSON для simplicity, binary для optimization)
#
# Сообщение клиента → сервер:
#   {"t": "auth",   "uid": 12345, "token": "abc"}
#   {"t": "action", "a": "buy",   "stock": "AAPL", "amt": 10}
#   {"t": "action", "a": "sell",  "stock": "TSLA", "amt": 5}
#   {"t": "render", "page": 0,    "type": "portfolio"}
#   {"t": "render", "page": 0,    "type": "market"}
#   {"t": "ping"}
#
# Сообщение сервер → клиент:
#   {"t": "auth_ok", "uid": 12345, "gold": 5000}
#   {"t": "tick",    "stocks": {"AAPL": 185.2, "TSLA": 245.1, ...}}
#   {"t": "batch",   "items": [...10 items...], "total": 245, "page": 0}
#   {"t": "error",   "m": "Not enough gold"}
#   {"t": "pong"}
#   {"t": "alert",   "m": "Your AAPL went +5%"}
#
# Типичный размер сообщения:
#   Client → Server: ~50-100 байт
#   Server → Client (tick): ~2-5 KB (10K акций × 20 байт)
#   Server → Client (batch): ~1-2 KB (10 элементов × 100-200 байт)
#
# Пропускная способность WebSocket:
#   1 соединение: ~100K msg/sec (текст JSON)
#   10K соединений: ~10K msg/sec (при broadcast)
#   Тик каждые 2 сек → 5 тиков/сек → 50K сообщений/сек
#
# Порты:
#   WS: 8765 (WebSocket для реалтайма)
#   HTTP: 8080 (REST для auth, history, leaderboard)
#   База: sqlite3 (local socket, не TCP)


# ============================================================
# ФОНДОВАЯ БИРЖА (In-Memory Stock Market)
# ============================================================

@dataclass
class Stock:
    id: int
    name: str
    ticker: str
    price: float
    base_price: float
    volatility: float
    trend: float
    holders: int = 0
    volume_24h: int = 0

    def tick(self):
        change = self.price * self.volatility * (2 * hash(str(time.time_ns() + self.id)) % 1000 / 1000 - 0.5)
        change += self.trend * self.price * 0.001
        self.price = max(0.01, self.price + change)
        self.volume_24h = int(self.volume_24h * 0.99 + abs(change) * 100)


STOCKS_COUNT = 10_000
TICKERS = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META", "NVDA", "JPM",
    "V", "MA", "BAC", "WMT", "DIS", "NFLX", "ADBE", "CRM", "INTC",
    "CSCO", "ORCL", "QCOM", "TXN", "NKE", "PYPL", "UBER", "ABNB",
    "SNOW", "PLTR", "RIVN", "COIN", "SQ", "SHOP", "SPOT", "ZM",
]


class StockMarket:
    def __init__(self):
        self.stocks = []
        self.stock_map = {}
        self.tick_count = 0
        self.order_book = defaultdict(lambda: {"buy": [], "sell": []})

        for i in range(STOCKS_COUNT):
            if i < len(TICKERS):
                ticker = TICKERS[i]
            else:
                ticker = f"S{i:04d}"
            base = round(10 + hash(ticker) % 500, 2)
            vol = 0.001 + (hash(ticker) % 100) / 10000
            trend = (hash(ticker) % 200 - 100) / 10000
            stock = Stock(
                id=i, name=ticker, ticker=ticker,
                price=base, base_price=base,
                volatility=vol, trend=trend
            )
            self.stocks.append(stock)
            self.stock_map[ticker] = stock

    def tick(self):
        self.tick_count += 1
        for stock in self.stocks:
            stock.tick()

    def get_top_n(self, n=100):
        return self.stocks[:n]

    def get_portfolio_stocks(self, holdings):
        result = []
        for stock_id, amount in holdings:
            if 0 <= stock_id < len(self.stocks) and amount > 0:
                s = self.stocks[stock_id]
                result.append({
                    "id": s.id, "ticker": s.ticker,
                    "price": round(s.price, 2),
                    "amount": amount,
                    "value": round(s.price * amount, 2)
                })
        return result

    def execute_buy(self, ticker, amount, user_gold):
        stock = self.stock_map.get(ticker)
        if not stock:
            return None, "Unknown stock"
        cost = stock.price * amount
        if cost > user_gold:
            return None, "Not enough gold"
        stock.holders += 1
        stock.volume_24h += amount
        stock.price *= (1 + amount * 0.0001)
        return {"cost": round(cost, 2), "new_price": round(stock.price, 2)}, None

    def execute_sell(self, ticker, amount, user_holdings):
        stock = self.stock_map.get(ticker)
        if not stock:
            return None, "Unknown stock"
        held = next((a for sid, a in user_holdings if sid == stock.id), 0)
        if held < amount:
            return None, "Not enough shares"
        revenue = stock.price * amount
        stock.holders = max(0, stock.holders - 1)
        stock.volume_24h += amount
        stock.price *= (1 - amount * 0.0001)
        return {"revenue": round(revenue, 2), "new_price": round(stock.price, 2)}, None


# ============================================================
# ХРАНИЛИЩЕ ПОЛЬЗОВАТЕЛЕЙ (SQLite)
# ============================================================

class UserStore:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=-100000")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                data       BLOB,
                last_login INTEGER,
                level      INTEGER DEFAULT 1,
                gold       INTEGER DEFAULT 100,
                xp         INTEGER DEFAULT 0,
                is_online  INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_users_level ON users(level DESC);
            CREATE INDEX IF NOT EXISTS idx_users_gold ON users(gold DESC);

            CREATE TABLE IF NOT EXISTS stock_history (
                stock_id INTEGER,
                tick     INTEGER,
                price    REAL,
                volume   INTEGER,
                PRIMARY KEY (stock_id, tick)
            );

            CREATE TABLE IF NOT EXISTS message_log (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER,
                type     TEXT,
                data     TEXT,
                ts       INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_msg_user ON message_log(user_id, ts DESC);

            CREATE TABLE IF NOT EXISTS leaderboard (
                user_id  INTEGER PRIMARY KEY,
                score    INTEGER,
                ts       INTEGER
            );
        """)
        self.conn.commit()

    def get_user(self, user_id):
        row = self.conn.execute(
            "SELECT data, level, gold, xp FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()
        if row:
            return {"data": row[0], "level": row[1], "gold": row[2], "xp": row[3]}
        return None

    def create_user(self, user_id, data_blob=None):
        if data_blob is None:
            data_blob = b'\x00' * USER_DATA_SIZE_BYTES
        self.conn.execute(
            "INSERT OR IGNORE INTO users (user_id, data, level, gold, xp, last_login) "
            "VALUES (?, ?, 1, 100, 0, ?)",
            (user_id, data_blob, int(time.time()))
        )
        self.conn.commit()

    def save_user(self, user_id, data_blob, level, gold, xp):
        self.conn.execute(
            "UPDATE users SET data=?, level=?, gold=?, xp=?, last_login=?, is_online=1 "
            "WHERE user_id=?",
            (data_blob, level, gold, xp, int(time.time()), user_id)
        )

    def flush(self):
        self.conn.commit()

    def get_top_users(self, limit=100):
        return self.conn.execute(
            "SELECT user_id, level, gold FROM users ORDER BY gold DESC LIMIT ?",
            (limit,)
        ).fetchall()

    def get_user_count(self):
        return self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


# ============================================================
# КЭШ АКТИВНЫХ ПОЛЬЗОВАТЕЛЕЙ
# ============================================================

class ActiveUserCache:
    """LRU-кэш для активных пользователей.
    Неактивные пользователи → на диск (SQLite).
    Активные → в памяти (dict)."""

    def __init__(self, max_size=MAX_ACTIVE_USERS):
        self.max_size = max_size
        self.cache = {}
        self.access_order = []
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get(self, user_id):
        if user_id in self.cache:
            self.stats["hits"] += 1
            self.access_order.remove(user_id)
            self.access_order.append(user_id)
            return self.cache[user_id]
        self.stats["misses"] += 1
        return None

    def put(self, user_id, user_data):
        if user_id in self.cache:
            self.access_order.remove(user_id)
        elif len(self.cache) >= self.max_size:
            evict_id = self.access_order.pop(0)
            del self.cache[evict_id]
            self.stats["evictions"] += 1
        self.cache[user_id] = user_data
        self.access_order.append(user_id)

    def remove(self, user_id):
        if user_id in self.cache:
            self.cache.pop(user_id)
            self.access_order.remove(user_id)

    def size(self):
        return len(self.cache)

    def stats_dict(self):
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total if total > 0 else 0
        return {**self.stats, "size": self.size(), "hit_rate": f"{hit_rate:.1%}"}


# ============================================================
# БУФЕР СООБЩЕНИЙ (Message Queue)
# ============================================================

class MessageBuffer:
    """Кольцевой буфер сообщений.
    При переполнении — старые сообщения удаляются.
    Отправка: batch по BATCH_RENDER_SIZE."""

    def __init__(self, max_size=MAX_MESSAGE_BUFFER):
        self.max_size = max_size
        self.queues = defaultdict(list)
        self.total_messages = 0
        self.dropped = 0

    def push(self, user_id, message):
        q = self.queues[user_id]
        if len(q) >= 100:
            q.pop(0)
            self.dropped += 1
        q.append(message)
        self.total_messages += 1
        if len(self.queues) * 100 > self.max_size:
            self._evict_oldest_users()

    def pop_batch(self, user_id, count=BATCH_RENDER_SIZE):
        q = self.queues.get(user_id, [])
        batch = q[:count]
        self.queues[user_id] = q[count:]
        return batch

    def _evict_oldest_users(self):
        if len(self.queues) > 10000:
            keys = list(self.queues.keys())[:5000]
            for k in keys:
                del self.queues[k]

    def stats_dict(self):
        return {
            "total_messages": self.total_messages,
            "dropped": self.dropped,
            "queues": len(self.queues),
        }


# ============================================================
# КОРПОРАТИВНАЯ ЭКОНОМИКА (Global Events)
# ============================================================

class EconomyEngine:
    """Глобальные события, влияющие на всех пользователей.
    Мелкие действия (покупка 1 акции) → микро-движение цены.
    Крупные действия (1000+ покупок) → макро-событие."""

    def __init__(self, market: StockMarket):
        self.market = market
        self.global_events = []
        self.trade_count = defaultdict(int)
        self.event_cooldown = 0

    def on_trade(self, ticker, action, amount, user_id):
        key = f"{ticker}_{int(time.time()) // 60}"
        self.trade_count[key] += amount

        stock = self.market.stock_map.get(ticker)
        if stock:
            if action == "buy":
                stock.price *= (1 + amount * 0.00005)
            else:
                stock.price *= (1 - amount * 0.00005)

        threshold = 100
        if self.trade_count[key] > threshold and self.event_cooldown <= 0:
            event = self._generate_event(ticker, self.trade_count[key])
            self.global_events.append(event)
            self.event_cooldown = 10

    def _generate_event(self, ticker, volume):
        types = [
            ("BOOM", f"{ticker} surge! +{volume} trades/min", 1.05),
            ("CRASH", f"{ticker} dump! -{volume} trades/min", 0.95),
            ("RUMOR", f"Rumors about {ticker}...", 1.0),
            ("ANALYST", f"Analysts upgrade {ticker}", 1.02),
        ]
        import random
        t, msg, mult = random.choice(types)
        stock = self.market.stock_map.get(ticker)
        if stock:
            stock.price *= mult
        return {"type": t, "msg": msg, "ts": time.time()}

    def tick(self):
        if self.event_cooldown > 0:
            self.event_cooldown -= 1

    def get_recent_events(self, n=5):
        return self.global_events[-n:]


# ============================================================
# WEBSOCKET СЕРВЕР
# ============================================================

class GameServer:
    def __init__(self):
        self.market = StockMarket()
        self.store = UserStore()
        self.cache = ActiveUserCache()
        self.messages = MessageBuffer()
        self.economy = EconomyEngine(self.market)
        self.connections = {}
        self.auth_tokens = {}

    async def ws_handler(self, websocket, path=None):
        user_id = None
        try:
            async for raw_msg in websocket:
                try:
                    msg = json.loads(raw_msg)
                except json.JSONDecodeError:
                    continue

                t = msg.get("t")

                if t == "auth":
                    user_id = msg.get("uid")
                    token = msg.get("token", "")
                    if user_id:
                        self.connections[user_id] = websocket
                        user = self.store.get_user(user_id)
                        if not user:
                            self.store.create_user(user_id)
                            user = self.store.get_user(user_id)
                        self.cache.put(user_id, user)
                        await websocket.send(json.dumps({
                            "t": "auth_ok",
                            "uid": user_id,
                            "gold": user["gold"],
                            "level": user["level"],
                        }))

                elif t == "action" and user_id:
                    await self.handle_action(user_id, msg, websocket)

                elif t == "render" and user_id:
                    await self.handle_render(user_id, msg, websocket)

                elif t == "ping":
                    await websocket.send(json.dumps({"t": "pong"}))

        except Exception:
            pass
        finally:
            if user_id and user_id in self.connections:
                del self.connections[user_id]
                self.cache.remove(user_id)

    async def handle_action(self, user_id, msg, ws):
        action = msg.get("a")
        stock_ticker = msg.get("stock", "")
        amount = msg.get("amt", 1)

        user = self.cache.get(user_id) or self.store.get_user(user_id)
        if not user:
            await ws.send(json.dumps({"t": "error", "m": "User not found"}))
            return

        gold = user.get("gold", 0)

        if action == "buy":
            result, err = self.market.execute_buy(stock_ticker, amount, gold)
            if err:
                await ws.send(json.dumps({"t": "error", "m": err}))
                return
            new_gold = gold - int(result["cost"])
            user["gold"] = new_gold
            self.cache.put(user_id, user)
            self.store.save_user(user_id, b'', user.get("level", 1), new_gold, user.get("xp", 0))
            self.economy.on_trade(stock_ticker, "buy", amount, user_id)
            await ws.send(json.dumps({
                "t": "trade_ok", "a": "buy",
                "stock": stock_ticker, "amt": amount,
                "cost": result["cost"], "gold": new_gold,
                "new_price": result["new_price"]
            }))

        elif action == "sell":
            holdings = user.get("holdings", [])
            result, err = self.market.execute_sell(stock_ticker, amount, holdings)
            if err:
                await ws.send(json.dumps({"t": "error", "m": err}))
                return
            new_gold = gold + int(result["revenue"])
            user["gold"] = new_gold
            self.cache.put(user_id, user)
            self.store.save_user(user_id, b'', user.get("level", 1), new_gold, user.get("xp", 0))
            self.economy.on_trade(stock_ticker, "sell", amount, user_id)
            await ws.send(json.dumps({
                "t": "trade_ok", "a": "sell",
                "stock": stock_ticker, "amt": amount,
                "revenue": result["revenue"], "gold": new_gold,
                "new_price": result["new_price"]
            }))

    async def handle_render(self, user_id, msg, ws):
        page = msg.get("page", 0)
        render_type = msg.get("type", "market")

        if render_type == "market":
            stocks = self.market.get_top_n(100)
            start = page * BATCH_RENDER_SIZE
            batch = stocks[start:start + BATCH_RENDER_SIZE]
            items = [{
                "ticker": s.ticker,
                "price": round(s.price, 2),
                "change": round((s.price - s.base_price) / s.base_price * 100, 2),
                "volume": s.volume_24h,
                "holders": s.holders,
            } for s in batch]
            total = len(stocks)
        elif render_type == "portfolio":
            user = self.cache.get(user_id) or self.store.get_user(user_id)
            holdings = user.get("holdings", []) if user else []
            stocks_data = self.market.get_portfolio_stocks(holdings)
            start = page * BATCH_RENDER_SIZE
            batch = stocks_data[start:start + BATCH_RENDER_SIZE]
            items = batch
            total = len(stocks_data)
        elif render_type == "leaderboard":
            top = self.store.get_top_users(100)
            start = page * BATCH_RENDER_SIZE
            batch = top[start:start + BATCH_RENDER_SIZE]
            items = [{"uid": u[0], "level": u[1], "gold": u[2]} for u in batch]
            total = len(top)
        else:
            items = []
            total = 0

        await ws.send(json.dumps({
            "t": "batch", "items": items,
            "total": total, "page": page,
            "type": render_type,
        }))

    async def market_ticker(self):
        """Каждые N секунд шлём обновление цен всем активным."""
        while True:
            self.market.tick()
            self.economy.tick()
            events = self.economy.get_recent_events(3)
            tick_data = {
                "t": "tick",
                "stocks": {s.ticker: round(s.price, 2) for s in self.market.stocks[:100]},
                "events": events,
            }
            tick_json = json.dumps(tick_data)
            disconnected = []
            for uid, ws in list(self.connections.items()):
                try:
                    await ws.send(tick_json)
                except Exception:
                    disconnected.append(uid)
            for uid in disconnected:
                self.connections.pop(uid, None)
            await asyncio.sleep(STOCK_UPDATE_INTERVAL)

    async def periodic_flush(self):
        """Каждые 30 сек сливаем кэш на диск."""
        while True:
            self.store.flush()
            await asyncio.sleep(30)

    async def periodic_stats(self):
        while True:
            print(f"[STATS] connections={len(self.connections)} "
                  f"cache={self.cache.stats_dict()} "
                  f"messages={self.messages.stats_dict()} "
                  f"users_db={self.store.get_user_count()}")
            await asyncio.sleep(60)


# ============================================================
# HTTP API (для leaderboard, auth, history)
# ============================================================

def create_http_app(server: GameServer):
    if not HAS_AIOHTTP:
        return None

    async def health(request):
        return web.json_response({
            "status": "ok",
            "connections": len(server.connections),
            "users_db": server.store.get_user_count(),
            "cache": server.cache.stats_dict(),
        })

    async def leaderboard(request):
        top = server.store.get_top_users(100)
        return web.json_response([{
            "uid": u[0], "level": u[1], "gold": u[2]
        } for u in top])

    async def stock_history(request):
        ticker = request.match_info.get("ticker", "")
        stock = server.market.stock_map.get(ticker)
        if not stock:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response({
            "ticker": ticker,
            "price": round(stock.price, 2),
            "base": stock.base_price,
            "volume_24h": stock.volume_24h,
            "holders": stock.holders,
        })

    async def register(request):
        data = await request.json()
        uid = data.get("uid")
        if not uid:
            return web.json_response({"error": "uid required"}, status=400)
        server.store.create_user(uid)
        return web.json_response({"status": "created", "uid": uid})

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/api/leaderboard", leaderboard)
    app.router.add_get("/api/stock/{ticker}", stock_history)
    app.router.add_post("/api/register", register)
    return app


# ============================================================
# ЗАПУСК
# ============================================================

async def main():
    server = GameServer()

    print(f"=== CORP HEIST SERVER v0.1 ===")
    print(f"Stocks: {len(server.market.stocks)}")
    print(f"DB: {server.store.db_path}")
    print(f"Max active users: {MAX_ACTIVE_USERS}")
    print(f"Batch render size: {BATCH_RENDER_SIZE}")
    print()

    tasks = [
        server.market_ticker(),
        server.periodic_flush(),
        server.periodic_stats(),
    ]

    if HAS_WEBSOCKETS:
        ws_server = await websockets.serve(server.ws_handler, HOST, WS_PORT)
        print(f"WebSocket: ws://{HOST}:{WS_PORT}")
    else:
        print("WebSocket: DISABLED (pip install websockets)")

    if HAS_AIOHTTP:
        http_app = create_http_app(server)
        runner = web.AppRunner(http_app)
        await runner.setup()
        site = web.TCPSite(runner, HOST, HTTP_PORT)
        await site.start()
        print(f"HTTP: http://{HOST}:{HTTP_PORT}")
    else:
        print("HTTP: DISABLED (pip install aiohttp)")

    print("\nServer running. Ctrl+C to stop.\n")
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
