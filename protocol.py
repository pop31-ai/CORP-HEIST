#!/usr/bin/env python3
"""
CORP HEIST — Бинарный протокол v2

МОДЕЛЬ:
  Игрок -> Персонаж -> Система
  Игрок <-> Игрок: ТОЛЬКО информационно (лидерборды, карточки богатства)
  Прямого P2P нет. Всё через персонажа и сервер.

ТРАФИК:
  Клиент-Сервер: бинарный, минимум байт
  Сервер-Клиент: batch-рендер 10 элементов
  P2P: нет (0 байт)
  Соцсети: пассивно (лидерборд, wealth cards)
"""

import struct
import time
import math
import random
import hashlib
from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


# ============================================================
# МОДЕЛЬ: Игрок -> Персонаж -> Система
# ============================================================
#
#   [ИГРОК]  <--->  [ПЕРСОНАЖ]  <--->  [СИСТЕМЫ]
#     |                  |                   |
#  login/wallet      stats/inventory    market/loot/shop
#  auth token        level/gold         stock exchange
#  device id         hero tier          gacha/pity
#                                       chain offers
#
#   [ИГРОК]  <---  [ЛИДЕРБОРД]  (только чтение, информационно)
#   [ИГРОК]  --->  [WEALTH CARD] (генерируется на клиенте, шарится в сеть)
#   [ИГРОК]  <---  [MARKET DATA] (агрегат, без P2P)
#
#   P2P-ВЗАИМОДЕЙСТВИЕ = 0 байт в реалтайме
#   Социальная связь = leaderboard rank + wealth card (статичные данные)


# ============================================================
# ПРОТОКОЛ
# ============================================================

class MsgType(IntEnum):
    # === AUTH (3 пакета) ===
    AUTH            = 0x01   # client: uid:u32 + token:u16[8]
    AUTH_OK         = 0x02   # server: uid:u32 + gold:u32 + level:u16 + hero_id:u8
    AUTH_FAIL       = 0x03   # server: reason:u8

    # === HEARTBEAT ===
    PING            = 0x10
    PONG            = 0x11

    # === ПЕРСОНАЖ (его данные) ===
    CHAR_INFO       = 0x20   # server: полное состояние персонажа
    CHAR_UPDATE     = 0x21   # client: обновить настройки персонажа

    # === РЫНОК (система, не P2P) ===
    MKT_SUB         = 0x30   # client: подписка на сектор
    MKT_TICK        = 0x31   # server: batch цен (10 акций)
    MKT_ORDER       = 0x32   # client: buy/sell order
    MKT_FILLED      = 0x33   # server: ордер исполнен

    # === ЛУТ (выпадает с акций через систему) ===
    LOOT_DROP       = 0x40   # server: лут упал
    LOOT_INV        = 0x41   # server: batch инвентаря (10 лутов)
    LOOT_SELL       = 0x42   # client: продать лут системе
    LOOT_USE        = 0x43   # client: применить лут

    # === ЦЕПОЧКИ ПОСРЕДНИКОВ ===
    CHAIN_OFFER     = 0x50   # server: оффер от цепочки
    CHAIN_RESP      = 0x51   # client: accept/reject
    CHAIN_SETTLED   = 0x52   # server: сделка завершена

    # === ГАЧА ===
    GACHA_ROLL      = 0x60   # client: крутить
    GACHA_RESULT    = 0x61   # server: результат

    # === ПАССИВНОЕ СОЦИАЛЬНОЕ (только инфо) ===
    LEADERBOARD     = 0x70   # server: batch топ-20
    WEALTH_CARD     = 0x71   # server: SVG карточка богатства (batch чанков)
    RANK_UPDATE     = 0x72   # server: обновление ранга

    # === БАТЧ-РЕНДЕР ===
    BATCH           = 0x80   # server: 10 элементов за пакет
    BATCH_ACK       = 0x81   # client: получил, следующие

    # === СИСТЕМНОЕ ===
    ERROR           = 0xFE
    DISCONNECT      = 0xFF


