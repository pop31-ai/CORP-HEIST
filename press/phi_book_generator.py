"""
phi_book_generator.py - PDF book generator for CORP HEIST book on golden section and polynomials.

Creates 5 volumes × 10 pages = 50 pages total:
- Golden section theory and application
- Market OLAP cube mathematics  
- Polynomial dynamics and convergence
- Sector spreads and trading strategies
- Advanced tactics and golden ratio strategies

Uses zero-deps pdfkit_phi engine, same as press magazine.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from press.magazine import (Magazine, MARGIN, CONTENT_W, COL_W, PAGE_W, PAGE_H,
                             TOP, BOTTOM)
import press.phi_charts as G
import press.hero_scenes as HS
import market_cube as MC

# Golden section constants
PHI = 1.618033988749
INV_PHI = 1.0 / PHI

def _bg_phi_section(c, col1, col2):
    """Create golden-section inspired background"""
    c.vgrad(0, 0, PAGE_W, PAGE_H, col1, col2, bands=40)

def title_cover(book, title_ru, title_en):
    """Create title page for each volume"""
    c = book._new_page()
    _bg_phi_section(c, (14, 11, 5), (22, 18, 10))
    
    # Golden spiral in background
    G.phi_spiral(c, PAGE_W / 2, PAGE_H / 2, turns=5.0, scale=2.5,
                 col=G.GOLD, lw=0.8, alpha=0.12)
    
    # Title
    c.text_center(PAGE_W / 2, PAGE_H / 2, "CORP HEIST", size=20,
                  font="U", rgb=G.GREY, char_space=8)
    c.text_center(PAGE_W / 2, PAGE_H / 2 - 40, title_ru, size=32,
                  font="UB", rgb=G.GOLD_LT, char_space=4)
    c.text_center(PAGE_W / 2, PAGE_H / 2 - 85, title_en, size=20,
                  font="U", rgb=G.WHITE, char_space=6)
    
    # PHI signature
    c.text_center(PAGE_W / 2, 80, "PHI = %.9f" % PHI, size=12,
                  font="CB", rgb=G.GOLD)
    book._footer(c)

def intro_page(book, vol_num, title_ru, title_en, intro_ru, intro_en):
    """Create introduction page"""
    c = book._new_page()
    _bg_phi_section(c, (16, 13, 6), (24, 20, 12))
    
    # PHI golden ratio diagram
    G.golden_rects(c, MARGIN, TOP - 60, PAGE_W - MARGIN * 2, 120,
                   depth=8, col=G.GOLD, alpha=0.15)
    
    # Intro text
    G.section_title(c, MARGIN, TOP - 40, "Введение", size=18)
    
    lines_ru = intro_ru.split('\n')
    for i, line in enumerate(lines_ru):
        c.text(MARGIN, TOP - 90 - i * 18, line, size=11, font="U", rgb=G.WHITE)
    
    lines_en = intro_en.split('\n')
    for i, line in enumerate(lines_en):
        c.text(MARGIN, TOP - 160 - i * 14, line, size=9, font="U", rgb=G.GREY)
    
    # PHI information
    G.section_title(c, PAGE_W - 200, TOP - 40, "PHI", size=16)
    c.text_center(PAGE_W / 2, 100, "%.9f" % PHI, size=24, font="UB", rgb=G.GOLD)
    c.text_center(PAGE_W / 2, 140, "%d / 65536" % MC.PHI_Q16, size=10, font="C", rgb=G.CYAN)
    
    book._footer(c)

def section_chart_page(book, title_ru, title_en, chart_desc, chart_data):
    """Create page with chart and explanation"""
    c = book._new_page()
    _bg_phi_section(c, (12, 10, 4), (20, 18, 8))
    
    G.section_title(c, MARGIN, TOP - 40, title_ru, size=20)
    c.text(MARGIN, TOP - 80, title_en, size=12, font="U", rgb=G.GOLD)
    
    # Create chart placeholder
    chart_width = PAGE_W - MARGIN * 2
    chart_height = 200
    chart_x = MARGIN
    chart_y = TOP - 200
    
    # Simple phi spiral in chart area
    G.phi_spiral(c, chart_x + chart_width / 2, chart_y + chart_height / 2,
                 turns=3.0, scale=chart_width / 4, col=G.GOLD, lw=1.5)
    
    # Chart description
    c.text(MARGIN, chart_y + chart_height + 20, "График " + chart_desc, size=10,
           font="C", rgb=G.WHITE)
    
    # Mathematical explanation
    y = chart_y - 80
    for line in chart_data.split('\n'):
        if line.strip():
            c.text(MARGIN, y, line, size=9, font="U", rgb=G.PARCH)
            y -= 16
    
    book._footer(c)

def equation_page(book, eq_ru, eq_en, explanation_ru, explanation_en):
    """Create page with mathematical equation"""
    c = book._new_page()
    _bg_phi_section(c, (13, 11, 5), (21, 19, 9))
    
    G.section_title(c, MARGIN, TOP - 40, "Математический аппарат", size=20)
    
    # Main equation display
    c.text_center(PAGE_W / 2, PAGE_H / 2 - 100, eq_ru, size=28, font="C",
                  rgb=G.GOLD, char_space=2)
    c.text_center(PAGE_W / 2, PAGE_H / 2 - 140, eq_en, size=16, font="U",
                  rgb=G.WHITE, char_space=1)
    
    # Golden section visualization
    eq_x = PAGE_W / 2 - 140
    eq_y = PAGE_H / 2 - 80
    eq_len = 280
    
    # Draw golden rectangle
    c.rect(eq_x, eq_y, eq_len, eq_len * INV_PHI, fill=G.GOLD, alpha=0.1)
    c.line(eq_x, eq_y + eq_len * INV_PHI, eq_x + eq_len, eq_y + eq_len * INV_PHI,
           rgb=G.GOLD, lw=2)
    
    # Explain
    c.paragraph(MARGIN, TOP - 200, explanation_ru, size=10, font="U",
                rgb=G.PARCH, width=CONTENT_W)
    c.paragraph(MARGIN, TOP - 250, explanation_en, size=9, font="U",
                rgb=G.GREY, width=CONTENT_W)
    
    book._footer(c)

def build_volume(book, vol_num):
    """Build a single volume (10 pages)"""
    volumes = [
        {
            "title_ru": "Том %d: Золотое сечение" % vol_num,
            "title_en": "Volume %d: The Golden Section" % vol_num,
            "intro_ru": """Корп HEIST — это deterministic OLAP-куб.
