import pygame
import sys
import math
import random
import time

from config import (
    WIDTH, HEIGHT, FPS, GAME_TITLE, VERSION, COLORS,
    CORPORATIONS, HERO_TEMPLATES, FLOOR_CONFIGS, PASSIVE_NODES,
    WARNING_TEXTS,
)
from heroes import Hero, Enemy
from battle import Battle
from shop import Shop, DonateShop
from ui import UIHelper
from save_system import save_game, load_game


STATE_MENU = "menu"
STATE_HEROES = "heroes"
STATE_HERO_DETAIL = "hero_detail"
STATE_FLOOR_SELECT = "floor_select"
STATE_BATTLE = "battle"
STATE_SHOP = "shop"
STATE_DONATE = "donate"
STATE_PASSIVE = "passive_tree"
STATE_SETTINGS = "settings"
STATE_GACHA_RESULT = "gacha_result"
STATE_WARNING = "warning"


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(f"{GAME_TITLE} v{VERSION}")
        self.clock = pygame.time.Clock()
        self.ui = UIHelper()
        self.running = True
        self.state = STATE_MENU
        self.prev_state = STATE_MENU

        self.gold = 300
        self.player_level = 1
        self.total_xp = 0
        self.heroes = []
        self.active_hero_index = -1
        self.current_floor = None
        self.current_floor_enemies = []
        self.current_enemy_index = 0
        self.battle = None
        self.battle_anim_timer = 0
        self.battle_animating = False
        self.xp_boost_active = False

        self.shop = Shop()
        self.donate_shop = DonateShop()
        self.gacha_results = []

        self.scroll = 0
        self.max_scroll = 0
        self.mouse_pos = (0, 0)
        self.mouse_clicked = False
        self.right_clicked = False
        self.hover_element = None

        self.menu_anim = 0
        self.floor_enemies_defeated = 0
        self.total_enemies_defeated = 0
        self.boss_active = False
        self.warning_shown = False
        self._save_check_cache = None

        self.new_game()

    def new_game(self):
        starter = Hero("analyst", "NEXUS_FINANCIAL")
        self.heroes = [starter]
        self.active_hero_index = 0
        self.gold = 300
        self.player_level = 1
        self.total_xp = 0
        self.floor_enemies_defeated = 0
        self.total_enemies_defeated = 0
        self._save_check_cache = None

    def try_load(self):
        data = load_game()
        if data:
            self.gold = data.get("gold", 300)
            self.player_level = data.get("player_level", 1)
            self.total_xp = data.get("total_xp", 0)
            self.total_enemies_defeated = data.get("total_enemies_defeated", 0)
            self.heroes = [Hero.from_dict(h) for h in data.get("heroes", [])]
            if self.heroes:
                self.active_hero_index = 0
            return True
        return False

    def get_save_data(self):
        return {
            "gold": self.gold,
            "player_level": self.player_level,
            "total_xp": self.total_xp,
            "total_enemies_defeated": self.total_enemies_defeated,
            "heroes": [h.to_dict() for h in self.heroes],
        }

    def get_active_hero(self):
        if 0 <= self.active_hero_index < len(self.heroes):
            return self.heroes[self.active_hero_index]
        return None

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.mouse_clicked = False
            self.right_clicked = False
            self.mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.mouse_clicked = True
                    elif event.button == 3:
                        self.right_clicked = True
                elif event.type == pygame.MOUSEWHEEL:
                    self.scroll -= event.y * 30
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.state in (STATE_HEROES, STATE_SHOP, STATE_DONATE,
                                          STATE_FLOOR_SELECT, STATE_SETTINGS,
                                          STATE_PASSIVE):
                            self.state = STATE_MENU
                        elif self.state == STATE_HERO_DETAIL:
                            self.state = STATE_HEROES
                        elif self.state == STATE_BATTLE:
                            pass
                        elif self.state == STATE_GACHA_RESULT:
                            self.state = STATE_SHOP
                    elif event.key == pygame.K_s:
                        save_game(self.get_save_data())

            self.scroll = max(0, min(self.scroll, max(0, self.max_scroll)))
            self.ui.update()
            self.draw()

            if self.state == STATE_BATTLE:
                self.update_battle()

            self.ui.tooltip.hide()
            pygame.display.flip()

        save_game(self.get_save_data())

    def draw(self):
        self.screen.fill(COLORS["bg_dark"])

        if self.state == STATE_MENU:
            self.draw_menu()
        elif self.state == STATE_WARNING:
            self.draw_warning()
        elif self.state == STATE_HEROES:
            self.draw_heroes()
        elif self.state == STATE_HERO_DETAIL:
            self.draw_hero_detail()
        elif self.state == STATE_FLOOR_SELECT:
            self.draw_floor_select()
        elif self.state == STATE_BATTLE:
            self.draw_battle()
        elif self.state == STATE_SHOP:
            self.draw_shop()
        elif self.state == STATE_DONATE:
            self.draw_donate()
        elif self.state == STATE_PASSIVE:
            self.draw_passive_tree()
        elif self.state == STATE_GACHA_RESULT:
            self.draw_gacha_result()
        elif self.state == STATE_SETTINGS:
            self.draw_settings()

        self.ui.particles.draw(self.screen)
        self.ui.draw_tooltip(self.screen)

    def draw_header(self, title, back_target=STATE_MENU):
        header_rect = pygame.Rect(0, 0, WIDTH, 55)
        pygame.draw.rect(self.screen, COLORS["bg_header"], header_rect)
        pygame.draw.line(self.screen, COLORS["border_dim"], (0, 55), (WIDTH, 55))

        back_rect = pygame.Rect(10, 10, 80, 35)
        mx, my = self.mouse_pos
        hover = back_rect.collidepoint(mx, my)
        self.ui.draw_button(self.screen, back_rect, "< Назад", hover)
        if hover and self.mouse_clicked:
            self.state = back_target
            self.scroll = 0

        t = self.ui.font_heading.render(title, True, COLORS["text_white"])
        self.screen.blit(t, (WIDTH // 2 - t.get_width() // 2, 14))

        gold_txt = self.ui.font_body.render(
            f"Золото: {self.gold}", True, COLORS["text_gold"])
        self.screen.blit(gold_txt, (WIDTH - gold_txt.get_width() - 15, 18))

        lvl_txt = self.ui.font_small.render(
            f"Ур. {self.player_level}", True, COLORS["neon_cyan"])
        self.screen.blit(lvl_txt, (WIDTH - gold_txt.get_width() - 15 - 70, 22))

    def draw_menu(self):
        self.menu_anim += 0.015
        phase = math.sin(self.menu_anim)

        for i in range(6):
            y_offset = int(50 * math.sin(self.menu_anim + i * 0.5))
            alpha = int(40 + 20 * math.sin(self.menu_anim + i))
            line_y = 100 + i * 100 + y_offset
            color = (max(0, min(255, 10 + alpha)), max(0, min(255, 20 + alpha)),
                     max(0, min(255, 50 + alpha)))
            pygame.draw.line(self.screen, color, (0, line_y), (WIDTH, line_y), 1)

        title = self.ui.font_huge.render("CORP", True, COLORS["neon_blue"])
        title2 = self.ui.font_huge.render("HEIST", True, COLORS["neon_gold"])
        tx = WIDTH // 2 - title.get_width() // 2
        glow_offset = int(2 * math.sin(self.menu_anim * 2))
        self.screen.blit(title, (tx + glow_offset, 80))
        self.screen.blit(title2, (tx + 30, 150))

        subtitle = self.ui.font_body.render(
            "Корпоративные войны. Финансовые империи.",
            True, COLORS["text_dim"])
        self.screen.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 230))

        buttons = [
            ("Начать игру", STATE_WARNING),
            ("Продолжить", None),
            ("Настройки", STATE_SETTINGS),
        ]

        btn_w = 260
        btn_h = 50
        start_y = 310
        mx, my = self.mouse_pos

        for i, (label, target) in enumerate(buttons):
            rect = pygame.Rect(WIDTH // 2 - btn_w // 2, start_y + i * 65, btn_w, btn_h)
            hover = rect.collidepoint(mx, my)
            disabled = (label == "Продолжить" and not self.try_load_save_check())
            self.ui.draw_button(self.screen, rect, label, hover, disabled)
            if hover and self.mouse_clicked and not disabled:
                if label == "Продолжить":
                    if self.try_load_save_check():
                        self.state = STATE_HEROES
                else:
                    self.state = target
                self.scroll = 0

        ver = self.ui.font_tiny.render(f"v{VERSION}", True, COLORS["border_dim"])
        self.screen.blit(ver, (WIDTH - ver.get_width() - 10, HEIGHT - 20))

    def try_load_save_check(self):
        if self._save_check_cache is None:
            self._save_check_cache = load_game() is not None
        return self._save_check_cache

    def draw_warning(self):
        self.draw_header("ПРЕДУПРЕЖДЕНИЕ")

        warn_rect = pygame.Rect(60, 80, WIDTH - 120, HEIGHT - 130)
        self.ui.draw_panel(self.screen, warn_rect, "Юридическая информация")

        y = 125
        for text in WARNING_TEXTS:
            t = self.ui.font_body.render(text, True, COLORS["text_danger"])
            self.screen.blit(t, (90, y))
            y += 35

        y += 15
        extra_warnings = [
            "CORP HEIST — бесплатная игра. Все персонажи вымышлены.",
            "Внутриигровые покупки за реальные деньги доступны.",
            "Рандомизация гача-механик: шансы опубликованы.",
            "Игра не связана с реальными корпорациями.",
            "Возрастное ограничение: 12+",
            "Разработчик не несёт ответственности за:",
            "  — реальные финансовые решения, принятые под влиянием игры",
            "  — время, проведённое в игре",
            "  — эмоциональные переживания, связанные с гача-механиками",
        ]
        for text in extra_warnings:
            t = self.ui.font_small.render(text, True, COLORS["text_dim"])
            self.screen.blit(t, (90, y))
            y += 28

        y += 20
        consent_rect = pygame.Rect(WIDTH // 2 - 150, y, 300, 50)
        mx, my = self.mouse_pos
        hover = consent_rect.collidepoint(mx, my)
        self.ui.draw_button(self.screen, consent_rect,
                            "Я принимаю условия", hover, color=COLORS["neon_green"])
        if hover and self.mouse_clicked:
            self.state = STATE_HEROES

    def draw_heroes(self):
        self.draw_header("АГЕНТЫ")
        self.max_scroll = max(0, len(self.heroes) * 120 - HEIGHT + 100)

        for i, hero in enumerate(self.heroes):
            y = 75 + i * 120 - int(self.scroll)
            if y < 50 or y > HEIGHT + 50:
                continue

            card_rect = pygame.Rect(40, y, WIDTH - 80, 105)
            mx, my = self.mouse_pos
            hover = card_rect.collidepoint(mx, my)
            corp_color = COLORS["text_dim"]
            if hero.corporation and hero.corporation in CORPORATIONS:
                corp_color = CORPORATIONS[hero.corporation]["color"]

            bg = COLORS["bg_card_hover"] if hover else COLORS["bg_card"]
            pygame.draw.rect(self.screen, bg, card_rect, border_radius=10)
            pygame.draw.rect(self.screen, corp_color, card_rect, 2, border_radius=10)

            self.ui.draw_tier_badge(self.screen, card_rect.x + 15, card_rect.y + 10,
                                    hero.tier, 18)
            self.ui.draw_stars(self.screen, card_rect.x + 55, card_rect.y + 12,
                               hero.star_count)

            name_txt = self.ui.font_heading.render(
                f"{hero.name}", True, COLORS["text_white"])
            self.screen.blit(name_txt, (card_rect.x + 15, card_rect.y + 38))

            role_txt = self.ui.font_small.render(
                hero.role, True, corp_color)
            self.screen.blit(role_txt, (card_rect.x + 15, card_rect.y + 68))

            lvl_txt = self.ui.font_small.render(
                f"Ур.{hero.level}", True, COLORS["neon_cyan"])
            self.screen.blit(lvl_txt, (card_rect.x + 15, card_rect.y + 86))

            stats = hero.get_all_stats()
            stat_x = card_rect.x + 130
            stat_labels = [
                ("HP", f"{hero.current_hp}/{int(stats['hp'])}", COLORS["hp_bar"]),
                ("ATK", f"{int(stats['attack'])}", COLORS["neon_red"]),
                ("DEF", f"{int(stats['defense'])}", COLORS["neon_blue"]),
                ("SPD", f"{int(stats['speed'])}", COLORS["neon_green"]),
                ("CRIT", f"{int(stats['crit_rate']*100)}%", COLORS["neon_gold"]),
            ]
            for si, (label, val, color) in enumerate(stat_labels):
                sx = stat_x + si * 110
                lt = self.ui.font_tiny.render(label, True, COLORS["text_dim"])
                vt = self.ui.font_small.render(val, True, color)
                self.screen.blit(lt, (sx, card_rect.y + 42))
                self.screen.blit(vt, (sx, card_rect.y + 60))

            if hero == self.get_active_hero():
                badge = self.ui.font_small.render("ACTIVE", True, COLORS["neon_green"])
                self.screen.blit(badge, (card_rect.right - 70, card_rect.y + 8))

            if hover:
                if self.mouse_clicked:
                    self.active_hero_index = i
                    self.state = STATE_HERO_DETAIL
                    self.scroll = 0

        if len(self.heroes) < 30:
            add_rect = pygame.Rect(WIDTH // 2 - 40, HEIGHT - 45, 80, 35)
            mx, my = self.mouse_pos
            hover = add_rect.collidepoint(mx, my)
            self.ui.draw_button(self.screen, add_rect, "+ Агент", hover,
                                color=COLORS["neon_gold"])
            if hover and self.mouse_clicked:
                self.state = STATE_SHOP
                self.scroll = 0

    def draw_hero_detail(self):
        hero = self.get_active_hero()
        if not hero:
            self.state = STATE_HEROES
            return

        self.draw_header(f"{hero.name}", STATE_HEROES)

        corp_color = COLORS["text_dim"]
        if hero.corporation and hero.corporation in CORPORATIONS:
            corp_color = CORPORATIONS[hero.corporation]["color"]

        left_panel = pygame.Rect(20, 65, 400, HEIGHT - 80)
        self.ui.draw_panel(self.screen, left_panel, "Характеристики", corp_color)

        y = 110
        self.ui.draw_tier_badge(self.screen, 40, y, hero.tier, 22)
        self.ui.draw_stars(self.screen, 90, y + 2, hero.star_count)
        y += 30

        name_t = self.ui.font_heading.render(hero.name, True, COLORS["text_white"])
        self.screen.blit(name_t, (40, y))
        y += 30
        role_t = self.ui.font_small.render(hero.role, True, corp_color)
        self.screen.blit(role_t, (40, y))
        y += 25
        desc_t = self.ui.font_small.render(hero.description, True, COLORS["text_dim"])
        self.screen.blit(desc_t, (40, y))
        y += 35

        stats = hero.get_all_stats()
        stat_list = [
            ("HP", f"{int(stats['hp'])}", hero.current_hp / max(1, stats['hp']),
             COLORS["hp_bar"], COLORS["hp_bg"]),
            ("Атака", f"{int(stats['attack'])}", stats['attack'] / 50,
             COLORS["neon_red"], (50, 15, 15)),
            ("Защита", f"{int(stats['defense'])}", stats['defense'] / 40,
             COLORS["neon_blue"], (15, 15, 50)),
            ("Скорость", f"{int(stats['speed'])}", stats['speed'] / 30,
             COLORS["neon_green"], (15, 50, 25)),
            ("Крит %", f"{stats['crit_rate']*100:.0f}%", stats['crit_rate'],
             COLORS["neon_gold"], (50, 45, 10)),
            ("Крит x", f"{stats['crit_dmg']:.1f}x", stats['crit_dmg'] / 3.0,
             COLORS["neon_pink"], (50, 15, 30)),
            ("Уклон", f"{stats['dodge']*100:.0f}%", stats['dodge'],
             COLORS["neon_cyan"], (15, 40, 40)),
        ]
        for label, val, fill, color, bg in stat_list:
            lt = self.ui.font_small.render(f"{label}", True, COLORS["text_dim"])
            vt = self.ui.font_small.render(val, True, color)
            self.screen.blit(lt, (40, y))
            self.screen.blit(vt, (130, y))
            self.ui.draw_bar(self.screen, 180, y + 3, 200, 12, fill, 1, color, bg)
            y += 22

        y += 15
        xp_txt = self.ui.font_small.render(
            f"XP: {hero.xp}/{hero.xp_to_next}", True, COLORS["xp_bar"])
        self.screen.blit(xp_txt, (40, y))
        self.ui.draw_bar(self.screen, 40, y + 18, 360, 10, hero.xp,
                         hero.xp_to_next, COLORS["xp_bar"], COLORS["xp_bg"])

        right_panel = pygame.Rect(440, 65, WIDTH - 460, HEIGHT - 80)
        self.ui.draw_panel(self.screen, right_panel, "Развитие")

        ry = 110
        for node_key, node in PASSIVE_NODES.items():
            if ry > HEIGHT - 50:
                break
            level = hero.passive_levels.get(node_key, 0)
            cost = hero.get_passive_cost(node_key)
            maxed = cost == -1

            node_rect = pygame.Rect(460, ry, WIDTH - 500, 55)
            pygame.draw.rect(self.screen, COLORS["bg_card"], node_rect, border_radius=6)
            pygame.draw.rect(self.screen, COLORS["border_dim"], node_rect, 1,
                             border_radius=6)

            nt = self.ui.font_body.render(node["name"], True, COLORS["text_white"])
            self.screen.blit(nt, (475, ry + 5))

            dt = self.ui.font_small.render(node["description"], True, COLORS["text_dim"])
            self.screen.blit(dt, (475, ry + 28))

            lvl_t = self.ui.font_small.render(
                f"Ур.{level}/{node['max_level']}", True, COLORS["neon_cyan"])
            self.screen.blit(lvl_t, (WIDTH - 250, ry + 8))

            if not maxed:
                btn_rect = pygame.Rect(WIDTH - 140, ry + 8, 110, 30)
                mx, my = self.mouse_pos
                hover = btn_rect.collidepoint(mx, my)
                can_afford = self.gold >= cost
                self.ui.draw_button(self.screen, btn_rect,
                                    f"{cost}g", hover, not can_afford,
                                    COLORS["neon_gold"] if can_afford else COLORS["text_danger"])
                if hover and self.mouse_clicked and can_afford:
                    self.gold -= cost
                    hero.upgrade_passive(node_key)
            else:
                max_t = self.ui.font_small.render("MAX", True, COLORS["text_gold"])
                self.screen.blit(max_t, (WIDTH - 110, ry + 15))

            ry += 62

    def draw_floor_select(self):
        self.draw_header("БИЗНЕС-ЦЕНТРЫ")

        hero = self.get_active_hero()
        if not hero:
            no_hero = self.ui.font_body.render(
                "Нет доступного агента", True, COLORS["text_danger"])
            self.screen.blit(no_hero, (WIDTH // 2 - no_hero.get_width() // 2, 150))
            return

        y = 75 - int(self.scroll)
        self.max_scroll = max(0, len(FLOOR_CONFIGS) * 140 - HEIGHT + 100)

        for i, floor_cfg in enumerate(FLOOR_CONFIGS):
            if y > HEIGHT or y < -140:
                y += 140
                continue

            unlocked = self.player_level >= floor_cfg["unlock_level"]
            card_rect = pygame.Rect(40, y, WIDTH - 80, 120)
            mx, my = self.mouse_pos
            hover = card_rect.collidepoint(mx, my) and unlocked

            bg = COLORS["bg_card_hover"] if hover else COLORS["bg_card"]
            if not unlocked:
                bg = (18, 18, 25)
            pygame.draw.rect(self.screen, bg, card_rect, border_radius=10)
            pygame.draw.rect(self.screen, floor_cfg["color"] if unlocked else COLORS["border_dim"],
                             card_rect, 2, border_radius=10)

            floor_t = self.ui.font_heading.render(
                f"Этаж {floor_cfg['floor']}: {floor_cfg['name']}",
                True, floor_cfg["color"] if unlocked else COLORS["border_dim"])
            self.screen.blit(floor_t, (card_rect.x + 15, card_rect.y + 12))

            build_t = self.ui.font_small.render(
                floor_cfg["building"], True,
                COLORS["text_dim"] if unlocked else COLORS["border_dim"])
            self.screen.blit(build_t, (card_rect.x + 15, card_rect.y + 42))

            enemies_t = self.ui.font_small.render(
                f"Враги: {', '.join(floor_cfg['enemies'])} | Босс: {floor_cfg['boss']}",
                True, COLORS["text_dim"] if unlocked else COLORS["border_dim"])
            self.screen.blit(enemies_t, (card_rect.x + 15, card_rect.y + 65))

            if not unlocked:
                lock_t = self.ui.font_body.render(
                    f"🔒 Нужен ур. {floor_cfg['unlock_level']}",
                    True, COLORS["text_danger"])
                self.screen.blit(lock_t, (card_rect.x + 15, card_rect.y + 90))
            else:
                start_rect = pygame.Rect(card_rect.right - 140, card_rect.y + 75, 120, 35)
                h = start_rect.collidepoint(mx, my)
                self.ui.draw_button(self.screen, start_rect, "В бой!", h,
                                    color=COLORS["neon_green"])
                if h and self.mouse_clicked:
                    self.start_floor(floor_cfg)

            y += 140

    def start_floor(self, floor_cfg):
        self.current_floor = floor_cfg
        self.current_floor_enemies = list(floor_cfg["enemies"])
        self.floor_enemies_defeated = 0
        self.boss_active = False
        self.spawn_enemy()

    def spawn_enemy(self):
        hero = self.get_active_hero()
        if not hero:
            return
        if self.boss_active:
            return

        floor_mult = 1.0 + self.current_floor["floor"] * 0.15 + \
            self.floor_enemies_defeated * 0.05

        if self.floor_enemies_defeated >= len(self.current_floor_enemies):
            boss_key = self.current_floor["boss"]
            enemy = Enemy(boss_key, floor_mult * 1.3)
            self.boss_active = True
        else:
            pool = self.current_floor_enemies
            enemy_key = pool[self.floor_enemies_defeated % len(pool)]
            enemy = Enemy(enemy_key, floor_mult)

        self.current_enemy_index = self.floor_enemies_defeated
        hero.heal_full()
        self.battle = Battle(hero, enemy)
        self.battle_anim_timer = 0
        self.battle_animating = False
        self.state = STATE_BATTLE
        self.scroll = 0

    def draw_battle(self):
        hero = self.get_active_hero()
        if not hero or not self.battle:
            return

        self.draw_header("БОЙ")

        enemy = self.battle.enemy
        is_boss = enemy.is_boss

        if is_boss:
            boss_glow = int(3 * (1 + math.sin(self.menu_anim * 3)))
            for i in range(boss_glow):
                pygame.draw.rect(self.screen, COLORS["neon_gold"],
                                 (30 - i, 30 - i, WIDTH - 40 + i * 2, HEIGHT - 40 + i * 2),
                                 1, border_radius=12)

        hero_panel = pygame.Rect(30, 65, WIDTH // 2 - 45, 200)
        enemy_panel = pygame.Rect(WIDTH // 2 + 15, 65, WIDTH // 2 - 45, 200)

        self.ui.draw_panel(self.screen, hero_panel, hero.name, COLORS["neon_blue"])
        self.ui.draw_panel(self.screen, enemy_panel,
                           f"{'★ ' if is_boss else ''}{enemy.name}",
                           COLORS["neon_gold"] if is_boss else COLORS["neon_red"])

        hp_y = 100
        self.ui.draw_bar(self.screen, 50, hp_y, hero_panel.w - 40, 20,
                         hero.current_hp, hero.get_stat("hp"),
                         COLORS["hp_bar"], COLORS["hp_bg"])
        hp_text = self.ui.font_small.render(
            f"HP: {hero.current_hp}/{int(hero.get_stat('hp'))}",
            True, COLORS["text_white"])
        self.screen.blit(hp_text, (55, hp_y + 2))

        enemy_hp_y = 100
        self.ui.draw_bar(self.screen, WIDTH // 2 + 30, enemy_hp_y,
                         enemy_panel.w - 40, 20,
                         enemy.current_hp, enemy.max_hp,
                         COLORS["neon_red"], COLORS["hp_bg"])
        ehp_text = self.ui.font_small.render(
            f"HP: {enemy.current_hp}/{enemy.max_hp}",
            True, COLORS["text_white"])
        self.screen.blit(ehp_text, (WIDTH // 2 + 35, enemy_hp_y + 2))

        hero_stats = hero.get_all_stats()
        stat_texts = [
            f"ATK:{int(hero_stats['attack'])}",
            f"DEF:{int(hero_stats['defense'])}",
            f"CRIT:{int(hero_stats['crit_rate']*100)}%",
        ]
        for si, txt in enumerate(stat_texts):
            st = self.ui.font_tiny.render(txt, True, COLORS["text_dim"])
            self.screen.blit(st, (50 + si * 110, hp_y + 25))

        e_stat_texts = [
            f"ATK:{enemy.attack}",
            f"DEF:{enemy.defense}",
            f"SPD:{enemy.speed}",
        ]
        for si, txt in enumerate(e_stat_texts):
            st = self.ui.font_tiny.render(txt, True, COLORS["text_dim"])
            self.screen.blit(st, (WIDTH // 2 + 30 + si * 110, hp_y + 25))

        log_panel = pygame.Rect(30, 280, WIDTH - 60, HEIGHT - 380)
        self.ui.draw_panel(self.screen, log_panel, "Ход боя")
        log_y = 320
        for entry in self.battle.log.entries[-12:]:
            if log_y > log_panel.bottom - 15:
                break
            t = self.ui.font_small.render(entry["text"], True, entry["color"])
            self.screen.blit(t, (50, log_y))
            log_y += 20

        btn_y = HEIGHT - 85
        if not self.battle.finished:
            attack_rect = pygame.Rect(WIDTH // 2 - 100, btn_y, 200, 45)
            mx, my = self.mouse_pos
            hover = attack_rect.collidepoint(mx, my)
            self.ui.draw_button(self.screen, attack_rect,
                                "⚔ АТАКОВАТЬ", hover, color=COLORS["neon_green"])
            if hover and self.mouse_clicked and not self.battle_animating:
                self.battle.hero_attack()
                self.battle_animating = True
                self.battle_anim_timer = 30
        else:
            if self.battle.result == "victory":
                xp_reward, gold_reward = self.battle.get_rewards()
                if self.xp_boost_active:
                    xp_reward = int(xp_reward * 1.5)
                    self.xp_boost_active = False

                res_t = self.ui.font_heading.render(
                    "ПОБЕДА!", True, COLORS["neon_green"])
                self.screen.blit(res_t, (WIDTH // 2 - res_t.get_width() // 2, btn_y - 40))

                rew_t = self.ui.font_body.render(
                    f"+{xp_reward} XP  |  +{gold_reward} золота",
                    True, COLORS["text_gold"])
                self.screen.blit(rew_t, (WIDTH // 2 - rew_t.get_width() // 2, btn_y - 10))

                cont_rect = pygame.Rect(WIDTH // 2 - 100, btn_y + 20, 200, 35)
                mx, my = self.mouse_pos
                hover = cont_rect.collidepoint(mx, my)
                self.ui.draw_button(self.screen, cont_rect, "Продолжить", hover,
                                    color=COLORS["neon_blue"])
                if hover and self.mouse_clicked:
                    hero.gain_xp(xp_reward)
                    self.gold += gold_reward
                    self.floor_enemies_defeated += 1
                    self.total_enemies_defeated += 1
                    self.check_level_up()
                    if self.boss_active:
                        self.state = STATE_FLOOR_SELECT
                        self.boss_active = False
                    else:
                        self.spawn_enemy()
            else:
                res_t = self.ui.font_heading.render(
                    "ПОРАЖЕНИЕ", True, COLORS["neon_red"])
                self.screen.blit(res_t, (WIDTH // 2 - res_t.get_width() // 2, btn_y - 30))

                retry_rect = pygame.Rect(WIDTH // 2 - 100, btn_y + 10, 200, 40)
                mx, my = self.mouse_pos
                hover = retry_rect.collidepoint(mx, my)
                self.ui.draw_button(self.screen, retry_rect, "Отступить", hover,
                                    color=COLORS["neon_red"])
                if hover and self.mouse_clicked:
                    self.state = STATE_FLOOR_SELECT
                    self.boss_active = False

    def update_battle(self):
        if self.battle_animating:
            self.battle_anim_timer -= 1
            if self.battle_anim_timer <= 0:
                self.battle_animating = False
                if not self.battle.finished:
                    self.battle.enemy_attack()

    def check_level_up(self):
        xp_per_level = int(100 * (self.player_level ** 1.3))
        while self.total_xp >= xp_per_level:
            self.total_xp -= xp_per_level
            self.player_level += 1
            xp_per_level = int(100 * (self.player_level ** 1.3))
            self.gold += self.player_level * 10

    def draw_shop(self):
        self.draw_header("МАГАЗИН")

        hero = self.get_active_hero()
        items = self.shop.get_shop_items()

        self.scroll = 0
        y = 80

        section_t = self.ui.font_heading.render("Наборы агентов", True, COLORS["neon_cyan"])
        self.screen.blit(section_t, (40, y))
        y += 35

        for item in items[:2]:
            card_rect = pygame.Rect(40, y, WIDTH - 80, 80)
            mx, my = self.mouse_pos
            hover = card_rect.collidepoint(mx, my)
            bg = COLORS["bg_card_hover"] if hover else COLORS["bg_card"]
            pygame.draw.rect(self.screen, bg, card_rect, border_radius=8)
            pygame.draw.rect(self.screen, COLORS["border_dim"], card_rect, 1,
                             border_radius=8)

            it = self.ui.font_heading.render(item["name"], True, COLORS["text_white"])
            self.screen.blit(it, (60, y + 10))

            dt = self.ui.font_small.render(item["description"], True, COLORS["text_dim"])
            self.screen.blit(dt, (60, y + 40))

            can_buy = self.gold >= item["cost"]
            buy_rect = pygame.Rect(card_rect.right - 150, y + 20, 130, 35)
            bh = buy_rect.collidepoint(mx, my)
            self.ui.draw_button(self.screen, buy_rect,
                                f"{item['cost']} золота", bh, not can_buy,
                                COLORS["neon_gold"] if can_buy else COLORS["text_danger"])
            if bh and self.mouse_clicked and can_buy:
                self.gold -= item["cost"]
                if item["type"] == "gacha_single":
                    result = self.shop.roll_single()
                    self.gacha_results = [result]
                    self.heroes.append(result)
                    self.state = STATE_GACHA_RESULT
                elif item["type"] == "gacha_multi":
                    results = self.shop.roll_multi()
                    self.gacha_results = results
                    self.heroes.extend(results)
                    self.state = STATE_GACHA_RESULT
                elif item["type"] == "heal":
                    if hero:
                        hero.heal_full()
                elif item["type"] == "xp_boost":
                    self.xp_boost_active = True
                elif item["type"] == "star_stone":
                    if hero:
                        hero.star_up()
            y += 90

        y += 10
        section2 = self.ui.font_heading.render("Предметы", True, COLORS["neon_gold"])
        self.screen.blit(section2, (40, y))
        y += 35

        for item in items[2:]:
            card_rect = pygame.Rect(40, y, WIDTH - 80, 80)
            mx, my = self.mouse_pos
            hover = card_rect.collidepoint(mx, my)
            bg = COLORS["bg_card_hover"] if hover else COLORS["bg_card"]
            pygame.draw.rect(self.screen, bg, card_rect, border_radius=8)
            pygame.draw.rect(self.screen, COLORS["border_dim"], card_rect, 1,
                             border_radius=8)

            it = self.ui.font_heading.render(item["name"], True, COLORS["text_white"])
            self.screen.blit(it, (60, y + 10))

            dt = self.ui.font_small.render(item["description"], True, COLORS["text_dim"])
            self.screen.blit(dt, (60, y + 40))

            can_buy = self.gold >= item["cost"]
            buy_rect = pygame.Rect(card_rect.right - 150, y + 20, 130, 35)
            bh = buy_rect.collidepoint(mx, my)
            self.ui.draw_button(self.screen, buy_rect,
                                f"{item['cost']} золота", bh, not can_buy,
                                COLORS["neon_gold"] if can_buy else COLORS["text_danger"])
            if bh and self.mouse_clicked and can_buy:
                self.gold -= item["cost"]
                if item["type"] == "heal" and hero:
                    hero.heal_full()
                elif item["type"] == "xp_boost":
                    self.xp_boost_active = True
                elif item["type"] == "star_stone" and hero:
                    hero.star_up()
            y += 90

        y += 20
        donate_rect = pygame.Rect(WIDTH // 2 - 140, y, 280, 45)
        mx, my = self.mouse_pos
        hover = donate_rect.collidepoint(mx, my)
        self.ui.draw_button(self.screen, donate_rect,
                            "Премиум магазин (Реальные деньги)", hover,
                            color=COLORS["neon_pink"])
        if hover and self.mouse_clicked:
            self.state = STATE_DONATE
            self.scroll = 0

        bottom_btns = [
            ("Дерево навыков", STATE_PASSIVE, COLORS["neon_purple"]),
            ("Бизнес-центры", STATE_FLOOR_SELECT, COLORS["neon_green"]),
        ]
        for i, (label, target, color) in enumerate(bottom_btns):
            bx = 40 + i * 260
            by = HEIGHT - 55
            btn_rect = pygame.Rect(bx, by, 240, 40)
            h = btn_rect.collidepoint(mx, my)
            self.ui.draw_button(self.screen, btn_rect, label, h, color=color)
            if h and self.mouse_clicked:
                self.state = target
                self.scroll = 0

    def draw_donate(self):
        self.draw_header("ПРЕМИУМ-МАГАЗИН")

        warn_t = self.ui.font_body.render(
            "Реальные деньги. Покупайте осознанно. 12+",
            True, COLORS["text_danger"])
        self.screen.blit(warn_t, (WIDTH // 2 - warn_t.get_width() // 2, 68))

        items = self.donate_shop.get_items()
        y = 100
        cols = 2
        card_w = (WIDTH - 120) // cols
        card_h = 140
        mx, my = self.mouse_pos

        for i, item in enumerate(items):
            col = i % cols
            row = i // cols
            cx = 40 + col * (card_w + 20)
            cy = y + row * (card_h + 15)

            card_rect = pygame.Rect(cx, cy, card_w, card_h)
            hover = card_rect.collidepoint(mx, my)
            bg = COLORS["bg_card_hover"] if hover else COLORS["bg_card"]
            pygame.draw.rect(self.screen, bg, card_rect, border_radius=10)
            pygame.draw.rect(self.screen, COLORS["neon_pink"], card_rect, 1,
                             border_radius=10)

            tag_t = self.ui.font_tiny.render(item["tag"], True, COLORS["neon_gold"])
            self.screen.blit(tag_t, (cx + 10, cy + 8))

            name_t = self.ui.font_heading.render(item["name"], True, COLORS["text_white"])
            self.screen.blit(name_t, (cx + 10, cy + 28))

            desc_t = self.ui.font_small.render(item["description"], True, COLORS["text_dim"])
            self.screen.blit(desc_t, (cx + 10, cy + 58))

            price_t = self.ui.font_heading.render(
                item["price_real"], True, COLORS["neon_pink"])
            self.screen.blit(price_t, (cx + 10, cy + 95))

            buy_rect = pygame.Rect(cx + card_w - 100, cy + card_h - 40, 85, 30)
            bh = buy_rect.collidepoint(mx, my)
            self.ui.draw_button(self.screen, buy_rect, "Купить", bh,
                                color=COLORS["neon_pink"])
            if bh and self.mouse_clicked:
                self.gold += item["amount"] if item["currency"] == "gold" else 0

        bottom_note = self.ui.font_tiny.render(
            "Все покупки виртуальны. Не являются офертой. 14-ФЗ, ст.32.",
            True, COLORS["text_dim"])
        self.screen.blit(bottom_note, (WIDTH // 2 - bottom_note.get_width() // 2,
                                        HEIGHT - 25))

    def draw_passive_tree(self):
        self.draw_header("ДЕРЕВО НАВЫКОВ")
        hero = self.get_active_hero()
        if not hero:
            return

        col_w = (WIDTH - 100) // 2
        col_gap = 30
        mx, my = self.mouse_pos
        y = 80 - int(self.scroll)
        self.max_scroll = max(0, len(PASSIVE_NODES) * 80 - HEIGHT + 150)

        for i, (node_key, node) in enumerate(PASSIVE_NODES.items()):
            col = i % 2
            row = i // 2
            nx = 40 + col * (col_w + col_gap)
            ny = y + row * 80

            if ny > HEIGHT or ny < -80:
                continue

            level = hero.passive_levels.get(node_key, 0)
            cost = hero.get_passive_cost(node_key)
            maxed = cost == -1

            node_rect = pygame.Rect(nx, ny, col_w, 65)
            hover = node_rect.collidepoint(mx, my) and not maxed
            bg = COLORS["bg_card_hover"] if hover else COLORS["bg_card"]
            pygame.draw.rect(self.screen, bg, node_rect, border_radius=8)
            pygame.draw.rect(self.screen, COLORS["neon_purple"] if level > 0 else COLORS["border_dim"],
                             node_rect, 1 if level == 0 else 2, border_radius=8)

            nt = self.ui.font_body.render(node["name"], True,
                                          COLORS["neon_purple"] if level > 0 else COLORS["text_white"])
            self.screen.blit(nt, (nx + 12, ny + 8))

            dt = self.ui.font_small.render(node["description"], True, COLORS["text_dim"])
            self.screen.blit(dt, (nx + 12, ny + 32))

            lvl_bar_w = 100
            fill = level / node["max_level"]
            self.ui.draw_bar(self.screen, nx + 12, ny + 50, lvl_bar_w, 8,
                             fill, 1, COLORS["neon_purple"], COLORS["xp_bg"], border=False)
            lvl_t = self.ui.font_tiny.render(f"{level}/{node['max_level']}", True, COLORS["text_dim"])
            self.screen.blit(lvl_t, (nx + 130, ny + 47))

            if not maxed:
                btn_rect = pygame.Rect(nx + col_w - 90, ny + 18, 75, 28)
                bh = btn_rect.collidepoint(mx, my)
                can_afford = self.gold >= cost
                self.ui.draw_button(self.screen, btn_rect, f"{cost}g", bh,
                                    not can_afford, COLORS["neon_gold"] if can_afford else COLORS["text_danger"])
                if bh and self.mouse_clicked and can_afford:
                    self.gold -= cost
                    hero.upgrade_passive(node_key)
            else:
                max_t = self.ui.font_body.render("MAX", True, COLORS["text_gold"])
                self.screen.blit(max_t, (nx + col_w - 55, ny + 22))

    def draw_gacha_result(self):
        self.draw_header("РЕКРУТИРОВАНИЕ", STATE_SHOP)

        if not self.gacha_results:
            self.state = STATE_SHOP
            return

        title_t = self.ui.font_heading.render(
            "Результат рекрутинга", True, COLORS["text_white"])
        self.screen.blit(title_t, (WIDTH // 2 - title_t.get_width() // 2, 70))

        tier_colors = {
            "B": COLORS["text_dim"],
            "A": COLORS["neon_blue"],
            "S": COLORS["neon_purple"],
            "SSR": COLORS["neon_gold"],
        }

        count = len(self.gacha_results)
        cols = min(count, 5)
        rows = (count + cols - 1) // cols
        card_w = min(180, (WIDTH - 80) // cols - 15)
        card_h = 220
        mx, my = self.mouse_pos

        start_x = (WIDTH - cols * (card_w + 15)) // 2
        start_y = 110

        for i, hero in enumerate(self.gacha_results):
            col = i % cols
            row = i // cols
            cx = start_x + col * (card_w + 15)
            cy = start_y + row * (card_h + 15)

            card_rect = pygame.Rect(cx, cy, card_w, card_h)
            tc = tier_colors.get(hero.tier, COLORS["text_dim"])

            pygame.draw.rect(self.screen, COLORS["bg_card"], card_rect, border_radius=10)
            glow_rect = pygame.Rect(cx - 2, cy - 2, card_w + 4, card_h + 4)
            pygame.draw.rect(self.screen, tc, glow_rect, 2, border_radius=12)

            self.ui.draw_tier_badge(self.screen, cx + 10, cy + 10, hero.tier, 20)
            self.ui.draw_stars(self.screen, cx + card_w - 90, cy + 12, hero.star_count)

            name_t = self.ui.font_body.render(hero.name, True, COLORS["text_white"])
            self.screen.blit(name_t, (cx + card_w // 2 - name_t.get_width() // 2,
                                       cy + 40))

            role_t = self.ui.font_small.render(hero.role, True, tc)
            self.screen.blit(role_t, (cx + card_w // 2 - role_t.get_width() // 2,
                                       cy + 65))

            icon_y = cy + 90
            stats = hero.get_all_stats()
            mini_stats = [
                f"HP:{int(stats['hp'])}",
                f"ATK:{int(stats['attack'])}",
                f"SPD:{int(stats['speed'])}",
                f"CRIT:{int(stats['crit_rate']*100)}%",
            ]
            for si, stxt in enumerate(mini_stats):
                st = self.ui.font_tiny.render(stxt, True, COLORS["text_dim"])
                self.screen.blit(st, (cx + 15, icon_y + si * 18))

            desc_lines = hero.description.split(".")
            for di, dl in enumerate(desc_lines[:2]):
                if dl.strip():
                    dlt = self.ui.font_tiny.render(dl.strip() + ".",
                                                   True, COLORS["text_dim"])
                    self.screen.blit(dlt, (cx + 10, cy + card_h - 45 + di * 15))

        if count > 0:
            btn_rect = pygame.Rect(WIDTH // 2 - 80, HEIGHT - 50, 160, 35)
            mx, my = self.mouse_pos
            hover = btn_rect.collidepoint(mx, my)
            self.ui.draw_button(self.screen, btn_rect, "Продолжить", hover,
                                color=COLORS["neon_blue"])
            if hover and self.mouse_clicked:
                self.state = STATE_SHOP
                self.scroll = 0

    def draw_settings(self):
        self.draw_header("НАСТРОЙКИ")

        y = 80
        settings = [
            ("Версия игры", VERSION, COLORS["text_dim"]),
            ("Героев в отряде", str(len(self.heroes)), COLORS["neon_cyan"]),
            ("Золото", str(self.gold), COLORS["text_gold"]),
            ("Уровень", str(self.player_level), COLORS["neon_blue"]),
            ("Всего врагов побеждено", str(self.total_enemies_defeated),
             COLORS["neon_green"]),
        ]

        for label, value, color in settings:
            pygame.draw.rect(self.screen, COLORS["bg_card"],
                             (60, y, WIDTH - 120, 40), border_radius=6)
            lt = self.ui.font_body.render(label, True, COLORS["text_dim"])
            vt = self.ui.font_body.render(value, True, color)
            self.screen.blit(lt, (80, y + 10))
            self.screen.blit(vt, (WIDTH - 80 - vt.get_width(), y + 10))
            y += 50

        y += 20
        mx, my = self.mouse_pos

        save_rect = pygame.Rect(WIDTH // 2 - 120, y, 240, 40)
        hover = save_rect.collidepoint(mx, my)
        self.ui.draw_button(self.screen, save_rect, "Сохранить (S)", hover,
                            color=COLORS["neon_green"])
        if hover and self.mouse_clicked:
            save_game(self.get_save_data())

        y += 55
        del_rect = pygame.Rect(WIDTH // 2 - 120, y, 240, 40)
        hover = del_rect.collidepoint(mx, my)
        self.ui.draw_button(self.screen, del_rect, "Начать заново", hover,
                            color=COLORS["neon_red"])
        if hover and self.mouse_clicked:
            from save_system import delete_save
            delete_save()
            self.new_game()
            self.state = STATE_MENU

        y += 70
        for i, text in enumerate(WARNING_TEXTS[:3]):
            wt = self.ui.font_tiny.render(text, True, COLORS["text_dim"])
            self.screen.blit(wt, (WIDTH // 2 - wt.get_width() // 2, y + i * 18))
