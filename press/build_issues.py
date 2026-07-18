# -*- coding: utf-8 -*-
"""
build_issues.py - 10 CORP HEIST 'srochnye vypuski', po 4 stranicy kazhdyi,
na normalnom russkom (vstroennaya kirillica). Zapusk: python build_issues.py
"""

import os
from magazine import Magazine, MARGIN, CONTENT_W, COL_W
import phi_charts as G
import phi_data as D

OUT = os.path.join(os.path.dirname(__file__), "out")
DATE = "18 июля 2026"


# ---------- chart draw factories ---------------------------------------
def f_candles(seed, sym, title=None):
    data = D.candles(seed, 34, 100.0 * (1 + (seed % 5) * 0.1))
    return lambda c, x, y, w, h: G.candlestick(c, x, y, w, h, data,
                                               title=title or (sym + " / ЗОЛОТО"))


def f_area(seed, title):
    s = D.phi_walk(seed, 40, 100.0, 0.04)
    return lambda c, x, y, w, h: G.area_chart(c, x, y, w, h, s, title=title)


def f_gauge(seed, title, label):
    frac = D.PhiRng(seed).next()
    return lambda c, x, y, w, h: G.gauge_panel(c, x, y, w, h, frac, title, label)


def f_donut(seed):
    snap = D.sector_snapshot(seed)
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
    rows = D.magnate_ladder(seed, 7)
    def _d(c, x, y, w, h):
        G.panel(c, x, y, w, h, fill=(12, 13, 26), border=G.GREY_DK, lw=0.8)
        G.section_title(c, x + 8, y + h - 16, "МАГНАТЫ", size=10)
        G.hbars(c, x + 8, y + 8, w - 16, h - 30, rows)
    return _d


def f_sparks(seed, title="СПАРК-СЕТКА"):
    snap = D.sector_snapshot(seed)
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
    curve = D.boss_curve(seed)
    def _d(c, x, y, w, h):
        G.panel(c, x, y, w, h, fill=(12, 13, 26), border=G.GREY_DK, lw=0.8)
        G.section_title(c, x + 8, y + h - 16, "БОСС: ФАЗЫ HP", size=10)
        G.hbars(c, x + 8, y + 8, w - 16, h - 30,
                [{"name": "Фаза %d" % b["phase"], "worth": b["hp"]} for b in curve],
                col=G.RED)
    return _d


def f_ladder(seed, title="PHI-СТЕПЕНИ"):
    vals = D.phi_series(seed, 9)
    def _d(c, x, y, w, h):
        G.panel(c, x, y, w, h, fill=(12, 13, 26), border=G.GREY_DK, lw=0.8)
        G.section_title(c, x + 8, y + h - 16, title, size=10)
        G.hbars(c, x + 8, y + 8, w - 16, h - 30,
                [{"name": "phi^%d" % i, "worth": v} for i, v in enumerate(vals)],
                col=G.PURPLE, fmt=lambda v: "%.3f" % v)
    return _d


def f_compare(seed, title="ЛИДЕРЫ / АУТСАЙДЕРЫ"):
    mk = D.market_snapshot(seed)
    ups = sorted(mk, key=lambda r: -r["chg"])[:3]
    downs = sorted(mk, key=lambda r: r["chg"])[:3]
    rows = [(u["sym"], u["chg"], d["chg"]) for u, d in zip(ups, downs)]
    return lambda c, x, y, w, h: G.compare_bars(c, x, y, w, h, rows, title=title)


def f_tiles(tiles):
    return lambda c, x, y, w, h: G.stat_tiles(c, x, y, w, h, tiles)


