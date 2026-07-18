"""Hero cover illustrations for CORP HEIST press issues.

Each scene is a pure vector composition drawn straight into a PDF page via
pdfkit_phi primitives (rect, line, polyline, circle, ring, star, regular_poly,
text) plus the phi_charts helpers (gloss, foil, phi_spiral, crown, panel,
alpha). No raster images, no external assets, zero runtime deps -- every
illustration is math + golden-section geometry, so it stays razor-sharp in
print at any size.

A scene builder returns a draw callable ``_d(c, x, y, w, h)`` suitable for
``Magazine.cover(..., hero_draw=...)``. Everything is deterministic: given the
same seed the same picture is produced, so PDFs rebuild bit-stable.
"""

import math

import phi_charts as G
from phi_charts import (INK, PANEL, PANEL2, GOLD, GOLD_LT, AMBER, GREEN, RED,
                        CYAN, PURPLE, GREY, GREY_DK, WHITE, PARCH)

PHI = 1.618033988749
INV_PHI = 0.6180339887498949
TAU = math.pi * 2


# --- tiny deterministic PRNG (no import random; reproducible builds) -------
def _rng(seed):
    s = (seed * 2654435761 + 1013904223) & 0xFFFFFFFF

    def nxt():
        nonlocal s
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        return s / 0x7FFFFFFF
    return nxt


def _frame(c, x, y, w, h, top=INK, bot=PANEL, border=GOLD):
    """Deep-space panel with vertical gradient + golden border + sheen."""
    c.vgrad(x, y, w, h, top, bot, bands=48)
    c.rect(x, y, w, h, stroke=border, lw=1.2)
    G.gloss(c, x, y, w, h, tint=WHITE, strength=0.10)


def _star_field(c, x, y, w, h, seed, n=48, col=WHITE):
    r = _rng(seed)
    G._alpha(c, 0.5)
    for _ in range(n):
        sx = x + r() * w
        sy = y + r() * h
        rad = 0.3 + r() * 0.9
        c.circle(sx, sy, rad, fill=col)
    G._alpha_reset(c)


def _caption(c, x, y, w, kicker, title, sub=None, col=GOLD):
    c.text(x + 10, y + 10, kicker, size=8, font="UB", rgb=col, char_space=2)
    c.text(x + 10, y + 24, title, size=15, font="UB", rgb=GOLD_LT)
    if sub:
        c.text(x + 10, y + 40, sub, size=8, font="U", rgb=GREY)


# ==========================================================================
# 1. PHI MARKET GALAXY -- a golden logarithmic spiral of orbiting tickers
# ==========================================================================
def scene_market_galaxy(seed=1, tickers=None):
    tickers = tickers or ["ALPHA", "BETA", "GAMMA", "DELTA", "OMEGA"]

    def _d(c, x, y, w, h):
        _frame(c, x, y, w, h)
        _star_field(c, x, y, w, h, seed, n=60)
        cx, cy = x + w * 0.5, y + h * 0.5
        maxr = min(w, h) * 0.42
        # nested golden spirals
        G.phi_spiral(c, cx, cy, turns=3.4, scale=maxr / 26.0,
                     col=GOLD, lw=1.0, alpha=0.55)
        G.phi_spiral(c, cx, cy, turns=3.0, scale=maxr / 30.0,
                     col=AMBER, lw=0.6, alpha=0.35)
        # orbital rings at phi radii + planets (tickers)
        r = _rng(seed)
        rad = maxr
        for i, tk in enumerate(tickers):
            G._alpha(c, 0.30)
            c.ring(cx, cy, rad, GOLD_LT, lw=0.5)
            G._alpha_reset(c)
            ang = r() * TAU
            px = cx + math.cos(ang) * rad
            py = cy + math.sin(ang) * rad
            pr = 4.5 + (len(tickers) - i) * 0.8
            c.circle(px, py, pr + 1.5, fill=AMBER)
            c.circle(px, py, pr, fill=GOLD_LT)
            c.text_center(px, py - pr - 8, tk, size=6.5, font="CB", rgb=WHITE)
            rad *= INV_PHI
        # golden core
        c.circle(cx, cy, 7, fill=WHITE)
        c.circle(cx, cy, 4, fill=GOLD)
        _caption(c, x, y, w, "PHI-RYNOK",
                 "GALAKTIKA TIKEROV", "1.618 pravit vsem", col=GOLD)
    return _d


