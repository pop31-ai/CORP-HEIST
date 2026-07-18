# -*- coding: utf-8 -*-
"""
build_issues.py - 10 CORP HEIST 'srochnye vypuski', po 4 stranicy kazhdyi,
na normalnom russkom (vstroennaya kirillica). Zapusk: python build_issues.py
"""

import os
from magazine import Magazine, MARGIN, CONTENT_W, COL_W
import phi_charts as G
import phi_data as D
from live_data import LiveData

OUT = os.path.join(os.path.dirname(__file__), "out")
DATE = "18 июля 2026"

# Shared data source: live server if reachable, else phi-synthetic fallback.
# Force synthetic with env PRESS_SYNTH=1 (used for reproducible offline builds).
DS = LiveData(force_synth=bool(os.environ.get("PRESS_SYNTH")))
SRC_TAG = DS.source


def _mk(seed):
    return DS.market_snapshot(seed)
def _sc(seed):
    return DS.sector_snapshot(seed)
def _cd(seed, n=34, start=100.0):
    return DS.candles(seed, n, start)
def _mg(seed, n=8):
    return DS.magnate_ladder(seed, n)


# ---------- chart draw factories ---------------------------------------
def f_candles(seed, sym, title=None):
    data = _cd(seed, 34, 100.0 * (1 + (seed % 5) * 0.1))
    return lambda c, x, y, w, h: G.candlestick(c, x, y, w, h, data,
                                               title=title or (sym + " / ЗОЛОТО"))


def f_area(seed, title):
    s = DS.phi_walk(seed, 40, 100.0, 0.04)
    return lambda c, x, y, w, h: G.area_chart(c, x, y, w, h, s, title=title)


def f_gauge(seed, title, label):
    frac = D.PhiRng(seed).next()
    return lambda c, x, y, w, h: G.gauge_panel(c, x, y, w, h, frac, title, label)


def f_heatmap(seed, title="ТЕПЛОКАРТА СЕКТОРОВ"):
    snap = _sc(seed)
    rows = [s["name"] for s in snap["sectors"]]
    cols = ["T1", "T2", "T3", "T4", "T5", "T6"]
    grid = []
    for r in rows:
        rr = D.PhiRng((hash(r) % 9991) + seed)
        grid.append([rr.next() * 100 - 40 for _ in cols])
    return lambda c, x, y, w, h: G.heatmap(c, x, y, w, h, rows, cols, grid, title=title)


def f_funnel(seed, title="ВОРОНКА ЛИКВИДАЦИЙ"):
    stages = DS.liquidation_stages(seed)
    return lambda c, x, y, w, h: G.funnel(c, x, y, w, h, stages, title=title)


def f_treemap(seed, title="TREEMAP КАПИТАЛОВ"):
    mags = _mg(seed, 7)
    pal = [G.GOLD, G.AMBER, G.CYAN, G.PURPLE, G.GREEN, G.RED, G.GREY]
    items = [(m["name"].split()[0], max(m["worth"], 1), pal[i])
             for i, m in enumerate(mags)]
    return lambda c, x, y, w, h: G.treemap(c, x, y, w, h, items, title=title)


def f_radar(seed, title="ПРОФИЛЬ МАГНАТА"):
    axes = ["РИСК", "ПЛЕЧО", "ТЕМП", "ХЕДЖ", "PHI", "ДОЛЯ"]
    r = D.PhiRng(seed)
    a = [0.4 + 0.55 * r.next() for _ in axes]
    b = [0.4 + 0.55 * r.next() for _ in axes]
    series = [("ЛИДЕР", a, G.GOLD), ("СРЕДНИЙ", b, G.CYAN)]
    return lambda c, x, y, w, h: G.radar(c, x, y, w, h, axes, series, title=title)