def hero_tape(seed):
    rows = D.market_snapshot(seed)
    def _d(c, x, y, w, h):
        G.panel(c, x, y, w, h, fill=(12, 13, 26), border=G.GREY_DK, lw=0.8)
        half = (w - 12) / 2
        G.candlestick(c, x + 6, y + 30, half, h - 40, D.candles(seed, 30), title=rows[0]["sym"])
        G.candlestick(c, x + 12 + half, y + 30, half, h - 40, D.candles(seed + 3, 30), title=rows[5]["sym"])
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
        G.tape(c, x + 8, y + 8, w - 16, D.market_snapshot(seed)[:12])
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
    m = Magazine(no, title, subtitle, "Журнал корпоративного грабежа", DATE, accent=accent)
    m.cover(headline, deck, hero_draw=hero)
    m.article(kicker, art_head, paras, charts=charts, pull_quote=quote, boxout=box)
    m.infographic_page(info_kicker, info_head, tiles, intro=info_intro)
    m.back_cover(back_lines, glossary=GLOSSARY)
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
        "Ротация видна по спаркам и весам долей.",
        [(f_donut(2), 1), (f_sparks(2), 1), (f_area(2, "ГОРЯЧИЙ СЕКТОР"), 2),
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
        "Порог сквиза и кривая маржи в цифрах.",
        [(f_tiles([("1/PHI", "МАРЖА", G.RED), ("×PHI", "СКВИЗ", G.AMBER), ("618", "КОМИССИЯ", G.GREY)]), 1),
         (f_gauge(3, "РИСК ШОРТА", "до сквиза"), 1), (f_candles(3, "GAMMA"), 2),
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
        "Как ставка тянет кредиты, бонды и хедж.",
        [(f_gauge(4, "СТАВКА СЕЙЧАС", "1/PHI..PHI"), 1), (f_tiles([("2.6ч", "ЦИКЛ", G.AMBER), ("PHI", "ПИК", G.GOLD)]), 1),
         (f_area(4, "ДРЕЙФ РЫНКА"), 2), (f_ladder(4), 1), (f_sparks(4), 1)],
        ["Слушай Центробанк.", "Ставка = ритм PHI.", "corp-heist / PHI PRESS"]))

    issues.append(make(5, "МАГНАТЫ", "Рейтинг богатства", G.GOLD,
        "Лестница магнатов: кто возглавляет PHI-пирамиду капитала",
        "Каждый ранг отстоит от следующего на коэффициент PHI.",
        f_magnates(5), "РЕЙТИНГ", "Пирамида богатства по золотому сечению",
        [P_A, P_B, P_C, P_D], [(f_magnates(5), 160), (f_ladder(5, "ШАГ РАНГА"), 120)],
        "Каждый ранг отстоит от следующего на PHI.",
        ("КОРОНА", ["PHI_CROWN, редкость 5", "Ценность 1 000 000", "Зал славы сезона"]),
        "ДАННЫЕ", "Топ капиталистов сезона",
        "Разрыв между рангами — ровно PHI.",
        [(f_magnates(5), 2), (f_tiles([("×PHI", "ШАГ", G.GOLD), ("8", "РАНГОВ", G.CYAN)]), 1),
         (f_gauge(5, "ДО ВЕРШИНЫ", "прогресс"), 1), (f_ladder(5), 2)],
        ["Взберись на вершину.", "Корона ждёт лучшего.", "corp-heist / PHI PRESS"]))

    issues.append(make(6, "МАГНАТ ГОДА", "Коронация сезона", G.GOLD,
        "Магнат года коронован: золотая корона сезона найдена",
        "Лучший капиталист получает PHI-корону, артефакт категории 11 и место в зале славы.",
        hero_crown(6, D.magnate_ladder(6, 1)[0]["name"], D.magnate_ladder(6, 1)[0]["worth"]),
        "СОБЫТИЕ", "Как заработать корону сезона",
        [P_B, P_A, P_D, P_C], [(f_magnates(6), 160), (f_candles(6, "OMEGA"), 120)],
        "Вечное место в зале славы CORP HEIST.",
        ("НАГРАДА", ["PHI-корона сезона", "Категория 11, редкость 5", "Бонус к боевой мощи"]),
        "ДАННЫЕ", "Путь к короне",
        "Что нужно, чтобы взойти на трон.",
        [(hero_crown(6, D.magnate_ladder(6, 1)[0]["name"], D.magnate_ladder(6, 1)[0]["worth"]), 2),
         (f_magnates(6), 1), (f_gauge(6, "ДО КОРОНЫ", "сезон"), 1), (f_ladder(6), 2)],
        ["Один трон на сезон.", "Стань магнатом года.", "corp-heist / PHI PRESS"]))

    issues.append(make(7, "ДЕРИВАТИВЫ", "Опционы на PHI-страйки", G.PURPLE,
        "Опционы Golden-500: PHI-размеченные страйки и таймер",
        "Колл и пут опционы со страйками через PHI и срасчётом по таймеру.",
        f_ladder(7, "СТРАЙКИ ПО PHI"), "ИНСТРУМЕНТ", "Деривативы: плечо на золоте",
        [P_D, P_C, P_A, P_B], [(f_candles(7, "SIGMA"), 150), (f_ladder(7), 130)],
        "Выплата больше PHI премии открывает знак PHI-OPTION.",
        ("ОПЦИОНЫ", ["Экспирация 60·PHI·PHI", "Размер позиции = PHI", "Страйки через PHI"]),
        "ДАННЫЕ", "Сетка страйков и премий",
        "PHI-шаг между страйками и порог значка.",
        [(f_ladder(7, "СТРАЙКИ"), 1), (f_gauge(7, "PHI-OPTION", "порог"), 1),
         (f_candles(7, "SIGMA"), 2), (f_tiles([("×PHI", "ВЫПЛАТА", G.PURPLE), ("PHI²", "ЭКСПИРА", G.CYAN)]), 1),
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
        "HP босса падает золотыми полосами.",
        [(f_boss(9), 2), (f_tiles([("×PHI", "БОНУС", G.CYAN), ("2", "КОРПЫ", G.GOLD)]), 1),
         (f_gauge(9, "СТРОЙКА", "небоскрёб"), 1), (f_magnates(9), 2)],
        ["Сила в гильдии.", "Небоскрёб растёт по PHI.", "corp-heist / PHI PRESS"]))

    issues.append(make(10, "МАРКЕТ-МЕЙКИНГ", "Спред на PHI", G.GOLD,
        "Маркет-мейкинг с плечом: ставь бид, продавай на PHI-спред",
        "Паркуйте заявку, покупайте на пересечении, автопродажа на бид·PHI.",
        hero_tape(10), "ПРО", "Маркет-мейкер: золотой спред",
        [P_C, P_A, P_D, P_B], [(f_candles(10, "PSI"), 150), (f_ladder(10, "СПРЕД PHI"), 130)],
        "Плечо до PHI, но флеш-крах запускает маржин-колл.",
        ("MM", ["Спред = PHI", "Макс плечо = PHI", "До 8 заявок"]),
        "ДАННЫЕ", "Экономика маркет-мейкера",
        "Спред, плечо и риск маржин-колла.",
        [(f_tiles([("PHI", "СПРЕД", G.GOLD), ("×PHI", "ПЛЕЧО", G.CYAN), ("8", "ЗАЯВОК", G.GREY)]), 1),
         (f_gauge(10, "ЗАГРУЗКА", "плечо"), 1), (f_candles(10, "PSI"), 2),
         (f_ladder(10), 1), (f_compare(10), 1)],
        ["Лови спред.", "Золото на пересечении.", "corp-heist / PHI PRESS"]))

    return issues


NAMES = [
    "vypusk_01_phi_rynok.pdf", "vypusk_02_sektora.pdf", "vypusk_03_shorty.pdf",
    "vypusk_04_centrobank.pdf", "vypusk_05_magnaty.pdf", "vypusk_06_magnat_goda.pdf",
    "vypusk_07_derivativy.pdf", "vypusk_08_boty.pdf", "vypusk_09_gildii.pdf",
    "vypusk_10_market_meiking.pdf",
]


def main():
    os.makedirs(OUT, exist_ok=True)
    total = 0
    for m, name in zip(build_all(), NAMES):
        path = os.path.join(OUT, name)
        m.save(path)
        sz = os.path.getsize(path)
        total += sz
        print("  [OK] %-32s %7d bytes" % (name, sz))
    print("Gotovo: 10 vypuskov po 4 stranicy, %d bytes" % total)


if __name__ == "__main__":
    main()
