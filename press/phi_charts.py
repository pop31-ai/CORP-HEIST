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


# --- heatmap (sector x period grid, colour by value) -------------------
def _heat_colour(t):
    """t in [0,1] -> red(cold) .. amber .. green(hot)."""
    t = clamp(t, 0.0, 1.0)
    if t < 0.5:
        u = t / 0.5
        return (int(lerp(RED[0], AMBER[0], u)), int(lerp(RED[1], AMBER[1], u)),
                int(lerp(RED[2], AMBER[2], u)))
    u = (t - 0.5) / 0.5
    return (int(lerp(AMBER[0], GREEN[0], u)), int(lerp(AMBER[1], GREEN[1], u)),
            int(lerp(AMBER[2], GREEN[2], u)))


def heatmap(c, x, y, w, h, rows, cols, grid, title=None):
    """grid[r][c] in raw values; auto-normalised. rows/cols are labels."""
    panel(c, x, y, w, h, fill=(12, 13, 26), border=GREY_DK, lw=0.8)
    if title:
        section_title(c, x + 8, y + h - 16, title, size=10)
    pad = 8
    lab_w = 58
    top = y + h - (24 if title else pad)
    iy = y + pad + 12
    ih = top - iy
    iw = w - pad * 2 - lab_w
    nr, nc = len(rows), len(cols)
    if nr == 0 or nc == 0:
        return
    flat = [v for r in grid for v in r]
    lo, hi = min(flat), max(flat)
    if hi <= lo:
        hi = lo + 1
    cw = iw / nc
    chh = ih / nr
    for ci, cl in enumerate(cols):
        c.text_center(x + pad + lab_w + cw * (ci + 0.5), iy - 10, str(cl),
                      size=6.5, font="U", rgb=GREY)
    for ri, rl in enumerate(rows):
        ry = iy + ih - chh * (ri + 1)
        c.text(x + pad, ry + chh * 0.32, str(rl), size=7.5, font="UB", rgb=PARCH)
        for ci in range(nc):
            v = grid[ri][ci]
            col = _heat_colour((v - lo) / (hi - lo))
            cx = x + pad + lab_w + cw * ci
            c.rect(cx + 1, ry + 1, cw - 2, chh - 2, fill=col)


# --- liquidation funnel (phi-narrowing stages) -------------------------
def funnel(c, x, y, w, h, stages, title=None, col=RED):
    """stages: list of (label, value). Widths narrow by data, phi-styled."""
    panel(c, x, y, w, h, fill=(12, 13, 26), border=GREY_DK, lw=0.8)
    if title:
        section_title(c, x + 8, y + h - 16, title, size=10)
    pad = 10
    top = y + h - (26 if title else pad)
    bottom = y + pad + 10
    n = len(stages) or 1
    seg_h = (top - bottom) / n
    maxv = max(v for _, v in stages) or 1
    cx = x + w / 2
    for i, (lab, v) in enumerate(stages):
        frac = clamp(v / maxv, 0.06, 1.0)
        bw = (w - pad * 2) * frac
        sy = top - seg_h * (i + 1)
        shade = lerp(0.55, 1.0, i / max(1, n - 1))
        cc = (int(col[0] * shade), int(col[1] * shade), int(col[2] * shade))
        # trapezoid via polygon
        next_frac = frac
        if i < n - 1:
            next_frac = clamp(stages[i + 1][1] / maxv, 0.06, 1.0)
        nbw = (w - pad * 2) * next_frac
        pts = [(cx - bw / 2, sy + seg_h), (cx + bw / 2, sy + seg_h),
               (cx + nbw / 2, sy + 2), (cx - nbw / 2, sy + 2)]
        c.polyline(pts, rgb=INK, lw=0.4, close=True, fill=cc)
        c.text_center(cx, sy + seg_h * 0.35, "%s  %s" % (lab, fmt_money(v)),
                      size=7.5, font="UB", rgb=WHITE)


