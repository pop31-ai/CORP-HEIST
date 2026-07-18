"""
brochure.py - personal glossy "Brochure of Success" for a single player.

A 2-page prestige booklet a player can flaunt: a foil cover with name, rank,
crown and headline wealth, then a spread with a capital-growth chart, a
metric radar, a holdings table and phi achievement plaques. Pure vector,
zero runtime deps, embedded Cyrillic like the rest of PHI PRESS.

Usage:
    from brochure import build_brochure
    build_brochure(char_dict, badges=..., rank=..., out_path=...)
"""
import math
import os
import sys
import time
from magazine import MARGIN, CONTENT_W, TOP
from pdfkit_phi import Doc, PAGE_W, PAGE_H, PHI, INV_PHI, text_width
import phi_charts as G

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import market_cube as cube
except Exception:
    cube = None

CORPS = ["MERIDIAN", "APEX", "NOVA", "VERTEX", "PULSAR", "ORION", "ZENITH"]


def _fmt(v):
    return G.fmt_money(v)


def _grade(net_worth):
    """Golden grade S/A/B/C/D from net worth on a phi ladder."""
    tiers = [("S", 5_000_000), ("A", 1_500_000), ("B", 500_000),
             ("C", 150_000), ("D", 0)]
    for g, thr in tiers:
        if net_worth >= thr:
            return g
    return "D"


