#!/usr/bin/env python3
"""
CORP HEIST — Брошура зарисовок (reportlab API)
Стартовый герой: Аналитик
"""
import os, math
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("Seg", "C:/Windows/Fonts/segoeui.ttf"))
pdfmetrics.registerFont(TTFont("SegB", "C:/Windows/Fonts/segoeuib.ttf"))

TAU = math.pi * 2
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "content", "CORP_HEIST_Analyst_Brochure.pdf")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
W, H = A4

# Colors
BG       = HexColor("#0A0A12")
PANEL    = HexColor("#12121E")
GOLD     = HexColor("#FFC800")
BLUE     = HexColor("#00AAFF")
DKBLUE   = HexColor("#0055AA")
WHITE    = HexColor("#CCCCDD")
GRAY     = HexColor("#555566")
RED      = HexColor("#FF3232")
ACCENT   = HexColor("#00DDFF")
GREEN    = HexColor("#00AA66")
AMBER    = HexColor("#00FF88")


def text(txt, x, y, color=WHITE, size=10, font="Seg", align="left"):
    c.setFillColor(color)
    c.setFont(font, size)
    tw = c.stringWidth(txt, font, size)
    if align == "center":
        c.drawString(x - tw / 2, y, txt)
    elif align == "right":
        c.drawString(x - tw, y, txt)
    else:
        c.drawString(x, y, txt)


def line(x1, y1, x2, y2, color=GRAY, w=0.5):
    c.setStrokeColor(color)
    c.setLineWidth(w)
    c.line(x1, y1, x2, y2)


def rect(x, y, w, h, color=BG, fill=1, stroke=0, strokeColor=GRAY, alpha=1.0):
    c.setFillColor(color)
    c.setFillAlpha(alpha)
    c.setStrokeColor(strokeColor)
    c.rect(x, y, w, h, fill=fill, stroke=stroke)
    c.setFillAlpha(1)


def rrect(x, y, w, h, r=4, color=PANEL, fill=1, stroke=0, strokeColor=GRAY, alpha=1.0):
    c.setFillColor(color)
    c.setFillAlpha(alpha)
    c.setStrokeColor(strokeColor)
    c.roundRect(x, y, w, h, r, fill=fill, stroke=stroke)
    c.setFillAlpha(1)


def draw_page_bg():
    """Draw the standard page background (dark + vignette)."""
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(PANEL)
    c.setFillAlpha(0.15)
    for i in range(8):
        c.circle(W/2 + math.sin(i*0.8)*100, H/2 + math.cos(i*0.8)*80, 40+i*15, fill=1, stroke=0)
    c.setFillAlpha(1)


def path_fill(points, color, alpha=1.0):
    p = c.beginPath()
    p.moveTo(points[0][0], points[0][1])
    for pt in points[1:]:
        p.lineTo(pt[0], pt[1])
    p.close()
    c.setFillColor(color)
    c.setFillAlpha(alpha)
    c.drawPath(p, fill=1, stroke=0)
    c.setFillAlpha(1)


def path_stroke(points, color, w=1, alpha=1.0):
    p = c.beginPath()
    p.moveTo(points[0][0], points[0][1])
    for pt in points[1:]:
        p.lineTo(pt[0], pt[1])
    c.setStrokeColor(color)
    c.setLineWidth(w)
    c.setStrokeAlpha(alpha)
    c.drawPath(p, fill=0, stroke=1)
    c.setStrokeAlpha(1)


def ellipse_fill(x1, y1, x2, y2, color, alpha=1.0):
    c.setFillColor(color)
    c.setFillAlpha(alpha)
    c.ellipse(x1, y1, x2, y2, fill=1, stroke=0)
    c.setFillAlpha(1)


def ellipse_stroke(x1, y1, x2, y2, color, w=1):
    c.setStrokeColor(color)
    c.setLineWidth(w)
    c.ellipse(x1, y1, x2, y2, fill=0, stroke=1)


# ====== SKETCH FUNCTIONS ======