# ============================================================
# ЗАГОЛОВОК (3 байта на ВСЕ сообщения)
# ============================================================

HDR_FMT  = "<BH"    # type:u8 + seq:u16
HDR_SIZE = struct.calcsize(HDR_SIZE) if False else 3  # type(1) + seq(2)


# ============================================================
# ПЕРСОНАЖ — 68 байт (вся сущность)
# ============================================================
# Это КЛЮЧЕВАЯ структура. Персонаж = посредник между игроком и системой.
# Вся логика идёт через персонажа.
#
#   offset  size  field           описание
#   0       4     user_id         ID игрока
#   4       4     gold            валюта
#   8       4     xp              опыт
#   12      2     level           уровень
#   14      1     hero_id         активный герой (0-9)
#   15      1     corp_id         корпорация (0-4)
#   16      1     floor           этаж (0-6)
#   17      1     gacha_pity      счётчик гачи
#   18      2     loot_count      количество лута
#   20      4     portfolio_value стоимость портфеля (u32)
#   24      4     net_worth       общее состояние (u32)
#   28      1     rank_percent    ранг (0-100 percentile)
#   29      1     prestige        престиж (0-255, апгрейд)
#   30      1     streak_days     серия дней
#   31      1     reserved        выравнивание
#   32      24    hero_levels     12 × u16 (уровни героев)
#   56      12    passives        12 × u8 (уровни пассивок)
#   68      ИТОГО
CHAR_FMT  = "<IIIHBBBBHIIBBBB12H12B"
CHAR_SIZE = struct.calcsize(CHAR_FMT)  # = 68


# ============================================================
# BATCH РЕНДЕР (10 элементов за пакет)
# ============================================================
# Для всего: инвентарь, лидерборд, рынок, лут.
# Формат: [count:u8] + N × element
# Макс. размер: 10 элементов × max_element_size

BATCH_MAX = 10

# Элемент лидерборда: user_id:u32 + net_worth:u32 + rank:u16 + hero_id:u8 = 11 bytes
LB_ENTRY_FMT  = "<IIHB"
LB_ENTRY_SIZE = struct.calcsize(LB_ENTRY_FMT)

# Элемент рынка: stock_id:u16 + price_i32:u32 + delta_i16:i16 + volume:u32 = 12 bytes
MKT_ENTRY_FMT  = "<HIhI"
MKT_ENTRY_SIZE = struct.calcsize(MKT_ENTRY_FMT)

# Элемент лута: code:u16 + rarity:u8 + qty:u16 + source_stock:u16 = 7 bytes
LOOT_ENTRY_FMT  = "<HBHH"
LOOT_ENTRY_SIZE = struct.calcsize(LOOT_ENTRY_FMT)


# ============================================================
# СОБОРЩИК ПАКЕТОВ
# ============================================================

