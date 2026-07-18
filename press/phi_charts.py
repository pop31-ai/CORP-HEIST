"""
phi_charts - reusable golden-section infographics drawn on a Canvas.

Every chart is pure vector math. Palette is the CORP HEIST corporate-gold set.
Charts take a Canvas plus a bounding box (x, y, w, h) with y at the BOX BOTTOM
(PDF convention).
"""

import math
from pdfkit_phi import PHI, INV_PHI, TAU, clamp, lerp, text_width

# --- CORP HEIST palette ------------------------------------------------
INK      = (10, 11, 22)       # deep space background
PANEL    = (16, 18, 34)       # panel fill
PANEL2   = (22, 24, 44)
GOLD     = (255, 200, 0)      # signature gold
GOLD_LT  = (255, 226, 75)
AMBER    = (255, 176, 32)
GREEN    = (0, 255, 140)
RED      = (255, 59, 59)
CYAN     = (0, 229, 255)
PURPLE   = (177, 75, 255)
GREY     = (150, 150, 168)
GREY_DK  = (60, 62, 84)
WHITE    = (230, 232, 240)
PARCH    = (222, 220, 210)


def fmt_money(v):
    v = float(v)
    if abs(v) >= 1e9:
        return "%.2fB" % (v / 1e9)
    if abs(v) >= 1e6:
        return "%.2fM" % (v / 1e6)
    if abs(v) >= 1e3:
        return "%.1fK" % (v / 1e3)
    return "%.0f" % v


def panel(c, x, y, w, h, fill=PANEL, border=GOLD, lw=1.0, radius_hint=True):
    """A framed panel with a subtle top-inset golden rule."""
    c.rect(x, y, w, h, fill=fill)
    c.rect(x, y, w, h, stroke=border, lw=lw)
    # golden inset rule near the top
    c.line(x + 6, y + h - 6, x + w - 6, y + h - 6, rgb=border, lw=0.4)


def section_title(c, x, y, s, size=13, rgb=GOLD, accent=AMBER):
    """A titled bar: gold square + spaced caps."""
    c.rect(x, y, size * 0.7, size * 0.7, fill=accent)
    c.text(x + size * 1.15, y, s, size=size, font="UB", rgb=rgb, char_space=1.5)
    w = text_width(s, size, "HB", 1.5)
    c.line(x + size * 1.15, y - 4, x + size * 1.15 + w, y - 4, rgb=accent, lw=0.6)


# --- candlestick chart -------------------------------------------------
def candlestick(c, x, y, w, h, data, title=None):
    if not data:
        return
    panel(c, x, y, w, h, fill=(12, 13, 26), border=GREY_DK, lw=0.8)
    pad = 10
    ix, iy, iw, ih = x + pad, y + pad, w - pad * 2, h - pad * 2 - (14 if title else 0)
    if title:
        section_title(c, x + pad, y + h - 16, title, size=11)
    highs = [d["h"] for d in data]
    lows = [d["l"] for d in data]
    hi, lo = max(highs), min(lows)
    if hi <= lo:
        hi = lo + 1
    rng = hi - lo

    def py(v):
        return iy + (v - lo) / rng * ih

    # golden horizontal guides at phi fractions
    for frac in (INV_PHI, 1 - INV_PHI):
        gy = iy + ih * frac
        c.set_alpha_gs(_DOC[0], 0.25) if _DOC[0] else None
        c.line(ix, gy, ix + iw, gy, rgb=GOLD, lw=0.3)
        if _DOC[0]:
            c.set_alpha_gs(_DOC[0], 1.0)
    n = len(data)
    slot = iw / n
    body_w = slot * INV_PHI
    for i, d in enumerate(data):
        cx = ix + slot * i + slot / 2
        up = d["c"] >= d["o"]
        col = GREEN if up else RED
        # wick
        c.line(cx, py(d["l"]), cx, py(d["h"]), rgb=col, lw=0.6)
        # body
        yb = py(min(d["o"], d["c"]))
        bh = max(0.8, abs(py(d["c"]) - py(d["o"])))
        c.rect(cx - body_w / 2, yb, body_w, bh, fill=col)
    # last price tag
    last = data[-1]["c"]
    c.text_right(ix + iw, iy + ih + 2, fmt_money(last),
                 size=9, font="CB", rgb=GOLD_LT)