def sketch_silhouette(cx, cy, s=1.0, label=""):
    c.saveState()
    c.translate(cx, cy)

    # Shadow
    p = c.beginPath()
    p.ellipse(-18*s, -95*s, 36*s, 8*s)
    c.setFillColor(HexColor("#000000"))
    c.setFillAlpha(0.2)
    c.drawPath(p, fill=1, stroke=0)
    c.setFillAlpha(1)

    # Legs
    c.setStrokeColor(ACCENT); c.setLineWidth(2*s)
    c.line(-8*s, -30*s, -10*s, -90*s)
    c.line(8*s, -30*s, 10*s, -90*s)
    # Shoes
    rect(-14*s, -95*s, 10*s, 8*s, DKBLUE)
    rect(4*s, -95*s, 10*s, 8*s, DKBLUE)

    # Torso (suit)
    torso = [(-15*s,-30*s),(-18*s,-10*s),(-12*s,25*s),(12*s,25*s),(18*s,-10*s),(15*s,-30*s)]
    path_fill(torso, HexColor("#1A1A3A"))
    path_stroke(torso, BLUE, 1.5)

    # Shirt V
    c.setStrokeColor(WHITE); c.setLineWidth(0.8*s)
    c.line(-6*s, 20*s, 0*s, -5*s)
    c.line(6*s, 20*s, 0*s, -5*s)

    # Tie
    c.setStrokeColor(RED); c.setLineWidth(2*s)
    c.line(0*s, 15*s, 0*s, -8*s)
    path_fill([(0,15*s),(-2*s,10*s),(2*s,10*s)], RED)

    # Head
    c.setFillColor(HexColor("#D4B896"))
    c.circle(0, 38*s, 12*s, fill=1, stroke=0)
    # Hair
    p = c.beginPath()
    p.arc(-12*s, 30*s, 12*s, 12*s, 60, 120)
    c.setFillColor(HexColor("#2A2A4A"))
    c.drawPath(p, fill=1, stroke=0)

    # Glasses
    ellipse_stroke(-10*s, 35*s, -2*s, 43*s, ACCENT, 1.2)
    ellipse_stroke(2*s, 35*s, 10*s, 43*s, ACCENT, 1.2)
    ellipse_fill(-9*s, 36*s, -3*s, 42*s, ACCENT, 0.25)
    ellipse_fill(3*s, 36*s, 9*s, 42*s, ACCENT, 0.25)
    c.setStrokeColor(ACCENT); c.setLineWidth(0.8*s)
    c.line(-2*s, 39*s, 2*s, 39*s)

    # USB bracelet
    c.setFillColor(AMBER)
    c.circle(20*s, -5*s, 2*s, fill=1, stroke=0)

    # Arms
    c.setStrokeColor(ACCENT); c.setLineWidth(1.8*s)
    c.line(-18*s, -10*s, -25*s, -35*s)
    c.line(18*s, -10*s, 28*s, -15*s)

    # Tablet
    rect(26*s, -28*s, 16*s, 12*s, HexColor("#1A2A1A"), stroke=1, strokeColor=HexColor("#00AA44"))
    rect(27*s, -27*s, 14*s, 10*s, HexColor("#003311"))
    for i in range(4):
        lw = 4 + (i * 3) % 8
        rect(28*s, (-26+i*2)*s, lw*s, 1*s, AMBER, alpha=0.6)

    # Hologram rings
    c.setStrokeColor(ACCENT); c.setLineWidth(0.4*s)
    c.setFillAlpha(0.08)
    for i in range(3):
        r = (8 + i*5) * s
        c.circle(34*s, -20*s, r, fill=0, stroke=1)
    c.setFillAlpha(1)

    c.restoreState()
    if label:
        text(label, cx, cy - 105*s, GRAY, 7, "Seg", align="center")