class PacketBuilder:

    def __init__(self):
        self._seq = 0

    def _seq_inc(self) -> int:
        self._seq = (self._seq + 1) & 0xFFFF
        return self._seq

    def _pack(self, msg_type: int, payload: bytes) -> bytes:
        return struct.pack("<BH", msg_type, self._seq_inc()) + payload

    # --- AUTH ---
    def auth(self, uid: int, token: int) -> bytes:
        """token = 8 × u16 (хеш пароля, 16 байт)"""
        t = struct.pack("<I", uid)
        for i in range(8):
            t += struct.pack("<H", (token >> (i * 16)) & 0xFFFF)
        return self._pack(MsgType.AUTH, t)

    def auth_ok(self, char_data: bytes) -> bytes:
        return self._pack(MsgType.AUTH_OK, char_data[:CHAR_SIZE])

    # --- ПЕРСОНАЖ ---
    def char_info(self, char: bytes) -> bytes:
        return self._pack(MsgType.CHAR_INFO, char[:CHAR_SIZE])

    # --- РЫНОК ---
    def mkt_order(self, stock_id: int, amount: int, side: int) -> bytes:
        """side: 0=buy, 1=sell"""
        return self._pack(MsgType.MKT_ORDER, struct.pack("<HhB", stock_id, amount, side))

    def mkt_tick_batch(self, entries: list) -> bytes:
        """batch до 10 акций"""
        payload = struct.pack("<B", min(len(entries), BATCH_MAX))
        for e in entries[:BATCH_MAX]:
            payload += struct.pack(MKT_ENTRY_FMT, e[0], e[1], e[2], e[3])
        return self._pack(MsgType.MKT_TICK, payload)

    # --- ЛУТ ---
    def loot_drop(self, code: int, rarity: int, qty: int, source_stock: int) -> bytes:
        return self._pack(MsgType.LOOT_DROP, struct.pack(LOOT_ENTRY_FMT, code, rarity, qty, source_stock))

    def loot_inv_batch(self, items: list) -> bytes:
        payload = struct.pack("<B", min(len(items), BATCH_MAX))
        for code, rarity, qty, src in items[:BATCH_MAX]:
            payload += struct.pack(LOOT_ENTRY_FMT, code, rarity, qty, src)
        return self._pack(MsgType.LOOT_INV, payload)

    # --- ЦЕПОЧКИ ---
    def chain_offer(self, loot_code: int, rarity: int,
                    chain_len: int, price_cents: int, ttl: int) -> bytes:
        """chain_len до 7 посредников, ttl в секундах"""
        return self._pack(MsgType.CHAIN_OFFER,
                          struct.pack("<HBBiH", loot_code, rarity, chain_len, price_cents, ttl))

    def chain_resp(self, loot_code: int, accept: bool) -> bytes:
        return self._pack(MsgType.CHAIN_RESP, struct.pack("<HB", loot_code, int(accept)))

    # --- ГАЧА ---
    def gacha_roll(self) -> bytes:
        return self._pack(MsgType.GACHA_ROLL, b'')

    def gacha_result(self, hero_id: int, rarity: int, pity: int) -> bytes:
        return self._pack(MsgType.GACHA_RESULT, struct.pack("<BBB", hero_id, rarity, pity))

    # --- ЛИДЕРБОРД ---
    def leaderboard_batch(self, entries: list) -> bytes:
        payload = struct.pack("<B", min(len(entries), BATCH_MAX))
        for uid, nw, rank, hero in entries[:BATCH_MAX]:
            payload += struct.pack(LB_ENTRY_FMT, uid, nw, rank, hero)
        return self._pack(MsgType.LEADERBOARD, payload)

    # --- WEALTH CARD (SVG, батчинг чанков) ---
    def wealth_card_chunk(self, chunk_id: int, total_chunks: int, data: bytes) -> bytes:
        """SVG разбивается на чанки по 200 байт"""
        return self._pack(MsgType.WEALTH_CARD,
                          struct.pack("<BB", chunk_id, total_chunks) + data[:200])

    # --- ОБЩЕЕ ---
    def error(self, code: int) -> bytes:
        return self._pack(MsgType.ERROR, struct.pack("<H", code))

    def pong(self) -> bytes:
        return self._pack(MsgType.PONG, b'')

    def batch_ack(self, page: int) -> bytes:
        return self._pack(MsgType.BATCH_ACK, struct.pack("<B", page))


# ============================================================
# ПАРСЕР ПАКЕТОВ
# ============================================================