# --- treemap (phi slice-and-dice of capital) ---------------------------
def treemap(c, x, y, w, h, items, title=None):
    """items: list of (label, value, colour). Golden slice-and-dice layout."""
    panel(c, x, y, w, h, fill=(12, 13, 26), border=GREY_DK, lw=0.8)
    if title:
        section_title(c, x + 8, y + h - 16, title, size=10)
    pad = 8
    ix, iy = x + pad, y + pad
    iw = w - pad * 2
    ih = h - pad * 2 - (14 if title else 0)
    items = sorted(items, key=lambda t: -t[1])
    total = sum(v for _, v, _ in items) or 1
    horiz = iw >= ih
    cx, cy, cw, ch = ix, iy, iw, ih
    rem = total
    for i, (lab, v, col) in enumerate(items):
        frac = v / rem if rem else 0
        last = (i == len(items) - 1)
        if horiz:
            seg = cw if last else cw * frac
            c.rect(cx + 1, cy + 1, seg - 2, ch - 2, fill=col)
            _tm_label(c, cx, cy, seg, ch, lab, v)
            cx += seg
            cw -= seg
        else:
            seg = ch if last else ch * frac
            c.rect(cx + 1, cy + ch - seg + 1, cw - 2, seg - 2, fill=col)
            _tm_label(c, cx, cy + ch - seg, cw, seg, lab, v)
            ch -= seg
        rem -= v
        horiz = not horiz


def _tm_label(c, x, y, w, h, lab, v):
    if w < 26 or h < 14:
        return
    c.text(x + 4, y + h - 12, str(lab), size=7.5, font="UB", rgb=INK)
    if h > 26:
        c.text(x + 4, y + h - 22, fmt_money(v), size=7, font="U", rgb=INK)


# --- radar / spider (multi-axis metric web) ----------------------------
def radar(c, x, y, w, h, axes, series, title=None):
    """axes: list of labels. series: list of (name, [0..1 values], colour).

    A golden-web radar comparing several metric profiles on shared axes.
    """
    panel(c, x, y, w, h, fill=(12, 13, 26), border=GREY_DK, lw=0.8)
    if title:
        section_title(c, x + 8, y + h - 16, title, size=10)
    n = len(axes)
    if n < 3:
        return
    cx = x + w / 2
    cy = y + (h - (16 if title else 0)) / 2 + 4
    r = min(w, h - (24 if title else 8)) / 2 - 20
    r = max(r, 10)
    ang = lambda i: math.pi / 2 - TAU * i / n
    # concentric golden rings
    for ring in (INV_PHI * INV_PHI, INV_PHI, 1.0):
        pts = [(cx + r * ring * math.cos(ang(i)),
                cy + r * ring * math.sin(ang(i))) for i in range(n)]
        c.polyline(pts, rgb=GREY_DK, lw=0.4, close=True)
    # spokes + axis labels
    for i, lab in enumerate(axes):
        ex, ey = cx + r * math.cos(ang(i)), cy + r * math.sin(ang(i))
        c.line(cx, cy, ex, ey, rgb=GREY_DK, lw=0.4)
        lx = cx + (r + 12) * math.cos(ang(i))
        ly = cy + (r + 8) * math.sin(ang(i))
        c.text_center(lx, ly - 2, str(lab), size=6.5, font="U", rgb=GREY)
    # series polygons
    for name, vals, col in series:
        pts = []
        for i in range(n):
            v = clamp(vals[i] if i < len(vals) else 0, 0.0, 1.0)
            pts.append((cx + r * v * math.cos(ang(i)),
                        cy + r * v * math.sin(ang(i))))
        fill = (int(col[0] * 0.32), int(col[1] * 0.32), int(col[2] * 0.32))
        c.polyline(pts, rgb=col, lw=1.2, close=True, fill=fill)
        for px, py in pts:
            c.circle(px, py, 1.6, fill=col)
    # legend
    ly = y + 10
    for name, vals, col in series:
        c.rect(x + 10, ly, 6, 6, fill=col)
        c.text(x + 20, ly, str(name), size=6.5, font="U", rgb=PARCH)
        ly += 10