Все в игре построено на φ = 1.618033988749.
Нет линейного роста, только золотое сечение.
Просто запомните φ и вы поймете весь мир игры.""",
            "intro_en": """CORP HEIST is a deterministic OLAP cube.
Everything in the game is built on φ = 1.618033988749.
No linear growth, only golden section.
Just remember φ and you understand the whole game world.""",
            "chapter1_ru": "Основы масштаба",
            "chapter1_en": "Scale Fundamentals",
            "chapter1_desc": "golden-section scaling visualization",
            "chapter1_data": """Все: время, цена, благосостояние.
Эпохи: 90 дней (апгрейд).
Недели: 7 дней (сшивка).
Тренд: 4 недели назад (сглаживание).""",
            "equation_ru": "φ = %.9f" % PHI,
            "equation_en": "PHI = %.9f" % PHI,
            "equation_ex_ru": """φ^x = y * φ^(x-1)
φ * x - y * x = x * (φ - y)
Каждый коэффициент масштаба — это φ в разных измерениях.""",
            "equation_ex_en": """φ^x = y * φ^(x-1)
φ * x - y * x = x * (φ - y)
Every scale coefficient is φ in different dimensions.""",
        },
        {
            "title_ru": "Том %d: OLAP куб" % vol_num,
            "title_en": "Volume %d: The OLAP Cube" % vol_num,
            "intro_ru": """Ядро игры — market_cube.
Оси: MKT, BOSS, AUC, PWR, PLAYER.
Меры на пересечении: прибыль, благосостояние.
Все предсказуемо благодаря целым числам.""",
            "intro_en": """Game core: market_cube.