class PacketParser:

    def parse(self, data: bytes) -> dict:
        if len(data) < 3:
            return {"err": "short"}
        mtype, seq = struct.unpack("<BH", data[:3])
        p = data[3:]
        r = {"type": mtype, "seq": seq}

        if mtype == MsgType.AUTH:
            uid = struct.unpack("<I", p[:4])[0]
            token = 0
            for i in range(8):
                token |= struct.unpack("<H", p[4+i*2:6+i*2])[0] << (i * 16)
            r["uid"] = uid
            r["token"] = token

        elif mtype == MsgType.AUTH_OK and len(p) >= CHAR_SIZE:
            r["char"] = parse_char(p[:CHAR_SIZE])

        elif mtype == MsgType.CHAR_INFO and len(p) >= CHAR_SIZE:
            r["char"] = parse_char(p[:CHAR_SIZE])

        elif mtype == MsgType.MKT_TICK:
            count = p[0]
            entries = []
            off = 1
            for _ in range(count):
                sid, price, delta, vol = struct.unpack(MKT_ENTRY_FMT, p[off:off+MKT_ENTRY_SIZE])
                entries.append({"id": sid, "price": price/100, "delta": delta/100, "vol": vol})
                off += MKT_ENTRY_SIZE
            r["stocks"] = entries

        elif mtype == MsgType.MKT_ORDER:
            sid, amt, side = struct.unpack("<HhB", p[:5])
            r["stock_id"] = sid
            r["amount"] = amt
            r["side"] = "buy" if side == 0 else "sell"

        elif mtype == MsgType.LOOT_DROP:
            code, rar, qty, src = struct.unpack(LOOT_ENTRY_FMT, p[:LOOT_ENTRY_SIZE])
            r["code"] = code
            r["rarity"] = rar
            r["qty"] = qty
            r["source"] = src

        elif mtype == MsgType.CHAIN_OFFER:
            code, rar, clen, price, ttl = struct.unpack("<HBBiH", p[:8])
            r["code"] = code
            r["rarity"] = rar
            r["chain_len"] = clen
            r["price_cents"] = price
            r["ttl"] = ttl

        elif mtype == MsgType.CHAIN_RESP:
            code, accept = struct.unpack("<HB", p[:3])
            r["code"] = code
            r["accept"] = bool(accept)

        elif mtype == MsgType.GACHA_RESULT:
            hid, rar, pity = struct.unpack("<BBB", p[:3])
            r["hero_id"] = hid
            r["rarity"] = rar
            r["pity"] = pity

        elif mtype == MsgType.LEADERBOARD:
            count = p[0]
            entries = []
            off = 1
            for _ in range(count):
                uid, nw, rank, hero = struct.unpack(LB_ENTRY_FMT, p[off:off+LB_ENTRY_SIZE])
                entries.append({"uid": uid, "net_worth": nw, "rank": rank, "hero": hero})
                off += LB_ENTRY_SIZE
            r["entries"] = entries

        elif mtype == MsgType.WEALTH_CARD:
            chunk_id, total = struct.unpack("<BB", p[:2])
            r["chunk_id"] = chunk_id
            r["total_chunks"] = total
            r["data"] = p[2:202]

        return r


def parse_char(data: bytes) -> dict:
    vals = struct.unpack(CHAR_FMT, data[:CHAR_SIZE])
    hero_levels = list(vals[15:27])  # 12 x u16
    passives = list(vals[27:39])     # 12 x u8
    return {
        "user_id":          vals[0],
        "gold":             vals[1],
        "xp":               vals[2],
        "level":            vals[3],
        "hero_id":          vals[4],
        "corp_id":          vals[5],
        "floor":            vals[6],
        "gacha_pity":       vals[7],
        "loot_count":       vals[8],
        "portfolio_value":  vals[9],
        "net_worth":        vals[10],
        "rank_percent":     vals[11],
        "prestige":         vals[12],
        "streak_days":      vals[13],
        "hero_levels":      hero_levels,
        "passives":         passives,
    }


