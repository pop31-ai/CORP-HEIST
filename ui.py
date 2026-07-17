import pygame
from config import COLORS, WIDTH, HEIGHT


class Tooltip:
    def __init__(self):
        self.lines = []
        self.visible = False
        self.rect = pygame.Rect(0, 0, 0, 0)

    def show(self, lines, pos):
        self.lines = lines
        self.visible = True
        font_small = pygame.font.SysFont("Segoe UI", 14)
        max_w = max(font_small.size(l)[0] for l in lines) + 24
        h = len(lines) * 20 + 16
        x = min(pos[0] + 10, WIDTH - max_w - 10)
        y = min(pos[1] + 10, HEIGHT - h - 10)
        self.rect = pygame.Rect(x, y, max_w, h)

    def hide(self):
        self.visible = False
        self.lines = []

    def draw(self, surface):
        if not self.visible:
            return
        pygame.draw.rect(surface, (15, 15, 28), self.rect, border_radius=6)
        pygame.draw.rect(surface, COLORS["border_dim"], self.rect, 1, border_radius=6)
        font = pygame.font.SysFont("Segoe UI", 14)
        y = self.rect.y + 8
        for line in self.lines:
            if line.startswith("!"):
                txt = font.render(line[1:], True, COLORS["text_gold"])
            elif line.startswith("#"):
                txt = font.render(line[1:], True, COLORS["text_danger"])
            else:
                txt = font.render(line, True, COLORS["text_dim"])
            surface.blit(txt, (self.rect.x + 12, y))
            y += 20


class Particle:
    def __init__(self, x, y, color, vx=0, vy=0, life=30, size=3):
        self.x = x
        self.y = y
        self.color = color
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy -= 0.05
        self.life -= 1

    def draw(self, surface):
        alpha = max(0, self.life / self.max_life)
        s = max(1, int(self.size * alpha))
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), s)

    def is_dead(self):
        return self.life <= 0


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit(self, x, y, color, count=8, spread=3, life=25):
        for _ in range(count):
            vx = (pygame.math.Vector2(1, 0).rotate(
                pygame.time.get_ticks() % 360) * (spread * (0.5 + 0.5 * (
                    (pygame.time.get_ticks() * _ * 7) % 100) / 100))).x
            vy = (spread * -0.5) - (pygame.time.get_ticks() % spread)
            self.particles.append(
                Particle(x, y, color, vx, vy, life, 3))

    def emit_text(self, x, y, text, color, size=24):
        pass

    def update(self):
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if not p.is_dead()]

    def draw(self, surface):
        for p in self.particles:
            p.draw(surface)