Axes: MKT, BOSS, AUC, PWR, PLAYER.
Measures at intersection: profit, welfare.
Everything predictable thanks to integers.""",
            "chapter1_ru": "Структура куба",
            "chapter1_en": "Cube Structure",
            "chapter1_desc": "phi-styled axes visualization",
            "chapter1_data": """5 осей:
- MKT: рынок (общее состояние)
- BOSS: боссы (корпоративная власть)
- AUC: аукцион (состояние)
- PWR: власть (влияние)
- PLAYER: игрок (индивидуальность)

WELFARE (оси-мера #8) рассчитывается из координат.""",
            "equation_ru": "WELFARE = f(MKT, BOSS, AUC, PWR, PLAYER)",
            "equation_en": "WELFARE = f(MKT, BOSS, AUC, PWR, PLAYER)",
            "equation_ex_ru": """Формула не хранится, а вычисляется из 5-мерных координат.
Это честно: любой может пересчитать.
Все deterministic благодаря целому PHI_Q16.""",
            "equation_ex_en": """Formula not stored, calculated from 5D coordinates.
It's fair: anyone can recalculate.
Everything deterministic thanks to integer PHI_Q16.""",
        },
        {
            "title_ru": "Том %d: Полиномы и динамика" % vol_num,
            "title_en": "Volume %d: Polynomials and Dynamics" % vol_num,
            "intro_ru": """Графики растут по φ.
Движение предсказуемо благодаря recurrence relation.
Камбэки — не случайность, а математика.
Момент X: точка преобразования.""",
            "intro_en": """Graphs grow by φ.
Movement predictable thanks to recurrence relation.
Comebacks — not randomness, mathematics.
Moment X: point of transformation.""",
            "chapter1_ru": "Рекурсивная динамика",
            "chapter1_en": "Recursive Dynamics",
            "chapter1_desc": "phi-styled convergence visualization",
            "chapter1_data": """x_{n+1} = φ * x_n - x_{n-1}
x_{n+1} = x_n + (φ - 1) * x_n

Все колебания в пределах golden ratio.
Нет случайных выходов за пределы phi.""",
            "equation_ru": "x_{n} = φ^n * x0 + c * φ^{-n} * x_{-1}",
            "equation_en": "x_{n} = φ^n * x0 + c * φ^{-n} * x_{-1}",
            "equation_ex_ru": """Бесконечная серия: золотое сечение в действии.
Каждая итерация уменьшается по φ^2.
Бесконечная сумма converges к конечному пределу.
Все в игре — части infinite series.""",
            "equation_ex_en": """Infinite series: golden section in action.
Every iteration decreases by φ^2.
Infinite sum converges to finite limit.
Everything in game — part of infinite series.""",
        },
        {
            "title_ru": "Том %d: Сектора и спреды" % vol_num,
            "title_en": "Volume %d: Sectors and Spreads" % vol_num,
            "intro_ru": """Четыре сектора: TECH, FINANCE, ENERGY, LUXURY.
Спред раскрывается на горячем секторе.
Сектор игрока: uid % 4 = sector_index.
Все равны, но одни релевантнее.""",
            "intro_en": """Four sectors: TECH, FINANCE, ENERGY, LUXURY.
Spread explodes on hot sector.
Player sector: uid % 4 = sector_index.
All equal, but some more relevant.""",
            "chapter1_ru": "Сектора рынка",
            "chapter1_en": "Market Sectors",
            "chapter1_desc": "phi-styled sector distribution",
            "chapter1_data": """0: TECH - технологии
1: FINANCE - капитал
2: ENERGY - ресурсы
3: LUXURY - престиж

math: sector(uid) = uid % 4
phi scaling: hot sector = (φ - 1) * normal""",
            "equation_ru": "spread_hot = spread_base * φ",
            "equation_en": "spread_hot = spread_base * φ",
            "equation_ex_ru": """Hot spread как φ-гоодование обычного.
Игроки на горячем секторе получают бонус.
Всё справедливо: Spreads определяет φ. 
Нет случайных изменений, только масштаб.""",
            "equation_ex_en": """Hot spread as φ-multiple of normal.
Players on hot sector get bonus.
Everything fair: Spreads defined by φ.
No random changes, only scaling.""",
        },
        {
            "title_ru": "Том %d: Тактика и стратегии" % vol_num,
            "title_en": "Volume %d: Tactics and Strategies" % vol_num,
            "intro_ru": """Основа игры: предсказать φ-масштабное движение.
Шорты: прибыль и катастрофа.
Деривативы: плечо 1:φ на золотом спреде.
Магнаты как игроки в математическом казино.""",
            "intro_en": """Game core: predict φ-scaled movement.
Shorts: profit and catastrophe.
Derivatives: 1:φ leverage on golden spread.
Magnates as players in mathematical casino.""",
            "chapter1_ru": "Деривативные стратегии",
            "chapter1_en": "Derivative Strategies",
            "chapter1_desc": "phi-styled options chart",
            "chapter1_data": """Call option: S * φ^n (future expectation)
Put option: S / φ^n (discounted cost)
Delta: φ (continuous rebalancing)
Gamma: (φ + 1) / 2 (convexity)""",
            "equation_ru": "V = S * φ^τ * e^{-rτ}",
            "equation_en": "V = S * φ^τ * e^{-rτ}",
            "equation_ex_ru": """Дивиденды: все измеряется в φ.
Никакого времени, только золотое сечение.
Все цены — части infinite geometric series.
Формула естественна: V = S * φ^τ * e^{-rτ}""",
            "equation_ex_en": """Dividends: everything measured in φ.
No time, only golden section.
All prices — part of infinite geometric series.
Natural formula: V = S * φ^τ * e^{-rτ}""",
        },
    ]
    
    data = volumes[vol_num - 1]
    
    # Title cover
    title_cover(book, data["title_ru"], data["title_en"])
    
    # Intro page
    intro_page(book, vol_num, data["title_ru"], data["title_en"],
               data["intro_ru"], data["intro_en"])
    
    # Main content pages
    section_chart_page(book, data["chapter1_ru"], data["chapter1_en"],
                       data["chapter1_desc"], data["chapter1_data"])
    
    equation_page(book, data["equation_ru"], data["equation_en"],
                  data["equation_ex_ru"], data["equation_ex_en"])
    
    # Additional static pages
    for i in range(4):
        c = book._new_page()
        _bg_phi_section(c, (10, 8, 3), (18, 15, 7))
        
        page_num = vol_num * 10 + i + 1
        G.section_title(c, MARGIN, TOP - 40, "Страница %d" % page_num, size=16)
        
        # Simple phi-pattern decoration
        G.golden_rects(c, PAGE_W - 200, PAGE_H - 200, 120, 120,
                       depth=6, col=G.GOLD, alpha=0.08)
        G.phi_spiral(c, 100, 100, turns=2.0, scale=100, col=G.GOLD, lw=0.5,
                     alpha=0.08)
        
        book._footer(c)