def f_waterfall(seed, title="ДЕКОМПОЗИЦИЯ PnL"):
    labels = ["БАЗА", "КОЛЛ", "ПУТ", "ХЕДЖ", "СКВИЗ", "КОМИС"]
    r = D.PhiRng(seed + 7)
    steps = []
    for lab in labels:
        d = (r.next() - 0.45) * 900 * G.PHI
        steps.append((lab, d))
    return lambda c, x, y, w, h: G.waterfall(c, x, y, w, h, steps,
                                             title=title, start=1000.0)


def f_bullet(seed, title="KPI МАРКЕТ-МЕЙКЕРА"):
    r = D.PhiRng(seed + 3)
    names = ["СПРЕД", "ОБЪЁМ", "ЗАЛИВКА", "PnL"]
    rows = []
    for nm in names:
        mv = 100.0
        tgt = 55 + 30 * r.next()
        act = 30 + 65 * r.next()
        rows.append((nm, act, tgt, mv))
    return lambda c, x, y, w, h: G.bullet(c, x, y, w, h, rows, title=title)


def f_donut(seed):
    snap = _sc(seed)
    cols = [G.CYAN, G.GOLD, G.AMBER, G.PURPLE]
    def _d(c, x, y, w, h):
        G.panel(c, x, y, w, h, fill=(12, 13, 26), border=G.GREY_DK, lw=0.8)
        G.section_title(c, x + 8, y + h - 16, "СЕКТОРА", size=10)
        r = min(w * 0.28, h * 0.34)
        G.golden_donut(c, x + w * 0.32, y + h * 0.45, r,
                       [abs(s["value"]) for s in snap["sectors"]],
                       [s["name"] for s in snap["sectors"]], cols, title="500")
        ly = y + h - 34
        for s, col in zip(snap["sectors"], cols):
            c.rect(x + w * 0.6, ly, 7, 7, fill=col)
            arr = "+" if s["chg"] >= 0 else ""
            c.text(x + w * 0.6 + 11, ly, "%s %s%.1f%%" % (s["name"], arr, s["chg"]),
                   size=7.5, font="UB", rgb=G.GREEN if s["chg"] >= 0 else G.RED)
            ly -= 13
    return _d


def f_magnates(seed):
    rows = _mg(seed, 7)
    def _d(c, x, y, w, h):
        G.panel(c, x, y, w, h, fill=(12, 13, 26), border=G.GREY_DK, lw=0.8)
        G.section_title(c, x + 8, y + h - 16, "МАГНАТЫ", size=10)
        G.hbars(c, x + 8, y + 8, w - 16, h - 30, rows)
    return _d


def f_sparks(seed, title="СПАРК-СЕТКА"):
    snap = _sc(seed)
    cols = [G.CYAN, G.GOLD, G.AMBER, G.PURPLE]
    def _d(c, x, y, w, h):
        G.panel(c, x, y, w, h, fill=(12, 13, 26), border=G.GREY_DK, lw=0.8)
        G.section_title(c, x + 8, y + h - 16, title, size=10)
        ch = (h - 30) / 4
        for i, s in enumerate(snap["sectors"]):
            sy = y + 8 + i * ch
            c.text(x + 8, sy + ch * 0.35, s["name"], size=7.5, font="UB", rgb=G.GREY)
            G.sparkline(c, x + 66, sy + 4, w - 120, ch - 8, s["spark"], col=cols[i])
            arr = "+" if s["chg"] >= 0 else ""
            c.text_right(x + w - 8, sy + ch * 0.35, "%s%.1f%%" % (arr, s["chg"]),
                         size=7.5, font="CB", rgb=G.GREEN if s["chg"] >= 0 else G.RED)
    return _d


def f_boss(seed):
    curve = DS.boss_curve(seed)
    def _d(c, x, y, w, h):
        G.panel(c, x, y, w, h, fill=(12, 13, 26), border=G.GREY_DK, lw=0.8)
        G.section_title(c, x + 8, y + h - 16, "БОСС: ФАЗЫ HP", size=10)
        G.hbars(c, x + 8, y + 8, w - 16, h - 30,
                [{"name": "Фаза %d" % b["phase"], "worth": b["hp"]} for b in curve],
                col=G.RED)
    return _d