# ==========================================================================
# 2. SECTOR PRISM -- light split into four sector spectra
# ==========================================================================
def scene_sector_prism(seed=2, sectors=None):
    sectors = sectors or [("TECH", CYAN), ("FINANCE", GOLD),
                          ("ENERGY", RED), ("LUXURY", PURPLE)]

    def _d(c, x, y, w, h):
        _frame(c, x, y, w, h)
        apex_x, apex_y = x + w * 0.22, y + h * 0.5
        # incoming white beam
        G._alpha(c, 0.7)
        c.line(x + 4, apex_y, apex_x, apex_y, rgb=WHITE, lw=2.0)
        G._alpha_reset(c)
        # the prism (triangle)
        tri = [(apex_x, apex_y + 34), (apex_x, apex_y - 34),
               (apex_x + 46, apex_y)]
        c.polyline(tri, rgb=GOLD_LT, lw=1.2, close=True, fill=PANEL2)
        G.gloss(c, apex_x, apex_y - 34, 46, 68, tint=WHITE, strength=0.18)
        # dispersed beams -> labelled sector bars
        sx = apex_x + 46
        n = len(sectors)
        spread = h * 0.66
        for i, (name, col) in enumerate(sectors):
            ty = apex_y + spread * (0.5 - (i + 0.5) / n)
            ex = x + w - 12
            G._alpha(c, 0.85)
            c.line(sx, apex_y, ex - 78, ty, rgb=col, lw=1.6)
            G._alpha_reset(c)
            c.rect(ex - 78, ty - 6, 66, 12, fill=col)
            c.text(ex - 74, ty - 4, name, size=7.5, font="UB", rgb=INK)
        _caption(c, x, y, w, "SEKTORA",
                 "SPEKTR RYNKA", "chetyre grani kapitala", col=GOLD)
    return _d


# ==========================================================================
# 3. SHORT STORM -- a crashing candle waterfall + squeeze bolt
# ==========================================================================
def scene_short_storm(seed=3):
    def _d(c, x, y, w, h):
        _frame(c, x, y, w, h, top=(26, 10, 12), bot=(12, 6, 10),
               border=RED)
        r = _rng(seed)
        n = 16
        bw = (w - 40) / n
        base = y + h * 0.82
        val = base
        for i in range(n):
            drop = (0.35 + r() * 0.9) * (h * 0.045)
            nv = max(y + h * 0.22, val - drop)
            bx = x + 20 + i * bw + bw * 0.5
            col = RED if nv < val else GREEN
            c.line(bx, val, bx, nv, rgb=col, lw=1.0)
            top = min(val, nv)
            c.rect(bx - bw * 0.28, top, bw * 0.56,
                   max(1.2, abs(val - nv)), fill=col)
            val = nv
        # squeeze lightning bolt through the crash
        bolt = [(x + w * 0.30, y + h * 0.90),
                (x + w * 0.46, y + h * 0.56),
                (x + w * 0.38, y + h * 0.54),
                (x + w * 0.58, y + h * 0.18)]
        G._alpha(c, 0.9)
        c.polyline(bolt, rgb=GOLD_LT, lw=2.4)
        G._alpha_reset(c)
        c.text_center(x + w * 0.5, y + h * 0.5, "SKVIZ", size=13,
                      font="UB", rgb=GOLD)
        _caption(c, x, y, w, "SHORTY",
                 "SHTORM MEDVEDEY", "vhod x PHI obnulyaet marzhu", col=RED)
    return _d


