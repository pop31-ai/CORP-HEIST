"""
bible.py - "Библия φ-экономики" (BIBLE of the PHI economy).

A glossy, multi-chapter reference BOOK built on the exact same zero-dependency
PDF engine as the press magazine (pdfkit_phi + phi_charts + magazine +
hero_scenes). Every formula and constant is imported live from market_cube so
the book is authoritative and can never drift from the running game.

Run:
    python bible.py                 -> out/bible.pdf
    PRESS_SYNTH=1 python bible.py   -> deterministic build (CI)

The PDF is a print-grade artefact and is gitignored (out/*.pdf); only this
generator lives in git. It is NOT served by the live site.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from magazine import (Magazine, MARGIN, CONTENT_W, COL_W, PAGE_W, PAGE_H,
                      TOP, BOTTOM)
import phi_charts as G
import hero_scenes as HS
import market_cube as MC

PHI = 1.618033988749


def _q16(v):
    return "%d/65536 = %.9f" % (v, v / 65536.0)


def _fmt_secs(s):
    d = s // (24 * 3600)
    return "%d c = %d дн." % (s, d)


CONST_ROWS = [
    ("φ (PHI_Q16)", _q16(MC.PHI_Q16), "Всё в игре масштабируется золотым сечением"),
    ("GENESIS", "%d" % MC.GENESIS, "Начало эпохи 0 (запуск мира, ~2026)"),
    ("EPOCH_LEN", _fmt_secs(MC.EPOCH_LEN), "Одна эпоха = технологический апгрейд"),
    ("WEEK_LEN", _fmt_secs(MC.WEEK_LEN), "Неделя — «свободное окно», сшивается на стыке"),
    ("TREND_WEEKS", "%d" % MC.TREND_WEEKS, "K: глубина взгляда тренда живого уровня"),
    ("M_WELFARE", "%d" % MC.M_WELFARE, "Ось-мера: уровень благосостояния игрока"),
]


def _bg_deep(c):
    c.vgrad(0, 0, PAGE_W, PAGE_H, (16, 13, 6), G.INK, bands=60)


def title_page(book):
    c = book.doc.page()
    _bg_deep(c)
    G.phi_spiral(c, PAGE_W / 2, PAGE_H / 2, turns=5.0, scale=2.6,
                 col=G.GOLD, lw=0.7, alpha=0.20)
    G.golden_rects(c, PAGE_W / 2 - 130, PAGE_H - 300, 260, 260,
                   depth=9, col=G.GOLD, alpha=0.08)
    c.text_center(PAGE_W / 2, PAGE_H - 170, "CORP HEIST", size=20,
                  font="U", rgb=G.GREY, char_space=8)
    c.text_center(PAGE_W / 2, PAGE_H - 260, "БИБЛИЯ", size=62,
                  font="UB", rgb=G.GOLD_LT, char_space=4)
    c.text_center(PAGE_W / 2, PAGE_H - 320, "φ-ЭКОНОМИКИ", size=40,
                  font="UB", rgb=G.GOLD, char_space=6)
    c.line(PAGE_W / 2 - 120, PAGE_H - 350, PAGE_W / 2 + 120, PAGE_H - 350,
           rgb=G.GOLD, lw=1.0)
    c.text_center(PAGE_W / 2, PAGE_H - 380,
                  "Полный свод законов рынка, построенного на золотом сечении",
                  size=11, font="U", rgb=G.WHITE)
    c.text_center(PAGE_W / 2, 120, "φ = %.12f" % PHI, size=12,
                  font="CB", rgb=G.GOLD)
    c.text_center(PAGE_W / 2, 96, "PHI PRESS  ·  издание для магнатов",
                  size=8, font="U", rgb=G.GREY, char_space=2)


def toc_page(book, chapters):
    c = book._new_page()
    G.section_title(c, MARGIN, TOP - 30, "ОГЛАВЛЕНИЕ", size=20)
    c.line(MARGIN, TOP - 40, PAGE_W - MARGIN, TOP - 40, rgb=G.GREY_DK, lw=0.6)
    y = TOP - 78
    for i, (num, title, _scene) in enumerate(chapters, 1):
        c.text(MARGIN, y, "%02d" % i, size=16, font="UB", rgb=G.GOLD)
        c.text(MARGIN + 44, y, title, size=13, font="U", rgb=G.WHITE)
        c.text_right(PAGE_W - MARGIN, y, num, size=10, font="C", rgb=G.GREY)
        y -= 34
    book._footer(c)


def chapter_cover(book, num, title, subtitle, hero):
    c = book._new_page()
    _bg_deep(c)
    hero(c, MARGIN, MARGIN + 40, CONTENT_W, (TOP - MARGIN - 140) * 0.5)
    c.rect(MARGIN, TOP - 4, 20, 4, fill=G.GOLD)
    c.text(MARGIN, TOP - 26, "ГЛАВА %02d" % num, size=11, font="UB",
           rgb=G.GOLD, char_space=3)
    for i, ln in enumerate(book._wrap(title, 24, "UB")):
        c.text(MARGIN, TOP - 56 - i * 30, ln, size=27, font="UB",
               rgb=G.GOLD_LT)
    c.paragraph(MARGIN, TOP - 120, subtitle, size=11, font="U",
                rgb=G.WHITE, width=CONTENT_W, leading=15)
    book._footer(c)


def build(out_path):
    book = Magazine(
        issue_no=0,
        title="Библия φ-экономики",
        subtitle="СВОД ЗАКОНОВ РЫНКА",
        tagline="ЗОЛОТОЕ СЕЧЕНИЕ ПРАВИТ ВСЕМ",
        date_str="ИЗДАНИЕ I",
        accent=G.GOLD,
    )

    chapters = [
        ("Гл.1", "Золотое сечение — корень мира", HS.scene_market_galaxy(1)),
        ("Гл.2", "Куб рынка: оси и меры", HS.scene_sector_prism(2)),
        ("Гл.3", "Цены, эпохи и недельный шов", HS.scene_cb_temple(4)),
        ("Гл.4", "Благосостояние из координат", HS.scene_crown_throne(6, name="МАГНАТ", worth=0)),
        ("Гл.5", "Сектора и тикеры", HS.scene_guild_towers(9)),
    ]

    title_page(book)
    toc_page(book, chapters)

    # ---- Chapter 1: PHI -------------------------------------------------
    chapter_cover(book, 1, "Золотое сечение — корень мира",
                  "Одно число φ задаёт масштаб всего: цен, времени, "
                  "благосостояния. Здесь — почему и как оно вшито в целых "
                  "числах ради бит-в-бит совпадения Python и JavaScript.",
                  HS.scene_market_galaxy(1))
    book.article(
        "ОСНОВА", "Почему именно φ",
        [
            "Философия мира проста: ни одна величина не растёт линейно. "
            "Всё дышит золотым сечением φ ≈ 1.618. Рынок, время эпох, "
            "уровень жизни игрока — всё умножается и делится на φ.",
            "Чтобы расчёт был детерминированным на сервере (Python) и в "
            "браузере (JavaScript) до последнего бита, φ хранится не как "
            "дробь с плавающей точкой, а как целое: PHI_Q16 = %d, то есть "
            "φ, умноженное на 65536." % MC.PHI_Q16,
            "Любое умножение на φ — это (x * PHI_Q16) >> 16 с целочисленным "
            "сдвигом. Никаких float, никакого sin в рантайме ядра. Оба "
            "языка дают идентичный результат, что подтверждают 2071 "
            "проверок паритета в CI.",
        ],
        charts=[
            (lambda c, x, y, w, h: G.stat_tiles(c, x, y, w, h, [
                ("φ", "золотое сечение", G.GOLD),
                ("Q16", "целое ×65536", G.CYAN),
                ("2071", "проверок паритета", G.GREEN),
            ]), 120),
            (lambda c, x, y, w, h: G.area_chart(
                c, x, y, w, h,
                [round(100 * PHI ** (i / 3.0)) for i in range(12)],
                col=G.GOLD, title="Рост по степеням φ"), 130),
        ],
        pull_quote="«Линейного роста не существует. Есть только φ.»",
        boxout=("ЗАКОН 1", [
            "φ = %.9f" % PHI,
            "×φ  ≡  (x·%d) >> 16" % MC.PHI_Q16,
            "Ядро — только целые",
        ]),
    )

    # ---- Chapter 2: the cube -------------------------------------------
    chapter_cover(book, 2, "Куб рынка: оси и меры",
                  "market_cube — детерминированный OLAP-куб. У каждой "
                  "точки есть координаты по осям и набор мер. Ничего не "
                  "хранится «как число» — всё вычисляется из координат.",
                  HS.scene_sector_prism(2))
    book.infographic_page(
        "МОДЕЛЬ", "Оси и меры куба",
        [
            (lambda c, x, y, w, h: G.table(
                c, x, y, w, h,
                ["Константа", "Значение", "Смысл"],
                [(r[0], r[1], r[2]) for r in CONST_ROWS],
                title="Константы ядра", aligns=["l", "l", "l"],
                col_weights=[1.1, 1.4, 2.2]), 2),
            (lambda c, x, y, w, h: G.stat_tiles(c, x, y, w, h, [
                ("MKT", "рынок", G.GOLD),
                ("BOSS", "боссы", G.RED),
                ("AUC", "аукцион", G.CYAN),
            ]), 1),
            (lambda c, x, y, w, h: G.stat_tiles(c, x, y, w, h, [
                ("PWR", "власть", G.VIOLET if hasattr(G, "VIOLET") else G.AMBER),
                ("PLAYER", "игрок", G.GREEN),
                ("×WELFARE", "мера %d" % MC.M_WELFARE, G.GOLD_LT),
            ]), 1),
        ],
        intro="Куб адресуется координатами по осям MKT / BOSS / AUC / PWR / "
              "PLAYER; на пересечении лежат меры, среди которых WELFARE — "
              "благосостояние. Значение не хранится, а выводится формулой.",
    )

    # ---- Chapter 3: prices/time ----------------------------------------
    chapter_cover(book, 3, "Цены, эпохи и недельный шов",
                  "Время нарезано на эпохи по 90 дней и недели по 7. На "
                  "стыке недели рынок «сшивается», чтобы свободное окно не "
                  "ломало непрерывность цены.",
                  HS.scene_cb_temple(4))
    book.article(
        "ВРЕМЯ", "Как течёт цена",
        [
            "Отсчёт мира начинается в GENESIS = %d. Эпоха длится %d дней — "
            "это «технологический апгрейд», меняющий базовые уровни. "
            "Внутри эпохи неделя (%d дней) задаёт ритм."
            % (MC.GENESIS, MC.EPOCH_LEN // 86400, MC.WEEK_LEN // 86400),
            "Тренд живого уровня смотрит на TREND_WEEKS = %d недели назад. "
            "Это сглаживает шум, но сохраняет реакцию на реальные сдвиги "
            "спроса." % MC.TREND_WEEKS,
            "На стыке недели значения аккуратно «подшиваются»: свободное "
            "окно не создаёт разрыва цены. Свеча благосостояния и котировки "
            "остаются непрерывными.",
        ],
        charts=[
            (lambda c, x, y, w, h: G.candlestick(
                c, x, y, w, h,
                [{"o": 100, "h": 108, "l": 96, "c": 104},
                 {"o": 104, "h": 112, "l": 101, "c": 110},
                 {"o": 110, "h": 118, "l": 107, "c": 109},
                 {"o": 109, "h": 121, "l": 108, "c": 119}],
                title="Свеча благосостояния"), 140),
            (lambda c, x, y, w, h: G.waterfall(
                c, x, y, w, h,
                [("эпоха", 40), ("тренд", 18), ("шов", -6), ("итог", 0)],
                title="Из чего цена", start=100), 120),
        ],
        boxout=("ЗАКОН 3", [
            "эпоха = %d дн." % (MC.EPOCH_LEN // 86400),
            "неделя = %d дн." % (MC.WEEK_LEN // 86400),
            "тренд назад = %d нед." % MC.TREND_WEEKS,
        ]),
    )

    # ---- Chapter 4: welfare --------------------------------------------
    chapter_cover(book, 4, "Благосостояние из координат",
                  "WELFARE (мера %d) не лежит в базе. Оно вычисляется из "
                  "координат игрока в кубе — значит, воспроизводимо и "
                  "проверяемо кем угодно." % MC.M_WELFARE,
                  HS.scene_crown_throne(6, name="МАГНАТ", worth=0))
    book.article(
        "ИГРОК", "Уровень жизни как функция",
        [
            "Благосостояние игрока — это не сохранённое число, а функция от "
            "его положения в кубе: сектор, капитал, эпоха, тренд. Одни и те "
            "же координаты всегда дают один и тот же уровень.",
            "Такой подход честен: любой может пересчитать свой WELFARE и "
            "получить тот же ответ, что и сервер. Расхождений нет — ядро "
            "целочисленное, а формула открыта.",
            "На карточке игрока рисуется свеча благосостояния и история "
            "куба прямо на Canvas, а PNG сохраняется в браузере без нагрузки "
            "на сервер.",
        ],
        charts=[
            (lambda c, x, y, w, h: G.gauge_panel(
                c, x, y, w, h, 0.618, "WELFARE", "уровень φ", col=G.GOLD), 130),
            (lambda c, x, y, w, h: G.area_chart(
                c, x, y, w, h,
                [round(60 + 30 * (i % 5)) for i in range(14)],
                col=G.GREEN, title="История благосостояния"), 120),
        ],
        pull_quote="«Твой уровень жизни — это твои координаты. И ничего кроме.»",
        boxout=("ЗАКОН 4", [
            "WELFARE = f(координаты)",
            "не хранится — считается",
            "мера №%d" % MC.M_WELFARE,
        ]),
    )

    # ---- Chapter 5: sectors --------------------------------------------
    sect_rows = [(str(k), v, "сектор игрока = uid %% 4 == %s" % k)
                 for k, v in sorted(MC.SECTOR_TICKERS.items())]
    chapter_cover(book, 5, "Сектора и тикеры",
                  "Четыре сектора делят рынок. Сектор игрока определяется "
                  "детерминированно из его uid, а горячий сектор ловится по "
                  "золотому спреду.",
                  HS.scene_guild_towers(9))
    book.infographic_page(
        "РЫНОК", "Четыре сектора",
        [
            (lambda c, x, y, w, h: G.table(
                c, x, y, w, h,
                ["#", "Тикер", "Правило"],
                sect_rows, title="SECTOR_TICKERS",
                aligns=["c", "l", "l"], col_weights=[0.5, 1.2, 2.5]), 2),
            (lambda c, x, y, w, h: G.stat_tiles(c, x, y, w, h, [
                (str(len(MC.SECTOR_TICKERS)), "сектора", G.GOLD),
                ("uid%4", "выбор сектора", G.CYAN),
                ("φ", "золотой спред", G.GOLD_LT),
            ]), 2),
        ],
        intro="Сектор игрока = uid mod 4. Это стабильно и проверяемо. "
              "Горячий сектор ищут там, где спред раскрывается по φ.",
    )

    # ---- back cover -----------------------------------------------------
    book.back_cover(
        [
            "БИБЛИЯ φ-ЭКОНОМИКИ",
            "Свод законов рынка CORP HEIST",
            "Всё вычислимо. Всё воспроизводимо.",
        ],
        glossary=[
            ("φ", "золотое сечение ≈ 1.618; масштаб всего в мире"),
            ("Куб", "market_cube: OLAP-модель осей и мер"),
            ("WELFARE", "благосостояние игрока, мера №%d" % MC.M_WELFARE),
            ("Эпоха", "%d дней, технологический апгрейд" % (MC.EPOCH_LEN // 86400)),
            ("Паритет", "бит-в-бит совпадение Python и JavaScript"),
        ],
    )

    book.save(out_path)
    return out_path


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "out")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "bible.pdf")
    build(path)
    size = os.path.getsize(path)
    print("bible.pdf written: %s (%d bytes, %.1f KB)" % (path, size, size / 1024.0))


if __name__ == "__main__":
    main()