def f_ladder(seed, title="PHI-СТЕПЕНИ"):
    vals = DS.phi_series(seed, 9)
    def _d(c, x, y, w, h):
        G.panel(c, x, y, w, h, fill=(12, 13, 26), border=G.GREY_DK, lw=0.8)
        G.section_title(c, x + 8, y + h - 16, title, size=10)
        G.hbars(c, x + 8, y + 8, w - 16, h - 30,
                [{"name": "phi^%d" % i, "worth": v} for i, v in enumerate(vals)],
                col=G.PURPLE, fmt=lambda v: "%.3f" % v)
    return _d


def f_compare(seed, title="ЛИДЕРЫ / АУТСАЙДЕРЫ"):
    mk = _mk(seed)
    ups = sorted(mk, key=lambda r: -r["chg"])[:3]
    downs = sorted(mk, key=lambda r: r["chg"])[:3]
    rows = [(u["sym"], u["chg"], d["chg"]) for u, d in zip(ups, downs)]
    return lambda c, x, y, w, h: G.compare_bars(c, x, y, w, h, rows, title=title)


def f_tiles(tiles):
    return lambda c, x, y, w, h: G.stat_tiles(c, x, y, w, h, tiles)


def hero_tape(seed):
    rows = _mk(seed)
    def _d(c, x, y, w, h):
        G.panel(c, x, y, w, h, fill=(12, 13, 26), border=G.GREY_DK, lw=0.8)
        half = (w - 12) / 2
        G.candlestick(c, x + 6, y + 30, half, h - 40, _cd(seed, 30), title=rows[0]["sym"])
        G.candlestick(c, x + 12 + half, y + 30, half, h - 40, _cd(seed + 3, 30), title=rows[5]["sym"])
        G.tape(c, x + 6, y + 6, w - 12, rows)
    return _d


def hero_crown(seed, name, worth):
    def _d(c, x, y, w, h):
        G.panel(c, x, y, w, h, fill=G.PANEL2, border=G.GOLD, lw=1.0)
        cx = x + w * 0.5
        G.crown(c, cx, y + h * 0.66, min(w, h) * 0.13)
        c.text_center(cx, y + h * 0.40, "МАГНАТ ГОДА", size=11, font="UB", rgb=G.GOLD, char_space=3)
        c.text_center(cx, y + h * 0.28, name, size=17, font="UB", rgb=G.GOLD_LT)
        c.text_center(cx, y + h * 0.16, "капитал: %s золота" % G.fmt_money(worth), size=10, font="CB", rgb=G.WHITE)
        G.tape(c, x + 8, y + 8, w - 16, _mk(seed)[:12])
    return _d


GLOSSARY = [
    ("PHI", "золотое сечение 1.618 — основа всех наград, урона и порогов."),
    ("СКВИЗ", "цена входа × PHI обнуляет маржу шорта."),
    ("ЦИКЛ ЦБ", "ставка колеблется между 1/PHI и PHI за ~2.6 часа."),
    ("КОРОНА", "артефакт магната года, редкость 5, ценность 1 000 000."),
]


def make(no, title, subtitle, accent, headline, deck, hero,
         kicker, art_head, paras, charts, quote, box,
         info_kicker, info_head, info_intro, tiles, back_lines):
    """Return an issue spec (data only); rendering is separate so both the
    standalone PDFs and the combined almanac can reuse it."""
    return dict(no=no, title=title, subtitle=subtitle, accent=accent,
                headline=headline, deck=deck, hero=hero, kicker=kicker,
                art_head=art_head, paras=paras, charts=charts, quote=quote,
                box=box, info_kicker=info_kicker, info_head=info_head,
                info_intro=info_intro, tiles=tiles, back_lines=back_lines)