def sketch_idle(cx, cy, s=1.0, label=""):
    c.saveState()
    c.translate(cx, cy)

    torso = [(-12*s,-30*s),(-15*s,20*s),(15*s,20*s),(12*s,-30*s)]
    path_fill(torso, HexColor("#1A1A3A"))
    path_stroke(torso, BLUE, 1)

    c.setFillColor(HexColor("#D4B896"))
    c.circle(0, 30*s, 11*s, fill=1, stroke=0)

    # Hand on chin
    c.setStrokeColor(ACCENT); c.setLineWidth(2*s)
    c.line(-15*s, 10*s, -10*s, 25*s)
    c.line(-10*s, 25*s, -4*s, 32*s)
    c.line(15*s, 10*s, 22*s, 0*s)

    # Hologram
    c.setStrokeColor(ACCENT); c.setLineWidth(0.3*s)
    for i in range(4):
        c.circle(28*s, 5*s, (6+i*4)*s, fill=0, stroke=1)

    # Glasses
    ellipse_stroke(-8*s, 27*s, -1*s, 34*s, ACCENT, 1)
    ellipse_stroke(1*s, 27*s, 8*s, 34*s, ACCENT, 1)

    c.restoreState()
    if label:
        text(label, cx, cy - 45*s, GRAY, 7, "Seg", align="center")


def sketch_attack(cx, cy, s=1.0, label=""):
    c.saveState()
    c.translate(cx, cy)

    torso = [(-10*s,-35*s),(-18*s,15*s),(18*s,15*s),(10*s,-35*s)]
    path_fill(torso, HexColor("#1A1A3A"))
    path_stroke(torso, BLUE, 1)

    c.setFillColor(HexColor("#D4B896"))
    c.circle(-5*s, 30*s, 10*s, fill=1, stroke=0)

    # Arms reaching forward
    c.setStrokeColor(ACCENT); c.setLineWidth(2*s)
    c.line(-18*s, 5*s, -30*s, -5*s)
    c.line(18*s, 5*s, 30*s, -5*s)

    # Virtual keyboard
    rect(-35*s, -15*s, 70*s, 20*s, ACCENT, alpha=0.15, stroke=1, strokeColor=ACCENT)
    for row in range(3):
        for col in range(8):
            a = 0.3 + (row + col) % 3 * 0.15
            rect((-33+col*8.5)*s, (-13+row*6)*s, 6*s, 4*s, AMBER, alpha=a)

    # Attack wave
    pts = []
    for i in range(30):
        px = (35 + i*2) * s
        py = (-5 + math.sin(i*0.5) * 8) * s
        pts.append((px, py))
    path_stroke(pts, RED, 1.5, 0.6)
    c.setFillColor(RED); c.setFillAlpha(0.6)
    c.circle(pts[-1][0], pts[-1][1], 3*s, fill=1, stroke=0)
    c.setFillAlpha(1)

    c.restoreState()
    if label:
        text(label, cx, cy - 50*s, GRAY, 7, "Seg", align="center")


def sketch_outfit(cx, cy, s=1.0, label=""):
    c.saveState()
    c.translate(cx, cy)

    # Jacket
    rect(-25*s, -40*s, 50*s, 80*s, HexColor("#1A1A3A"), stroke=1, strokeColor=BLUE)
    # Lapels
    c.setStrokeColor(WHITE); c.setLineWidth(0.6*s)
    c.line(-10*s, 40*s, 0*s, 10*s)
    c.line(10*s, 40*s, 0*s, 10*s)
    # Buttons
    c.setFillColor(GOLD)
    for i in range(4):
        c.circle(0*s, (25-i*10)*s, 1.5*s, fill=1, stroke=0)
    # Cuffs
    rect(-28*s, -42*s, 6*s, 10*s, HexColor("#222244"))
    rect(22*s, -42*s, 6*s, 10*s, HexColor("#222244"))
    c.setFillColor(GOLD)
    c.circle(-25*s, -37*s, 1*s, fill=1, stroke=0)
    c.circle(25*s, -37*s, 1*s, fill=1, stroke=0)
    # Pocket
    rect(10*s, 15*s, 12*s, 15*s, HexColor("#1A1A3A"), stroke=1, strokeColor=GRAY)
    rect(14*s, 16*s, 1*s, 12*s, GOLD)

    # Glasses detail (zoomed)
    c.saveState()
    c.translate(50*s, 20*s)
    ellipse_stroke(-15*s, -8*s, -3*s, 8*s, ACCENT, 1.5)
    ellipse_stroke(3*s, -8*s, 15*s, 8*s, ACCENT, 1.5)
    c.setStrokeColor(ACCENT); c.setLineWidth(0.8*s)
    c.line(-15*s, 0*s, -22*s, -2*s)
    c.line(15*s, 0*s, 22*s, -2*s)
    ellipse_fill(-14*s, -7*s, -4*s, 7*s, ACCENT, 0.2)
    ellipse_fill(4*s, -7*s, 14*s, 7*s, ACCENT, 0.2)
    c.setFillColor(WHITE)
    c.circle(-9*s, 3*s, 2*s, fill=1, stroke=0)
    c.circle(9*s, 3*s, 2*s, fill=1, stroke=0)
    c.restoreState()

    c.restoreState()
    if label:
        text(label, cx, cy - 50*s, GRAY, 7, "Seg", align="center")


