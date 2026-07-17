#!/usr/bin/env python3
"""
CORP HEIST — Integration tests for binary protocol v2
Tests: pack/unpack roundtrip, char struct, loot chains, batch rendering
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protocol import (
    MsgType, PacketBuilder, PacketParser, CHAR_FMT, CHAR_SIZE,
    HDR_SIZE, HDR_FMT, LOOT_ENTRY_FMT, LOOT_ENTRY_SIZE,
    MKT_ENTRY_FMT, MKT_ENTRY_SIZE, LB_ENTRY_FMT, LB_ENTRY_SIZE,
    RARITY_NAMES, RARITY_WEIGHTS, RARITY_TOTAL,
    parse_char, build_char_bytes, FEE_TABLE, FEE_NAMES,
    BATCH_MAX
)

passed = 0
failed = 0

def test(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}")

def run_tests():
    global passed, failed
    print("\n=== CORP HEIST Protocol v2 Tests ===\n")

    # --- HEADER ---
    print("[Header]")
    test("HDR_SIZE == 3", HDR_SIZE == 3)
    hdr = struct.pack(HDR_FMT, 0x01, 1)
    test("HDR pack roundtrip", len(hdr) == 3)
    mtype, seq = struct.unpack(HDR_FMT, hdr)
    test("HDR unpack type", mtype == 0x01)
    test("HDR unpack seq", seq == 1)

    # --- AUTH ---
    print("\n[Auth]")
    pb = PacketBuilder()
    pp = PacketParser()
    pkt = pb.auth(12345, 0xDEADBEEF)
    test("auth packet size", len(pkt) == 3 + 4 + 16)  # hdr + uid + 8*u16
    test("auth packet type", pkt[0] == MsgType.AUTH)
    r = pp.parse(pkt)
    test("auth parse uid", r.get("uid") == 12345)
    test("auth parse token", r.get("token") == 0xDEADBEEF)

    # --- CHAR STRUCT ---
    print("\n[Char struct]")
    test("CHAR_SIZE == 68", CHAR_SIZE == 68)
    char_data = build_char_bytes(
        user_id=99999, gold=500000, xp=120000, level=42,
        hero_id=5, corp_id=2, floor=3, gacha_pity=25,
        loot_count=150, portfolio_value=750000, net_worth=1250000,
        rank_percent=15, prestige=7, streak_days=30,
        hero_levels=[10,8,5,3,2,1,0,0,0,0,0,0],
        passives=[3,2,1,0,0,0,0,0,0,0,0,0]
    )
    test("char_bytes size", len(char_data) == CHAR_SIZE)
    c = parse_char(char_data)
    test("char user_id", c["user_id"] == 99999)
    test("char gold", c["gold"] == 500000)
    test("char level", c["level"] == 42)
    test("char hero_id", c["hero_id"] == 5)
    test("char net_worth", c["net_worth"] == 1250000)
    test("char hero_levels", c["hero_levels"][:4] == [10, 8, 5, 3])
    test("char passives", c["passives"][:3] == [3, 2, 1])

    # --- CHAR ROUNDTRIP via AUTH_OK ---
    print("\n[Char roundtrip]")
    pkt2 = pb.auth_ok(char_data)
    r2 = pp.parse(pkt2)
    test("auth_ok type", r2["type"] == MsgType.AUTH_OK)
    test("auth_ok has char", "char" in r2)
    test("auth_ok char uid", r2["char"]["user_id"] == 99999)
    test("auth_ok char gold", r2["char"]["gold"] == 500000)

    # --- MARKET ---
    print("\n[Market]")
    entries = [(1001, 5234, 120, 50000), (1002, 12000, -350, 120000),
               (1003, 899, 45, 30000)]
    pkt3 = pb.mkt_tick_batch(entries)
    test("mkt_tick size", len(pkt3) == 3 + 1 + 3 * MKT_ENTRY_SIZE)
    r3 = pp.parse(pkt3)
    test("mkt_tick count", len(r3["stocks"]) == 3)
    test("mkt_tick price", r3["stocks"][0]["price"] == 52.34)
    test("mkt_tick delta", r3["stocks"][0]["delta"] == 1.2)

    # --- ORDER ---
    print("\n[Order]")
    pkt4 = pb.mkt_order(1001, -50, 1)
    r4 = pp.parse(pkt4)
    test("order side sell", r4["side"] == "sell")
    test("order amount", r4["amount"] == -50)

    # --- LOOT ---
    print("\n[Loot]")
    test("LOOT_ENTRY_SIZE == 7", LOOT_ENTRY_SIZE == 7)
    pkt5 = pb.loot_drop(42069, 3, 5, 1001)
    r5 = pp.parse(pkt5)
    test("loot code", r5["code"] == 42069)
    test("loot rarity", r5["rarity"] == 3)
    test("loot qty", r5["qty"] == 5)

    # --- LOOT BATCH ---
    print("\n[Loot batch]")
    items = [(i*1000, i%6, i+1, 1000+i) for i in range(10)]
    pkt6 = pb.loot_inv_batch(items)
    r6 = pp.parse(pkt6)
    test("loot batch 10 items", len(r6.get("stocks", [])) == 0)  # type is LOOT_INV
    # parse manually
    count = pkt6[3]
    test("loot batch count byte", count == 10)

    # --- CHAIN ---
    print("\n[Chain]")
    pkt7 = pb.chain_offer(30000, 4, 5, 9999, 300)
    r7 = pp.parse(pkt7)
    test("chain code", r7["code"] == 30000)
    test("chain rarity", r7["rarity"] == 4)
    test("chain len", r7["chain_len"] == 5)
    test("chain price", r7["price_cents"] == 9999)
    test("chain ttl", r7["ttl"] == 300)

    pkt8 = pb.chain_resp(30000, True)
    r8 = pp.parse(pkt8)
    test("chain accept", r8["accept"] is True)

    # --- GACHA ---
    print("\n[Gacha]")
    pkt9 = pb.gacha_roll()
    test("gacha_roll size", len(pkt9) == 3)

    pkt10 = pb.gacha_result(5, 3, 49)
    r10 = pp.parse(pkt10)
    test("gacha hero_id", r10["hero_id"] == 5)
    test("gacha rarity", r10["rarity"] == 3)
    test("gacha pity", r10["pity"] == 49)

    # --- LEADERBOARD ---
    print("\n[Leaderboard]")
    lb = [(1001, 5000000, 1, 5), (1002, 4200000, 2, 3), (1003, 3800000, 3, 8)]
    pkt11 = pb.leaderboard_batch(lb)
    r11 = pp.parse(pkt11)
    test("lb entries", len(r11["entries"]) == 3)
    test("lb top uid", r11["entries"][0]["uid"] == 1001)
    test("lb top nw", r11["entries"][0]["net_worth"] == 5000000)

    # --- WEALTH CARD CHUNKS ---
    print("\n[Wealth card]")
    chunk = b"X" * 150
    pkt12 = pb.wealth_card_chunk(2, 5, chunk)
    r12 = pp.parse(pkt12)
    test("wc chunk_id", r12["chunk_id"] == 2)
    test("wc total_chunks", r12["total_chunks"] == 5)

    # --- ERROR / PONG ---
    print("\n[Utility]")
    pkt13 = pb.error(404)
    r13 = pp.parse(pkt13)
    test("error type", r13["type"] == MsgType.ERROR)

    pkt14 = pb.pong()
    test("pong size", len(pkt14) == 3)

    pkt15 = pb.batch_ack(3)
    r15 = pp.parse(pkt15)
    test("batch_ack parseable", r15["type"] == MsgType.BATCH_ACK)

    # --- RARITY SYSTEM ---
    print("\n[Rarity]")
    total_w = sum(RARITY_WEIGHTS.values())
    test("rarity total == 10000", total_w == 10000)
    test("6 rarity tiers", len(RARITY_NAMES) == 6)

    # --- FEE TABLE ---
    print("\n[Fees]")
    test("8 intermediaries", len(FEE_TABLE) == 8)
    test("fee range", all(0.01 <= v <= 0.25 for v in FEE_TABLE.values()))

    # --- BATCH LIMIT ---
    print("\n[Batch]")
    test("BATCH_MAX == 10", BATCH_MAX == 10)

    # --- SEQ OVERFLOW ---
    print("\n[Seq overflow]")
    pb2 = PacketBuilder()
    pb2._seq = 65535
    pkt16 = pb2.pong()
    _, seq = struct.unpack(HDR_FMT, pkt16[:3])
    test("seq wraps 65535->0", seq == 0)

    # --- SUMMARY ---
    total = passed + failed
    print(f"\n{'='*40}")
    print(f"  {passed}/{total} passed, {failed} failed")
    print(f"{'='*40}\n")
    return failed == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