def render_issue(m, spec, with_back=True):
    """Draw one issue's pages into an existing Magazine m."""
    m.accent = spec["accent"]
    m.title = spec["title"]
    m.subtitle = spec["subtitle"]
    m.issue_no = spec["no"]
    m.cover(spec["headline"], spec["deck"], hero_draw=spec["hero"])
    m.article(spec["kicker"], spec["art_head"], spec["paras"],
              charts=spec["charts"], pull_quote=spec["quote"], boxout=spec["box"])
    m.infographic_page(spec["info_kicker"], spec["info_head"], spec["tiles"],
                       intro=spec["info_intro"])
    if with_back:
        m.back_cover(spec["back_lines"], glossary=GLOSSARY)


def issue_magazine(spec):
    m = Magazine(spec["no"], spec["title"], spec["subtitle"],
                 "Журнал корпоративного грабежа",
                 "%s · %s" % (DATE, SRC_TAG), accent=spec["accent"])
    render_issue(m, spec, with_back=True)
    return m


# ---------- shared paragraphs (real Russian) ---------------------------
P_A = ("Золотое сечение не просто красиво. В экономике CORP HEIST каждая награда, "
       "каждый уровень и каждая просадка рынка масштабируются коэффициентом PHI, "
       "равным 1.618. Это создаёт рост, который ощущается естественным: не линейный, "
       "а спиральный, как раковина наутилуса.")
P_B = ("Игроки, понимающие PHI-кривую, получают преимущество. Пассивное дерево, "
       "артефакты и престиж растут по одному закону. Тот, кто выжидает и накапливает, "
       "собирает сложный золотой процент.")
P_C = ("Рынок реагирует на ставку Центробанка. Голубиная политика поднимает цены на "
       "PHI-дрейф вверх, ястребиная давит вниз. Трейдеры читают цикл и открывают "
       "позиции до разворота. Это не казино — это математика.")
P_D = ("Восемь ботов торгуют круглосуточно. Momentum- и revert-агенты наполняют ленту "
       "сделок, исполняют заявки и реагируют на флеш-крахи. Рынок никогда не спит.")