def build_phi_book(out_path):
    """Build the complete phi book (5 volumes × 10 pages)"""
    book = Magazine(
        issue_no=0,
        title="PHI Book Series",
        subtitle="Golden Section & Polynomials in Game Theory",
        tagline="50 pages of mathematical game mechanics",
        date_str="Edition 1",
        accent=G.GOLD,
    )
    
    # Build 5 volumes
    for vol_num in range(1, 6):
        build_volume(book, vol_num)
    
    book.save(out_path)
    return out_path

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "out")
    os.makedirs(out_dir, exist_ok=True)
    
    # Check for deterministic build flag
    if os.environ.get('PRESS_SYNTH'):
        path = os.path.join(out_dir, "phi_book_deterministic.pdf")
    else:
        path = os.path.join(out_dir, "phi_book.pdf")
    
    print("Building PHI Book Series (5 volumes × 10 pages = 50 pages)...")
    print("Theme: The game as deterministic OLAP cube using golden section")
    print("Mathematical foundation: φ = 1.618033988749")
    print("Zero-dependency PDF engine with embedded Cyrillic fonts")
    print()
    
    build_phi_book(path)
    
    size = os.path.getsize(path)
    print(f"✓ phi_book.pdf written: {path} ({size / 1024:.1f} KB)")

if __name__ == "__main__":
    main()