# ==========================================================================
# 4. CENTRAL BANK TEMPLE -- columns + a rate pendulum swinging 1/PHI..PHI
# ==========================================================================
def scene_cb_temple(seed=4):
    def _d(c, x, y, w, h):
        _frame(c, x, y, w, h)
        cx = x + w * 0.5
        base_y = y + h * 0.20
        roof_y = y + h * 0.66
        span = w * 0.62
        # pediment
        ped = [(cx - span * 0.5 - 10, roof_y),
               (cx + span * 0.5 + 10, roof_y),
               (cx, roof_y + h * 0.20)]
        c.polyline(ped, rgb=GOLD_LT, lw=1.4, close=True, fill=PANEL2)
        c.rect(cx - span * 0.5 - 14, roof_y - 8, span + 28, 8, fill=AMBER)
        # columns
        ncol = 5
        for i in range(ncol):
            colx = cx - span * 0.5 + span * i / (ncol - 1)
            c.rect(colx - 5, base_y, 10, roof_y - 8 - base_y, fill=PANEL2,
                   stroke=GOLD, lw=0.6)
            for f in range(4):
                fx = colx - 3 + f * 2
                G._alpha(c, 0.4)
                c.line(fx, base_y + 4, fx, roof_y - 12, rgb=GOLD, lw=0.4)
                G._alpha_reset(c)
        c.rect(cx - span * 0.5 - 14, base_y - 8, span + 28, 8, fill=AMBER)
        # rate pendulum
        piv_x, piv_y = cx, roof_y + h * 0.16
        ang = math.radians(28)  # sits toward PHI side
        ln = h * 0.30
        ex = piv_x + math.sin(ang) * ln
        ey = piv_y - math.cos(ang) * ln
        G._alpha(c, 0.35)
        c.polyline([(piv_x - math.sin(ang) * ln, piv_y - math.cos(ang) * ln),
                    (piv_x, piv_y), (ex, ey)], rgb=GREY, lw=0.6)
        G._alpha_reset(c)
        c.line(piv_x, piv_y, ex, ey, rgb=GOLD_LT, lw=1.4)
        c.circle(ex, ey, 6, fill=GOLD)
        c.circle(piv_x, piv_y, 2.5, fill=WHITE)
        c.text_center(piv_x - math.sin(ang) * ln, ey + 4, "1/PHI",
                      size=6.5, font="CB", rgb=GREY)
        c.text_center(ex, ey - 12, "PHI", size=6.5, font="CB", rgb=GOLD_LT)
        _caption(c, x, y, w, "CENTROBANK",
                 "HRAM STAVKI", "mayatnik 1/PHI .. PHI", col=GOLD)
    return _d


# ==========================================================================
# 5. MAGNATE HALL -- a colonnade of golden silhouettes on pedestals
# ==========================================================================
def scene_magnate_hall(seed=5, names=None):
    names = names or ["I", "II", "III", "IV", "V"]

    def _d(c, x, y, w, h):
        _frame(c, x, y, w, h)
        n = len(names)
        slot = (w - 24) / n
        floor = y + h * 0.16
        for i, nm in enumerate(names):
            bx = x + 12 + slot * i + slot * 0.5
            ph = h * (0.28 + 0.16 * INV_PHI ** (i))  # golden step-down
            # pedestal
            c.rect(bx - slot * 0.32, floor, slot * 0.64, 10,
                   fill=PANEL2, stroke=GOLD, lw=0.6)
            # bust silhouette (head + shoulders)
            hy = floor + 10 + ph
            c.circle(bx, hy, slot * 0.14, fill=GOLD_LT if i == 0 else AMBER)
            sh = [(bx - slot * 0.26, floor + 10),
                  (bx - slot * 0.16, hy - slot * 0.05),
                  (bx + slot * 0.16, hy - slot * 0.05),
                  (bx + slot * 0.26, floor + 10)]
            c.polyline(sh, rgb=GOLD if i == 0 else GREY_DK, lw=0.8,
                       close=True, fill=PANEL2)
            if i == 0:
                G.crown(c, bx, hy + slot * 0.16, slot * 0.10)
            c.text_center(bx, floor - 8, nm, size=7, font="CB",
                          rgb=WHITE if i == 0 else GREY)
        _caption(c, x, y, w, "MAGNATY",
                 "ZAL SLAVY", "pyat velichaishih kapitalov", col=GOLD)
    return _d


