#!/usr/bin/env python3
"""
CORP HEIST — Wealth Card Bridge Tests
Tests: char_bytes_to_json, char_from_params, build/parse roundtrip via API
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wealth_card_bridge import char_bytes_to_json, char_from_params, generate_demo_chars, CHARS_DB
from protocol import build_char_bytes, parse_char, CHAR_SIZE

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
    print("\n=== Wealth Card Bridge Tests ===\n")

    # char_from_params
    print("[char_from_params]")
    c = char_from_params(user_id=42, gold=99999, level=77, net_worth=500000)
    test("uid", c["user_id"] == 42)
    test("gold", c["gold"] == 99999)
    test("level", c["level"] == 77)
    test("net_worth", c["net_worth"] == 500000)
    test("has history", "history" in c)
    test("has stocks", "stocks" in c)
    test("has loot", "loot" in c)
    test("hero_levels len", len(c["hero_levels"]) == 12)
    test("passives len", len(c["passives"]) == 12)

    # build -> bytes -> char_bytes_to_json
    print("\n[Binary -> JSON]")
    data = build_char_bytes(
        user_id=7777, gold=123456, xp=500000, level=88,
        hero_id=3, corp_id=1, floor=4, gacha_pity=10,
        loot_count=200, portfolio_value=800000, net_worth=2000000,
        rank_percent=5, prestige=9, streak_days=60,
        hero_levels=[15,12,10,8,5,3,1,0,0,0,0,0],
        passives=[4,3,2,1,0,0,0,0,0,0,0,0]
    )
    test("bytes len", len(data) == CHAR_SIZE)
    j = char_bytes_to_json(data)
    test("json uid", j["user_id"] == 7777)
    test("json gold", j["gold"] == 123456)
    test("json level", j["level"] == 88)
    test("json net_worth", j["net_worth"] == 2000000)
    test("json hero_levels", j["hero_levels"][:4] == [15, 12, 10, 8])

    # short data
    print("\n[Edge cases]")
    short = char_bytes_to_json(b'\x00' * 10)
    test("short data -> error", short.get("error") == "short data")

    # generate demo chars
    print("\n[Demo data]")
    generate_demo_chars(100)
    test("100 chars generated", len(CHARS_DB) == 100)
    uid = list(CHARS_DB.keys())[0]
    dc = CHARS_DB[uid]
    test("demo has stocks", len(dc["stocks"]) > 0)
    test("demo has loot", len(dc["loot"]) > 0)
    test("demo has history", len(dc["history"]) > 0)
    test("demo gold > 0", dc["gold"] > 0)
    test("demo net_worth > 0", dc["net_worth"] > 0)

    # roundtrip: dict -> build -> bytes -> parse -> compare
    print("\n[Full roundtrip]")
    orig = char_from_params(user_id=12345, gold=888888, level=55, net_worth=3000000)
    raw = build_char_bytes(
        orig["user_id"], orig["gold"], orig["xp"], orig["level"],
        orig["hero_id"], orig["corp_id"], orig["floor"],
        orig["gacha_pity"], orig["loot_count"], orig["portfolio_value"],
        orig["net_worth"], orig["rank_percent"], orig["prestige"], orig["streak_days"],
        orig["hero_levels"], orig["passives"]
    )
    parsed = parse_char(raw)
    test("roundtrip uid", parsed["user_id"] == orig["user_id"])
    test("roundtrip gold", parsed["gold"] == orig["gold"])
    test("roundtrip level", parsed["level"] == orig["level"])
    test("roundtrip net_worth", parsed["net_worth"] == orig["net_worth"])

    # summary
    total = passed + failed
    print(f"\n{'='*40}")
    print(f"  {passed}/{total} passed, {failed} failed")
    print(f"{'='*40}\n")
    return failed == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