def build_all():
    issues = []
    issues.append(make(1, "PHI-РЫНОК", "Запуск Golden-500", G.GOLD,
        "Индекс Golden-500 стартует: рынок на золотом сечении",
        "Композитный PHI-взвешенный индекс объединяет 20 активов, IPO и M&A в одну свечную историю.",
        hero_tape(1), "АНАЛИТИКА", "Почему PHI управляет всем рынком",
        [P_A, P_B, P_C, P_D], [(f_candles(1, "ALPHA"), 150), (f_sparks(1), 130)],
        "Рост спиральный, а не линейный.",
        ("КЛЮЧ ДНЯ", ["PHI = 1.618033988749", "20 активов в индексе", "Свечи по 60·PHI секунд"]),
        "ДАННЫЕ", "Панель индекса Golden-500",
        "Полная картина рынка в шести золотых плитках.",
        [(f_tiles([("+6.9%", "ALPHA", G.GREEN), ("500", "АКТИВОВ", G.GOLD), ("1.618", "PHI", G.CYAN)]), 1),
         (f_donut(1), 1), (f_area(1, "ИНДЕКС"), 2),
         (f_compare(1), 1), (f_gauge(1, "ВОЛАТИЛЬНОСТЬ", "PHI-диапазон"), 1)],
        ["Индекс Golden-500 открыт.", "Торгуйте по золотому сечению.", "corp-heist / PHI PRESS"]))

    issues.append(make(2, "СЕКТОРА", "Ротация TECH → LUXURY", G.CYAN,
        "Секторная ротация: капитал бегает по четырём PHI-группам",
        "TECH, FINANCE, ENERGY и LUXURY делят рынок на золотые кварты.",
        f_donut(2), "СТРАТЕГИЯ", "Как ловить горячий сектор",
        [P_C, P_A, P_D, P_B], [(f_donut(2), 150), (f_sparks(2), 130)],
        "Горячий сектор притягивает поток, холодный разгружается.",
        ("СЕКТОРА", ["TECH — инновации", "FINANCE — банк и ЦБ", "ENERGY — рейд-топливо", "LUXURY — артефакты"]),
        "ДАННЫЕ", "Карта четырёх PHI-секторов",
        "Ротация видна по спаркам, весам долей и тепловой карте.",
        [(f_donut(2), 1), (f_sparks(2), 1), (f_heatmap(2), 2),
         (f_compare(2), 1), (f_gauge(2, "РОТАЦИЯ", "поток"), 1)],
        ["Следи за ротацией.", "Кварты золотого сечения.", "corp-heist / PHI PRESS"]))

    issues.append(make(3, "ШОРТЫ", "Анатомия сквиза", G.RED,
        "Короткая позиция и PHI-сквиз: как сгорают маржи",
        "Продажа в короткую даёт PHI-плечо, но цена входа × PHI запускает сквиз.",
        f_candles(3, "GAMMA", "GAMMA: зона сквиза"), "РИСК", "Шорты: прибыль и катастрофа",
        [P_B, P_C, P_A, P_D], [(f_candles(3, "GAMMA"), 150), (f_ladder(3, "МАРЖА ПО PHI"), 130)],
        "Цена входа умноженная на PHI запускает сквиз.",
        ("ПАРАМЕТРЫ", ["Маржа = 1/PHI", "Сквиз-мульт = PHI", "Комиссия = (PHI-1)/100"]),
        "ДАННЫЕ", "Механика короткой позиции",
        "Порог сквиза, кривая маржи и воронка ликвидаций.",
        [(f_tiles([("1/PHI", "МАРЖА", G.RED), ("×PHI", "СКВИЗ", G.AMBER), ("618", "КОМИССИЯ", G.GREY)]), 1),
         (f_gauge(3, "РИСК ШОРТА", "до сквиза"), 1), (f_funnel(3), 2),
         (f_ladder(3), 1), (f_compare(3), 1)],
        ["Шорт — не для слабых.", "PHI решает, кто выживет.", "corp-heist / PHI PRESS"]))

    issues.append(make(4, "ЦЕНТРОБАНК", "Цикл ставки PHI", G.AMBER,
        "Центробанк задаёт ритм: ставка колеблет весь рынок",
        "Глобальная PHI-ставка осциллирует между 1/PHI и PHI на цикле около 2.6 часа.",
        f_ladder(4, "СТАВКА: PHI-ЦИКЛ"), "МАКРО", "Читаем цикл Центробанка",
        [P_C, P_B, P_D, P_A], [(f_sparks(4, "ДРЕЙФ РЫНКА"), 150), (f_ladder(4), 130)],
        "Голубиная политика поднимает цены, ястребиная давит.",
        ("ЦИКЛ", ["Диапазон [1/PHI, PHI]", "Период ~ 3600·PHI·PHI", "Влияет на кредиты и бонды"]),
        "ДАННЫЕ", "Осциллятор ставки ЦБ",
        "Как ставка тянет кредиты, бонды и хедж; тепловая карта секторов.",
        [(f_gauge(4, "СТАВКА СЕЙЧАС", "1/PHI..PHI"), 1), (f_tiles([("2.6ч", "ЦИКЛ", G.AMBER), ("PHI", "ПИК", G.GOLD)]), 1),
         (f_heatmap(4, "РЕАКЦИЯ СЕКТОРОВ"), 2), (f_ladder(4), 1), (f_sparks(4), 1)],
        ["Слушай Центробанк.", "Ставка = ритм PHI.", "corp-heist / PHI PRESS"]))

    issues.append(make(5, "МАГНАТЫ", "Рейтинг богатства", G.GOLD,
        "Лестница магнатов: кто возглавляет PHI-пирамиду капитала",
        "Каждый ранг отстоит от следующего на коэффициент PHI.",
        f_magnates(5), "РЕЙТИНГ", "Пирамида богатства по золотому сечению",
        [P_A, P_B, P_C, P_D], [(f_magnates(5), 160), (f_ladder(5, "ШАГ РАНГА"), 120)],
        "Каждый ранг отстоит от следующего на PHI.",
        ("КОРОНА", ["PHI_CROWN, редкость 5", "Ценность 1 000 000", "Зал славы сезона"]),
        "ДАННЫЕ", "Топ капиталистов сезона",
        "Разрыв между рангами — ровно PHI. Ниже — treemap долей.",
        [(f_magnates(5), 2), (f_tiles([("×PHI", "ШАГ", G.GOLD), ("8", "РАНГОВ", G.CYAN)]), 1),
         (f_gauge(5, "ДО ВЕРШИНЫ", "прогресс"), 1), (f_treemap(5), 2)],
        ["Взберись на вершину.", "Корона ждёт лучшего.", "corp-heist / PHI PRESS"]))

    issues.append(make(6, "МАГНАТ ГОДА", "Коронация сезона", G.GOLD,
        "Магнат года коронован: золотая корона сезона найдена",
        "Лучший капиталист получает PHI-корону, артефакт категории 11 и место в зале славы.",
        hero_crown(6, _mg(6, 1)[0]["name"], _mg(6, 1)[0]["worth"]),
        "СОБЫТИЕ", "Как заработать корону сезона",
        [P_B, P_A, P_D, P_C], [(f_magnates(6), 160), (f_candles(6, "OMEGA"), 120)],
        "Вечное место в зале славы CORP HEIST.",
        ("НАГРАДА", ["PHI-корона сезона", "Категория 11, редкость 5", "Бонус к боевой мощи"]),
        "ДАННЫЕ", "Путь к короне",
        "Что нужно, чтобы взойти на трон; профиль лидера в радаре.",
        [(hero_crown(6, _mg(6, 1)[0]["name"], _mg(6, 1)[0]["worth"]), 2),
         (f_magnates(6), 1), (f_gauge(6, "ДО КОРОНЫ", "сезон"), 1), (f_radar(6), 2)],
        ["Один трон на сезон.", "Стань магнатом года.", "corp-heist / PHI PRESS"]))

    issues.append(make(7, "ДЕРИВАТИВЫ", "Опционы на PHI-страйки", G.PURPLE,
        "Опционы Golden-500: PHI-размеченные страйки и таймер",
        "Колл и пут опционы со страйками через PHI и срасчётом по таймеру.",
        f_ladder(7, "СТРАЙКИ ПО PHI"), "ИНСТРУМЕНТ", "Деривативы: плечо на золоте",
        [P_D, P_C, P_A, P_B], [(f_candles(7, "SIGMA"), 150), (f_ladder(7), 130)],
        "Выплата больше PHI премии открывает знак PHI-OPTION.",
        ("ОПЦИОНЫ", ["Экспирация 60·PHI·PHI", "Размер позиции = PHI", "Страйки через PHI"]),
        "ДАННЫЕ", "Сетка страйков и премий",
        "PHI-шаг между страйками, порог значка и декомпозиция PnL.",
        [(f_ladder(7, "СТРАЙКИ"), 1), (f_gauge(7, "PHI-OPTION", "порог"), 1),
         (f_waterfall(7), 2), (f_tiles([("×PHI", "ВЫПЛАТА", G.PURPLE), ("PHI²", "ЭКСПИРА", G.CYAN)]), 1),
         (f_area(7, "ПРЕМИЯ"), 1)],
        ["Плечо на золоте.", "Опцион PHI ждёт.", "corp-heist / PHI PRESS"]))

    issues.append(make(8, "БОТЫ", "Живая лента рынка", G.GREEN,
        "Восемь PHI-ботов держат рынок живым круглосуточно",
        "Momentum и revert агенты исполняют заявки, наполняют ленту и реагируют на флеш-крахи.",
        hero_tape(8), "ТЕХНИКА", "Как работают торговые боты",
        [P_D, P_A, P_C, P_B], [(f_candles(8, "DELTA"), 150), (f_sparks(8, "АКТИВНОСТЬ БОТОВ"), 130)],
        "Рынок никогда не спит — восемь агентов на страже.",
        ("БОТЫ", ["N = 8 агентов", "Агрессия = PHI - 1", "Лента до 40 строк"]),
        "ДАННЫЕ", "Пульс восьми ботов",
        "Их сделки видны в бегущей строке всегда.",
        [(f_tiles([("8", "БОТОВ", G.GREEN), ("PHI-1", "АГРЕССИЯ", G.CYAN), ("40", "ЛЕНТА", G.GREY)]), 1),
         (f_gauge(8, "АКТИВНОСТЬ", "рынок"), 1), (hero_tape(8), 2),
         (f_sparks(8), 1), (f_area(8, "ОБЪЁМ"), 1)],
        ["Боты не спят.", "Лента течёт всегда.", "corp-heist / PHI PRESS"]))

    issues.append(make(9, "ГИЛЬДИИ", "Небоскрёбы и войны", G.CYAN,
        "Гильдейские войны и небоскрёбы: коллективный PHI-бонус",
        "Две корпорации гонятся за общим боссом, приз делится по PHI.",
        f_boss(9), "КООП", "Сила гильдии в золотом сечении",
        [P_B, P_D, P_A, P_C], [(f_boss(9), 150), (f_magnates(9), 130)],
        "Приз делится по PHI — счёт идёт на секунды.",
        ("ГИЛЬДИЯ", ["Небоскрёб: общая стройка", "Бонус к урону всем", "Приз войны делится PHI"]),
        "ДАННЫЕ", "Фазы босса и приз войны",
        "HP босса падает золотыми полосами; воронка урона по фазам.",
        [(f_boss(9), 2), (f_tiles([("×PHI", "БОНУС", G.CYAN), ("2", "КОРПЫ", G.GOLD)]), 1),
         (f_gauge(9, "СТРОЙКА", "небоскрёб"), 1), (f_funnel(9, "ВОРОНКА ФАЗ"), 2)],
        ["Сила в гильдии.", "Небоскрёб растёт по PHI.", "corp-heist / PHI PRESS"]))

    issues.append(make(10, "МАРКЕТ-МЕЙКИНГ", "Спред на PHI", G.GOLD,
        "Маркет-мейкинг с плечом: ставь бид, продавай на PHI-спред",
        "Паркуйте заявку, покупайте на пересечении, автопродажа на бид·PHI.",
        hero_tape(10), "ПРО", "Маркет-мейкер: золотой спред",
        [P_C, P_A, P_D, P_B], [(f_candles(10, "PSI"), 150), (f_ladder(10, "СПРЕД PHI"), 130)],
        "Плечо до PHI, но флеш-крах запускает маржин-колл.",
        ("MM", ["Спред = PHI", "Макс плечо = PHI", "До 8 заявок"]),
        "ДАННЫЕ", "Экономика маркет-мейкера",
        "Спред, плечо, риск маржин-колла и KPI против цели.",
        [(f_tiles([("PHI", "СПРЕД", G.GOLD), ("×PHI", "ПЛЕЧО", G.CYAN), ("8", "ЗАЯВОК", G.GREY)]), 1),
         (f_gauge(10, "ЗАГРУЗКА", "плечо"), 1), (f_bullet(10), 2),
         (f_ladder(10), 1), (f_compare(10), 1)],
        ["Лови спред.", "Золото на пересечении.", "corp-heist / PHI PRESS"]))

    return issues


