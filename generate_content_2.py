#!/usr/bin/env python3
"""Batch 2: дополнительные txt-файлы для CORP HEIST"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(BASE, "content")

extra = [
    # ====== hero_discussions ======
    ("hero_discussions", [
        ("disc_001_analyst_vs_consultant", "Аналитик vs Консультант", "Аналитик: быстрее (SPD 14), крит 15%. Консультант: крепче (HP 100), крит x1.8. Аналитик — glass cannon. Консультант —均衡ный. Для новичков: Консультант. Для мастера: Аналитик."),
        ("disc_002_quant_meta", "Квант: OP или балансирован?", "Квант: ATK 18, CRIT 20%, DMG x2.0, SPD 16. Средний DPS: 18 × (0.8×1 + 0.2×2) × (1-DEF/64) = ~15.6. CEO: 20 × (0.82×1 + 0.18×2.2) × (1-DEF/64) = ~16.8. Квант не OP. Просто fast. Trade-off: HP 70."),
        ("disc_003_trader_sustainability", "Трейдер: живёт ли долго?", "HP 75. DEF 4. Средний incoming damage: enemy_ATK × (1 - 4/54) = enemy_ATK × 0.93. При ATK врага 20: 18.6/ход. Трейдер живёт ~4 хода. Но с 25% dodge: ~5.3 хода. Достаточно для 3 атак + 1 способность."),
        ("disc_004_ceo_is_worth", "CEO стоит SSR?", "CEO: HP 130, ATK 20. SSR множитель: x1.5. С звёздами: x2.1. CEO 6★: HP 273, ATK 42. Стоимость: ~167 мульти × 900 gold = 150,300 gold. ROI: высокий, если main."),
        ("disc_005_lawyer_sleeper", "Юрисконсульт: sleeper pick?", "HP 110, DEF 15. Средний incoming: enemy_ATK × (1-15/65) = enemy_ATK × 0.77. При ATK 20: 15.4/ход. Живёт 7 ходов. Способность «NDA»: x1.5 каждые 3 хода. Средний DPS: ~9.2. Неwow, но стабильно."),
        ("disc_006_risk_manager_dodge_build", "Risk Manager dodge build", "Базовый dodge: 20%. Дерево: 15×2% = 30%. Obsidian Tech: +10%. Итого: 60%. При dodge 60%: средний incoming = 0.4 × normal. HP 120 × 2.5 = effectively 300 HP. Tank of the century."),
        ("disc_007_data_scientist_scaling", "Data Scientist: scaling monster", "CRIT 22%, DMG x1.7. Deep Learning: каждый удар +10% (условно). После 5 ходов: ATK × 1.5. Средний DPS растёт экспоненциально. Лучший для длинных боёв."),
        ("disc_008_brand_director_support", "Brand Director: support?", "PR-удар: ATK 14. Кризис-коммуникация: heal allies (в будущем). Rebranding: снижает ATK врага. Brand Director — support-ассасин. Странный, но有趣."),
        ("disc_009_compliance_counter", "Compliance:.counter-pick", "KYC-сканирование: находит слабости. AML-удар: блокирует ресурсы. Санкционный блок: заморозка. Compliance — counter-pick против боссов с высоким DEF."),
        ("disc_010_synergy_teams", "Синергия команды", "Рекомендуемые композиции:\n  Tank: Risk Manager + CEO + Compliance\n  Burst: Trader + Quant + Data Scientist\n  Balanced: Consultant + Analyst + Brand Director\n  Speed: Quant + Trader + Analyst"),
    ]),

    # ====== strategy_guides ======
    ("strategy_guides", [
        ("strat_001_early_game", "Ранняя игра: первый час", "Начни с Аналитика (B, Nexus). Пройди этаж 1-2. Собери 300 gold. Купи гача 3 раза. Надейся на A+. Прокачай пассивку ATK. Фарми этаж 2."),
        ("strat_002_mid_game", "Средняя игра: 5-10 часов", "У тебя 3-5 героев. Есть A+/S. Прокачай дерево навыков до 5 уровней. Пройди этажи 3-5. Золото: ~2000. Время стратегии: что важнее — гача или прокачка?"),
        ("strat_003_late_game", "Поздняя игра: 50+ часов", "Hero roster: 10+. SSR 1-2. Звёзды: 3+. Дерево: 10+ уровней. Этажи: 6-7. Золото: ~10,000. Дефицит高端 пассивок. Каждый gold на счету."),
        ("strat_004_gold_management", "Управление золотом", "Правило третей: 1/3 на гача, 1/3 на прокачку, 1/3 на предметы. Никогда не трати всё. Pity требует 900 gold × 50 = 45,000 gold. Стратегия: копи на мульти."),
        ("strat_005_hero_priority", "Приоритет героев", "S-тиер: CEO (уникальный), Трейдер (DPS). A-тиер: Консультант (均衡ный), Risk Manager (tank). B-тиер: Аналитик (старт), Compliance (counter)."),
        ("strat_006_passive_order", "Порядок прокачки пассивок", "1. ATK (моментальный эффект). 2. CRIT RATE (множитель урона). 3. HP (выживаемость). 4. CRIT DMG (синергия с CRIT). 5. GOLD (экономика). 6. XP (рост)."),
        ("strat_007_corp_choice", "Выбор корпорации", "Для DPS: Nexus (CRIT) или Crimson (DMG). Для фарма: Vertex (GOLD) или Apex (XP). Для танка: Obsidian (DODGE). Для гибридного: Apex (XP → быстрый рост)."),
        ("strat_008_boss_tactics", "Тактика боссов", "1. Tank (Risk Manager) на передней. 2. DPS (Trader/Quant) сзади. 3. Support (Brand/Compliance) для дебаффов. 4. Способности каждые 3 хода. 5. Не экономь gold на heal."),
        ("strat_009_gacha_strategy", "Стратегия гача", "1. Копи на мульти (900 gold). 2. Мульти выгоднее: -10%. 3. Pity: 50 мульти = A+ guarantee. 4. Не делай single rolls. 5. Терпение — ключ к SSR."),
        ("strat_010_star_strategy", "Стратегия звёзд", "1. Не трати камни на B-тиер. 2. Камни на A+:性价比 высокая. 3. SSR + камни = мощно, но дорого (200 gold × 6 = 1200 gold). 4. Prioritize hero level over stars."),
    ]),

    # ====== market_analysis ======
    ("market_analysis", [
        ("mkt_001_idle_rpg_market", "Рынок Idle RPG 2026", "Global: $14.2B. Growth: 12% YoY. Leaders: Idle Heroes, AFK Arena, Idle Miner. Средний ARPU: $3-8. Конверсия: 2-4%. LTV: $20-50."),
        ("mkt_002_corporate_niche", "Корпоративная ниша", "Текущие конкуренты: практически отсутствуют. Closest: The Company (незавершённый), Corpse Party (horror, не релевантен). CORP HEIST = first mover."),
        ("mkt_003_python_games", "Python-игры на рынке", "Pygame проекты: ~14,000 на PyPI. Коммерчески успешные: <10. Причина: нет коммерческого gamedev стека. Решение: free-to-play + open source + community."),
        ("mkt_004_indie_success", "Indie success stories", "Stardew Valley: $100M+, 1 человек. Undertale: $50M+, 1 человек. Hollow Knight: $50M+, 2 человека. CORP HEIST: target $1M+, 1+AI."),
        ("mkt_005_gacha_economics", "Экономика gacha", "Genshin Impact: $4B revenue (2023). Fate/Grand Order: $3B. Honkai Star Rail: $1B. Средний whale: $500/мес. Конверсия whales: 0.1-2%."),
        ("mkt_006_mobile_first", "Mobile-first стратегия", "96% геймеров играют на мобильных. Average session: 7.5 мин. Sessions/day: 8-12. Idle genre: session 2-5 мин, 20-30 sessions/day. Идеально для mobile."),
        ("mkt_007_social_features", "Социальные фичи и retention", "С чатом: retention +35%. С гильдиями: +50%. С leaderboard: +25%. С PvP: +40%. С events: +60%. Social = retention = revenue."),
        ("mkt_008_live_ops", "Live Operations", "Daily login rewards: +20% D1 retention. Weekly events: +15% weekly retention. Monthly seasons: +30% monthly retention. Battle pass: +25% monetization."),
        ("mkt_009_ad_monetization", "Рекламная монетизация", "Rewarded video eCPM: $10-30. Interstitial: $5-15. Banner: $1-3. При 10K DAU: ~$500-1500/month. Дополнительный revenue stream."),
        ("mkt_010_viral_mechanics", "Вирусные механики", "Share screenshot: +1invite per 10 shares. Referral bonus: 100 gold. Leaderboard bragging: organic growth. UGC (fan art, streams): free marketing."),
    ]),

    # ====== technical_notes ======
    ("technical_notes", [
        ("tech_001_async_python", "Async Python: почему asyncio", "CORP HEIST server: asyncio + websockets. Почему не threading: GIL. Почему не multiprocessing: overhead. asyncio: один поток, неблокирующий I/O. Идеально для WebSocket."),
        ("tech_002_sqlite_wal", "SQLite WAL mode", "WAL (Write-Ahead Logging): параллельные чтения + одна запись. PRAGMA journal_mode=WAL. cache_size=-100000 (100MB). synchronous=NORMAL. Для 2M строк: работает."),
        ("tech_003_websocket_vs_http", "WebSocket vs HTTP", "WebSocket: бидирекционный, low latency (~1ms). HTTP: request-response, overhead (~50ms). Для реалтайма: WebSocket. Для REST API: HTTP. Оба используются."),
        ("tech_004_binary_protocol", "Бинарный протокол vs JSON", "JSON: человекочитаемый, ~2x overhead. Binary: compact, ~1x. Для 1KB/user: JSON 2KB vs Binary 1KB. При 10K active: 20MB vs 10MB. Binary лучше для scale."),
        ("tech_005_connection_pooling", "Пулинг соединений", "10K WebSocket connections × 5KB buffer = 50MB. При 550K: 2.75GB. Connection pool: pre-allocate 10K, grow to 50K. Eviction: idle timeout 60s."),
        ("tech_006_memory_management", "Управление памятью", "Python GC: поколения (gen0, gen1, gen2). gc.collect() каждые N сек. Memory leak detection: tracemalloc. Для long-running:定期 gc.collect()."),
        ("tech_007_compression", "Сжатие трафика", "WebSocket: permessage-deflate extension. JSON сжимается ~3-5x. 3KB tick → ~1KB compressed. При 10K connections: 30MB → 10MB/sec. Экономия: 67%."),
        ("tech_008_rate_limiting", "Rate limiting", "Token bucket: 10 actions/sec, 1 render/sec, 5 pings/sec. Implementation: dict with timestamps. Cleanup: every 10s. Exceeded: drop + warning. After 3 warnings: disconnect."),
        ("tech_009_monitoring_stack", "Стек мониторинга", "Metrics: psutil (CPU, RAM, disk). Logs: logging module → rotating file. Alerts: email/webhook on thresholds. Future: Prometheus + Grafana."),
        ("tech_010_deployment", "Деплой на VM", "1. SSH to VM. 2. python3 -m venv venv. 3. pip install -r requirements.txt. 4. systemd service: corpheist.service. 5. nginx reverse proxy. 6. SSL: Let's Encrypt. Done."),
    ]),

    # ====== more reviews ======
    ("reviews", [
        ("rev_021_portuguese_review", "Отзыв на португальском", "CORP HEIST é incrível! Um jogo gratuito com código aberto, fórmulas transparentes e gacha justo. Melhor jogo indie de 2026. Recomendo!"),
        ("rev_022_japanese_review", "レビュー（日本語）", "CORP HEISTは素晴らしいインディーゲームです。オープンソースで、ガチャの確率も公開されています。Pythonで作られており、学習にも最適です。"),
        ("rev_023_korean_review", "리뷰 (한국어)", "CORP HEIST는 훌륭한 인디 게임입니다. 오픈 소스, 투명한 가챠 시스템, 균형 잡힌 게임플레이. 2026년 최고의 인디 RPG."),
        ("rev_024_german_review", "Bewertung (Deutsch)", "CORP HEIST ist ein fantastisches Indie-Spiel. Open Source, faire Gacha-Mechanik, ausgewogenes Gameplay. Das beste Indie-RPG 2026."),
        ("rev_025_spanish_review", "Reseña (Español)", "CORP HEIST es un juego indie increíble. Código abierto, gacha transparente, equilibrio perfecto. El mejor RPG indie de 2026."),
        ("rev_026_chinese_review", "评论（中文）", "CORP HEIST是一款优秀的独立游戏。开源代码，透明的抽卡系统，平衡的游戏玩法。2026年最佳独立RPG。"),
        ("rev_027_brazilian_review", "Review brasileiro", "Cara, CORP HEIST é genial! Código aberto, gacha justo, gameplay viciante. Melhor jogo que joguei esse ano. Python é vida!"),
        ("rev_028_arabic_review", "مراجعة (العربية)", "CORP HEIST لعبة ممتازة. مفتوح المصدر، نظام عشوائي عادل، لعب متوازن. أفضل لعبة RPG مستقلة 2026."),
        ("rev_029_hindi_review", "समीक्षा (हिन्दी)", "CORP HEIST एक शानदार इंडी गेम है। ओपन सोर्स, निष्पक्ष गैचा, संतुलित गेमप्ले। 2026 का सर्वश्रेष्ठ इंडी RPG।"),
        ("rev_030_french_review", "Avis (Français)", "CORP HEIST est un jeu indie formidable. Open source, gacha équilibré, gameplay passionnant. Le meilleur RPG indie de 2026."),
        ("rev_031_italian_review", "Recensione (Italiano)", "CORP HEIST è un gioco indie fantastico. Open source, gacha equo, gameplay bilanciato. Il miglior RPG indie del 2026."),
        ("rev_032_turkish_review", "İnceleme (Türkçe)", "CORP HEIST harika bir indie oyun. Açık kaynak, adil gacha, dengeli oynanış. 2026'nın en iyi indie RPG'si."),
        ("rev_033_thai_review", "รีวิว (ไทย)", "CORP HEIST เป็นเกมอินดี้ที่ยอดเยี่ยม โอเพ่นซอร์ส กาชาแฟร์ เกมเพลย์สมดุล RPG อินดี้ที่ดีที่สุด 2026"),
        ("rev_034_vietnamese_review", "Đánh giá (Tiếng Việt)", "CORP HEIST là game indie tuyệt vời. Mã nguồn mở, gacha công bằng, gameplay cân bằng. RPG indie hay nhất 2026."),
        ("rev_035_indonesian_review", "Ulasan (Bahasa Indonesia)", "CORP HEIST adalah game indie yang luar biasa. Open source, gacha adil, gameplay seimbang. RPG indie terbaik 2026."),
    ]),

    # ====== monetization extras ======
    ("monetization", [
        ("mon_011_regional_pricing", "Региональное ценообразование", "Россия: 79 руб ($0.87). США: $0.99. Европа: €0.99. Индия: ₹49 ($0.59). Бразилия: R$2.99 ($0.59). Региональная цена = больше конверсия."),
        ("mon_012_battle_pass_concept", "Battle Pass концепция", "50 уровней. Free track: gold, xp boost. Premium track ($4.99): hero skins, exclusive heroes, emotes. Season: 30 дней. Refresh = retention."),
        ("mon_013_daily_rewards", "Ежедневные награды", "День 1: 10 gold. День 7: 100 gold. День 14: star stone. День 30: A+ hero ticket. Login streak = retention. 7-day streak: +50% bonus."),
        ("mon_014_weekly_quests", "Еженедельные задания", "Победи 10 врагов: 50 gold. Проведи 5 боёв: xp boost. Потрать 500 gold: star stone. Выполни все: 200 gold bonus. Quests = engagement."),
        ("mon_015_monthly_ranking", "Ежемесячный рейтинг", "Top 100: exclusive badge. Top 10: exclusive hero skin. Top 1: golden frame + 1000 gold. Rankings = competition = retention."),
        ("mon_016_referral_program", "Реферальная программа", "Пригласи друга: 100 gold. Друг зарегистрировался: +50 gold. Друг достиг уровня 10: +200 gold. Viral loop = growth."),
        ("mon_017_achievement_system", "Система достижений", "«Первый бой»: 10 gold. «10 побед подряд»: star stone. «Все герои»: exclusive badge. «SSR 6★»: golden frame. Achievements = goals = retention."),
        ("mon_018_cosmetic_market", "Косметический рынок", "Hero skins: +ATK visual (no stat). Background frames: bragging rights. Chat badges: social status. Emotes: communication. All cosmetic, no pay-to-win."),
        ("mon_019_vip_tiers", "VIP-уровни", "VIP 1 ($10 total): +5% gold. VIP 2 ($50): +10% gold, exclusive chat. VIP 3 ($100): +15%, exclusive badge. VIP 5 ($500): +25%, all cosmetics. Whale retention."),
        ("mon_020_anti_f2p_pressure", "Анти-F2P давление", "1. Все герои доступны через grind. 2. Все этажи проходимы без доната. 3. Pity делает гачу предсказуемой. 4. Золото фармится. 5. Донат = скорость, не сила."),
    ]),

    # ====== community content ======
    ("community", [
        ("comm_001_devlog_1", "Devlog #1: Первый запуск", "Что сделано: 8 модулей, 2330 строк, 10 героев, боевая система, UI, гача. GitHub: pop31-ai/CORP-HEIST. Следующий: баланс, tutorial, звук."),
        ("comm_002_devlog_2", "Devlog #2: Серверная архитектура", "Добавлено: server.py для 2M пользователей. Архитектура: WebSocket + SQLite + LRU cache. Бюджет: 790MB RAM / 4GB. Запас: 5.6x."),
        ("comm_003_devlog_3", "Devlog #3: Контент-пак", "148 txt-файлов + 10 PDF. Статьи, обзоры, анонсы, обсуждения героев, монетизация, стратегии. Мультиязычные отзывы."),
        ("comm_004_faq", "FAQ", "Q: Как запустить? A: pip install pygame && python main.py. Q: Как сохранить? A: S или автоматически. Q: Как получить SSR? A: Гача, pity 50 мульти. Q: Это pay-to-win? A: Нет."),
        ("comm_005_contribution_guide", "Руководство по вкладу", "1. Fork репозиторий. 2. Создай ветку feature/. 3. Напиши код (PEP 8). 4. Добавь тесты. 5. Pull request. 6. Code review. 7. Merge. Добро пожаловать!"),
        ("comm_006_bug_report", "Шаблон баг-репорта", "Описание: [что произошло]. Шаги: [как воспроизвести]. Ожидание: [что должно быть]. Окружение: [ОС, Python, Pygame]. Скриншот: [если есть]."),
        ("comm_007_feature_request", "Шаблон feature request", "Описание: [что хочется]. Причина: [зачем]. Варианты: [как можно реализовать]. Приоритет: [low/medium/high]."),
        ("comm_008_discord_rules", "Правила Discord", "1. Будь уважителен. 2. Нет спама. 3. Используй каналы по теме. 4. Нет NSFW. 5. Нет политики. 6. Помогай новичкам. 7. Наслаждайся игрой."),
        ("comm_009_streamer_kit", "Streamer Kit", "Obs overlay template. Alert sounds. Chat commands (!gold, !hero, !stock). Stream description template. Hashtags: #CorpHeist #IndieGame #Python."),
        ("comm_010_fan_art Contest", "Фан-арт конкурс", "Приз: эксклюзивный hero skin. Категории: digital art, pixel art, 3D, meme. Жюри: community vote + developer pick. Частота: ежемесячно."),
    ]),
]

count = 0
for folder, files in extra:
    dirpath = os.path.join(CONTENT, folder)
    os.makedirs(dirpath, exist_ok=True)
    for filename, title, body in files:
        path = os.path.join(dirpath, f"{filename}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{'='*60}\n")
            f.write(f"{title}\n")
            f.write(f"{'='*60}\n\n")
            f.write(body.strip() + "\n")
        count += 1

print(f"Batch 2: создано {count} txt-файлов")