def sketch_ability_quantum(cx, cy, s=1.0, label=""):
    c.saveState()
    c.translate(cx, cy)

    # Rings
    c.setStrokeColor(ACCENT); c.setLineWidth(1*s)
    for i in range(5):
        c.circle(0, 0, (10+i*8)*s, fill=0, stroke=1)

    # Equations
    c.setFillColor(ACCENT); c.setFillAlpha(0.5)
    eqs = ["E=mc2", "dP/dt", "sigma", "alpha", "beta"]
    for i, eq in enumerate(eqs):
        a = i * TAU / 5 + 0.3
        ex = math.cos(a) * 35 * s
        ey = math.sin(a) * 35 * s
        sz = max(5, int(7*s))
        c.setFont("Seg", sz)
        c.drawString(ex - 10*s, ey, eq)
    c.setFillAlpha(1)

    # Radial lines
    c.setStrokeColor(BLUE); c.setLineWidth(0.4*s)
    for i in range(8):
        a = i * TAU / 8
        c.line(math.cos(a)*20*s, math.sin(a)*20*s,
               math.cos(a)*38*s, math.sin(a)*38*s)

    # Center
    c.setFillColor(GOLD)
    c.circle(0, 0, 3*s, fill=1, stroke=0)

    c.restoreState()
    if label:
        text(label, cx, cy - 50*s, GRAY, 7, "Seg", align="center")