# ==========================================================================
# 6. CROWN THRONE -- laurel + radiant crown of the magnate of the year
# ==========================================================================
def scene_crown_throne(seed=6, name="", worth=0):
    def _d(c, x, y, w, h):
        _frame(c, x, y, w, h)
        cx, cy = x + w * 0.5, y + h * 0.56
        # radiant burst behind crown
        G._alpha(c, 0.5)
        for k in range(24):
            a = TAU * k / 24
            rr = min(w, h) * (0.30 + 0.14 * (k % 2))
            c.line(cx, cy, cx + math.cos(a) * rr, cy + math.sin(a) * rr,
                   rgb=GOLD if k % 2 else AMBER, lw=0.6)
        G._alpha_reset(c)
        # laurel wreath (two arcs of leaves)
        for side in (-1, 1):
            for k in range(7):
                t = k / 6.0
                a = math.radians(210 + side * (40 + t * 70))
                lr = min(w, h) * 0.30
                lx = cx + math.cos(a) * lr
                ly = cy + math.sin(a) * lr - 6
                c.circle(lx, ly, 3.4 - t * 1.2, fill=GREEN)
        G.crown(c, cx, cy, min(w, h) * 0.15)
        c.text_center(cx, y + h * 0.30, "MAGNAT GODA", size=11, font="UB",
                      rgb=GOLD, char_space=3)
        if name:
            c.text_center(cx, y + h * 0.20, name, size=15, font="UB",
                          rgb=GOLD_LT)
        if worth:
            c.text_center(cx, y + h * 0.11,
                          "kapital: %s zolota" % G.fmt_money(worth),
                          size=9, font="CB", rgb=WHITE)
        _caption(c, x, y, w, "MAGNAT GODA", "KORONA", col=GOLD)
    return _d


# ==========================================================================
# 7. DERIVATIVES WEB -- a lattice of nodes/options wired to a spot core
# ==========================================================================
def scene_derivatives_web(seed=7):
    def _d(c, x, y, w, h):
        _frame(c, x, y, w, h)
        r = _rng(seed)
        cx, cy = x + w * 0.5, y + h * 0.5
        nodes = []
        rings = (min(w, h) * 0.20, min(w, h) * 0.34, min(w, h) * 0.46)
        counts = (5, 8, 11)
        for ri, (rad, cnt) in enumerate(zip(rings, counts)):
            for k in range(cnt):
                a = TAU * k / cnt + r() * 0.3
                nodes.append((cx + math.cos(a) * rad,
                              cy + math.sin(a) * rad, ri))
        # edges to core + between neighbours
        G._alpha(c, 0.28)
        for nx, ny, ri in nodes:
            col = (CYAN, GOLD, PURPLE)[ri]
            c.line(cx, cy, nx, ny, rgb=col, lw=0.4)
        G._alpha_reset(c)
        for nx, ny, ri in nodes:
            col = (CYAN, GOLD_LT, PURPLE)[ri]
            c.circle(nx, ny, 2.4, fill=col)
        # spot core
        c.circle(cx, cy, 8, fill=GOLD)
        c.circle(cx, cy, 4, fill=WHITE)
        c.text_center(cx, cy - 18, "SPOT", size=6.5, font="CB", rgb=WHITE)
        _caption(c, x, y, w, "DERIVATIVY",
                 "SET KONTRAKTOV", "call / put / future", col=CYAN)
    return _d


# ==========================================================================
# 8. BOT SWARM -- a neural mesh of trading bots
# ==========================================================================
def scene_bot_swarm(seed=8):
    def _d(c, x, y, w, h):
        _frame(c, x, y, w, h, top=(8, 14, 12), bot=PANEL, border=GREEN)
        r = _rng(seed)
        cols = 6
        rows = 3
        pts = []
        for j in range(rows):
            for i in range(cols):
                px = x + 24 + (w - 48) * i / (cols - 1)
                py = y + h * 0.28 + (h * 0.44) * j / (rows - 1)
                px += (r() - 0.5) * 10
                py += (r() - 0.5) * 8
                pts.append((px, py))
        # mesh edges between adjacent columns
        G._alpha(c, 0.22)
        for j in range(rows):
            for i in range(cols):
                a = pts[j * cols + i]
                if i + 1 < cols:
                    b = pts[j * cols + i + 1]
                    c.line(a[0], a[1], b[0], b[1], rgb=GREEN, lw=0.4)
                if j + 1 < rows:
                    b = pts[(j + 1) * cols + i]
                    c.line(a[0], a[1], b[0], b[1], rgb=GREEN, lw=0.4)
        G._alpha_reset(c)
        # bot nodes (hex chips)
        for k, (px, py) in enumerate(pts):
            on = r() > 0.4
            c.regular_poly(px, py, 5.5, 6, rot=math.pi / 6,
                           fill=GREEN if on else PANEL2, stroke=GREEN, lw=0.6)
            c.circle(px, py, 1.6, fill=INK if on else GREEN)
        _caption(c, x, y, w, "BOTY",
                 "ROY ALGORITMOV", "kak rabotaet armiya botov", col=GREEN)
    return _d