def build_char_bytes(user_id, gold, xp, level, hero_id, corp_id, floor,
                     gacha_pity, loot_count, portfolio_value, net_worth,
                     rank_percent, prestige, streak_days,
                     hero_levels, passives) -> bytes:
    hl = (hero_levels + [0]*12)[:12]
    pa = (passives + [0]*12)[:12]
    return struct.pack(CHAR_FMT,
        user_id, gold, xp, level, hero_id, corp_id, floor,
        gacha_pity, loot_count, portfolio_value, net_worth,
        rank_percent, prestige, streak_days, 0,
        *hl, *pa
    )


# ============================================================
# ЛУТ-СИСТЕМА (2 байта = 65535 кодов)
# ============================================================

RARITY_NAMES = {0: "Common", 1: "Uncommon", 2: "Rare", 3: "Epic", 4: "Legendary", 5: "Unique"}

RARITY_RANGES = {
    0: (0x0000, 0x0FFF),   # 4096 Common
    1: (0x1000, 0x1FFF),   # 4096 Uncommon
    2: (0x2000, 0x2FFF),   # 4096 Rare
    3: (0x3000, 0x3FFF),   # 4096 Epic
    4: (0x4000, 0x4FFF),   # 4096 Legendary
    5: (0x5000, 0x5FFF),   # 4096 Unique
}

RARITY_WEIGHTS = {0: 7000, 1: 2000, 2: 700, 3: 250, 4: 40, 5: 10}
RARITY_TOTAL = sum(RARITY_WEIGHTS.values())  # 10000

RARITY_VALUE = {0: 10, 1: 50, 2: 250, 3: 1500, 4: 10000, 5: 50000}

# Посредники
FEE_TABLE = {
    0: 0.05,  # MarketMaker
    1: 0.08,  # Broker
    2: 0.12,  # Insurer
    3: 0.15,  # Transformer
    4: 0.10,  # AuctionHouse
    5: 0.03,  # ArbitrageBot
    6: 0.02,  # DarkPool
    7: 0.20,  # DataMiner
}
FEE_NAMES = {
    0: "MarketMaker", 1: "Broker", 2: "Insurer", 3: "Forge",
    4: "Auction", 5: "Arbitrage", 6: "DarkPool", 7: "DataMiner"
}


def roll_loot(seed: int) -> Tuple[int, int]:
    """(loot_code, rarity)"""
    h = ((seed * 2654435761) ^ (seed >> 13) * 0x9E3779B9) & 0xFFFF
    cumul = 0
    for r in range(6):
        cumul += RARITY_WEIGHTS[r]
        if h < cumul:
            lo, hi = RARITY_RANGES[r]
            code = lo + (((seed * 1237 + 7919) ^ (seed >> 5)) % (hi - lo + 1))
            return code, r
    return 0, 0


def make_chain(rarity: int, rng: random.Random) -> List[int]:
    """Список intermediary_id для цепочки"""
    length = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 7}.get(rarity, 1)
    return [rng.randint(0, 7) for _ in range(length)]


def chain_price(base_value: int, chain: List[int]) -> int:
    """Финальная цена после комиссий"""
    v = base_value
    for mid in chain:
        v = int(v * (1.0 - FEE_TABLE[mid]))
    return v


# ============================================================
# СИМУЛЯЦИЯ
# ============================================================