def sketch_ability_arb(cx, cy, s=1.0, label=""):
    c.saveState()
    c.translate(cx, cy)

    # Attack wave
    pts = []
    for i in range(40):
        px = (-40 + i*2) * s
        py = math.sin(i*0.4) * 15 * s * math.exp(-i*0.05)
        pts.append((px, py))
    path_stroke(pts, RED, 2, 0.7)

    # Fill under
    fill_pts = pts + [(pts[-1][0], -20*s), (pts[0][0], -20*s)]
    path_fill(fill_pts, RED, 0.08)

    # Dollar signs
    c.setFillColor(GOLD); c.setFillAlpha(0.4)
    for i in range(6):
        dx = (-30 + i*12) * s
        dy = (5 + math.sin(i*1.2)*10) * s
        sz = max(6, int(8*s))
        c.setFont("SegB", sz)
        c.drawString(dx, dy, "$")
    c.setFillAlpha(1)

    # Impact point
    c.setFillColor(RED)
    c.circle(pts[-1][0], pts[-1][1], 4*s, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.circle(pts[-1][0], pts[-1][1], 2*s, fill=1, stroke=0)

    c.restoreState()
    if label:
        text(label, cx, cy - 30*s, GRAY, 7, "Seg", align="center")


def sketch_floor(cx, cy, s=1.0, label=""):
    c.saveState()
    c.translate(cx, cy)

    # Floor
    rect(-40*s, -5*s, 80*s, 15*s, HexColor("#0D0D18"))
    # Grid lines
    c.setStrokeColor(HexColor("#1A1A2E")); c.setLineWidth(0.3*s)
    for i in range(-40, 41, 10):
        c.line(i*s, -5*s, i*s, 10*s)
    for i in range(-5, 11, 5):
        c.line(-40*s, i*s, 40*s, i*s)

    # Columns
    for cx2 in [-30, 0, 30]:
        rect((cx2-3)*s, -5*s, 6*s, 55*s, HexColor("#1A1A2E"))
        c.setStrokeColor(BLUE); c.setLineWidth(0.5*s)
        c.rect((cx2-3)*s, -5*s, 6*s, 55*s, fill=0, stroke=1)

    # Ceiling
    rect(-40*s, 50*s, 80*s, 5*s, HexColor("#0A0A15"))
    # Neon strip
    c.setStrokeColor(ACCENT); c.setLineWidth(1.5*s)
    c.line(-35*s, 52*s, 35*s, 52*s)

    # Windows
    for i in range(-35, 36, 15):
        rect(i*s, 10*s, 12*s, 38*s, HexColor("#001122"))
        rect(i*s, 10*s, 12*s, 19*s, HexColor("#003344"), alpha=0.3)

    c.restoreState()
    if label:
        text(label, cx, cy - 12*s, GRAY, 7, "Seg", align="center")


def draw_skill_tree(cx, cy, s=1.0):
    c.saveState()
    c.translate(cx, cy)

    nodes = [
        (0, 0, "ANALYST", GOLD, 3*s),
        (-25, -18, "DODGE", BLUE, 2*s),
        (25, -18, "CRIT", RED, 2*s),
        (-40, -35, "SPEED", ACCENT, 1.5*s),
        (-10, -35, "DEF", GREEN, 1.5*s),
        (10, -35, "ATK", RED, 1.5*s),
        (40, -35, "DMG", GOLD, 1.5*s),
    ]

    # Edges
    c.setStrokeColor(GRAY); c.setLineWidth(0.5*s)
    edges = [(0,1),(0,2),(1,3),(1,4),(2,5),(2,6)]
    for a, b in edges:
        c.line(nodes[a][0]*s, nodes[a][1]*s, nodes[b][0]*s, nodes[b][1]*s)

    # Nodes
    for nx, ny, name, color, r in nodes:
        c.setFillColor(color); c.setFillAlpha(0.15)
        c.circle(nx*s, ny*s, r, fill=1, stroke=0)
        c.setFillAlpha(1)
        c.setStrokeColor(color); c.setLineWidth(0.8*s)
        c.circle(nx*s, ny*s, r, fill=0, stroke=1)
        c.setFillColor(WHITE)
        sz = max(5, int(6*s))
        c.setFont("Seg", sz)
        tw = c.stringWidth(name, "Seg", sz)
        c.drawString(nx*s - tw/2, (ny-1)*s, name)

    c.restoreState()


def draw_stats(cx, cy, s=1.0):
    stats = [("HP",80,100,BLUE),("ATK",12,25,RED),("DEF",8,20,GREEN),
             ("SPD",14,20,ACCENT),("CRIT",15,30,GOLD),("DODGE",5,25,HexColor("#AA00FF"))]
    for i, (name, val, mx, color) in enumerate(stats):
        iy = cy - i * 14 * s
        text(name, cx, iy, GRAY, int(7*s), "SegB")
        rect(cx+25*s, iy-1, 60*s, 6, HexColor("#1A1A2E"))
        rect(cx+25*s, iy-1, (val/mx)*60*s, 6, color)
        text(str(val), cx+90*s, iy, WHITE, int(7*s), "SegB")


# ============================================================
# BUILD PDF
# ============================================================
print("Generating CORP HEIST Analyst Brochure...")
c = canvas.Canvas(OUT, pagesize=A4)
c.setTitle("CORP HEIST - Analyst Concept Brochure")
c.setAuthor("CORP HEIST Team")

# ===== PAGE 1: Title =====
rect(0, 0, W, H, BG)
line(40, H-80, W-40, H-80, BLUE, 2)
line(40, 80, W-40, 80, BLUE, 2)

text("CORP HEIST", W/2, H-130, GOLD, 36, "SegB", "center")
text("CONCEPT ART BROCHURE", W/2, H-155, BLUE, 14, "Seg", "center")
text("#001", W/2, H-175, GRAY, 10, "Seg", "center")

sketch_silhouette(W/2, H/2+20, 2.2)

text("ANALYST", W/2, H/2-120, BLUE, 24, "SegB", "center")
text("\"Every formula is open\"", W/2, H/2-140, GRAY, 10, "Seg", "center")

rrect(W/2-20, H/2-170, 40, 18, 4, BLUE, strokeColor=BLUE)
text("B", W/2, H/2-166, WHITE, 12, "SegB", "center")

text("github.com/pop31-ai/CORP-HEIST", W/2, 50, GRAY, 8, "Seg", "center")
text("Open Source | Python + Pygame | MIT License", W/2, 38, GRAY, 7, "Seg", "center")

c.showPage()

# ===== PAGE 2: Silhouettes + Poses =====
rect(0, 0, W, H, BG)
text("01  SILUET + POSES", 40, H-50, GOLD, 16, "SegB")
line(40, H-55, 200, H-55, GOLD, 1)

sketch_silhouette(150, H-230, 1.8, "STANDING")
sketch_idle(420, H-230, 1.8, "IDLE")
sketch_attack(690, H-230, 1.8, "ATTACK")

text("Figure: average height, lean build", 40, H-330, WHITE, 8)
text("Outfit: dark blue business suit, white shirt", 40, H-345, WHITE, 8)
text("Accessories: blue-tinted glasses, USB bracelet", 40, H-360, WHITE, 8)
text("Weapon: laptop-tablet projecting quantum equations", 40, H-375, WHITE, 8)
text("IDLE: glasses adjustment, hologram flicker", 40, H-400, ACCENT, 8)
text("ATTACK: virtual keyboard tap -> projection flies to enemy", 40, H-415, RED, 8)

c.showPage()

# ===== PAGE 3: Outfit Detail =====
rect(0, 0, W, H, BG)
text("02  OUTFIT DETAIL", 40, H-50, GOLD, 16, "SegB")
line(40, H-55, 200, H-55, GOLD, 1)

sketch_outfit(W/2, H/2+30, 2.0)

text("Suit: dark blue, premium class", 40, 120, WHITE, 8)
text("Shirt: white, V-neck collar", 40, 105, WHITE, 8)
text("Tie: red, thin", 40, 90, WHITE, 8)
text("Cuffs: gold buttons", 40, 75, WHITE, 8)
text("Glasses: blue lenses, thin frame", 40, 60, WHITE, 8)
text("USB bracelet: neon glow, generates data", 40, 45, WHITE, 8)

c.showPage()

# ===== PAGE 4: Abilities =====
rect(0, 0, W, H, BG)
text("03  ABILITIES", 40, H-50, GOLD, 16, "SegB")
line(40, H-55, 200, H-55, GOLD, 1)

sketch_ability_quantum(180, H-220, 2.0, "QUANTUM ANALYSIS")
sketch_ability_arb(520, H-220, 2.0, "ARBITRAGE STRIKE")

text("QUANTUM ANALYSIS", 40, H-320, ACCENT, 12, "SegB")
text("Basic attack. Equation projections deal damage", 40, H-335, WHITE, 8)
text("scaled by ATK stat.", 40, H-348, WHITE, 8)

text("ARBITRAGE STRIKE", 40, H-370, RED, 12, "SegB")
text("Data shockwave. AoE damage to all enemies.", 40, H-385, WHITE, 8)
text("Cooldown: 3 turns.", 40, H-398, WHITE, 8)

text("STATS", 40, H-420, GOLD, 12, "SegB")
draw_stats(40, H-435, 1.0)

c.showPage()

# ===== PAGE 5: Skill Tree + Floor =====
rect(0, 0, W, H, BG)
text("04  SKILL TREE + FLOOR", 40, H-50, GOLD, 16, "SegB")
line(40, H-55, 220, H-55, GOLD, 1)

draw_skill_tree(200, H-250, 2.0)
text("PASSIVE SKILL TREE", 200, H-320, BLUE, 10, "SegB", "center")
text("Each level gives skill points.", 200, H-338, GRAY, 8, "Seg", "center")
text("Tree defines playstyle: attack, defense, speed.", 200, H-352, GRAY, 8, "Seg", "center")

sketch_floor(550, H/2, 1.5, "FLOOR 1: LOBBY")
text("Business Center: 7 floors", 550, H/2-50, BLUE, 9, "SegB", "center")
text("Each floor = new challenge", 550, H/2-65, GRAY, 8, "Seg", "center")
text("Enemies scale exponentially", 550, H/2-78, GRAY, 8, "Seg", "center")
text("Rewards grow with risk", 550, H/2-91, GRAY, 8, "Seg", "center")

c.showPage()

# ===== PAGE 6: Lore + Roster =====
rect(0, 0, W, H, BG)
text("05  LORE + ROSTER", 40, H-50, GOLD, 16, "SegB")
line(40, H-55, 220, H-55, GOLD, 1)

text("THE ANALYST", 40, H-85, BLUE, 14, "SegB")
text("\"Every number tells a story.", 40, H-105, ACCENT, 9)
text("Every formula reveals a truth.\"", 40, H-118, ACCENT, 9)

lore = [
    "Former quantum analyst at a hedge fund.",
    "Fired after exposing a market manipulation",
    "scheme using quantum algorithms.",
    "Now works for himself, using his skills to",
    "analyze corporate structures and find",
    "weak points in the system.",
]
for i, ln in enumerate(lore):
    text(ln, 40, H-145-i*15, WHITE, 9)

text("HERO ROSTER", 40, H-250, GOLD, 12, "SegB")
heroes = [
    ("ANALYST","B","#00AAFF","HP:80 ATK:12 DEF:8 SPD:14"),
    ("CONSULTANT","A","#FFC800","HP:100 ATK:15 DEF:10 SPD:10"),
    ("QUANT","S","#AA00FF","HP:70 ATK:18 DEF:5 SPD:16"),
    ("LAWYER","A","#FF3232","HP:110 ATK:10 DEF:15 SPD:8"),
    ("CEO","SSR","#FFC800","HP:130 ATK:20 DEF:12 SPD:12"),
]
for i, (name, tier, color, stats) in enumerate(heroes):
    hy = H-275 - i*35
    rrect(40, hy-5, 200, 28, 3, HexColor(color), alpha=0.08, strokeColor=HexColor(color))
    text(tier, 48, hy+2, HexColor(color), 11, "SegB")
    text(name, 75, hy+2, WHITE, 10, "SegB")
    text(stats, 75, hy-10, GRAY, 7)

sketch_silhouette(550, H/2+40, 1.0)
text("10 HEROES", 550, H/2-50, BLUE, 10, "SegB", "center")
text("5 CORPORATIONS", 550, H/2-65, GOLD, 10, "SegB", "center")
text("7 FLOORS", 550, H/2-80, RED, 10, "SegB", "center")

c.showPage()

# ===== PAGE 7: Monetization + Links =====
rect(0, 0, W, H, BG)
text("06  SYSTEMS + LINKS", 40, H-50, GOLD, 16, "SegB")
line(40, H-55, 250, H-55, GOLD, 1)

sections = [
    ("GACHA SYSTEM", BLUE, [
        "SSR: 3% | S: 7% | A: 20% | B: 70%",
        "Pity: guaranteed A+ every 50 rolls",
        "Transparent rates, published formulas",
    ]),
    ("STOCK MARKET", GOLD, [
        "10,000 tradeable stocks",
        "Real-time price simulation",
        "Loot drops from stock trades",
        "Intermediary chain system (8 types)",
    ]),
    ("LOOT CHAINS", RED, [
        "MarketMaker -> Broker -> Forge -> Auction",
        "Each intermediary takes 2-20% fee",
        "DarkPool: best price, but risk of loss",
    ]),
    ("PROTOCOL", ACCENT, [
        "Binary: 3-114 bytes per message",
        "Player -> Character -> System",
        "Zero P2P traffic",
        "1200 math render algorithms",
        "Auto-refresh every hour (traffic saving)",
        "Donate: sacrifice loot for gold multiplier",
    ]),
]

y = H - 80
for title, color, items in sections:
    text(title, 40, y, color, 12, "SegB")
    y -= 18
    for item in items:
        text(item, 50, y, WHITE, 8)
        y -= 13
    y -= 10

text("LINKS", 40, y - 5, GOLD, 12, "SegB")
y -= 25
for lnk in [
    "github.com/pop31-ai/CORP-HEIST",
    "Python 3.12+ | Pygame 2.6+",
    "License: MIT",
]:
    text(lnk, 50, y, GRAY, 8)
    y -= 13

rrect(W/2-120, 30, 240, 30, 4, GOLD)
text("CORP HEIST", W/2, 38, BG, 14, "SegB", "center")

# === PAGE 7: LOOT DISCLAIMER ===
c.showPage()
draw_page_bg()

text("LEGAL NOTICE", W/2, H - 60, GOLD, 22, "SegB", "center")

disclaimer_lines = [
    ("LOOT & ITEM OWNERSHIP", RED, [
        "Loot icons displayed in CORP HEIST are personal",
        "symbols of ownership. They do not represent real",
        "property, financial instruments, or legal claims.",
        "",
        "CORP HEIST does not own, endorse, or guarantee",
        "the value of any displayed loot item.",
    ]),
    ("TEMPORARY UNAVAILABILITY", ACCENT, [
        "Items may be temporarily unavailable due to:",
        "  - Routine maintenance and recalibration",
        "  - Aesthetic cleaning and polishing",
        "  - System upgrades and optimization",
        "  - Security audits and compliance checks",
        "",
        "During maintenance, items display a",
        "'MAINTENANCE' status indicator.",
    ]),
    ("NO FINANCIAL ADVICE", GOLD, [
        "All stock market data, portfolio values, and net",
        "worth figures are simulated for entertainment.",
        "Nothing in CORP HEIST constitutes financial",
        "advice, investment recommendation, or",
        "guarantee of real-world returns.",
    ]),
    ("COMPLIANCE", GRAY, [
        "14-ФЗ (Advertising) | 39-ФЗ (Securities)",
        "152-ФЗ (Personal Data) | 149-ФЗ (Information)",
        "Age rating: 12+ | Rating: 0+",
    ]),
    ("MONETIZATION", GOLD, [
        "Donate: system decides budget, rates published",
        "Everything obtainable for something",
        "Buy Gold: USD + RUB, system sets rate",
        "Money-Back: per 14-ФЗ, system decides eligibility",
        "No pay-to-win: all items cosmetic/symbolic",
    ]),
]

y = H - 100
for title, color, items in disclaimer_lines:
    text(title, 40, y, color, 11, "SegB")
    y -= 16
    for item in items:
        text(item, 50, y, WHITE if item else GRAY, 7.5)
        y -= 11
    y -= 8

# decorative maintenance wrench sketch
c.setStrokeColor(GRAY); c.setLineWidth(1.5)
c.line(80, 80, 100, 100)
c.circle(105, 105, 6, fill=0, stroke=1)
c.line(100, 110, 95, 115)
text("MAINTENANCE", 90, 70, GRAY, 7, "SegB", "center")

rrect(W/2-120, 30, 240, 30, 4, GOLD)
text("CORP HEIST", W/2, 38, BG, 14, "SegB", "center")

c.save()
sz = os.path.getsize(OUT)
print(f"  -> {OUT}")
print(f"  -> {sz} bytes ({sz//1024} KB)")
print("Done!")
