import random
from config import (
    HERO_TEMPLATES, GACHA_COST, GACHA_MULTICOST, GACHA_RATES,
    CORPORATIONS,
)
from heroes import Hero


class Shop:
    def __init__(self):
        self.gacha_pity = 0
        self.guaranteed_pity = 50

    def roll_single(self):
        self.gacha_pity += 1
        if self.gacha_pity >= self.guaranteed_pity:
            self.gacha_pity = 0
            tier = self._pick_tier_guaranteed()
        else:
            tier = self._pick_tier()
        return self._roll_hero(tier)

    def roll_multi(self):
        results = []
        for _ in range(10):
            results.append(self.roll_single())
        return results

    def _pick_tier(self):
        r = random.random()
        cumulative = 0
        for t, rate in GACHA_RATES.items():
            cumulative += rate
            if r <= cumulative:
                return t
        return "B"

    def _pick_tier_guaranteed(self):
        r = random.random()
        if r < 0.3:
            return "SSR"
        elif r < 0.6:
            return "S"
        else:
            return "A"

    def _roll_hero(self, tier):
        candidates = [k for k, v in HERO_TEMPLATES.items() if v["tier"] == tier]
        if not candidates:
            candidates = list(HERO_TEMPLATES.keys())
        key = random.choice(candidates)
        corp_key = random.choice(list(CORPORATIONS.keys()))
        return Hero(key, corp_key)

    def get_shop_items(self):
        items = []
        items.append({
            "id": "gacha_single",
            "name": "Один агент",
            "description": f"Случайный агент (B/A/S/SSR)",
            "cost": GACHA_COST,
            "currency": "gold",
            "type": "gacha_single",
        })
        items.append({
            "id": "gacha_multi",
            "name": "10 агентов",
            "description": f"10 случайных (один A+)",
            "cost": GACHA_MULTICOST,
            "currency": "gold",
            "type": "gacha_multi",
        })
        items.append({
            "id": "heal_potion",
            "name": "Отдых в спа",
            "description": "Полное восстановление HP",
            "cost": 30,
            "currency": "gold",
            "type": "heal",
        })
        items.append({
            "id": "xp_boost",
            "name": "Бустер аналитики",
            "description": "+50% XP следующей миссии",
            "cost": 80,
            "currency": "gold",
            "type": "xp_boost",
        })
        items.append({
            "id": "star_stone",
            "name": "Камень эволюции",
            "description": "+1 звезда герою",
            "cost": 200,
            "currency": "gold",
            "type": "star_stone",
        })
        return items


class DonateShop:
    def __init__(self):
        self.items = [
            {
                "id": "donate_gold_pack",
                "name": "Золотой запас",
                "description": "+500 золота",
                "price_real": "79 руб",
                "currency": "gold",
                "amount": 500,
                "tag": "ХИТ",
            },
            {
                "id": "donate_premium_pass",
                "name": "Премиум-пропуск",
                "description": "Доступ к элитным миссиям на 30 дней",
                "price_real": "299 руб",
                "currency": "premium_days",
                "amount": 30,
                "tag": "ВЫГОДА",
            },
            {
                "id": "donate_star_pack",
                "name": "Звёздный набор",
                "description": "3 Камня эволюции",
                "price_real": "149 руб",
                "currency": "star_stones",
                "amount": 3,
                "tag": "НОВИНКА",
            },
            {
                "id": "donate_gacha_pack",
                "name": "Набор рекрута",
                "description": "10+1 случайных агентов",
                "price_real": "399 руб",
                "currency": "gacha_tickets",
                "amount": 11,
                "tag": "ЛУЧШЕЕ",
            },
            {
                "id": "donate_vip",
                "name": "VIP-статус",
                "description": "x2 ко всем наградам на 7 дней",
                "price_real": "199 руб",
                "currency": "vip_days",
                "amount": 7,
                "tag": "СУПЕР",
            },
        ]

    def get_items(self):
        return self.items