# --- sparkline ---------------------------------------------------------
def sparkline(c, x, y, w, h, series, col=GOLD, fill=True):
    if len(series) < 2:
        return
    lo, hi = min(series), max(series)
    if hi <= lo:
        hi = lo + 1
    pts = []
    for i, v in enumerate(series):
        px = x + i / (len(series) - 1) * w
        pyv = y + (v - lo) / (hi - lo) * h
        pts.append((px, pyv))
    if fill:
        poly = [(x, y)] + pts + [(x + w, y)]
        if _DOC[0]:
            c.set_alpha_gs(_DOC[0], 0.18)
        c.polyline(poly, rgb=col, lw=0.1, close=True, fill=col)
        if _DOC[0]:
            c.set_alpha_gs(_DOC[0], 1.0)
    c.polyline(pts, rgb=col, lw=1.1)
    # endpoint dot
    c.circle(pts[-1][0], pts[-1][1], 1.6, fill=col)


# --- golden donut (sector weights) -------------------------------------
def golden_donut(c, cx, cy, r, weights, labels, cols, title=None):
    total = sum(weights) or 1
    a0 = math.pi / 2
    inner = r * INV_PHI
    steps_full = 96
    for wgt, col in zip(weights, cols):
        frac = wgt / total
        a1 = a0 - frac * TAU
        steps = max(2, int(steps_full * frac))
        pts = []
        for s in range(steps + 1):
            a = lerp(a0, a1, s / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        for s in range(steps, -1, -1):
            a = lerp(a0, a1, s / steps)
            pts.append((cx + inner * math.cos(a), cy + inner * math.sin(a)))
        c.polyline(pts, rgb=INK, lw=0.4, close=True, fill=col)
        a0 = a1
    c.circle(cx, cy, inner, stroke=GREY_DK, lw=0.6)
    c.circle(cx, cy, r, stroke=GREY_DK, lw=0.6)
    if title:
        c.text_center(cx, cy + 4, title, size=9, font="UB", rgb=GOLD)
        c.text_center(cx, cy - 8, "PHI", size=7, font="U", rgb=GREY)


# --- horizontal phi bars (ladders / rankings) --------------------------
def hbars(c, x, y, w, h, rows, maxv=None, col=GOLD, label_key="name",
          val_key="worth", fmt=fmt_money):
    n = len(rows)
    if n == 0:
        return
    maxv = maxv or max(r[val_key] for r in rows) or 1
    gap = h / n
    bar_h = gap * INV_PHI
    for i, row in enumerate(rows):
        by = y + h - gap * (i + 1) + (gap - bar_h) / 2
        frac = clamp(row[val_key] / maxv, 0.02, 1.0)
        bw = w * frac
        # gradient-ish: two-tone by phi split
        c.rect(x, by, bw, bar_h, fill=col)
        c.rect(x, by, bw * INV_PHI, bar_h, fill=GOLD_LT)
        c.text(x + 4, by + bar_h * 0.28, str(row.get(label_key, "")),
               size=8, font="UB", rgb=INK)
        c.text_right(x + w - 2, by + bar_h * 0.28, fmt(row[val_key]),
                     size=8, font="CB", rgb=WHITE)


# --- phi spiral (decorative + logarithmic growth motif) ----------------
def phi_spiral(c, cx, cy, turns=3.2, scale=2.0, col=GOLD, lw=0.8, alpha=0.6):
    if _DOC[0]:
        c.set_alpha_gs(_DOC[0], alpha)
    pts = []
    steps = int(turns * 60)
    b = math.log(PHI) / (math.pi / 2)  # logarithmic spiral growth
    for i in range(steps + 1):
        th = i / 60.0 * TAU / (TAU / (math.pi / 2)) * (math.pi / 2)
        th = i * (TAU * turns / steps)
        rr = scale * math.exp(b * th)
        pts.append((cx + rr * math.cos(th), cy + rr * math.sin(th)))
    c.polyline(pts, rgb=col, lw=lw)
    if _DOC[0]:
        c.set_alpha_gs(_DOC[0], 1.0)


# --- golden rectangle subdivision (motif for covers) -------------------
def golden_rects(c, x, y, w, h, depth=7, col=GOLD, alpha=0.4):
    if _DOC[0]:
        c.set_alpha_gs(_DOC[0], alpha)
    cx, cy, cw, ch = x, y, w, h
    horiz = True
    for _ in range(depth):
        c.rect(cx, cy, cw, ch, stroke=col, lw=0.5)
        if horiz:
            cut = cw * INV_PHI
            cx = cx + cut
            cw = cw - cut
        else:
            cut = ch * INV_PHI
            cy = cy + ch - cut
            ch = cut
        horiz = not horiz
    if _DOC[0]:
        c.set_alpha_gs(_DOC[0], 1.0)


# --- crown badge (magnate of the year) ---------------------------------
def crown(c, cx, cy, r, col=GOLD, gem=RED):
    base_y = cy - r * 0.5
    pts = [
        (cx - r, base_y),
        (cx - r, cy + r * 0.2),
        (cx - r * 0.5, cy - r * 0.1),
        (cx, cy + r * 0.6),
        (cx + r * 0.5, cy - r * 0.1),
        (cx + r, cy + r * 0.2),
        (cx + r, base_y),
    ]
    c.polyline(pts, rgb=AMBER, lw=1.0, close=True, fill=col)
    c.rect(cx - r, base_y - r * 0.28, r * 2, r * 0.28, fill=AMBER)
    for gx in (-r * 0.5, 0, r * 0.5):
        c.circle(cx + gx, cy + r * 0.05, r * 0.12, fill=gem)


# --- big stat block ----------------------------------------------------
def stat(c, x, y, w, big, label, col=GOLD, sub=None):
    c.text(x, y + 12, big, size=26, font="UB", rgb=col)
    c.text(x, y, label, size=8, font="U", rgb=GREY, char_space=1.2)
    if sub:
        c.text_right(x + w, y + 16, sub, size=9, font="CB", rgb=GREEN
                     if not sub.startswith("-") else RED)


# --- ticker tape strip -------------------------------------------------
def tape(c, x, y, w, rows, h=16, col=GOLD):
    c.rect(x, y, w, h, fill=(6, 6, 12))
    c.rect(x, y, w, h, stroke=GREY_DK, lw=0.5)
    cx = x + 8
    for row in rows:
        up = row["chg"] >= 0
        arrow = "+" if up else ""
        s = "%s %.2f %s%.1f%%" % (row["sym"], row["price"], arrow, row["chg"])
        c.text(cx, y + h * 0.3, s, size=8, font="CB",
               rgb=GREEN if up else RED)
        cx += text_width(s, 8, "CB") + 18
        if cx > x + w - 40:
            break


# --- area chart (filled line, big) -------------------------------------
def area_chart(c, x, y, w, h, series, col=GOLD, title=None):
    panel(c, x, y, w, h, fill=(12, 13, 26), border=GREY_DK, lw=0.8)
    pad = 10
    if title:
        section_title(c, x + pad, y + h - 16, title, size=10)
    ih = h - pad * 2 - (14 if title else 0)
    iw = w - pad * 2
    ix, iy = x + pad, y + pad
    if len(series) < 2:
        return
    lo, hi = min(series), max(series)
    if hi <= lo:
        hi = lo + 1
    # golden guide lines
    for f in (INV_PHI, 1 - INV_PHI):
        gy = iy + ih * f
        if _DOC[0]:
            c.set_alpha_gs(_DOC[0], 0.2)
        c.line(ix, gy, ix + iw, gy, rgb=GOLD, lw=0.3)
        if _DOC[0]:
            c.set_alpha_gs(_DOC[0], 1.0)
    pts = []
    for i, v in enumerate(series):
        px = ix + i / (len(series) - 1) * iw
        pyv = iy + (v - lo) / (hi - lo) * ih
        pts.append((px, pyv))
    poly = [(ix, iy)] + pts + [(ix + iw, iy)]
    if _DOC[0]:
        c.set_alpha_gs(_DOC[0], 0.22)
    c.polyline(poly, rgb=col, lw=0.1, close=True, fill=col)
    if _DOC[0]:
        c.set_alpha_gs(_DOC[0], 1.0)
    c.polyline(pts, rgb=col, lw=1.4)
    c.circle(pts[-1][0], pts[-1][1], 2.2, fill=col)
    c.text_right(ix + iw, iy + ih + 2, "%.2f" % series[-1], size=9,
                 font="CB", rgb=GOLD_LT)


# --- gauge / dial (phi position in a range) ----------------------------
def gauge(c, cx, cy, r, frac, label, col=GOLD):
    frac = clamp(frac, 0.0, 1.0)
    a0 = math.pi * 1.15
    a1 = math.pi * (-0.15)
    # track
    steps = 40
    trk = [(cx + r * math.cos(lerp(a0, a1, i / steps)),
            cy + r * math.sin(lerp(a0, a1, i / steps))) for i in range(steps + 1)]
    c.polyline(trk, rgb=GREY_DK, lw=4)
    # value arc
    va = lerp(a0, a1, frac)
    val = [(cx + r * math.cos(lerp(a0, va, i / steps)),
            cy + r * math.sin(lerp(a0, va, i / steps))) for i in range(steps + 1)]
    c.polyline(val, rgb=col, lw=4)
    # needle
    c.line(cx, cy, cx + r * 0.8 * math.cos(va), cy + r * 0.8 * math.sin(va),
           rgb=GOLD_LT, lw=1.6)
    c.circle(cx, cy, 3, fill=GOLD_LT)
    c.text_center(cx, cy - r * 0.55, label, size=8, font="UB", rgb=GREY)
    c.text_center(cx, cy + r * 0.2, "%d%%" % int(frac * 100), size=15,
                  font="UB", rgb=col)


def gauge_panel(c, x, y, w, h, frac, title, label, col=GOLD):
    panel(c, x, y, w, h, fill=(12, 13, 26), border=GREY_DK, lw=0.8)
    section_title(c, x + 8, y + h - 16, title, size=10)
    gauge(c, x + w / 2, y + h * 0.42, min(w, h) * 0.28, frac, label, col)


# --- big number tiles row ----------------------------------------------
def stat_tiles(c, x, y, w, h, tiles):
    """tiles: list of (big, label, colour). Laid out on a golden grid."""
    n = len(tiles) or 1
    tw = (w - (n - 1) * 8) / n
    for i, (big, label, col) in enumerate(tiles):
        tx = x + i * (tw + 8)
        panel(c, tx, y, tw, h, fill=PANEL2, border=GREY_DK, lw=0.8)
        c.text_center(tx + tw / 2, y + h * 0.42, big, size=20, font="UB",
                      rgb=col)
        c.text_center(tx + tw / 2, y + h * 0.16, label, size=7.5, font="U",
                      rgb=GREY)


# --- comparison paired bars --------------------------------------------
def compare_bars(c, x, y, w, h, rows, title=None,
                 col_a=GREEN, col_b=RED):
    """rows: list of (label, a, b). a green (up), b red (down)."""
    panel(c, x, y, w, h, fill=(12, 13, 26), border=GREY_DK, lw=0.8)
    if title:
        section_title(c, x + 8, y + h - 16, title, size=10)
    ih = h - 30
    iy = y + 8
    n = len(rows) or 1
    gap = ih / n
    bar_h = gap * INV_PHI / 2
    maxv = max(max(abs(a), abs(b)) for _, a, b in rows) or 1
    for i, (lab, a, b) in enumerate(rows):
        by = iy + ih - gap * (i + 1) + (gap - bar_h * 2) / 2
        c.rect(x + 70, by + bar_h, (w - 90) * (abs(a) / maxv), bar_h, fill=col_a)
        c.rect(x + 70, by, (w - 90) * (abs(b) / maxv), bar_h, fill=col_b)
        c.text(x + 8, by + bar_h * 0.6, lab, size=8, font="UB", rgb=PARCH)


# module-level doc handle for alpha graphics states (set by magazine.py)
_DOC = [None]


def bind_doc(doc):
    _DOC[0] = doc
