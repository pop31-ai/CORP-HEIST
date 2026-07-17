import random
from config import HERO_TEMPLATES, PASSIVE_NODES, PASSIVE_TIER_BONUS


class Hero:
    def __init__(self, template_key, corporation=None):
        t = HERO_TEMPLATES[template_key]
        self.template_key = template_key
        self.name = t["name"]
        self.role = t["role"]
        self.tier = t["tier"]
        self.description = t["description"]
        self.abilities = list(t["abilities"])
        self.corporation = corporation

        self.level = 1
        self.xp = 0
        self.xp_to_next = self._calc_xp_needed(1)

        self.base_hp = t["hp"]
        self.base_attack = t["attack"]
        self.base_defense = t["defense"]
        self.base_speed = t["speed"]
        self.base_crit_rate = t["crit_rate"]
        self.base_crit_dmg = t["crit_dmg"]
        self.base_dodge = t["dodge"]

        self.passive_levels = {k: 0 for k in PASSIVE_NODES}
        self.star_count = 1
        self.max_stars = 6

        self.current_hp = self.get_stat("hp")

    def _calc_xp_needed(self, level):
        return int(50 * (level ** 1.6))

    def get_stat(self, stat):
        val = getattr(self, f"base_{stat}", 0)
        if stat == "hp":
            val += self.level * 8
        elif stat == "attack":
            val += self.level * 2
        elif stat == "defense":
            val += self.level * 1
        elif stat == "speed":
            val += self.level * 0.5

        for node_key, node in PASSIVE_NODES.items():
            lvl = self.passive_levels.get(node_key, 0)
            if lvl > 0 and node["stat"] == stat:
                val += lvl * node["flat"]

        tier_mult = PASSIVE_TIER_BONUS.get(self.tier, 1.0)
        star_mult = 1.0 + (self.star_count - 1) * 0.08
        val *= tier_mult * star_mult

        if self.corporation:
            from config import CORPORATIONS
            corp = CORPORATIONS.get(self.corporation)
            if corp:
                if corp["bonus_type"] == stat:
                    val *= (1.0 + corp["bonus_value"])

        if stat in ("crit_rate", "dodge"):
            val = min(val, 0.75)
        elif stat == "crit_dmg":
            val = min(val, 5.0)

        return val

    def get_all_stats(self):
        return {
            "hp": self.get_stat("hp"),
            "attack": self.get_stat("attack"),
            "defense": self.get_stat("defense"),
            "speed": self.get_stat("speed"),
            "crit_rate": self.get_stat("crit_rate"),
            "crit_dmg": self.get_stat("crit_dmg"),
            "dodge": self.get_stat("dodge"),
        }

    def gain_xp(self, amount):
        xp_mult = 1.0
        for node_key, node in PASSIVE_NODES.items():
            lvl = self.passive_levels.get(node_key, 0)
            if lvl > 0 and node["stat"] == "xp_mult":
                xp_mult += lvl * node["flat"]
        amount = int(amount * xp_mult)
        self.xp += amount
        leveled = False
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.level += 1
            self.xp_to_next = self._calc_xp_needed(self.level)
            leveled = True
        if leveled:
            self.current_hp = self.get_stat("hp")
        return leveled

    def upgrade_passive(self, node_key):
        node = PASSIVE_NODES.get(node_key)
        if not node:
            return False, 0
        current = self.passive_levels.get(node_key, 0)
        if current >= node["max_level"]:
            return False, 0
        cost = int(node["cost_base"] * (node["cost_mult"] ** current))
        self.passive_levels[node_key] = current + 1
        return True, cost

    def get_passive_cost(self, node_key):
        node = PASSIVE_NODES.get(node_key)
        if not node:
            return 0
        current = self.passive_levels.get(node_key, 0)
        if current >= node["max_level"]:
            return -1
        return int(node["cost_base"] * (node["cost_mult"] ** current))

    def star_up(self):
        if self.star_count >= self.max_stars:
            return False
        self.star_count += 1
        self.current_hp = self.get_stat("hp")
        return True

    def take_damage(self, raw_damage):
        defense = self.get_stat("defense")
        reduction = defense / (defense + 50)
        actual = max(1, int(raw_damage * (1 - reduction)))
        self.current_hp = max(0, self.current_hp - actual)
        return self.is_alive()

    def heal(self, amount):
        max_hp = self.get_stat("hp")
        self.current_hp = min(max_hp, self.current_hp + amount)

    def is_alive(self):
        return self.current_hp > 0

    def heal_full(self):
        self.current_hp = self.get_stat("hp")

    def to_dict(self):
        return {
            "template_key": self.template_key,
            "corporation": self.corporation,
            "level": self.level,
            "xp": self.xp,
            "star_count": self.star_count,
            "passive_levels": self.passive_levels,
        }

    @classmethod
    def from_dict(cls, data):
        h = cls(data["template_key"], data.get("corporation"))
        h.level = data.get("level", 1)
        h.xp = data.get("xp", 0)
        h.xp_to_next = h._calc_xp_needed(h.level)
        h.star_count = data.get("star_count", 1)
        h.passive_levels = data.get("passive_levels", {k: 0 for k in PASSIVE_NODES})
        h.current_hp = h.get_stat("hp")
        return h


class Enemy:
    def __init__(self, template_key, floor_mult=1.0):
        from config import ENEMY_TEMPLATES
        t = ENEMY_TEMPLATES[template_key]
        self.name = t["name"]
        self.max_hp = int(t["hp"] * floor_mult)
        self.current_hp = self.max_hp
        self.attack = int(t["attack"] * floor_mult)
        self.defense = int(t["defense"] * floor_mult)
        self.speed = int(t["speed"] * floor_mult)
        self.xp_reward = int(t["xp_reward"] * floor_mult)
        self.gold_reward = int(t["gold_reward"] * floor_mult)
        self.is_boss = "boss" in template_key or floor_mult > 2.0
        self.crit_rate = 0.08 if not self.is_boss else 0.15
        self.crit_dmg = 1.5 if not self.is_boss else 2.0

    def take_damage(self, raw_damage):
        reduction = self.defense / (self.defense + 50)
        actual = max(1, int(raw_damage * (1 - reduction)))
        self.current_hp = max(0, self.current_hp - actual)
        return self.is_alive()

    def is_alive(self):
        return self.current_hp > 0