NAMES = [
    "vypusk_01_phi_rynok.pdf", "vypusk_02_sektora.pdf", "vypusk_03_shorty.pdf",
    "vypusk_04_centrobank.pdf", "vypusk_05_magnaty.pdf", "vypusk_06_magnat_goda.pdf",
    "vypusk_07_derivativy.pdf", "vypusk_08_boty.pdf", "vypusk_09_gildii.pdf",
    "vypusk_10_market_meiking.pdf",
]


ALMANAC_NAME = "almanac_full.pdf"


def build_almanac(specs):
    """One big PDF: title page + contents + all 10 issues (no per-issue back)."""
    m = Magazine(0, "АЛЬМАНАХ", "Полное собрание",
                 "Журнал корпоративного грабежа",
                 "%s · %s" % (DATE, SRC_TAG), accent=G.GOLD)
    # --- title page ---
    from magazine import MARGIN as _M
    from pdfkit_phi import PAGE_W, PAGE_H
    c = m._new_page()
    c.vgrad(0, 0, PAGE_W, PAGE_H, (26, 21, 8), G.INK, bands=64)
    G.phi_spiral(c, PAGE_W / 2, PAGE_H / 2, turns=4.6, scale=2.6,
                 col=G.GOLD, lw=0.9, alpha=0.5)
    c.text_center(PAGE_W / 2, PAGE_H - 200, "CORP HEIST", size=44, font="UB",
                  rgb=G.GOLD, char_space=5)
    c.text_center(PAGE_W / 2, PAGE_H - 240, "PHI PRESS · АЛЬМАНАХ", size=16,
                  font="UB", rgb=G.GOLD_LT, char_space=3)
    c.text_center(PAGE_W / 2, PAGE_H - 268,
                  "Полное собрание десяти срочных выпусков", size=11,
                  font="U", rgb=G.WHITE)
    c.star(PAGE_W / 2, PAGE_H / 2, 46, 46 * 0.618, 5,
           fill=G.GOLD_LT, stroke=G.GOLD)
    c.text_center(PAGE_W / 2, 90, "%s · источник: %s" % (DATE, SRC_TAG),
                  size=9, font="U", rgb=G.GREY, char_space=1)
    m._footer(c)
    # --- contents page ---
    c = m._new_page()
    c.rect(_M, PAGE_H - _M - 4, 20, 4, fill=G.GOLD)
    c.text(_M, PAGE_H - _M - 20, "СОДЕРЖАНИЕ", size=9, font="UB",
           rgb=G.GOLD, char_space=2)
    c.text(_M, PAGE_H - _M - 48, "Десять выпусков", size=24, font="UB",
           rgb=G.GOLD_LT)
    cy = PAGE_H - _M - 90
    for i, sp in enumerate(specs):
        page_start = 3 + i * 3  # title+contents = 2 pages, then 3 per issue
        c.rect(_M, cy, 8, 8, fill=sp["accent"])
        c.text(_M + 16, cy, "#%02d  %s" % (sp["no"], sp["title"]),
               size=12, font="UB", rgb=G.WHITE)
        c.text(_M + 200, cy, sp["subtitle"], size=10, font="U", rgb=G.GREY)
        c.text_right(PAGE_W - _M, cy, "стр. %d" % page_start, size=10,
                     font="CB", rgb=sp["accent"])
        c.line(_M + 16, cy - 4, PAGE_W - _M, cy - 4, rgb=G.GREY_DK, lw=0.3)
        cy -= 30
    m._footer(c)
    # --- all issues (3 pages each: cover + article + infographic) ---
    for sp in specs:
        render_issue(m, sp, with_back=False)
    return m


def main():
    os.makedirs(OUT, exist_ok=True)
    specs = build_all()
    total = 0
    for sp, name in zip(specs, NAMES):
        m = issue_magazine(sp)
        path = os.path.join(OUT, name)
        m.save(path)
        sz = os.path.getsize(path)
        total += sz
        print("  [OK] %-32s %7d bytes" % (name, sz))
    alm = build_almanac(specs)
    apath = os.path.join(OUT, ALMANAC_NAME)
    alm.save(apath)
    asz = os.path.getsize(apath)
    total += asz
    print("  [OK] %-32s %7d bytes  (%d стр.)"
          % (ALMANAC_NAME, asz, len(alm.doc.pages)))
    print("Gotovo: 10 vypuskov + almanac, %d bytes (istochnik: %s)"
          % (total, SRC_TAG))


if __name__ == "__main__":
    main()
