#!/usr/bin/env python3
"""Генерация PDF-набросков героев с поддержкой кириллицы (Segoe UI TTF) + маркетинг на 15 языках"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(BASE, "content")
HERO_PDFS = os.path.join(CONTENT, "hero_pdfs")
MARKETING = os.path.join(CONTENT, "marketing_15langs")
os.makedirs(HERO_PDFS, exist_ok=True)
os.makedirs(MARKETING, exist_ok=True)

# ====== REGISTER TTF FONTS ======
FONT_REG = "C:/Windows/Fonts/segoeui.ttf"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
pdfmetrics.registerFont(TTFont("SegoeUI", FONT_REG))
pdfmetrics.registerFont(TTFont("SegoeUIBold", FONT_BOLD))

# ====== HERO DATA ======
HEROES = [
    ("analyst", "Аналитик", "B", "#00AAFF", [
        ("СИЛУЭТ", "Средний рост, худощавое телосложение"),
        ("ОДЕЖДА", "Тёмно-синий деловой костюм, белая рубашка"),
        ("АКСЕССУАРЫ", "Очки с голубым оттенком линз, USB-браслет"),
        ("ОРУЖИЕ", "Ноутбук-планшет, проецирующий квантовые уравнения"),
        ("", ""),
        ("ЦВЕТА", "#00AAFF основной, #1A1A2E вторичный, #FFFFFF акцент"),
        ("ПОЗА", "Одна рука подпирает подбородок, другая操控ирует голограммой"),
        ("ВЫРАЖЕНИЕ", "Сосредоточенность, лёгкая надменность"),
        ("", ""),
        ("IDLE", "Покачивание очков, мерцание голограммы"),
        ("АТАКА", "Нажатие виртуальной клавиатуры → проекция летит во врага"),
        ("", ""),
        ("HP 80  ATK 12  DEF 8  SPD 14", "CRIT 15%  DMG x1.5  DODGE 5%"),
        ("СПОСОБНОСТИ", "Квантовый анализ · Арбитражный удар · Стресс-тест"),
    ]),
    ("consultant", "Консультант", "A", "#FFC800", [
        ("СИЛУЭТ", "Выше среднего, уверенная осанка, широкие плечи"),
        ("ОДЕЖДА", "Серый костюм премиум-класса, галстук"),
        ("АКСЕССУАРЫ", "Золотые манжеты, портфель-планшет"),
        ("ОРУЖИЕ", "Голограммная презентация → щит/меч"),
        ("", ""),
        ("ЦВЕТА", "#FFC800 основной, #2D2D3A вторичный, #FFD700 акцент"),
        ("ПОЗА", "Прямая спина, руки за спиной, взгляд сверху вниз"),
        ("ВЫРАЖЕНИЕ", "Хладнокровная улыбка"),
        ("", ""),
        ("IDLE", "Пересчёт цифр в воздухе, золотые частицы"),
        ("АТАКА", "Разворот презентации → данные обрушиваются"),
        ("", ""),
        ("HP 100  ATK 15  DEF 10  SPD 10", "CRIT 10%  DMG x1.8  DODGE 8%"),
        ("СПОСОБНОСТИ", "Due Diligence · Синергия · Выкуп акций"),
    ]),
    ("quant", "Квант", "S", "#AA00FF", [
        ("СИЛУЭТ", "Стройный, угловатый, неестественно быстрые движения"),
        ("ОДЕЖДА", "Чёрное худи + неоновые линии по швам"),
        ("АКСЕССУАРЫ", "VR-очки на лбу, кабели от перчаток к запястьям"),
        ("ОРУЖИЕ", "Перчатки с хирургическими лезвиями из данных"),
        ("", ""),
        ("ЦВЕТА", "#AA00FF основной, #0D0D1A вторичный, #00FFAA акцент"),
        ("ПОЗА", "Сгорблен, пальцы на невидимой клавиатуре"),
        ("ВЫРАЖЕНИЕ", "Холодная расчётливость, глаза горят"),
        ("", ""),
        ("IDLE", "Пальцы бешено двигаются, вращающиеся уравнения"),
        ("АТАКА", "HFT-шторм — цифры обрушиваются на врага"),
        ("", ""),
        ("HP 70  ATK 18  DEF 5  SPD 16", "CRIT 20%  DMG x2.0  DODGE 12%"),
        ("СПОСОБНОСТИ", "Нейросеть · HFT-шторм · Алгоритм хаоса"),
    ]),
    ("lawyer", "Юрисконсульт", "A", "#FF3232", [
        ("СИЛУЭТ", "Крупный, широкий, неподвижный как скала"),
        ("ОДЕЖДА", "Тёмно-бордовый костюм, золотые пуговицы, мантия"),
        ("АКСЕССУАРЫ", "Огромная книга законов на цепи"),
        ("ОРУЖИЕ", "Книга Законов, защитные барьеры"),
        ("", ""),
        ("ЦВЕТА", "#FF3232 основной, #1A0A0A вторичный, #FFD700 акцент"),
        ("ПОЗА", "Руки сложены на груди, стоит как монумент"),
        ("ВЫРАЖЕНИЕ", "Абсолютное спокойствие"),
        ("", ""),
        ("IDLE", "Страницы переливаются, щит мерцает"),
        ("АТАКА", "Волна юридических текстов → красная печать"),
        ("", ""),
        ("HP 110  ATK 10  DEF 15  SPD 8", "CRIT 8%  DMG x1.3  DODGE 3%"),
        ("СПОСОБНОСТИ", "Антимонопольный щит · Иск о банкротстве · NDA"),
    ]),
    ("ceo", "CEO", "SSR", "#FFC800", [
        ("СИЛУЭТ", "Идеальная осанка, квадратные плечи, доминирование"),
        ("ОДЕЖДА", "Безупречный чёрный костюм, белоснежная рубашка, красный галстук"),
        ("АКСЕССУАРЫ", "Золотые часы, бейдж CEO, кольцо с гравировкой"),
        ("ОРУЖИЕ", "Командный жезл, проецирующий армии данных"),
        ("", ""),
        ("ЦВЕТА", "#FFC800 основной, #0A0A12 вторичный, #FF0000 акцент"),
        ("ПОЗА", "Рука в кармане, другая указывает, взгляд вперёд"),
        ("ВЫРАЖЕНИЕ", "Властная решимость"),
        ("", ""),
        ("IDLE", "Часы тикают золотым, тени совета директоров"),
        ("АТАКА", "Волюнтаризм → ударная волна приказа"),
        ("", ""),
        ("HP 130  ATK 20  DEF 12  SPD 12", "CRIT 18%  DMG x2.2  DODGE 7%"),
        ("СПОСОБНОСТИ", "Волюнтаризм · Реструктуризация · Golden Parachute"),
    ]),
    ("data_scientist", "Data Scientist", "S", "#00FF8C", [
        ("СИЛУЭТ", "Средний, гибкий, движется как танцор данных"),
        ("ОДЕЖДА", "Куртка-бомбер с нашивками нейросетей, джинсы, кроссовки"),
        ("АКСЕССУАРЫ", "AR-очки, планшет с визуализациями, наушники"),
        ("ОРУЖИЕ", "Жидкий металл, формирующий оружие на лету"),
        ("", ""),
        ("ЦВЕТА", "#00FF8C основной, #0A1A0A вторичный, #AAFFEE акцент"),
        ("ПОЗА", "Склонился над планшетом,操控ирует голограммой"),
        ("ВЫРАЖЕНИЕ", "Любопытство + азарт"),
        ("", ""),
        ("IDLE", "Данные струятся по планшету, нейросеть вокруг головы"),
        ("АТАКА", "Deep Learning → матрицы умножаются в реальном времени"),
        ("", ""),
        ("HP 85  ATK 16  DEF 7  SPD 13", "CRIT 22%  DMG x1.7  DODGE 15%"),
        ("СПОСОБНОСТИ", "Deep Learning · Предиктивный удар · Data Mining"),
    ]),
    ("risk_manager", "Risk Manager", "A", "#00AA66", [
        ("СИЛУЭТ", "Крепкий, широкий, неподвижный как бетонная стена"),
        ("ОДЕЖДА", "Тёмно-зелёный костюм, жилет-броня под пиджаком"),
        ("АКСЕССУАРЫ", "Щит-планшет на предплечье, ремень с датчиками"),
        ("ОРУЖИЕ", "Щит Мониторинга — проецирует защитные поля"),
        ("", ""),
        ("ЦВЕТА", "#00AA66 основной, #0A1A14 вторичный, #66FFBB акцент"),
        ("ПОЗА", "Прикрытая стойка, щит наперевес"),
        ("ВЫРАЖЕНИЕ", "Абсолютное спокойствие в хаосе"),
        ("", ""),
        ("IDLE", "Щит пульсирует, датчики сканируют"),
        ("АТАКА", "Хеджирование → защитное поле расширяется"),
        ("", ""),
        ("HP 120  ATK 11  DEF 18  SPD 9", "CRIT 6%  DMG x1.4  DODGE 20%"),
        ("СПОСОБНОСТИ", "Хеджирование · Стресс-тест · Кризис-менеджмент"),
    ]),
    ("trader", "Трейдер", "SSR", "#FF0000", [
        ("СИЛУЭТ", "Худой, нервный, полон энергии, постоянное движение"),
        ("ОДЕЖДА", "Разорванный деловой костюм, галстук расстёгнут"),
        ("АКСЕССУАРЫ", "3 монитора-голограммы, кабели, кофейная кружка"),
        ("ОРУЖИЕ", "Flash Crash — ударная волна рыночного обрушения"),
        ("", ""),
        ("ЦВЕТА", "#FF0000 основной, #1A0505 вторичный, #00FF00 акцент"),
        ("ПОЗА", "Наклонён к экранам, пальцы летают, глаза расширены"),
        ("ВЫРАЖЕНИЕ", "Безумная концентрация"),
        ("", ""),
        ("IDLE", "Мониторы мелькают красным/зелёным, кофе стучит"),
        ("АТАКА", "Flash Crash → красная волна → враг = 0"),
        ("", ""),
        ("HP 75  ATK 22  DEF 4  SPD 20", "CRIT 25%  DMG x2.5  DODGE 18%"),
        ("СПОСОБНОСТИ", "Flash Crash · Margin Call · Short Squeeze"),
    ]),
    ("compliance", "Compliance Officer", "A", "#5588CC", [
        ("СИЛУЭТ", "Стройный, прямой, каждое движение выверено"),
        ("ОДЕЖДА", "Безукоризненный серо-голубой костюм, значок на груди"),
        ("АКСЕССУАРЫ", "Сканер-бейдж, папка с проверочными листами"),
        ("ОРУЖИЕ", "KYC-сканер — луч, выявляющий слабости"),
        ("", ""),
        ("ЦВЕТА", "#5588CC основной, #0A0A1E вторичный, #FFFFFF акцент"),
        ("ПОЗА", "Руки за спиной, осматривает поле как инспектор"),
        ("ВЫРАЖЕНИЕ", "Невозмутимая строгость"),
        ("", ""),
        ("IDLE", "Сканер пульсирует, папка открывается/закрывается"),
        ("АТАКА", "KYC-сканирование → инфракрасный луч"),
        ("", ""),
        ("HP 105  ATK 13  DEF 14  SPD 11", "CRIT 12%  DMG x1.6  DODGE 10%"),
        ("СПОСОБНОСТИ", "KYC-сканирование · AML-удар · Санкционный блок"),
    ]),
    ("brand_director", "Brand Director", "S", "#FF00AA", [
        ("СИЛУЭТ", "Элегантный, грациозный, каждое движение — постановочное"),
        ("ОДЕЖДА", "Дизайнерский костюм, яркие акценты, avant-garde"),
        ("АКСЕССУАРЫ", "VR-очки на лбу, смарт-браслет, буклет Brand Guidelines"),
        ("ОРУЖИЕ", "PR-волна — ударная волна репутации"),
        ("", ""),
        ("ЦВЕТА", "#FF00AA основной, #1A0514 вторичный, #FFD700 акцент"),
        ("ПОЗА", "Рука на бедре, другая操控ирует голограммой бренда"),
        ("ВЫРАЖЕНИЕ", "Самоуверенная прелесть"),
        ("", ""),
        ("IDLE", "Лого бренда вращается, фейерверки данных"),
        ("АТАКА", "PR-удар → волна медиа давления"),
        ("", ""),
        ("HP 90  ATK 14  DEF 9  SPD 15", "CRIT 16%  DMG x1.9  DODGE 14%"),
        ("СПОСОБНОСТИ", "PR-удар · Кризис-коммуникация · Rebranding"),
    ]),
]


def make_hero_pdf(key, name, tier, color_hex, lines):
    path = os.path.join(HERO_PDFS, f"hero_{key}.pdf")
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    color = HexColor(color_hex)

    # Background
    c.setFillColor(HexColor("#0A0A12"))
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Decorative lines
    c.setStrokeColor(HexColor("#1A1A2E"))
    c.setLineWidth(0.5)
    for i in range(20):
        ly = 40 + i * 42
        c.line(30, ly, w - 30, ly)

    # Title
    c.setFillColor(color)
    c.setFont("SegoeUIBold", 32)
    c.drawString(50, h - 70, name)

    # Tier badge
    tier_colors = {"B": "#888899", "A": "#00AAFF", "S": "#AA00FF", "SSR": "#FFC800"}
    tc = HexColor(tier_colors.get(tier, "#FFFFFF"))
    c.setFillColor(tc)
    c.roundRect(50, h - 105, 60, 28, 6, fill=1, stroke=0)
    c.setFillColor(HexColor("#0A0A12"))
    c.setFont("SegoeUIBold", 16)
    c.drawString(62, h - 97, tier)

    # Separator line
    c.setStrokeColor(color)
    c.setLineWidth(2)
    c.line(50, h - 115, w - 50, h - 115)

    # Content
    y = h - 145
    for label, value in lines:
        if not label and not value:
            y -= 12
            continue
        if not value:
            # Section header
            c.setFillColor(color)
            c.setFont("SegoeUIBold", 13)
            c.drawString(50, y, label)
            y -= 20
        elif label in ("HP 80  ATK 12  DEF 8  SPD 14",
                        "HP 100  ATK 15  DEF 10  SPD 10",
                        "HP 70  ATK 18  DEF 5  SPD 16",
                        "HP 110  ATK 10  DEF 15  SPD 8",
                        "HP 130  ATK 20  DEF 12  SPD 12",
                        "HP 85  ATK 16  DEF 7  SPD 13",
                        "HP 120  ATK 11  DEF 18  SPD 9",
                        "HP 75  ATK 22  DEF 4  SPD 20",
                        "HP 105  ATK 13  DEF 14  SPD 11",
                        "HP 90  ATK 14  DEF 9  SPD 15"):
            # Stats bar
            c.setFillColor(HexColor("#1A1A2E"))
            c.roundRect(45, y - 5, w - 90, 22, 4, fill=1, stroke=0)
            c.setFillColor(HexColor("#00FF8C"))
            c.setFont("SegoeUIBold", 11)
            c.drawString(55, y, label + "  " + value)
            y -= 28
        else:
            # Normal line
            c.setFillColor(tc)
            c.setFont("SegoeUIBold", 11)
            c.drawString(50, y, label)
            c.setFillColor(HexColor("#CCCCDD"))
            c.setFont("SegoeUI", 11)
            c.drawString(50 + c.stringWidth(label, "SegoeUIBold", 11) + 12, y, value)
            y -= 18

        if y < 60:
            c.showPage()
            c.setFillColor(HexColor("#0A0A12"))
            c.rect(0, 0, w, h, fill=1, stroke=0)
            y = h - 50

    # Footer
    c.setFillColor(color)
    c.setFont("SegoeUI", 9)
    c.drawString(50, 30, f"CORP HEIST  |  Hero Design Document  |  {name} ({tier})")
    c.setFillColor(HexColor("#555566"))
    c.drawString(w - 180, 30, "github.com/pop31-ai/CORP-HEIST")

    c.save()
    return path


# ====== GENERATE PDFs ======
print("Генерация PDF с TTF-шрифтами...")
pdfs = []
for key, name, tier, color, lines in HEROES:
    p = make_hero_pdf(key, name, tier, color, lines)
    pdfs.append(p)
    print(f"  OK: {os.path.basename(p)}")
print(f"PDF: {len(pdfs)} файлов\n")


# ====== MARKETING CONTENT: 15 LANGUAGES ======
LANGUAGES = [
    ("ru", "Русский"),
    ("en", "English"),
    ("zh", "中文"),
    ("ja", "日本語"),
    ("ko", "한국어"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("es", "Español"),
    ("pt", "Português"),
    ("it", "Italiano"),
    ("tr", "Türkçe"),
    ("ar", "العربية"),
    ("hi", "हिन्दी"),
    ("th", "ไทย"),
    ("id", "Bahasa Indonesia"),
]

AD_TEMPLATES = {
    "short_ad": {
        "ru": "CORP HEIST — Корпоративные войны. 10 героев. Открытый код. Играть бесплатно →",
        "en": "CORP HEIST — Corporate Wars. 10 heroes. Open source. Play free →",
        "zh": "CORP HEIST — 企业战争。10位英雄。开源。免费游玩 →",
        "ja": "CORP HEIST — 企業戦争。10人のヒーロー。オープンソース。無料プレイ →",
        "ko": "CORP HEIST — 기업 전쟁. 10명의 영웅. 오픈 소스. 무료 플레이 →",
        "de": "CORP HEIST — Konzerenkriege. 10 Helden. Open Source. Kostenlos spielen →",
        "fr": "CORP HEIST — Guerres corporatives. 10 héros. Open source. Jouer gratuitement →",
        "es": "CORP HEIST — Guerras corporativas. 10 héroes. Código abierto. Jugar gratis →",
        "pt": "CORP HEIST — Guerras corporativas. 10 heróis. Código aberto. Jogar grátis →",
        "it": "CORP HEIST — Guerre corporate. 10 eroi. Open source. Gioca gratis →",
        "tr": "CORP HEIST — Şirket Savaşları. 10 kahraman. Açık kaynak. Ücretsiz oyna →",
        "ar": "CORP HEIST — حروب الشركات. 10 أبطال. مفتوح المصدر. العب مجاناً →",
        "hi": "CORP HEIST — कॉर्पोरेट युद्ध। 10 नायक। ओपन सोर्स। मुफ्त में खेलें →",
        "th": "CORP HEIST — สงครามองค์กร. 10 ฮีโร่. โอเพ่นซอร์ส. เล่นฟรี →",
        "id": "CORP HEIST — Perang Korporat. 10 Pahlawan. Open Source. Main gratis →",
    },
    "hook_ad": {
        "ru": "Ты CEO или стажёр? Узнай в CORP HEIST — корпоративном RPG, где каждая формула открыта.",
        "en": "Are you the CEO or the intern? Find out in CORP HEIST — the corporate RPG where every formula is open.",
        "zh": "你是CEO还是实习生？在CORP HEIST中找到答案——每条公式都公开的企业RPG。",
        "ja": "あなたはCEOかそれともインターン？CORP HEISTで答えを見つけよう。全フォーマル公開の企業RPG。",
        "ko": "당신은 CEO인가 인턴인가? CORP HEIST에서 찾아보세요 — 모든 공식이 공개된 기업 RPG.",
        "de": "Bist du CEO oder Praktikant? Finde es heraus in CORP HEIST — dem Konzern-RPG mit offenen Formeln.",
        "fr": "Êtes-vous PDG ou stagiaire? Découvrez-le dans CORP HEIST — le RPG corporate où chaque formule est ouverte.",
        "es": "¿Eres CEO o becario? Descúbrelo en CORP HEIST — el RPG corporativo donde cada fórmula es abierta.",
        "pt": "Você é CEO ou estagiário? Descubra no CORP HEIST — o RPG corporativo onde cada fórmula é aberta.",
        "it": "Sei il CEO o il tirocinante? Scoprilo in CORP HEIST — l'RPG corporate dove ogni formula è aperta.",
        "tr": "CEO mi stajyer misin? CORP HEIST'te keşfet — her formülün açık olduğu kurumsal RPG.",
        "ar": "أنت المدير التنفيذي أم متدرّب؟ اكتشف في CORP HEIST — لعبة RPG حيث كل صيغة مفتوحة.",
        "hi": "आप CEO हैं या इंटर्न? CORP HEIST में पता लगाएं — कॉर्पोरेट RPG जहाँ हर फॉर्मूला खुला है।",
        "th": "คุณเป็น CEO หรือเด็กฝึกงาน? ค้นหาใน CORP HEIST — RPG องค์กรที่ทุกสูตรเปิดเผย",
        "id": "Kamu CEO atau magang? Temukan di CORP HEIST — RPG korporat di mana setiap rumus terbuka.",
    },
    "long_ad": {
        "ru": "CORP HEIST — бесплатная turn-based RPG на Python. 10 героев от Аналитика до CEO. 5 корпораций. 7 этажей небоскрёбов. Гача с прозрачными шансами (SSR 3%). Дерево навыков. Боевая система с формулами. Открытый код на GitHub. Играть бесплатно — github.com/pop31-ai/CORP-HEIST",
        "en": "CORP HEIST — free turn-based RPG in Python. 10 heroes from Analyst to CEO. 5 corporations. 7 skyscraper floors. Gacha with transparent rates (SSR 3%). Skill tree. Formula-based combat. Open source on GitHub. Play free — github.com/pop31-ai/CORP-HEIST",
        "zh": "CORP HEIST — 免费Python回合制RPG。10位英雄从分析师到CEO。5家企业。7层摩天大楼。透明概率抽卡（SSR 3%）。技能树。公式化战斗。GitHub开源。免费游玩 — github.com/pop31-ai/CORP-HEIST",
        "ja": "CORP HEIST — 無料ターン制RPG（Python）。アナリストからCEOまで10人のヒーロー。5つの企業。7階の摩天楼。透明なガチャ（SSR 3%）。スキルツリー。数式ベースの戦闘。GitHubでオープンソース。無料プレイ — github.com/pop31-ai/CORP-HEIST",
        "ko": "CORP HEIST — 무료 턴제 RPG. 분석가부터 CEO까지 10명의 영웅. 5개 기업. 7층 빌딩. 투명한 가챠(SSR 3%). 스킬 트리. 공식 기반 전투. GitHub 오픈 소스. 무료 플레이 — github.com/pop31-ai/CORP-HEIST",
        "de": "CORP HEIST — kostenloses rundenbasiertes RPG in Python. 10 Helden vom Analysten bis CEO. 5 Konzerne. 7 Etagen. Faire Gacha (SSR 3%). Skill-Baum. Formelbasiertes Combat. Open Source auf GitHub. Kostenlos spielen — github.com/pop31-ai/CORP-HEIST",
        "fr": "CORP HEIST — RPG gratuit au tour par tour en Python. 10 héros de l'analyste au PDG. 5 sociétés. 7 étages. Gacha équitable (SSR 3%). Arbre de compétences. Combat basé sur des formules. Open source sur GitHub. Jouer gratuitement — github.com/pop31-ai/CORP-HEIST",
        "es": "CORP HEIST — RPG gratuito por turnos en Python. 10 héroes del Analista al CEO. 5 corporaciones. 7 pisos. Gacha transparente (SSR 3%). Árbol de habilidades. Combate basado en fórmulas. Código abierto en GitHub. Jugar gratis — github.com/pop31-ai/CORP-HEIST",
        "pt": "CORP HEIST — RPG gratuito por turnos em Python. 10 heróis do Analista ao CEO. 5 corporações. 7 andares. Gacha transparente (SSR 3%). Árvore de habilidades. Combate baseado em fórmulas. Código aberto no GitHub. Jogar grátis — github.com/pop31-ai/CORP-HEIST",
        "it": "CORP HEIST — RPG gratuito a turni in Python. 10 eroi dall'Analista al CEO. 5 corporazioni. 7 piani. Gacha trasparente (SSR 3%). Albero abilità. Combattimento basato su formule. Open source su GitHub. Gioca gratis — github.com/pop31-ai/CORP-HEIST",
        "tr": "CORP HEIST — ücretsiz tur bazlı RPG. 10 kahraman Analist'ten CEO'ya. 5 şirket. 7 kat. Şeffaf gacha (SSR 3%). Yetenek ağacı. Formül bazlı dövüş. GitHub'da açık kaynak. Ücretsiz oyna — github.com/pop31-ai/CORP-HEIST",
        "ar": "CORP HEIST — لعبة RPG مجانية بالدورات في Python. 10 أبطال من المحلل إلى المدير التنفيذي. 5 شركات. 7 طوابق. سحب عادل (SSR 3%). شجرة مهارات. قتال بالصيغ. مفتوح المصدر على GitHub. العب مجاناً — github.com/pop31-ai/CORP-HEIST",
        "hi": "CORP HEIST — मुफ्त टर्न-आधारित RPG Python में। एनालिस्ट से CEO तक 10 नायक। 5 कॉर्पोरेशन। 7 मंजिलें। पारदर्शी गचा (SSR 3%)। स्किल ट्री। सूत्र-आधारित युद्ध। GitHub पर ओपन सोर्स। मुफ्त में खेलें — github.com/pop31-ai/CORP-HEIST",
        "th": "CORP HEIST — RPG ผลัดกันเล่นฟรีใน Python. 10 ฮีโร่จากนักวิเคราะห์ถึง CEO. 5 องค์กร. 7 ชั้น. กาชาโปร่งใส (SSR 3%). ทักษะ树. ต่อสู้ด้วยสูตร. โอเพ่นซอร์สบน GitHub. เล่นฟรี — github.com/pop31-ai/CORP-HEIST",
        "id": "CORP HEIST — RPG gratis turn-based di Python. 10 pahlawan dari Analis hingga CEO. 5 korporasi. 7 lantai. Gacha transparan (SSR 3%). Skill tree. Pertarungan berbasis rumus. Open source di GitHub. Main gratis — github.com/pop31-ai/CORP-HEIST",
    },
    "app_store_desc": {
        "ru": "CORP HEIST — корпоративная turn-based RPG с открытым исходным кодом. Прокачивай героев от стажёра до CEO. Сражайся в бизнес-центрах. Собирай акции. Управляй корпорацией. Прозрачная гача-система с опубликованными шансами. Формулы баланса доступны каждому.",
        "en": "CORP HEIST — corporate turn-based RPG with open source code. Level up heroes from intern to CEO. Fight in business centers. Collect stocks. Manage corporations. Transparent gacha with published rates. Balance formulas available to all.",
        "zh": "CORP HEIST — 开源企业回合制RPG。将英雄从实习生升级到CEO。在商业中心战斗。收集股票。管理企业。透明抽卡，概率公开。平衡公式人人可查。",
        "ja": "CORP HEIST — オープンソースの企業ターン制RPG。インターンからCEOへヒーローをレベルアップ。ビジネスセンターで戦う。株式を収集。企業を管理。公開確率の透明ガチャ。バランスフォーマルは誰でも閲覧可能。",
        "ko": "CORP HEIST — 오픈 소스 기업 턴제 RPG. 인턴에서 CEO까지 영웅을 성장시키세요. 비즈니스 센터에서 전투. 주식 수집. 기업 관리. 공개된 확률의 투명한 가챠. 밸런스 공식을 모두가 확인할 수 있습니다.",
        "de": "CORP HEIST — Open-Source-Konzern-RPG. Helden vom Praktikanten zum CEO. Kämpfe in Businesscentern. Sammle Aktien. Verwalte Konzerne. Faire Gacha mit veröffentlichten Raten. Formeln für jeden zugänglich.",
        "fr": "CORP HEIST — RPG corporate open source. Évoluez de stagiaire à PDG. Combattez dans les centres d'affaires. Collectez des actions. Gérez des sociétés. Gacha équitable avec taux publiés. Formules accessibles à tous.",
        "es": "CORP HEIST — RPG corporativo de código abierto. Evoluciona de becario a CEO. Lucha en centros de negocios. Recoge acciones. Gestiona corporaciones. Gacha transparente con tasas publicadas. Fórmulas accesibles para todos.",
        "pt": "CORP HEIST — RPG corporativo de código aberto. Evolua de estagiário a CEO. Lute em centros de negócios. Colete ações. Gerencie corporações. Gacha transparente com taxas publicadas. Fórmulas acessíveis a todos.",
        "it": "CORP HEIST — RPG corporate open source. Evolvi da tirocinante a CEO. Combatti nei centri commerciali. Raccogli azioni. Gestisci corporazioni. Gacha trasparente con tassi pubblicati. Formule accessibili a tutti.",
        "tr": "CORP HEIST — açık kaynak kurumsal RPG. Stajyerden CEO'ya evrimleş. İş merkezlerinde savaş. Hisseleri topla. Şirketleri yönet. Yayın oranlarıyla şeffaf gacha. Formüller herkese açık.",
        "ar": "CORP HEIST — لعبة RPG مفتوحة المصدر. تطوّر من متدرّب إلى مدير تنفيذي. قاتل في مراكز الأعمال. اجمع الأسهم. أدر الشركات. سحب شفاف بمعدلات منشورة. الصيغ متاحة للجميع.",
        "hi": "CORP HEIST — ओपन सोर्स कॉर्पोरेट RPG। इंटर्न से CEO तक विकसित हों। बिज़नेस सेंटर में लड़ें। शेयर इकट्ठा करें। कॉर्पोरेशन प्रबंधित करें। प्रकाशित दरों के साथ पारदर्शी गचा। सभी के लिए सूत्र उपलब्ध।",
        "th": "CORP HEIST — RPG องค์กรโอเพ่นซอร์ส. พัฒนาจากเด็กฝึกงานเป็น CEO. ต่อสู้ในศูนย์ธุรกิจ. เก็บหุ้น. จัดการองค์กร. กาชาโปร่งใสพร้อมอัตราที่เปิดเผย. สูตรเข้าถึงได้ทุกคน",
        "id": "CORP HEIST — RPG korporat open source. Evolusi dari magang ke CEO. Bertarung di pusat bisnis. Kumpulkan saham. Kelola korporasi. Gacha transparan dengan rate yang dipublikasikan. Rumus tersedia untuk semua.",
    },
    "social_post": {
        "ru": "🎮CORP HEIST вышел! Бесплатная корпоративная RPG на Python.\n\n✅ 10 героев (Аналитик → CEO)\n✅ 5 корпораций с бонусами\n✅ 7 этажей бизнес-центров\n✅ Честная гача (SSR 3%, pity 50)\n✅ Открытый код\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "en": "🎮CORP HEIST is out! Free corporate RPG in Python.\n\n✅ 10 heroes (Analyst → CEO)\n✅ 5 corporations with bonuses\n✅ 7 business center floors\n✅ Fair gacha (SSR 3%, pity 50)\n✅ Open source code\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "zh": "🎮CORP HEIST发布！免费Python企业RPG。\n\n✅ 10位英雄（分析师→CEO）\n✅ 5家企业加成\n✅ 7层商业中心\n✅ 公平抽卡（SSR 3%，保底50）\n✅ 开源代码\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "ja": "🎮CORP HEISTリリース！無料Python企業RPG。\n\n✅ 10人のヒーロー（アナリスト→CEO）\n✅ 5つの企業ボーナス\n✅ 7階のビジネスセンター\n✅ 公正なガチャ（SSR 3%、ピティ50）\n✅ オープンソース\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "ko": "🎮CORP HEIST 출시! 무료 Python 기업 RPG.\n\n✅ 10명의 영웅 (분석가→CEO)\n✅ 5개 기업 보너스\n✅ 7층 비즈니스 센터\n✅ 공정한 가챠 (SSR 3%, 피티 50)\n✅ 오픈 소스 코드\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "de": "🎮CORP HEIST ist da! Kostenloses Konzern-RPG in Python.\n\n✅ 10 Helden (Analyst → CEO)\n✅ 5 Konzerne mit Boni\n✅ 7 Etagen Business-Center\n✅ Faire Gacha (SSR 3%, Pity 50)\n✅ Open Source Code\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "fr": "🎮CORP HEIST est sorti! RPG corporate gratuit en Python.\n\n✅ 10 héros (Analyste → PDG)\n✅ 5 sociétés avec bonus\n✅ 7 étages de centres d'affaires\n✅ Gacha équitable (SSR 3%, pity 50)\n✅ Code open source\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "es": "🎮CORP HEIST ya está aquí! RPG corporativo gratuito en Python.\n\n✅ 10 héroes (Analista → CEO)\n✅ 5 corporaciones con bonus\n✅ 7 pisos de centros de negocios\n✅ Gacha transparente (SSR 3%, pity 50)\n✅ Código abierto\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "pt": "🎮CORP HEIST lançado! RPG corporativo gratuito em Python.\n\n✅ 10 heróis (Analista → CEO)\n✅ 5 corporações com bônus\n✅ 7 andares de centros de negócios\n✅ Gacha transparente (SSR 3%, pity 50)\n✅ Código aberto\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "it": "🎮CORP HEIST è uscito! RPG corporate gratuito in Python.\n\n✅ 10 eroi (Analista → CEO)\n✅ 5 corporazioni con bonus\n✅ 7 piani di centri commerciali\n✅ Gacha trasparente (SSR 3%, pity 50)\n✅ Codice open source\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "tr": "🎮CORP HEIST çıktı! Ücretsiz kurumsal RPG Python ile.\n\n✅ 10 kahraman (Analist → CEO)\n✅ 5 şirket bonuslu\n✅ 7 kat iş merkezi\n✅ Adil gacha (SSR 3%, pity 50)\n✅ Açık kaynak kodu\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "ar": "🎮CORP HEIST صدر! لعبة RPG مجانية بـ Python.\n\n✅ 10 أبطال (محلل → مدير تنفيذي)\n✅ 5 شركات بمكافآت\n✅ 7 طوابق مراكز أعمال\n✅ سحب عادل (SSR 3%, pity 50)\n✅ كود مفتوح المصدر\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "hi": "🎮CORP HEIST लॉन्च! Python में मुफ्त कॉर्पोरेट RPG।\n\n✅ 10 नायक (एनालिस्ट → CEO)\n✅ 5 कॉर्पोरेशन बोनस\n✅ 7 मंजिल बिज़नेस सेंटर\n✅ पारदर्शी गचा (SSR 3%, pity 50)\n✅ ओपन सोर्स कोड\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "th": "🎮CORP HEIST วางจำหน่ายแล้ว! RPG องค์กรฟรีใน Python\n\n✅ 10 ฮีโร่ (นักวิเคราะห์ → CEO)\n✅ 5 องค์กรพร้อมโบนัส\n✅ 7 ชั้นศูนย์ธุรกิจ\n✅ กาชาโปร่งใส (SSR 3%, pity 50)\n✅ โค้ดโอเพ่นซอร์ส\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
        "id": "🎮CORP HEIST rilis! RPG korporat gratis di Python.\n\n✅ 10 pahlawan (Analis → CEO)\n✅ 5 korporasi dengan bonus\n✅ 7 lantai pusat bisnis\n✅ Gacha transparan (SSR 3%, pity 50)\n✅ Kode open source\n\n#CorpHeist #IndieGame #Python #OpenSource #Gamedev",
    },
    "landing_headline": {
        "ru": "Стань CEO. Разбей корпорацию. Играй бесплатно.",
        "en": "Become the CEO. Break the corporation. Play for free.",
        "zh": "成为CEO。打破企业垄断。免费游玩。",
        "ja": "CEOになれ。企業を打ち破れ。無料でプレイ。",
        "ko": "CEO가 되어라. 기업을 부수어라. 무료로 플레이.",
        "de": "Werde CEO. Zerstöre den Konzern. Spiele kostenlos.",
        "fr": "Devenez PDG. Brisez la société. Jouez gratuitement.",
        "es": "Sé el CEO. Destruye la corporación. Juega gratis.",
        "pt": "Seja o CEO. Destrua a corporação. Jogue grátis.",
        "it": "Diventa il CEO. Distruggi la corporazione. Gioca gratis.",
        "tr": "CEO Ol. Şirketi Yık. Ücretsiz Oyna.",
        "ar": "كن المدير التنفيذي. دمّر الشركة. العب مجاناً.",
        "hi": "CEO बनें। कॉर्पोरेशन तोड़ें। मुफ्त में खेलें।",
        "th": "เป็น CEO ทำลายองค์กร เล่นฟรี",
        "id": "Jadilah CEO. Hancurkan korporasi. Main gratis.",
    },
    "email_subject": {
        "ru": "🎮 Корпоративные войны начались — CORP HEIST",
        "en": "🎮 Corporate Wars have begun — CORP HEIST",
        "zh": "🎮 企业战争已经打响 — CORP HEIST",
        "ja": "🎮 企業戦争が開始されました — CORP HEIST",
        "ko": "🎮 기업 전쟁이 시작되었습니다 — CORP HEIST",
        "de": "🎮 Konzernkrieg hat begonnen — CORP HEIST",
        "fr": "🎮 Les guerres corporatives ont commencé — CORP HEIST",
        "es": "🎮 Las guerras corporativas han comenzado — CORP HEIST",
        "pt": "🎮 As guerras corporativas começaram — CORP HEIST",
        "it": "🎮 Le guerre corporate sono iniziate — CORP HEIST",
        "tr": "🎮 Şirket Savaşları başladı — CORP HEIST",
        "ar": "🎮 حروب الشركات بدأت — CORP HEIST",
        "hi": "🎮 कॉर्पोरेट युद्ध शुरू हो गया — CORP HEIST",
        "th": "🎮 สงครามองค์กรเริ่มแล้ว — CORP HEIST",
        "id": "🎮 Perang Korporat telah dimulai — CORP HEIST",
    },
}

# ====== WRITE MARKETING FILES ======
print("Генерация маркетингового контента на 15 языках...")
count = 0
for lang_code, lang_name in LANGUAGES:
    lang_dir = os.path.join(MARKETING, lang_code)
    os.makedirs(lang_dir, exist_ok=True)
    for template_key, translations in AD_TEMPLATES.items():
        text = translations.get(lang_code, translations["en"])
        path = os.path.join(lang_dir, f"{template_key}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{'='*60}\n")
            f.write(f"Language: {lang_name} ({lang_code})\n")
            f.write(f"Template: {template_key}\n")
            f.write(f"{'='*60}\n\n")
            f.write(text.strip() + "\n")
        count += 1

print(f"Маркетинг: {count} файлов ({len(LANGUAGES)} языков × {len(AD_TEMPLATES)} шаблонов)")
print(f"\nИТОГО: {len(pdfs)} PDF + {count} маркетинг txt = {len(pdfs) + count} новых файлов")