def demo():
    print("=" * 72)
    print("CORP HEIST — Binary Protocol v2: Player->Char->System")
    print("=" * 72)

    # --- 1. Размеры пакетов ---
    print("\n[1] PACKET SIZES\n")
    B = PacketBuilder()

    tests = [
        ("AUTH",          B.auth(12345, 0xDEADBEEF)),
        ("AUTH_OK",       B.auth_ok(build_char_bytes(
            12345, 50000, 99999, 15, 3, 2, 4, 0, 42, 18000, 85000, 23, 1, 30,
            [10,8,12,15,6,20,3,11,7,14,9,5], [5,3,7,2,8,4,6,1,9,3,2,7]))),
        ("CHAR_INFO",     B.char_info(build_char_bytes(
            12345, 50000, 99999, 15, 3, 2, 4, 0, 42, 18000, 85000, 23, 1, 30,
            [10,8,12,15,6,20,3,11,7,14,9,5], [5,3,7,2,8,4,6,1,9,3,2,7]))),
        ("MKT_ORDER",     B.mkt_order(42, 100, 0)),
        ("MKT_TICK x10",  B.mkt_tick_batch([(i, 15000+i*100, -50+i*10, 1000+i) for i in range(10)])),
        ("LOOT_DROP",     B.loot_drop(0x2042, 2, 1, 42)),
        ("LOOT_INV x10",  B.loot_inv_batch([(0x1000+i, i%6, 3, i*7) for i in range(10)])),
        ("CHAIN_OFFER",   B.chain_offer(0x3456, 3, 4, 8500, 300)),
        ("CHAIN_RESP",    B.chain_resp(0x3456, True)),
        ("GACHA_ROLL",    B.gacha_roll()),
        ("GACHA_RESULT",  B.gacha_result(5, 4, 47)),
        ("LEADER x10",    B.leaderboard_batch([(1000+i, 80000-i*5000, i+1, i%10) for i in range(10)])),
    ]

    json_approx = {
        "AUTH": 55, "AUTH_OK": 180, "CHAR_INFO": 350, "MKT_ORDER": 50,
        "MKT_TICK x10": 650, "LOOT_DROP": 60, "LOOT_INV x10": 450,
        "CHAIN_OFFER": 75, "CHAIN_RESP": 40, "GACHA_ROLL": 30,
        "GACHA_RESULT": 50, "LEADER x10": 500
    }

    print(f"  {'Packet':<16} {'Binary':>7} {'JSON~':>7} {'Save':>6}")
    print(f"  {'-'*16} {'-'*7} {'-'*7} {'-'*6}")
    for name, data in tests:
        j = json_approx.get(name, 100)
        save = 100 - len(data)*100//j if j > 0 else 0
        print(f"  {name:<16} {len(data):>5} B  {j:>5} B  {save:>4}%")

    # --- 2. Лут дропы ---
    print("\n[2] LOOT DROPS (20 samples)\n")
    rng = random.Random(42)
    total_base = 0
    total_chain = 0

    for i in range(20):
        seed = rng.randint(0, 0xFFFFFFFF)
        code, rar = roll_loot(seed)
        base = RARITY_VALUE[rar]
        chain = make_chain(rar, rng)
        final = chain_price(base, chain)
        total_base += base
        total_chain += final
        chain_names = "->".join(FEE_NAMES[c] for c in chain)
        pct = (1 - final/base)*100 if base > 0 else 0
        print(f"  #{i+1:02d} 0x{code:04X} [{RARITY_NAMES[rar]:10s}] ${base:>6,} -> ${final:>6,} "
              f"(fee {pct:.0f}%, {len(chain)} links)  {chain_names}")

    print(f"\n  TOTAL: ${total_base:,} -> ${total_chain:,} (avg fee: {(1-total_chain/total_base)*100:.1f}%)")

    # --- 3. Модель трафика ---
    print("\n[3] TRAFFIC MODEL\n")
    print("  Player <-> Server: binary, ~50-65 bytes/msg")
    print("  P2P: ZERO (player->char->system only)")
    print("  Social: passive (leaderboard + wealth card)")
    print()
    print("  10K concurrent players:")
    print("    Login:    10K x 65B = 650 KB (one-time)")
    print("    Tick/2s:  10K x 55B = 550 KB / 2s = 275 KB/s")
    print("    Loot:     10K x 9B  = 90 KB  (on drop)")
    print("    Gacha:    10K x 3B  = 30 KB  (on roll)")
    print("    TOTAL:    ~300 KB/s sustained = 0.3 MB/s")
    print()
    print("  vs JSON: ~1.5 MB/s sustained -> save 80%")
    print("  vs P2P:  would be ~5 MB/s -> we use 0")


if __name__ == "__main__":
    demo()
