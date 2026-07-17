import random
from heroes import Hero, Enemy


class BattleLog:
    def __init__(self):
        self.entries = []
        self.max_entries = 50

    def add(self, text, color=(200, 200, 200)):
        self.entries.append({"text": text, "color": color})
        if len(self.entries) > self.max_entries:
            self.entries.pop(0)

    def clear(self):
        self.entries = []


class Battle:
    def __init__(self, hero, enemy):
        self.hero = hero
        self.enemy = enemy
        self.log = BattleLog()
        self.turn = 0
        self.finished = False
        self.result = None
        self.pending_damage = []

    def calculate_attack(self, attacker_stats, is_hero=True):
        damage = attacker_stats["attack"]
        is_crit = random.random() < attacker_stats["crit_rate"]
        if is_crit:
            damage = int(damage * attacker_stats["crit_dmg"])
        is_dodge = random.random() < attacker_stats.get("dodge", 0)
        return damage, is_crit, is_dodge

    def hero_attack(self):
        if self.finished:
            return []

        events = []
        self.turn += 1

        hero_stats = self.hero.get_all_stats()
        raw_damage, is_crit, _ = self.calculate_attack(hero_stats, True)

        if self.enemy.defense > 0:
            reduction = self.enemy.defense / (self.enemy.defense + 50)
        else:
            reduction = 0
        actual = max(1, int(raw_damage * (1 - reduction)))

        killed = not self.enemy.take_damage(actual)

        ability = None
        if self.turn % 3 == 0 and self.hero.abilities:
            ability = random.choice(self.hero.abilities)

        if ability:
            ability_damage = int(actual * 1.5)
            self.enemy.current_hp = max(0, self.enemy.current_hp - ability_damage)
            actual = ability_damage
            events.append(("ability", ability, actual))
            if not self.enemy.is_alive():
                killed = True

        events.append(("hero_attack", actual, is_crit, killed))

        if is_crit:
            self.log.add(
                f"  КРИТИЧЕСКИЙ УДАР! {self.hero.name} наносит {actual} урона!",
                (255, 215, 0))
        else:
            self.log.add(
                f"  {self.hero.name} атакует: {actual} урона",
                (200, 200, 220))

        if ability:
            self.log.add(
                f"  ★ {ability}! Бонусный урон!",
                (0, 230, 230))

        if killed:
            self.finished = True
            self.result = "victory"
            self.log.add(
                f"  >>> {self.enemy.name} уничтожен!",
                (0, 255, 140))

        return events

    def enemy_attack(self):
        if self.finished:
            return []

        events = []
        enemy_stats = {
            "attack": self.enemy.attack,
            "crit_rate": self.enemy.crit_rate,
            "crit_dmg": self.enemy.crit_dmg,
            "dodge": 0,
        }
        hero_stats = self.hero.get_all_stats()

        raw_damage, is_crit, _ = self.calculate_attack(enemy_stats, False)
        is_dodge = random.random() < hero_stats["dodge"]

        if is_dodge:
            events.append(("dodge",))
            self.log.add(
                f"  {self.hero.name} уклоняется от атаки!",
                (0, 230, 230))
            return events

        reduction = hero_stats["defense"] / (hero_stats["defense"] + 50)
        actual = max(1, int(raw_damage * (1 - reduction)))
        self.hero.current_hp = max(0, self.hero.current_hp - actual)

        events.append(("enemy_attack", actual, is_crit,
                        not self.hero.is_alive()))

        if is_crit:
            self.log.add(
                f"  {self.enemy.name} критит! -{actual} HP",
                (255, 80, 80))
        else:
            self.log.add(
                f"  {self.enemy.name} атакует: -{actual} HP",
                (200, 120, 120))

        if not self.hero.is_alive():
            self.finished = True
            self.result = "defeat"
            self.log.add(
                f"  >>> {self.hero.name} повержен!",
                (255, 50, 50))

        return events

    def get_rewards(self):
        if self.result == "victory":
            return self.enemy.xp_reward, self.enemy.gold_reward
        return 0, 0