# ==========================================================================
# 9. GUILD TOWERS -- a skyline of golden-ratio skyscrapers
# ==========================================================================
def scene_guild_towers(seed=9):
    def _d(c, x, y, w, h):
        _frame(c, x, y, w, h)
        _star_field(c, x, y + h * 0.4, w, h * 0.6, seed, n=36)
        r = _rng(seed)
        base = y + h * 0.14
        n = 7
        tw = (w - 20) / n
        for i in range(n):
            bx = x + 10 + i * tw
            th = h * (0.30 + 0.55 * abs(math.sin(i * PHI)))
            th = min(th, h * 0.80)
            c.rect(bx + 2, base, tw - 4, th, fill=PANEL2, stroke=GOLD, lw=0.6)
            G.gloss(c, bx + 2, base, tw - 4, th, tint=GOLD, strength=0.10)
            # windows grid
            G._alpha(c, 0.7)
            rows = int(th / 9)
            for rr in range(rows):
                for cc in range(2):
                    if r() > 0.45:
                        wx = bx + 6 + cc * (tw - 12) * 0.6
                        wy = base + 5 + rr * 9
                        c.rect(wx, wy, 2.4, 3.2, fill=GOLD_LT)
            G._alpha_reset(c)
            # antenna beacon on tallest
            if th > h * 0.6:
                c.line(bx + tw * 0.5, base + th, bx + tw * 0.5,
                       base + th + 8, rgb=GOLD, lw=0.8)
                c.circle(bx + tw * 0.5, base + th + 9, 2, fill=RED)
        c.rect(x, base - 4, w, 4, fill=AMBER)
        _caption(c, x, y, w, "GILDII",
                 "BASHNI KORPORACIY", "kto vladeet gorizontom", col=GOLD)
    return _d


# ==========================================================================
# 10. MARKET MAKER -- an order book ladder + golden balance scale
# ==========================================================================
def scene_market_maker(seed=10):
    def _d(c, x, y, w, h):
        _frame(c, x, y, w, h)
        r = _rng(seed)
        # order book ladder on the left
        lx = x + 16
        lw = w * 0.34
        mid = y + h * 0.5
        rows = 6
        rh = (h * 0.62) / (rows * 2)
        for k in range(rows):
            # asks (red, above)
            aw = lw * (0.4 + r() * 0.6)
            ay = mid + rh * (k + 1)
            c.rect(lx, ay, aw, rh - 1, fill=RED)
            # bids (green, below)
            bw = lw * (0.4 + r() * 0.6)
            by = mid - rh * (k + 1)
            c.rect(lx, by, bw, rh - 1, fill=GREEN)
        c.line(lx, mid, lx + lw, mid, rgb=GOLD_LT, lw=1.0)
        c.text(lx, mid + 2, "SPRED", size=6.5, font="CB", rgb=GOLD)
        # balance scale on the right
        sx = x + w * 0.72
        sy = y + h * 0.66
        c.line(sx, y + h * 0.14, sx, sy, rgb=GOLD, lw=1.4)  # post
        beam = w * 0.20
        c.line(sx - beam * 0.5, sy, sx + beam * 0.5, sy, rgb=GOLD_LT, lw=1.6)
        for side, col, lab in ((-1, GREEN, "BID"), (1, RED, "ASK")):
            px = sx + side * beam * 0.5
            for ch in (-6, 6):
                c.line(px, sy, px + ch, sy - 16, rgb=GREY, lw=0.5)
            c.polyline([(px - 9, sy - 16), (px + 9, sy - 16),
                        (px + 5, sy - 24), (px - 5, sy - 24)],
                       rgb=col, lw=0.8, close=True, fill=PANEL2)
            c.text_center(px, sy - 21, lab, size=6, font="CB", rgb=col)
        c.circle(sx, y + h * 0.14, 3, fill=GOLD_LT)
        _caption(c, x, y, w, "MARKET-MEIKING",
                 "STAKAN I VESY", "zolotoy spred", col=GOLD)
    return _d