class Brochure:
    def __init__(self, char, badges=None, rank=None):
        self.c = char
        self.badges = badges or {}
        self.rank = rank
        self.uid = char.get("user_id", 0)
        self.name = char.get("name") or ("Магнат #%d" % self.uid)
        self.nw = char.get("net_worth", 0)
        self.accent = G.GOLD
        self.doc = Doc(title="CORP HEIST - Brochure %d" % self.uid,
                       author="PHI PRESS")
        G.bind_doc(self.doc)
        self._page = 0

    def _bg(self, c):
        c.fill_page(G.INK)
        G.golden_rects(c, PAGE_W - 210, PAGE_H - 210, 190, 190,
                       depth=7, col=self.accent, alpha=0.06)
        G.phi_spiral(c, MARGIN + 30, MARGIN + 40, turns=3.0, scale=1.4,
                     col=self.accent, lw=0.5, alpha=0.05)

    def _new_page(self):
        self._page += 1
        c = self.doc.page()
        self._bg(c)
        return c

    def _footer(self, c):
        y = MARGIN * 0.55
        c.line(MARGIN, y + 10, PAGE_W - MARGIN, y + 10, rgb=G.GREY_DK, lw=0.5)
        c.text(MARGIN, y, "CORP HEIST  /  БРОШЮРА УСПЕХА", size=7,
               font="UB", rgb=G.GREY, char_space=1.0)
        c.text_center(PAGE_W / 2, y, "личный экземпляр", size=7,
                      font="U", rgb=G.GREY, char_space=2.0)
        c.text_right(PAGE_W - MARGIN, y, "str. %d" % self._page,
                     size=7, font="CB", rgb=self.accent)

    # ---------------- cover -------------------------------------------
    def cover(self):
        c = self._new_page()
        corp = CORPS[self.c.get("corp_id", 0) % len(CORPS)]
        # foil masthead banner
        band_h = 96
        G.foil(c, 0, PAGE_H - band_h, PAGE_W, band_h, base=self.accent)
        c.text(MARGIN, PAGE_H - 46, "CORP HEIST", size=30, font="UB",
               rgb=G.INK, char_space=3)
        c.text(MARGIN, PAGE_H - 66, "БРОШЮРА УСПЕХА · %s" % corp, size=9,
               font="UB", rgb=(40, 30, 6), char_space=2)
        c.text_right(PAGE_W - MARGIN, PAGE_H - 46, "ID %d" % self.uid,
                     size=12, font="CB", rgb=G.INK)

        # crown + name
        cy = PAGE_H - band_h - 70
        G.crown(c, PAGE_W / 2, cy + 26, 26, col=G.GOLD_LT, gem=G.RED)
        c.text_center(PAGE_W / 2, cy - 18, self.name, size=26, font="UB",
                      rgb=G.GOLD_LT, char_space=1)
        grade = _grade(self.nw)
        c.text_center(PAGE_W / 2, cy - 40,
                      "КЛАСС %s · ПРЕСТИЖ %d" % (grade, self.c.get("prestige", 0)),
                      size=10, font="UB", rgb=G.WHITE, char_space=2)

        # hero wealth plaque (glossy)
        py = cy - 150
        pw, ph = CONTENT_W, 92
        c.rect(MARGIN, py, pw, ph, fill=(22, 18, 8))
        c.rect(MARGIN, py, pw, ph, stroke=self.accent, lw=1.0)
        G.gloss(c, MARGIN, py, pw, ph, tint=self.accent, strength=0.14)
        G.emboss_frame(c, MARGIN, py, pw, ph, col=self.accent)
        c.text_center(PAGE_W / 2, py + ph - 24, "ЧИСТЫЙ КАПИТАЛ", size=9,
                      font="UB", rgb=G.GREY, char_space=3)
        c.text_center(PAGE_W / 2, py + 24, _fmt(self.nw), size=34, font="CB",
                      rgb=G.GOLD_LT)

        # three stat tiles
        tiles = [
            ("УР. %d" % self.c.get("level", 1), "УРОВЕНЬ", G.CYAN),
            ("TOP %d%%" % self.c.get("rank_percent", 99), "РАНГ", G.GOLD),
            ("%d дн" % self.c.get("streak_days", 0), "СТРИК", G.GREEN),
        ]
        G.stat_tiles(c, MARGIN, py - 86, CONTENT_W, 72, tiles)

        # capital growth sparkline hero
        hist = self.c.get("history") or []
        if len(hist) > 3:
            G.area_chart(c, MARGIN, MARGIN + 30, CONTENT_W,
                         (py - 86 - MARGIN - 40), hist[-60:],
                         col=self.accent, title="РОСТ КАПИТАЛА")
        self._footer(c)
        return c

    # ---------------- spread ------------------------------------------
    def spread(self):
        c = self._new_page()
        c.rect(MARGIN, TOP - 4, 20, 4, fill=self.accent)
        c.text(MARGIN, TOP - 20, "ДОСЬЕ МАГНАТА", size=9, font="UB",
               rgb=self.accent, char_space=2)
        c.text(MARGIN, TOP - 44, self.name, size=22, font="UB", rgb=G.GOLD_LT)

        half = (CONTENT_W - 14) / 2
        top_y = TOP - 60
        block_h = 150

        # left: metric radar
        axes = ["КАПИТАЛ", "УРОВЕНЬ", "ПРЕСТИЖ", "СТРИК", "РАНГ", "ЛУТ"]
        mx = max(1.0, self.nw / 5_000_000.0)
        vals = [
            G.clamp(self.nw / 5_000_000.0, 0, 1),
            G.clamp(self.c.get("level", 1) / 100.0, 0, 1),
            G.clamp(self.c.get("prestige", 0) / 10.0, 0, 1),
            G.clamp(self.c.get("streak_days", 0) / 365.0, 0, 1),
            G.clamp((100 - self.c.get("rank_percent", 99)) / 100.0, 0, 1),
            G.clamp(self.c.get("loot_count", 0) / 100.0, 0, 1),
        ]
        G.radar(c, MARGIN, top_y - block_h, half, block_h, axes,
                [("ВЫ", vals, self.accent)], title="ПРОФИЛЬ")

        # right: portfolio table
        stocks = self.c.get("stocks") or []
        stocks = sorted(stocks, key=lambda s: -(s.get("price", 0) * s.get("held", 0)))[:6]
        rows = []
        for s in stocks:
            val = s.get("price", 0) * s.get("held", 0)
            d = s.get("delta", 0)
            rows.append((s.get("name", "?"), "%d" % s.get("held", 0),
                         _fmt(val), ("+%.1f" % d) if d >= 0 else ("%.1f" % d)))
        if not rows:
            rows = [("—", "0", "0", "0.0")]
        G.table(c, MARGIN + half + 14, top_y - block_h, half, block_h,
                ["АКТИВ", "ШТ", "СТОИМ", "ИЗМ%"], rows,
                title="ПОРТФЕЛЬ", aligns=["l", "r", "r", "r"],
                col_weights=[1.3, 0.7, 1, 0.9])

        # middle band: waterfall of wealth composition
        wf_y = top_y - block_h - 14 - 130
        gold = self.c.get("gold", 0)
        pv = self.c.get("portfolio_value", 0)
        loot_val = sum(l.get("value", 0) * l.get("qty", 1)
                       for l in (self.c.get("loot") or []))
        steps = [("ЗОЛОТО", gold), ("ПОРТФЕЛЬ", pv), ("ЛУТ", loot_val),
                 ("ПРОЧЕЕ", max(0, self.nw - gold - pv - loot_val))]
        G.waterfall(c, MARGIN, wf_y, CONTENT_W, 130, steps,
                    title="ИЗ ЧЕГО СЛОЖЕН КАПИТАЛ", start=0.0)

        # bottom: badges plaques (left half) + welfare candles (right half)
        by = wf_y - 14 - 96
        bw_half = (CONTENT_W - 14) / 2
        blist = self.badges.get("badges") if isinstance(self.badges, dict) else None
        c.rect(MARGIN, by, bw_half, 96, fill=(16, 18, 34))
        c.rect(MARGIN, by, bw_half, 96, stroke=G.GREY_DK, lw=0.8)
        G.section_title(c, MARGIN + 8, by + 96 - 16, "ЗНАКИ ОТЛИЧИЯ", size=10)
        earned = [b for b in (blist or []) if b.get("earned")]
        if earned:
            n = min(len(earned), 3)
            cw = (bw_half - 16) / n
            for i, b in enumerate(earned[:n]):
                bx = MARGIN + 8 + cw * i
                c.star(bx + cw / 2, by + 52, 14, 6, 5,
                       fill=G.GOLD_LT, stroke=self.accent)
                nm = b.get("name", "")[:12]
                c.text_center(bx + cw / 2, by + 24, nm, size=6.5,
                              font="U", rgb=G.PARCH)
        else:
            c.text_center(MARGIN + bw_half / 2, by + 44,
                          "Зарабатывай знаки", size=9, font="U", rgb=G.GREY)
        self._welfare_block(c, MARGIN + bw_half + 14, by, bw_half, 96)
        self._footer(c)
        return c

    # ---------------- welfare (standard of living) --------------------
    def _welfare_block(self, c, x, y, w, h):
        """Weekly welfare candles + saldo - the player's standard-of-living
        ledger, computed straight from the market cube (deterministic, no
        stored history). See docs/CUBE.md 5b."""
        if cube is None:
            c.rect(x, y, w, h, fill=(16, 18, 34))
            c.rect(x, y, w, h, stroke=G.GREY_DK, lw=0.8)
            G.section_title(c, x + 8, y + h - 16, "БЛАГОПОЛУЧИЕ", size=10)
            return
        now = int(time.time())
        quotes = cube.welfare_quotes(self.uid, now, 8)
        ex = cube.welfare_explain(self.uid, now)
        # candlestick fills the panel; title drawn by candlestick()
        G.candlestick(c, x, y, w, h, quotes, title="БЛАГОПОЛУЧИЕ · УРОВЕНЬ ЖИЗНИ")
        # saldo over the last 8 weeks
        if len(quotes) >= 2:
            saldo = quotes[-1]["c"] - quotes[0]["o"]
            col = G.GREEN if saldo >= 0 else G.RED
            sign = "+" if saldo >= 0 else "−"
            c.text(x + 10, y + 8, "сальдо 8нед: %s%s" % (sign, G.fmt_money(abs(saldo))),
                   size=7, font="CB", rgb=col)
        c.text_right(x + w - 10, y + 8, "класс жизни %d" % ex["living_tier"],
                     size=7, font="CB", rgb=G.GOLD_LT)

    def build(self):
        self.cover()
        self.spread()
        return self

    def save(self, path):
        self.build()
        self.doc.save(path)
        return path


def build_brochure(char, badges=None, rank=None, out_path=None):
    b = Brochure(char, badges=badges, rank=rank)
    if out_path:
        return b.save(out_path)
    b.build()
    return b.doc.to_bytes() if hasattr(b.doc, "to_bytes") else None