class FloatingText:
    def __init__(self):
        self.texts = []

    def add(self, x, y, text, color, size=24, duration=45):
        font = pygame.font.SysFont("Segoe UI Bold", size)
        self.texts.append({
            "surface": font.render(text, True, color),
            "x": x,
            "y": y,
            "life": duration,
            "max_life": duration,
        })

    def update(self):
        for t in self.texts:
            t["y"] -= 1.2
            t["life"] -= 1
        self.texts = [t for t in self.texts if t["life"] > 0]

    def draw(self, surface):
        for t in self.texts:
            alpha = max(0, t["life"] / t["max_life"])
            surf = t["surface"]
            if alpha < 1.0:
                temp = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
                temp.blit(surf, (0, 0))
                temp.set_alpha(int(alpha * 255))
                surface.blit(temp, (t["x"] - surf.get_width() // 2, t["y"]))
            else:
                surface.blit(surf, (t["x"] - surf.get_width() // 2, t["y"]))


class UIHelper:
    def __init__(self):
        self.font_title = pygame.font.SysFont("Segoe UI Bold", 36)
        self.font_heading = pygame.font.SysFont("Segoe UI Bold", 24)
        self.font_body = pygame.font.SysFont("Segoe UI", 18)
        self.font_small = pygame.font.SysFont("Segoe UI", 14)
        self.font_tiny = pygame.font.SysFont("Segoe UI", 11)
        self.font_huge = pygame.font.SysFont("Segoe UI Bold", 64)
        self.tooltip = Tooltip()
        self.particles = ParticleSystem()
        self.floating = FloatingText()
        self.glow_phase = 0

    def update(self):
        self.glow_phase = (self.glow_phase + 0.02) % 6.28
        self.particles.update()
        self.floating.update()

    def draw_bar(self, surface, x, y, w, h, value, max_val, color, bg_color, border=True):
        pygame.draw.rect(surface, bg_color, (x, y, w, h), border_radius=3)
        fill = max(0, min(1, value / max(max_val, 1)))
        if fill > 0:
            pygame.draw.rect(surface, color, (x, y, int(w * fill), h), border_radius=3)
        if border:
            pygame.draw.rect(surface, COLORS["border_dim"], (x, y, w, h), 1, border_radius=3)

    def draw_button(self, surface, rect, text, hover=False, disabled=False, color=None):
        if color is None:
            color = COLORS["neon_blue"] if not disabled else COLORS["border_dim"]
        bg = COLORS["bg_card_hover"] if hover else COLORS["bg_card"]
        if disabled:
            bg = (20, 20, 30)
        pygame.draw.rect(surface, bg, rect, border_radius=8)
        c = color if not disabled else (80, 80, 100)
        glow = int(3 * (1 + self.glow_phase))
        if hover and not disabled:
            pygame.draw.rect(surface, c, rect, 2, border_radius=8)
            glow_surf = pygame.Surface((rect.w + 4, rect.h + 4), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (*c, 30), (0, 0, rect.w + 4, rect.h + 4),
                             border_radius=10)
            surface.blit(glow_surf, (rect.x - 2, rect.y - 2))
        else:
            pygame.draw.rect(surface, COLORS["border_dim"], rect, 1, border_radius=8)
        font = self.font_small if rect.h < 35 else self.font_body
        txt = font.render(text, True, c if not disabled else (80, 80, 100))
        surface.blit(txt, (rect.centerx - txt.get_width() // 2,
                           rect.centery - txt.get_height() // 2))

    def draw_panel(self, surface, rect, title=None, border_color=None):
        pygame.draw.rect(surface, COLORS["bg_panel"], rect, border_radius=10)
        bc = border_color or COLORS["border_dim"]
        pygame.draw.rect(surface, bc, rect, 1, border_radius=10)
        if title:
            pygame.draw.rect(surface, COLORS["bg_header"],
                             (rect.x, rect.y, rect.w, 36), border_radius=10)
            pygame.draw.rect(surface, bc,
                             (rect.x, rect.y + 34, rect.w, 2), 0)
            t = self.font_body.render(title, True, bc)
            surface.blit(t, (rect.x + 12, rect.y + 8))

    def draw_tier_badge(self, surface, x, y, tier, size=20):
        tier_colors = {
            "B": COLORS["text_dim"],
            "A": COLORS["neon_blue"],
            "S": COLORS["neon_purple"],
            "SSR": COLORS["neon_gold"],
        }
        c = tier_colors.get(tier, COLORS["text_dim"])
        font = pygame.font.SysFont("Segoe UI Bold", size)
        txt = font.render(tier, True, c)
        surface.blit(txt, (x, y))

    def draw_stars(self, surface, x, y, count, max_count=6):
        for i in range(max_count):
            c = COLORS["neon_gold"] if i < count else COLORS["border_dim"]
            pygame.draw.polygon(surface, c, self._star_points(x + i * 18, y + 8, 7))

    def _star_points(self, cx, cy, r):
        points = []
        for i in range(10):
            import math
            angle = math.radians(i * 36 - 90)
            rr = r if i % 2 == 0 else r * 0.4
            points.append((cx + rr * math.cos(angle), cy + rr * math.sin(angle)))
        return points

    def draw_tooltip(self, surface):
        self.tooltip.draw(surface)

    def draw_scrollbar(self, surface, x, y, h, scroll_pos, total, visible):
        if total <= visible:
            return
        bar_h = max(30, int(h * visible / total))
        bar_y = y + int((h - bar_h) * scroll_pos / max(1, total - visible))
        pygame.draw.rect(surface, COLORS["border_dim"], (x, y, 6, h), border_radius=3)
        pygame.draw.rect(surface, COLORS["neon_blue"], (x, bar_y, 6, bar_h), border_radius=3)