# --- waterfall (stepwise PnL decomposition) ----------------------------
def waterfall(c, x, y, w, h, steps, title=None, start=0.0):
    """steps: list of (label, delta). Green up, red down, gold totals.

    Shows how a running balance is built from sequential contributions.
    """
    panel(c, x, y, w, h, fill=(12, 13, 26), border=GREY_DK, lw=0.8)
    if title:
        section_title(c, x + 8, y + h - 16, title, size=10)
    pad = 10
    ix, iy = x + pad, y + pad + 12
    iw = w - pad * 2
    ih = h - pad * 2 - (18 if title else 0) - 12
    if ih <= 0 or not steps:
        return
    run = start
    lows = [start]
    highs = [start]
    for _, d in steps:
        nxt = run + d
        lows.append(min(run, nxt))
        highs.append(max(run, nxt))
        run = nxt
    lo, hi = min(lows), max(highs)
    if hi <= lo:
        hi = lo + 1
    scale = ih / (hi - lo)
    y0 = iy + (0 - lo) * scale if lo <= 0 <= hi else iy
    n = len(steps)
    bw = iw / n * 0.62
    gap = iw / n
    run = start
    prev_top = iy + (start - lo) * scale
    for i, (lab, d) in enumerate(steps):
        nxt = run + d
        bx = ix + gap * i + (gap - bw) / 2
        ytop = iy + (max(run, nxt) - lo) * scale
        ybot = iy + (min(run, nxt) - lo) * scale
        col = GREEN if d >= 0 else RED
        c.rect(bx, ybot, bw, max(ytop - ybot, 1), fill=col)
        # connector to previous bar top
        if i > 0:
            c.line(ix + gap * (i - 1) + (gap + bw) / 2, prev_top,
                   bx, iy + (run - lo) * scale, rgb=GREY_DK, lw=0.4)
        prev_top = iy + (nxt - lo) * scale
        c.text_center(bx + bw / 2, ybot - 9, str(lab), size=6, font="U", rgb=GREY)
        c.text_center(bx + bw / 2, ytop + 2,
                      ("+" if d >= 0 else "") + fmt_money(d),
                      size=6, font="UB", rgb=col)
        run = nxt
    # baseline + final total marker
    c.line(ix, y0, ix + iw, y0, rgb=GREY, lw=0.4)
    c.text_right(ix + iw, iy + ih + 2, "ИТОГ " + fmt_money(run),
                 size=7.5, font="UB", rgb=GOLD)


# --- bullet graph (actual vs target with qualitative bands) ------------
def bullet(c, x, y, w, h, rows, title=None):
    """rows: list of (label, actual, target, maxv). Compact KPI bars.

    Each row: graded background bands (phi thirds), a value bar, a target tick.
    """
    panel(c, x, y, w, h, fill=(12, 13, 26), border=GREY_DK, lw=0.8)
    if title:
        section_title(c, x + 8, y + h - 16, title, size=10)
    pad = 10
    top = y + h - (26 if title else pad)
    n = len(rows) or 1
    lab_w = 62
    bar_x = x + pad + lab_w
    bar_w = w - pad * 2 - lab_w
    row_h = (top - (y + pad)) / n
    bands = (int(GREY_DK[0] * 0.7), int(GREY_DK[1] * 0.7), int(GREY_DK[2] * 0.7))
    for i, (lab, actual, target, maxv) in enumerate(rows):
        cy = top - row_h * (i + 1)
        bh = row_h * 0.5
        by = cy + (row_h - bh) / 2
        mv = maxv or 1
        # qualitative bands: dark / mid / light (phi thirds)
        for k, frac in enumerate((INV_PHI * INV_PHI, INV_PHI, 1.0)):
            shade = 0.35 + 0.18 * k
            bc = (int(GREY_DK[0] * shade + 20), int(GREY_DK[1] * shade + 20),
                  int(GREY_DK[2] * shade + 22))
            c.rect(bar_x, by, bar_w * frac, bh, fill=bc)
        # value bar
        vfrac = clamp(actual / mv, 0.0, 1.0)
        col = GREEN if actual >= target else AMBER
        c.rect(bar_x, by + bh * 0.28, bar_w * vfrac, bh * 0.44, fill=col)
        # target tick
        tx = bar_x + bar_w * clamp(target / mv, 0.0, 1.0)
        c.rect(tx - 1, by - 2, 2, bh + 4, fill=GOLD_LT)
        # labels
        c.text(x + pad, by + bh * 0.28, str(lab), size=7, font="UB", rgb=PARCH)
        c.text_right(bar_x + bar_w, by + bh + 1, fmt_money(actual),
                     size=6.5, font="UB", rgb=col)


# module-level doc handle for alpha graphics states (set by magazine.py)
_DOC = [None]


def bind_doc(doc):
    _DOC[0] = doc
