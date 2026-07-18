#!/usr/bin/env python3
"""
CORP HEIST — Golden Economy Module
Everything scales by the golden ratio PHI = 1.618033988749...

This module is the connective tissue between:
  - GAMEPLAY  : phi-duel arena, hero progression, corp ranks
  - CONTENT   : corps, floors, Golden Artifact loot category
  - METAGAME  : guilds, leaderboard, market summary
  - VISUAL    : phi-spiral loot chains, fractal artifacts (see wealth_card.html)

Design rule: every reward/damage/threshold follows a phi curve so the
numbers feel "organic" and the UI can render them as golden spirals.
"""
import random
import math
import time

PHI = 1.618033988749
TAU = math.pi * 2.0


# ============================================================
# CONTENT DATA (corps, floors, artifacts)
# ============================================================

# 5 base corps + 3 new "golden" corps (7 total, a phi-friendly count)
CORPS = [
    "MERIDIAN", "APEX", "NOVA", "VERTEX", "PULSAR",
    "AUREATE", "SOLARIS",   # new golden corps
]

# 7 floors + 5 new "high-rise" floors (12 total: 12 = phi*phi*phi truncated-ish)
FLOORS = [
    "Lobby", "Trading Floor", "Vault", "Boardroom", "Data Center",
    "Sky Garden", "Penthouse",
    "Cloud Spire", "Gold Reserve", "Quantum Floor", "Throne Room", "Apex Atrium",
]

# New loot category: Golden Artifact (id 10) — drawn as fractal in client
ARTIFACT_BASE_VALUE = 50000
ARTIFACT_NAME_POOL = [
    "Golden Ratio", "Fib Spiral", "Phi Medallion", "Aurea Crown",
    "Midas Sigil", "Solar Compass", "Vault Key Prime", "Gilded Mandate",
]

# Hero power follows a phi curve per level
def hero_power(base, level):
    """Power grows as base * PHI^(level/10)."""
    return int(base * (PHI ** (level / 10.0)))

def _sky_combat(state, corp_id):
    """Combat power multiplier from the corp skyscraper (forward-safe)."""
    try:
        return sky_reward_mult(state, corp_id)
    except Exception:
        return 1.0

# Arena reward scales with opponent rank gap via phi (softened for balance)
def duel_reward(base_reward, rank_gap):
    """Higher-ranked opponent beaten => bigger reward by phi^(gap/2).
    Softer than phi^gap so top ranks stay reachable (max ~4x at gap 6)."""
    return int(base_reward * (PHI ** (min(rank_gap, 6) / 2.0)))

# Progression threshold to next level: phi-weighted
def level_threshold(level):
    return int(1000 * (PHI ** (level / 5.0)))


# ============================================================
# META: GUILDS / CORP RANKS
# ============================================================

class GuildSystem:
    """Corp-based guilds. Players grouped by corp_id. Rank by total net worth.
    Info-only (no real money, no P2P)."""

    def __init__(self, state):
        self.state = state

    def corp_totals(self):
        totals = {i: {"net": 0, "members": 0, "name": CORPS[i % len(CORPS)]}
                  for i in range(len(CORPS))}
        for c in self.state.chars.values():
            cid = c["corp_id"] % len(CORPS)
            totals[cid]["net"] += c["net_worth"]
            totals[cid]["members"] += 1
        ranking = sorted(totals.values(), key=lambda x: -x["net"])
        for rank, g in enumerate(ranking, 1):
            g["rank"] = rank
        return ranking

    def leaderboard(self, top=50):
        items = []
        for uid, c in self.state.chars.items():
            items.append({
                "user_id": uid,
                "name": f"Player_{uid}",
                "net_worth": c["net_worth"],
                "level": c["level"],
                "corp": CORPS[c["corp_id"] % len(CORPS)],
                "floor": FLOORS[c["floor"] % len(FLOORS)],
                "tier": c.get("tier", 0),
            })
        items.sort(key=lambda x: -x["net_worth"])
        for rank, it in enumerate(items[:top], 1):
            it["rank"] = rank
        return items[:top]

    def market_summary(self):
        """Info-only market snapshot: top movers, phi-banded volatility."""
        stocks = sorted(self.state.stocks, key=lambda s: -abs(s["delta"]))[:8]
        return {
            "top_movers": [
                {"name": s["name"], "price": s["price"], "delta": s["delta"]}
                for s in stocks
            ],
            "phi_band": round(PHI, 4),
            "note": "Informational only. No trading advice. Rates set by system.",
        }

    def season_rewards(self, top=10):
        """Top players by seasonal points. Prize pool split by phi:
        rank 1 gets a fraction, each next rank gets prev/phi (in-game gold)."""
        ranked = sorted(self.state.chars.values(),
                        key=lambda c: -season_points(c))[:top]
        season, week = current_season()
        # prize pool scales with number of players and season
        pool = int(1_000_000 * (PHI ** (week / SEASON_WEEKS)))
        # phi-decay shares: share_r = pool * (phi-1) / phi^r  (geometric, sums ~pool)
        rewards = []
        for r, c in enumerate(ranked, 1):
            share = int(pool * (PHI - 1) / (PHI ** r))
            rewards.append({
                "rank": r,
                "user_id": c["user_id"],
                "name": f"Player_{c['user_id']}",
                "points": season_points(c),
                "prize_gold": share,
                "corp": CORPS[c["corp_id"] % len(CORPS)],
            })
        return {
            "season": season,
            "week": week,
            "prize_pool": pool,
            "note": "Prizes are in-game gold only. No real money. Awarded at season end.",
            "top": rewards,
        }


# ============================================================
# GAMEPLAY: PHI-DUEL ARENA
# ============================================================

class Arena:
    """One-shot pulse duel. Opponent chosen by rank proximity (phi gap).
    Winner gains gold + xp scaled by phi; loser loses a fraction.
    No P2P, no real money — purely in-game economy."""

    def __init__(self, state):
        self.state = state

    def _rank_list(self):
        return sorted(self.state.chars.values(), key=lambda c: -c["net_worth"])

    def find_opponent(self, uid):
        ranked = self._rank_list()
        me = self.state.chars.get(uid)
        if not me:
            return None
        my_rank = next((i for i, c in enumerate(ranked) if c["user_id"] == uid), 0)
        # opponent at a phi-gap distance (1, 2, 3, 5, 8...) for fair-ish match
        gaps = [1, 2, 3, 5, 8, 13]
        gap = random.choice(gaps)
        opp_idx = min(len(ranked) - 1, my_rank + gap)
        return ranked[opp_idx], gap

    def fight(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        opp, gap = self.find_opponent(uid)
        if not opp:
            return {"error": "no opponent"}

        # passive bonuses (phi-scaled multipliers)
        mults = passive_bonus(me.get("passives", [0] * 12))
        pow_mult = mults.get("power_mult", 1.0)
        gold_mult = mults.get("gold_mult", 1.0)

        # power = hero power * level scaling * passive power_mult
        sky = _sky_combat(self.state, me["corp_id"])
        my_pow = hero_power(100 + me["level"] * 10, me["hero_levels"][me["hero_id"] % 12])
        my_pow = int(my_pow * pow_mult * sky)
        opp_pow = hero_power(100 + opp["level"] * 10, opp["hero_levels"][opp["hero_id"] % 12])
        # add a little randomness (phi-weighted swing)
        swing = random.uniform(1 / PHI, PHI)
        my_pow = int(my_pow * swing)

        win = my_pow >= opp_pow
        base = 500 * (me["level"] + 1)
        reward = duel_reward(base, gap) if win else -int(base / PHI)
        # gold_mult applies to positive rewards only
        if reward > 0:
            reward = int(reward * gold_mult)

        me["gold"] = max(0, me["gold"] + reward)
        me["xp"] += reward if win else 0
        # level up check (phi threshold)
        while me["xp"] >= level_threshold(me["level"]):
            me["xp"] -= level_threshold(me["level"])
            me["level"] += 1
        self.state.mark_dirty(uid)

        return {
            "win": win,
            "my_power": my_pow,
            "opp_power": opp_pow,
            "opp_name": f"Player_{opp['user_id']}",
            "reward_gold": reward,
            "level": me["level"],
            "phi_swing": round(swing, 3),
            "gap": gap,
            "power_mult": round(pow_mult, 3),
            "gold_mult": round(gold_mult, 3),
        }


# ============================================================
# CONTENT: GOLDEN ARTIFACT LOOT
# ============================================================

def roll_artifact():
    """Generate a Golden Artifact loot entry (category 10)."""
    code = random.randint(0, 65535)
    value = int(ARTIFACT_BASE_VALUE * (PHI ** random.uniform(0, 3)))
    return {
        "code": code,
        "rarity": 5,            # artifact is top rarity
        "cat": 10,              # 10 = golden artifact (client renders fractal)
        "name": random.choice(ARTIFACT_NAME_POOL),
        "qty": 1,
        "value": value,
        "phi_seed": round(random.uniform(0, TAU), 4),
    }


def maybe_drop_artifact(chance=0.02):
    if random.random() < chance:
        return roll_artifact()
    return None


# ============================================================
# SEASONS (phi-weeks: a season = PHI * 7 ≈ 11.3 weeks)
# ============================================================

SEASON_WEEKS = int(PHI * 7)          # ~11 weeks per season
SEASON_EPOCH = 1700000000            # arbitrary fixed epoch (unix-ish)
WEEK_SEC = 7 * 24 * 3600

def current_season(now=None):
    now = now or int(time.time())
    weeks = (now - SEASON_EPOCH) // WEEK_SEC
    return weeks // SEASON_WEEKS, (weeks % SEASON_WEEKS) + 1

def season_progress(now=None):
    now = now or int(time.time())
    weeks = (now - SEASON_EPOCH) // WEEK_SEC
    return round((weeks % SEASON_WEEKS + 1) / SEASON_WEEKS, 3)

def season_points(char):
    """Seasonal rating points scale with phi: net_worth^0.5 * phi^(prestige)."""
    base = math.sqrt(max(1, char.get("net_worth", 0)))
    return int(base * (PHI ** char.get("prestige", 0)))


# ============================================================
# PASSIVE TREE (phi-cost nodes, phi-scaled bonuses)
# ============================================================
# 12 nodes; unlock cost scales by phi^(depth). Each node multiplies a stat.

PASSIVE_NODES = [
    {"id": i, "name": n, "stat": s, "depth": i // 3,
     "cost": int(50 * (PHI ** (i // 3))),
     "mult": round(PHI ** (0.25 + (i % 3) * 0.1), 3)}
    for i, (n, s) in enumerate([
        ("Gold Yield", "gold_mult"), ("Duel Power", "power_mult"),
        ("Loot Luck", "luck_mult"), ("Trade Edge", "trade_mult"),
        ("Vault Cap", "cap_mult"), ("Prestige Gain", "pres_mult"),
        ("Floor Reach", "floor_mult"), ("Market Sense", "market_mult"),
        ("Guild Bond", "guild_mult"), ("Artifact Find", "art_mult"),
        ("Net Worth", "net_mult"), ("Phi Mastery", "phi_mult"),
    ])
]

def passive_bonus(passives):
    """passives = list of 12 ints (levels per node). Return aggregated mults."""
    mults = {}
    for node, lvl in zip(PASSIVE_NODES, passives):
        mults[node["stat"]] = round(mults.get(node["stat"], 1.0) * (node["mult"] ** lvl), 4)
    return mults

def unlock_cost(node_id, current_lvl):
    node = PASSIVE_NODES[node_id]
    return int(node["cost"] * (PHI ** current_lvl))


# ============================================================
# PRESTIGE / ASCENSION (reset progress for a permanent phi-multiplier)
# ============================================================
# Ascending resets level/xp/gold to base but grants a permanent prestige rank.
# Every stat that reads prestige (season_points, gold gains) grows by phi^prestige.

PRESTIGE_BASE_LEVEL = 21      # min level to ascend (Fibonacci number)
PRESTIGE_BASE_NET = 100_000   # min net worth to ascend

def prestige_requirement(current_prestige):
    """Requirement scales by phi each ascension."""
    lvl = int(PRESTIGE_BASE_LEVEL * (PHI ** current_prestige))
    net = int(PRESTIGE_BASE_NET * (PHI ** current_prestige))
    return {"level": lvl, "net_worth": net}

def prestige_multiplier(prestige):
    """Permanent global gold/power multiplier from prestige ranks."""
    return round(PHI ** prestige, 4)


class Prestige:
    """Ascension system. Reset level/xp/gold; gain a permanent prestige rank.
    Purely in-game — no real money involved."""

    def __init__(self, state):
        self.state = state

    def status(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        p = me.get("prestige", 0)
        req = prestige_requirement(p)
        eligible = me["level"] >= req["level"] and me.get("net_worth", 0) >= req["net_worth"]
        # pres_mult passive boosts the prestige reward multiplier
        mults = passive_bonus(me.get("passives", [0] * 12))
        pres_boost = mults.get("pres_mult", 1.0)
        return {
            "prestige": p,
            "current_mult": prestige_multiplier(p),
            "next_mult": round(prestige_multiplier(p + 1) * pres_boost, 4),
            "requirement": req,
            "level": me["level"],
            "net_worth": me.get("net_worth", 0),
            "eligible": eligible,
        }

    def ascend(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        st = self.status(uid)
        if not st.get("eligible"):
            return {"error": "not eligible", **st}
        me["prestige"] = me.get("prestige", 0) + 1
        # reset progression (keep passives, prestige, corp identity)
        me["level"] = 1
        me["xp"] = 0
        me["gold"] = 1000
        me["net_worth"] = PRESTIGE_BASE_NET  # keep a phi-seed of net worth
        self.state.mark_dirty(uid)
        return {
            "ascended": True,
            "prestige": me["prestige"],
            "new_mult": prestige_multiplier(me["prestige"]),
            "note": "Progress reset. Permanent phi-multiplier gained (in-game only).",
        }


# ============================================================
# GUILD RAIDS (coop boss; phi-scaled HP; loot split by phi shares)
# ============================================================
# The whole corp attacks a shared boss. Each strike deals damage = hero power.
# Boss HP scales by phi with the season week. Loot pool splits by phi-decay.

RAID_BASE_HP = 5_000_000

class Raid:
    """Per-corp coop boss. State stored on GuildState.raids[corp_id]."""

    def __init__(self, state):
        self.state = state
        if not hasattr(state, "raids"):
            state.raids = {}

    def _boss(self, corp_id):
        season, week = current_season()
        max_hp = int(RAID_BASE_HP * (PHI ** (week / PHI)))
        r = self.state.raids.get(corp_id)
        if not r or r.get("season_week") != (season, week):
            r = {
                "corp_id": corp_id,
                "name": f"{CORPS[corp_id % len(CORPS)]} Titan",
                "max_hp": max_hp,
                "hp": max_hp,
                "season_week": (season, week),
                "contributions": {},   # uid -> total damage
            }
            self.state.raids[corp_id] = r
        return r

    def status(self, corp_id):
        r = self._boss(corp_id)
        top = sorted(r["contributions"].items(), key=lambda kv: -kv[1])[:10]
        return {
            "boss": r["name"],
            "hp": r["hp"],
            "max_hp": r["max_hp"],
            "pct": round(100 * r["hp"] / r["max_hp"], 2),
            "defeated": r["hp"] <= 0,
            "top_contributors": [
                {"user_id": u, "damage": d} for u, d in top
            ],
        }

    def strike(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        corp_id = me["corp_id"] % len(CORPS)
        r = self._boss(corp_id)
        if r["hp"] <= 0:
            return {"error": "boss already defeated", **self.status(corp_id)}

        mults = passive_bonus(me.get("passives", [0] * 12))
        pres = prestige_multiplier(me.get("prestige", 0))
        base = hero_power(100 + me["level"] * 10,
                          me["hero_levels"][me["hero_id"] % 12])
        dmg = int(base * mults.get("power_mult", 1.0) * pres *
                  _sky_combat(self.state, corp_id) *
                  random.uniform(1 / PHI, PHI))
        r["hp"] = max(0, r["hp"] - dmg)
        r["contributions"][uid] = r["contributions"].get(uid, 0) + dmg
        self.state.mark_dirty(uid)

        result = {"damage": dmg, "boss_hp": r["hp"], "boss_max": r["max_hp"]}
        if r["hp"] <= 0:
            result["defeated"] = True
            result["loot"] = self._distribute(r)
        return result

    def _distribute(self, r):
        """Split a phi-scaled loot pool among contributors by phi-decay shares
        ordered by damage dealt. In-game gold only."""
        pool = int(r["max_hp"] // PHI)   # gold pool ~ boss HP / phi
        ranked = sorted(r["contributions"].items(), key=lambda kv: -kv[1])
        out = []
        for rank, (u, dmg) in enumerate(ranked, 1):
            share = int(pool * (PHI - 1) / (PHI ** rank))
            c = self.state.chars.get(u)
            if c:
                c["gold"] = c.get("gold", 0) + share
                self.state.mark_dirty(u)
            out.append({"rank": rank, "user_id": u, "damage": dmg,
                        "reward_gold": share})
        return {"pool": pool, "shares": out,
                "note": "Raid loot is in-game gold only. No real money."}


# ============================================================
# DAILY PHI-QUESTS (3/day; phi-scaled gold rewards)
# ============================================================
# Deterministic per (uid, day) so all clients agree without server storage.

QUEST_POOL = [
    ("Win {n} phi-duels", "duels"),
    ("Reach net worth {n}", "net"),
    ("Unlock {n} passive levels", "passives"),
    ("Deal {n} raid damage", "raid"),
    ("Earn {n} gold today", "gold"),
]

def _day_index(now=None):
    now = now or int(time.time())
    return now // (24 * 3600)

def daily_quests(uid, now=None):
    """Return 3 deterministic quests for the day, phi-scaled rewards."""
    day = _day_index(now)
    rng = random.Random(uid * 1_000_003 + day)
    picks = rng.sample(range(len(QUEST_POOL)), 3)
    quests = []
    for slot, idx in enumerate(picks):
        desc, kind = QUEST_POOL[idx]
        target = int(3 * (PHI ** (slot + rng.randint(1, 3))))
        reward = int(1000 * (PHI ** (slot + 2)))
        quests.append({
            "slot": slot,
            "kind": kind,
            "desc": desc.format(n=target),
            "target": target,
            "reward_gold": reward,
        })
    return {"day": day, "quests": quests,
            "note": "Rewards are in-game gold only."}

def claim_quest(state, uid, slot, now=None):
    """Claim a quest reward (server trusts client progress for this info-game).
    Prevents double-claim via char['quest_claims'] = {day: [slots]}."""
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    day = _day_index(now)
    q = daily_quests(uid, now)["quests"]
    if slot < 0 or slot >= len(q):
        return {"error": "bad slot"}
    claims = me.setdefault("quest_claims", {})
    day_key = str(day)
    done = claims.setdefault(day_key, [])
    if slot in done:
        return {"error": "already claimed", "slot": slot}
    reward = q[slot]["reward_gold"]
    me["gold"] = me.get("gold", 0) + reward
    done.append(slot)
    # prune old days
    for k in list(claims.keys()):
        if k != day_key:
            del claims[k]
    state.mark_dirty(uid)
    return {"claimed": True, "slot": slot, "reward_gold": reward,
            "gold": me["gold"]}


# ============================================================
# ACHIEVEMENTS / BADGES (phi-thresholded milestones)
# ============================================================

# id, name, description, check(char)->bool, reward_gold (phi-scaled)
ACHIEVEMENTS = [
    ("first_loot",  "First Blood",     "Own at least 1 loot item",
        lambda c: len(c.get("loot", [])) >= 1,                       int(1000 * PHI**1)),
    ("collector",   "Collector",       "Own 13 loot items (Fib)",
        lambda c: len(c.get("loot", [])) >= 13,                      int(1000 * PHI**3)),
    ("hoarder",     "Golden Hoarder",  "Own 55 loot items (Fib)",
        lambda c: len(c.get("loot", [])) >= 55,                      int(1000 * PHI**5)),
    ("rising",      "Rising Star",     "Reach level 8",
        lambda c: c.get("level", 1) >= 8,                            int(1000 * PHI**2)),
    ("executive",   "Executive",       "Reach level 21 (phi tier)",
        lambda c: c.get("level", 1) >= 21,                           int(1000 * PHI**4)),
    ("magnate",     "Magnate",         "Net worth over 1,000,000",
        lambda c: c.get("net_worth", 0) >= 1_000_000,                int(1000 * PHI**6)),
    ("tycoon",      "Golden Tycoon",   "Net worth over 100,000,000",
        lambda c: c.get("net_worth", 0) >= 100_000_000,              int(1000 * PHI**8)),
    ("ascended",    "Ascended",        "Prestige at least once",
        lambda c: c.get("prestige", 0) >= 1,                         int(1000 * PHI**5)),
    ("transcend",   "Transcendent",    "Prestige 5 times",
        lambda c: c.get("prestige", 0) >= 5,                         int(1000 * PHI**7)),
    ("streaker",    "Devoted",         "13-day login streak (Fib)",
        lambda c: c.get("streak_days", 0) >= 13,                     int(1000 * PHI**4)),
    ("topfloor",    "Top Floor",       "Reach the Apex Atrium (floor 12)",
        lambda c: c.get("floor", 0) >= 11,                           int(1000 * PHI**5)),
    ("artifact",    "Artifact Bearer", "Own a Golden Artifact",
        lambda c: any(l.get("rarity", 0) >= 5 or l.get("cat") == 10 for l in c.get("loot", [])),
                                                                     int(1000 * PHI**6)),
]

def evaluate_achievements(char):
    """Return list of achievement states for a char (unlocked flag + reward)."""
    out = []
    for aid, name, desc, check, reward in ACHIEVEMENTS:
        try:
            done = bool(check(char))
        except Exception:
            done = False
        out.append({"id": aid, "name": name, "desc": desc,
                    "unlocked": done, "reward_gold": reward})
    return out

def claim_achievements(state, uid):
    """Grant gold for newly-unlocked achievements (once each).
    Tracks claimed ids in char['ach_claimed']."""
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    claimed = me.setdefault("ach_claimed", [])
    total = 0
    newly = []
    for a in evaluate_achievements(me):
        if a["unlocked"] and a["id"] not in claimed:
            claimed.append(a["id"])
            total += a["reward_gold"]
            newly.append({"id": a["id"], "name": a["name"],
                          "reward_gold": a["reward_gold"]})
    if total:
        me["gold"] = me.get("gold", 0) + total
        state.mark_dirty(uid)
    return {"granted_gold": total, "newly_unlocked": newly,
            "achievements": evaluate_achievements(me),
            "note": "Rewards are in-game gold only."}


# ============================================================
# REFERRAL SYSTEM (invite a friend -> phi bonus, in-game gold only)
# ============================================================

REFERRAL_BONUS = int(1000 * PHI ** 4)   # bonus to referrer per accepted invite

def referral_code(uid):
    """Deterministic short code for a user id (base36-ish)."""
    n = (uid * 2654435761) & 0xFFFFFF
    alpha = "ACDEFGHJKLMNPQRSTUVWXYZ23456789"
    s = ""
    for _ in range(5):
        s = alpha[n % len(alpha)] + s
        n //= len(alpha)
    return "PHI-" + s

def _code_to_uid_map(state):
    return {referral_code(u): u for u in state.chars.keys()}

def accept_referral(state, uid, code):
    """New player redeems a referral code. Both sides get in-game gold.
    Guards: cannot self-refer, cannot redeem twice."""
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    if me.get("referred_by"):
        return {"error": "already redeemed a code"}
    ref_uid = _code_to_uid_map(state).get(str(code).strip().upper())
    if ref_uid is None:
        return {"error": "invalid code"}
    if ref_uid == uid:
        return {"error": "cannot refer yourself"}
    # newcomer bonus (phi-scaled, slightly smaller than referrer's)
    newbie_bonus = int(REFERRAL_BONUS / PHI)
    me["referred_by"] = ref_uid
    me["gold"] = me.get("gold", 0) + newbie_bonus
    referrer = state.chars.get(ref_uid)
    if referrer is not None:
        referrer["gold"] = referrer.get("gold", 0) + REFERRAL_BONUS
        referrer["referrals"] = referrer.get("referrals", 0) + 1
        state.mark_dirty(ref_uid)
    state.mark_dirty(uid)
    return {"accepted": True, "referrer": ref_uid,
            "your_bonus": newbie_bonus, "referrer_bonus": REFERRAL_BONUS,
            "gold": me["gold"], "note": "In-game gold only. No real money."}

def referral_status(state, uid):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    return {"code": referral_code(uid),
            "referrals": me.get("referrals", 0),
            "earned_gold": me.get("referrals", 0) * REFERRAL_BONUS,
            "referred_by": me.get("referred_by"),
            "bonus_per_invite": REFERRAL_BONUS,
            "note": "Invite friends for in-game gold. No real-money reward."}


# ============================================================
# DAILY GOLDEN CHEST (phi-timer, streak-scaled reward)
# ============================================================

CHEST_BASE = int(1000 * PHI ** 3)   # base daily gold

def chest_status(state, uid, now=None):
    """Report whether today's chest is available + next reward preview."""
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    now = now or int(time.time())
    day = now // (24 * 3600)
    last = me.get("chest_day", -1)
    available = (day != last)
    # streak grows while claimed on consecutive days
    streak = me.get("chest_streak", 0)
    preview_streak = streak + 1 if available else streak
    reward = int(CHEST_BASE * (PHI ** min(preview_streak, 8) / PHI))
    secs_left = 0 if available else ((last + 1) * 24 * 3600 - now)
    return {
        "available": available,
        "chest_streak": streak,
        "reward_preview": reward,
        "seconds_left": max(0, secs_left),
        "note": "Daily chest gives in-game gold only.",
    }

def open_chest(state, uid, now=None):
    """Open the daily chest -> in-game gold, phi-scaled by chest streak."""
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    now = now or int(time.time())
    day = now // (24 * 3600)
    last = me.get("chest_day", -1)
    if day == last:
        return {"error": "already opened today", **chest_status(state, uid, now)}
    # consecutive-day streak
    if last == day - 1:
        me["chest_streak"] = me.get("chest_streak", 0) + 1
    else:
        me["chest_streak"] = 1
    streak = me["chest_streak"]
    reward = int(CHEST_BASE * (PHI ** min(streak, 8) / PHI))
    me["chest_day"] = day
    me["gold"] = me.get("gold", 0) + reward
    state.mark_dirty(uid)
    return {"opened": True, "reward_gold": reward, "chest_streak": streak,
            "gold": me["gold"], "note": "In-game gold only."}


# ============================================================
# WORLD BOSS (single global boss, shared HP for everyone)
# ============================================================

WORLD_BOSS_NAMES = ["Aurum Leviathan", "The Gilded Devourer", "Phi Colossus",
                    "Midas Wyrm", "Sovereign of Debt", "The Golden Maw"]
WORLD_BOSS_BASE_HP = 50_000_000

class WorldBoss:
    """One global boss shared by all players. State on state.world_boss.
    Rolls a new boss each phi-week; loot pool shared by phi-shares."""

    def __init__(self, state):
        self.state = state
        if not hasattr(state, "world_boss"):
            state.world_boss = None

    def _boss(self):
        season, week = current_season()
        wb = self.state.world_boss
        # scale HP up each week; new boss identity per season-week
        max_hp = int(WORLD_BOSS_BASE_HP * (PHI ** (week / PHI)))
        if not wb or wb.get("season_week") != [season, week]:
            idx = (season * 7 + week) % len(WORLD_BOSS_NAMES)
            wb = {
                "name": WORLD_BOSS_NAMES[idx],
                "max_hp": max_hp,
                "hp": max_hp,
                "season_week": [season, week],
                "contributions": {},     # uid -> total damage
                "loot_pool": int(1_000_000 * (PHI ** (week / PHI))),
            }
            self.state.world_boss = wb
        return wb

    def status(self):
        wb = self._boss()
        top = sorted(wb["contributions"].items(), key=lambda kv: -kv[1])[:10]
        return {
            "boss": wb["name"],
            "hp": wb["hp"],
            "max_hp": wb["max_hp"],
            "pct": round(100 * wb["hp"] / wb["max_hp"], 4),
            "defeated": wb["hp"] <= 0,
            "loot_pool": wb["loot_pool"],
            "participants": len(wb["contributions"]),
            "top_contributors": [{"user_id": int(u), "damage": d}
                                 for u, d in top],
            "season_week": wb["season_week"],
            "note": "Shared world boss. Rewards are in-game gold only.",
        }

    def strike(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        wb = self._boss()
        if wb["hp"] <= 0:
            return {"error": "world boss already defeated", **self.status()}
        mults = passive_bonus(me.get("passives", [0] * 12))
        pres = prestige_multiplier(me.get("prestige", 0))
        base = hero_power(100 + me.get("level", 1) * 10,
                          me.get("hero_levels", [1] * 12)[me.get("hero_id", 0) % 12])
        dmg = int(base * mults.get("power_mult", 1.0) * pres *
                  _sky_combat(self.state, me["corp_id"]) *
                  random.uniform(1 / PHI, PHI))
        wb["hp"] = max(0, wb["hp"] - dmg)
        key = str(uid)
        wb["contributions"][key] = wb["contributions"].get(key, 0) + dmg
        result = {"damage": dmg, "boss_hp": wb["hp"], "boss_max": wb["max_hp"],
                  "boss": wb["name"],
                  "pct": round(100 * wb["hp"] / wb["max_hp"], 4)}
        if wb["hp"] <= 0:
            # distribute loot pool by phi-weighted contribution shares
            result["defeated"] = True
            ranked = sorted(wb["contributions"].items(), key=lambda kv: -kv[1])
            pool = wb["loot_pool"]
            payouts = {}
            for rank, (u, _d) in enumerate(ranked):
                share = int(pool * (PHI - 1) / (PHI ** rank))
                payouts[u] = share
                cu = int(u)
                ch = self.state.chars.get(cu)
                if ch is not None:
                    ch["gold"] = ch.get("gold", 0) + share
                    self.state.mark_dirty(cu)
            result["my_reward"] = payouts.get(key, 0)
            result["payouts_count"] = len(payouts)
        self.state.mark_dirty(uid)
        return result


# ============================================================
# AUCTION HOUSE (list an item, others outbid; in-game gold only)
# ============================================================

AUCTION_DURATION = 3600          # seconds a listing stays open
AUCTION_MIN_INCREMENT = PHI       # each bid must beat current by * phi-ish

class Auction:
    """Player auctions. State on state.auctions (list of dicts).
    Bids and payouts are in-game gold only."""

    def __init__(self, state):
        self.state = state
        if not hasattr(state, "auctions"):
            state.auctions = []
        if not hasattr(state, "_auction_seq"):
            state._auction_seq = 0

    def _expire(self, now):
        """Settle auctions that ran out of time."""
        for a in self.state.auctions:
            if a["status"] == "open" and now >= a["ends"]:
                self._settle(a)

    def _settle(self, a):
        a["status"] = "sold" if a.get("top_bidder") else "expired"
        seller = self.state.chars.get(a["seller"])
        if a.get("top_bidder"):
            # gold already escrowed from bidder at bid time -> pay seller
            if seller is not None:
                seller["gold"] = seller.get("gold", 0) + a["top_bid"]
                self.state.mark_dirty(a["seller"])
            # give item to winner
            winner = self.state.chars.get(a["top_bidder"])
            if winner is not None:
                winner.setdefault("loot", []).append(dict(a["item"]))
                winner["net_worth"] = winner.get("net_worth", 0) + a["item"].get("value", 0)
                self.state.mark_dirty(a["top_bidder"])
        else:
            # no bids: return item to seller
            if seller is not None:
                seller.setdefault("loot", []).append(dict(a["item"]))
                seller["net_worth"] = seller.get("net_worth", 0) + a["item"].get("value", 0)
                self.state.mark_dirty(a["seller"])

    def list_item(self, uid, code, start_price, now=None):
        now = now or int(time.time())
        self._expire(now)
        me = self.state.chars.get(uid)
        if not me or not me.get("loot"):
            return {"error": "no loot"}
        item = next((l for l in me["loot"] if l["code"] == code), None)
        if not item:
            return {"error": "item not found"}
        me["loot"].remove(item)
        me["net_worth"] = me.get("net_worth", 0) - item.get("value", 0)
        self.state._auction_seq += 1
        start = max(1, int(start_price or int(item.get("value", 10) / PHI)))
        a = {"id": self.state._auction_seq, "seller": uid, "item": dict(item),
             "start_price": start, "top_bid": 0, "top_bidder": None,
             "ends": now + AUCTION_DURATION, "status": "open"}
        self.state.auctions.append(a)
        self.state.mark_dirty(uid)
        return {"ok": True, "auction": self._public(a, now)}

    def bid(self, uid, auction_id, amount, now=None):
        now = now or int(time.time())
        self._expire(now)
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        a = next((x for x in self.state.auctions if x["id"] == auction_id), None)
        if not a or a["status"] != "open":
            return {"error": "auction closed"}
        if a["seller"] == uid:
            return {"error": "cannot bid on your own listing"}
        min_bid = max(a["start_price"], int(a["top_bid"] * AUCTION_MIN_INCREMENT) + 1)
        amount = int(amount)
        if amount < min_bid:
            return {"error": f"bid must be >= {min_bid}", "min_bid": min_bid}
        if me.get("gold", 0) < amount:
            return {"error": "not enough gold"}
        # refund previous top bidder
        prev = self.state.chars.get(a["top_bidder"]) if a["top_bidder"] else None
        if prev is not None:
            prev["gold"] = prev.get("gold", 0) + a["top_bid"]
            self.state.mark_dirty(a["top_bidder"])
        # escrow new bid
        me["gold"] -= amount
        a["top_bid"] = amount
        a["top_bidder"] = uid
        self.state.mark_dirty(uid)
        return {"ok": True, "auction": self._public(a, now), "gold": me["gold"]}

    def _public(self, a, now):
        return {"id": a["id"], "seller": a["seller"],
                "item": a["item"], "start_price": a["start_price"],
                "top_bid": a["top_bid"], "top_bidder": a["top_bidder"],
                "seconds_left": max(0, a["ends"] - now),
                "min_next": max(a["start_price"], int(a["top_bid"] * AUCTION_MIN_INCREMENT) + 1),
                "status": a["status"]}

    def listings(self, now=None):
        now = now or int(time.time())
        self._expire(now)
        return {"auctions": [self._public(a, now) for a in self.state.auctions
                             if a["status"] == "open"],
                "note": "Bids are in-game gold only. No real money."}


# ============================================================
# GUILD WARS (two corps race to beat a shared war-boss)
# ============================================================

WAR_BASE_HP = 20_000_000

class GuildWar:
    """Two corps race to deal the most damage to a shared war boss
    within a phi-week. Winner corp splits a phi prize pool (in-game gold)."""

    def __init__(self, state):
        self.state = state
        if not hasattr(state, "guild_war"):
            state.guild_war = None

    def _war(self):
        season, week = current_season()
        gw = self.state.guild_war
        if not gw or gw.get("season_week") != [season, week]:
            # pair corps 0v1 rotating by week
            a = (week * 2) % len(CORPS)
            b = (a + 1) % len(CORPS)
            hp = int(WAR_BASE_HP * (PHI ** (week / PHI)))
            gw = {
                "corp_a": a, "corp_b": b,
                "name_a": CORPS[a], "name_b": CORPS[b],
                "hp": hp, "max_hp": hp,
                "dmg_a": 0, "dmg_b": 0,
                "season_week": [season, week],
                "prize_pool": int(500_000 * (PHI ** (week / PHI))),
                "contributions": {},   # uid -> dmg
            }
            self.state.guild_war = gw
        return gw

    def status(self):
        gw = self._war()
        total = gw["dmg_a"] + gw["dmg_b"] or 1
        return {
            "boss": "War Titan",
            "corp_a": gw["name_a"], "corp_b": gw["name_b"],
            "dmg_a": gw["dmg_a"], "dmg_b": gw["dmg_b"],
            "share_a": round(100 * gw["dmg_a"] / total, 2),
            "share_b": round(100 * gw["dmg_b"] / total, 2),
            "hp": gw["hp"], "max_hp": gw["max_hp"],
            "pct": round(100 * gw["hp"] / gw["max_hp"], 2),
            "leader": (gw["name_a"] if gw["dmg_a"] >= gw["dmg_b"] else gw["name_b"]),
            "prize_pool": gw["prize_pool"],
            "defeated": gw["hp"] <= 0,
            "note": "Guild war rewards are in-game gold only.",
        }

    def attack(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        gw = self._war()
        corp = me["corp_id"] % len(CORPS)
        if corp not in (gw["corp_a"], gw["corp_b"]):
            return {"error": "your corp is not in this war",
                    "corp_a": gw["name_a"], "corp_b": gw["name_b"]}
        if gw["hp"] <= 0:
            return {"error": "war already decided", **self.status()}
        mults = passive_bonus(me.get("passives", [0] * 12))
        pres = prestige_multiplier(me.get("prestige", 0))
        base = hero_power(100 + me.get("level", 1) * 10,
                          me.get("hero_levels", [1] * 12)[me.get("hero_id", 0) % 12])
        dmg = int(base * mults.get("power_mult", 1.0) * pres *
                  _sky_combat(self.state, me["corp_id"]) *
                  random.uniform(1 / PHI, PHI))
        gw["hp"] = max(0, gw["hp"] - dmg)
        if corp == gw["corp_a"]:
            gw["dmg_a"] += dmg
        else:
            gw["dmg_b"] += dmg
        gw["contributions"][str(uid)] = gw["contributions"].get(str(uid), 0) + dmg
        self.state.mark_dirty(uid)
        result = {"damage": dmg, "for_corp": CORPS[corp], **self.status()}
        if gw["hp"] <= 0:
            win_corp = gw["corp_a"] if gw["dmg_a"] >= gw["dmg_b"] else gw["corp_b"]
            # payout winners by phi-share of their contribution
            winners = [(int(u), d) for u, d in gw["contributions"].items()
                       if self.state.chars.get(int(u), {}).get("corp_id", -1) % len(CORPS) == win_corp]
            winners.sort(key=lambda x: -x[1])
            pool = gw["prize_pool"]
            for rank, (u, _d) in enumerate(winners):
                share = int(pool * (PHI - 1) / (PHI ** rank))
                ch = self.state.chars.get(u)
                if ch is not None:
                    ch["gold"] = ch.get("gold", 0) + share
                    self.state.mark_dirty(u)
            result["winner"] = CORPS[win_corp]
            result["winners_paid"] = len(winners)
        return result


# ============================================================
# INVESTMENT BONDS (phi-yield on a timer; in-game gold)
# ============================================================

BOND_TIERS = [
    # name, min_principal, phi_power (yield=principal*(phi**power)-principal), lock_seconds
    ("Bronze φ-Bond",   1_000,   0.15, 3600),
    ("Silver φ-Bond",   10_000,  0.30, 4 * 3600),
    ("Gold φ-Bond",     100_000, 0.50, 12 * 3600),
    ("Platinum φ-Bond", 1_000_000, 0.80, 24 * 3600),
]

def bond_tiers():
    out = []
    for name, minp, power, lock in BOND_TIERS:
        yld = round((PHI ** power) - 1, 4)
        out.append({"name": name, "min_principal": minp,
                    "yield_pct": round(yld * 100, 2), "lock_seconds": lock})
    return {"tiers": out, "note": "Bond yields are in-game gold only."}

def buy_bond(state, uid, tier_idx, principal, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    if tier_idx < 0 or tier_idx >= len(BOND_TIERS):
        return {"error": "bad tier"}
    name, minp, power, lock = BOND_TIERS[tier_idx]
    principal = int(principal)
    if principal < minp:
        return {"error": f"minimum principal is {minp}"}
    if me.get("gold", 0) < principal:
        return {"error": "not enough gold"}
    me["gold"] -= principal
    rate = central_rate(now)
    payout = int(principal * (PHI ** (power * rate)))
    bond = {"id": now * 1000 + random.randint(0, 999), "tier": tier_idx,
            "name": name, "principal": principal, "payout": payout,
            "cb_rate": rate, "matures": now + lock}
    me.setdefault("bonds", []).append(bond)
    state.mark_dirty(uid)
    return {"ok": True, "bond": bond, "gold": me["gold"]}

def bond_status(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    bonds = me.get("bonds", [])
    out = []
    for b in bonds:
        out.append({**b, "matured": now >= b["matures"],
                    "seconds_left": max(0, b["matures"] - now)})
    return {"bonds": out, "gold": me.get("gold", 0), **bond_tiers()}

def claim_bonds(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    bonds = me.get("bonds", [])
    matured = [b for b in bonds if now >= b["matures"]]
    total = sum(b["payout"] for b in matured)
    me["bonds"] = [b for b in bonds if now < b["matures"]]
    if total:
        me["gold"] = me.get("gold", 0) + total
        state.mark_dirty(uid)
    return {"claimed_count": len(matured), "payout": total,
            "gold": me.get("gold", 0),
            "note": "Bond payouts are in-game gold only."}


# ============================================================
# DERIVATIVES EXCHANGE (phi options & futures on corp stocks)
# ============================================================

# Contract expires after a phi-scaled window; strike/premium follow phi.
DERIV_EXPIRY = int(1800 * PHI)     # ~48.5 min lock
DERIV_PREMIUM_RATE = PHI - 1       # 0.618 of intrinsic-ish, scales premium

def _stock_by_name(state, name):
    for s in getattr(state, "stocks", []):
        if s["name"] == name:
            return s
    return None

def deriv_quote(state, name):
    """Quote a phi option/future chain for a stock."""
    s = _stock_by_name(state, name)
    if not s:
        return {"error": "unknown symbol"}
    spot = s["price"]
    # phi-laddered strikes around spot
    strikes = [round(spot / PHI, 2), round(spot, 2), round(spot * PHI, 2)]
    chain = []
    for k in strikes:
        # premium scales with distance and phi
        call_prem = round(max(spot - k, 0) + spot * DERIV_PREMIUM_RATE / PHI, 2)
        put_prem = round(max(k - spot, 0) + spot * DERIV_PREMIUM_RATE / PHI, 2)
        chain.append({"strike": k, "call_premium": call_prem, "put_premium": put_prem})
    return {"symbol": name, "spot": spot, "delta": s.get("delta", 0),
            "chain": chain, "future_price": round(spot * (1 + DERIV_PREMIUM_RATE / (PHI ** 3)), 2),
            "expiry_seconds": DERIV_EXPIRY,
            "note": "Derivatives settle in in-game gold only."}

def open_position(state, uid, name, kind, strike, qty, now=None):
    """kind: 'call' | 'put' | 'future'. Pay premium/margin in gold."""
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    s = _stock_by_name(state, name)
    if not s:
        return {"error": "unknown symbol"}
    kind = str(kind).lower()
    qty = max(1, int(qty))
    spot = s["price"]
    if kind == "future":
        entry = round(spot * (1 + DERIV_PREMIUM_RATE / (PHI ** 3)), 2)
        cost = round(entry * qty / PHI, 2)      # margin = 1/phi of notional
        strike = entry
    elif kind in ("call", "put"):
        strike = round(float(strike), 2)
        prem = (max(spot - strike, 0) if kind == "call" else max(strike - spot, 0)) + spot * DERIV_PREMIUM_RATE / PHI
        cost = round(prem * qty, 2)
    else:
        return {"error": "bad kind"}
    if me.get("gold", 0) < cost:
        return {"error": "not enough gold", "cost": cost}
    me["gold"] -= int(math.ceil(cost))
    pos = {"id": now * 1000 + random.randint(0, 999), "symbol": name,
           "kind": kind, "strike": strike, "qty": qty,
           "entry_spot": spot, "cost": int(math.ceil(cost)),
           "expires": now + DERIV_EXPIRY}
    me.setdefault("derivs", []).append(pos)
    state.mark_dirty(uid)
    return {"ok": True, "position": pos, "gold": me["gold"]}

def _settle_value(pos, spot):
    q = pos["qty"]
    if pos["kind"] == "call":
        return max(spot - pos["strike"], 0) * q
    if pos["kind"] == "put":
        return max(pos["strike"] - spot, 0) * q
    # future: profit vs entry + return margin
    return (spot - pos["strike"]) * q / PHI + pos["cost"]

def deriv_status(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    out = []
    for p in me.get("derivs", []):
        s = _stock_by_name(state, p["symbol"])
        spot = s["price"] if s else p["entry_spot"]
        val = round(_settle_value(p, spot), 2)
        out.append({**p, "spot": spot, "settle_value": val,
                    "pnl": round(val - (0 if p["kind"] == "future" else p["cost"]), 2),
                    "expired": now >= p["expires"],
                    "seconds_left": max(0, p["expires"] - now)})
    return {"positions": out, "gold": me.get("gold", 0),
            "note": "Derivatives settle in in-game gold only."}

def settle_derivs(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    derivs = me.get("derivs", [])
    due = [p for p in derivs if now >= p["expires"]]
    total = 0
    pnl = 0
    for p in due:
        s = _stock_by_name(state, p["symbol"])
        spot = s["price"] if s else p["entry_spot"]
        val = int(max(0, _settle_value(p, spot)))
        total += val
        pnl += val - (0 if p["kind"] == "future" else int(p.get("cost", 0)))
    me["derivs"] = [p for p in derivs if now < p["expires"]]
    if total:
        me["gold"] = me.get("gold", 0) + total
        state.mark_dirty(uid)
    if due:
        record_trade_pnl(state, uid, pnl, now=now)
    return {"settled_count": len(due), "payout": total, "gold": me.get("gold", 0),
            "note": "Derivatives settle in in-game gold only."}


# ============================================================
# GUILD SKYSCRAPER (collective build; each floor gives phi bonus)
# ============================================================

FLOOR_BASE_COST = 100_000          # gold to fund floor 1
SKY_MAX_FLOORS = 34                # fibonacci-ish cap

def _sky(state, corp_id):
    if not hasattr(state, "skyscrapers"):
        state.skyscrapers = {}
    c = corp_id % len(CORPS)
    if c not in state.skyscrapers:
        state.skyscrapers[c] = {"corp": c, "floors": 0, "progress": 0, "contributions": {}}
    return state.skyscrapers[c]

def floor_cost(floor):
    """Cost of the NEXT floor scales by phi."""
    return int(FLOOR_BASE_COST * (PHI ** (floor / PHI)))

def sky_bonus_pct(floors):
    """Total corp-wide bonus % from built floors (phi-diminishing sum)."""
    total = 0.0
    for f in range(floors):
        total += (PHI - 1) * (1 / (PHI ** (f / (PHI * 2))))
    return round(total, 2)

def sky_reward_mult(state, corp_id):
    """Multiplier applied to a member's gold rewards from their corp tower."""
    sk = _sky(state, corp_id)
    return 1.0 + sky_bonus_pct(sk["floors"]) / 100.0

def sky_member_mult(state, uid):
    me = state.chars.get(uid)
    if not me:
        return 1.0
    return sky_reward_mult(state, me["corp_id"])

def sky_status(state, corp_id):
    sk = _sky(state, corp_id)
    nxt = floor_cost(sk["floors"])
    top = sorted(sk["contributions"].items(), key=lambda x: -x[1])[:5]
    return {"corp": CORPS[sk["corp"]], "floors": sk["floors"],
            "max_floors": SKY_MAX_FLOORS,
            "next_floor_cost": nxt, "progress": sk["progress"],
            "progress_pct": round(100 * sk["progress"] / nxt, 2) if nxt else 100,
            "bonus_pct": sky_bonus_pct(sk["floors"]),
            "top_builders": [{"uid": int(u), "gold": g} for u, g in top],
            "note": "Skyscraper bonus applies to the whole corp; funded in gold."}

def sky_fund(state, uid, amount):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    amount = int(amount)
    if amount <= 0:
        return {"error": "bad amount"}
    if me.get("gold", 0) < amount:
        return {"error": "not enough gold"}
    sk = _sky(state, me["corp_id"])
    if sk["floors"] >= SKY_MAX_FLOORS:
        return {"error": "skyscraper complete", **sky_status(state, me["corp_id"])}
    me["gold"] -= amount
    sk["progress"] += amount
    sk["contributions"][str(uid)] = sk["contributions"].get(str(uid), 0) + amount
    built = 0
    while sk["floors"] < SKY_MAX_FLOORS and sk["progress"] >= floor_cost(sk["floors"]):
        sk["progress"] -= floor_cost(sk["floors"])
        sk["floors"] += 1
        built += 1
    state.mark_dirty(uid)
    res = sky_status(state, me["corp_id"])
    res["ok"] = True
    res["funded"] = amount
    res["floors_built"] = built
    res["gold"] = me["gold"]
    return res


# ============================================================
# GOLDEN HOUR (timed x-phi rewards window with countdown)
# ============================================================

GH_CYCLE = int(3600 * PHI)         # a golden hour every ~97 min
GH_DURATION = int(600 * PHI)       # lasts ~16 min
GH_MULT = PHI                      # rewards x phi during the window

def golden_hour(now=None):
    now = now or int(time.time())
    phase = now % GH_CYCLE
    active = phase < GH_DURATION
    if active:
        return {"active": True, "multiplier": round(GH_MULT, 6),
                "seconds_left": GH_DURATION - phase,
                "next_in": 0,
                "note": "All gold rewards are multiplied by phi during Golden Hour."}
    return {"active": False, "multiplier": 1.0,
            "seconds_left": 0,
            "next_in": GH_CYCLE - phase,
            "note": "Golden Hour arrives on a phi cycle."}

def golden_multiplier(now=None):
    return GH_MULT if golden_hour(now)["active"] else 1.0


# ============================================================
# M&A (buy a stake in a corp; earn phi-share of members' income)
# ============================================================

# Total shares per corp; buying shares diverts a phi-fraction of that
# corp's members' earned gold to shareholders, pro-rata by shares held.
CORP_TOTAL_SHARES = 1000
MA_DIVIDEND_RATE = (PHI - 1) / (PHI ** 2)     # ~0.236 of earnings go to shareholders

def _ma(state):
    if not hasattr(state, "corp_shares"):
        # corp_shares[corp_id] = {"held": {uid: qty}, "price": base}
        state.corp_shares = {}
    return state.corp_shares

def _corp_book(state, corp_id):
    ma = _ma(state)
    c = corp_id % len(CORPS)
    if c not in ma:
        ma[c] = {"held": {}, "base_price": 1000}
    return ma[c]

def share_price(state, corp_id):
    """Price per share rises by phi as more shares are held (scarcity)."""
    book = _corp_book(state, corp_id)
    sold = sum(book["held"].values())
    frac = sold / CORP_TOTAL_SHARES
    return int(book["base_price"] * (PHI ** (frac * 3)))

def ma_status(state, corp_id=None, uid=None):
    out = []
    for cid in range(len(CORPS)):
        book = _corp_book(state, cid)
        sold = sum(book["held"].values())
        holders = sorted(book["held"].items(), key=lambda x: -x[1])[:5]
        entry = {"corp": CORPS[cid], "corp_id": cid,
                 "shares_sold": sold, "total_shares": CORP_TOTAL_SHARES,
                 "share_price": share_price(state, cid),
                 "dividend_rate_pct": round(MA_DIVIDEND_RATE * 100, 2),
                 "top_holders": [{"uid": int(u), "shares": q} for u, q in holders]}
        if uid is not None:
            entry["your_shares"] = book["held"].get(str(uid), 0)
        out.append(entry)
    return {"corps": out,
            "note": "Corp stakes pay phi-share dividends in in-game gold only."}

def buy_shares(state, uid, corp_id, qty):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    qty = max(1, int(qty))
    book = _corp_book(state, corp_id)
    sold = sum(book["held"].values())
    if sold + qty > CORP_TOTAL_SHARES:
        return {"error": f"only {CORP_TOTAL_SHARES - sold} shares left"}
    total_cost = 0
    for _ in range(qty):
        total_cost += share_price(state, corp_id)
        book["held"][str(uid)] = book["held"].get(str(uid), 0) + 1
    if me.get("gold", 0) < total_cost:
        # roll back
        book["held"][str(uid)] -= qty
        if book["held"][str(uid)] <= 0:
            book["held"].pop(str(uid), None)
        return {"error": "not enough gold", "cost": total_cost}
    me["gold"] -= total_cost
    state.mark_dirty(uid)
    res = {"ok": True, "bought": qty, "cost": total_cost, "gold": me["gold"],
           "your_shares": book["held"][str(uid)],
           "corp": CORPS[corp_id % len(CORPS)]}
    return res

def _pay_dividends(state, earner_uid, gross):
    """When a member of corp C earns gold, divert a phi-fraction to C's shareholders."""
    earner = state.chars.get(earner_uid)
    if not earner:
        return 0
    corp = earner["corp_id"] % len(CORPS)
    book = _corp_book(state, corp)
    sold = sum(book["held"].values())
    if sold <= 0:
        return 0
    pool = int(gross * MA_DIVIDEND_RATE)
    if pool <= 0:
        return 0
    paid = 0
    for u, q in book["held"].items():
        share = int(pool * q / CORP_TOTAL_SHARES)
        if share <= 0:
            continue
        ch = state.chars.get(int(u))
        if ch is not None:
            ch["gold"] = ch.get("gold", 0) + share
            state.mark_dirty(int(u))
            paid += share
    return paid


# ============================================================
# CENTRAL GOLD AWARD (Golden Hour x-phi + M&A dividends)
# ============================================================

def award_gold(state, uid, base_amount, now=None, dividends=True):
    """Single funnel for gold rewards: applies Golden Hour multiplier,
    credits the player, and pays M&A dividends to corp shareholders.
    Returns {gained, golden, dividends_paid, gold}."""
    me = state.chars.get(uid)
    if not me:
        return {"gained": 0, "golden": False, "dividends_paid": 0, "gold": 0}
    gh = golden_multiplier(now)
    sky = sky_reward_mult(state, me["corp_id"])
    mult = gh * sky
    gained = int(round(base_amount * mult))
    me["gold"] = me.get("gold", 0) + gained
    div = _pay_dividends(state, uid, gained) if dividends else 0
    ipo_div = _pay_ipo_dividends(state, uid, gained) if dividends else 0
    state.mark_dirty(uid)
    return {"gained": gained, "golden": gh > 1.0,
            "multiplier": round(gh, 6),
            "sky_mult": round(sky, 4),
            "sky_bonus_pct": round((sky - 1.0) * 100, 2),
            "dividends_paid": div, "ipo_dividends_paid": ipo_div,
            "gold": me["gold"]}


# ============================================================
# INSIDER NEWS (random phi events move stocks; early entry profits)
# ============================================================

NEWS_TEMPLATES = [
    ("{sym} lands golden merger — analysts stunned", "up", PHI),
    ("{sym} posts record phi-quarter earnings", "up", PHI / 1.3),
    ("{sym} unveils breakthrough — shares surge", "up", PHI / 1.1),
    ("Regulator probes {sym} accounting", "down", 1 / PHI),
    ("{sym} guidance slashed — sell-off begins", "down", 1 / (PHI * 1.1)),
    ("{sym} CEO resigns amid scandal", "down", 1 / (PHI * 1.3)),
]
NEWS_INTERVAL = int(300 * PHI)     # a new headline every ~8 min
NEWS_MAX = 12

def _news(state):
    if not hasattr(state, "news"):
        state.news = []
    if not hasattr(state, "_news_seq"):
        state._news_seq = 0
    if not hasattr(state, "_news_last"):
        state._news_last = 0
    return state.news

def tick_news(state, now=None):
    """Generate a headline on the phi interval and move the stock by phi."""
    now = now or int(time.time())
    news = _news(state)
    if now - state._news_last < NEWS_INTERVAL and news:
        return None
    stocks = getattr(state, "stocks", [])
    if not stocks:
        return None
    state._news_last = now
    stock = random.choice(stocks)
    tmpl, direction, factor = random.choice(NEWS_TEMPLATES)
    old = stock["price"]
    stock["price"] = round(max(0.01, old * factor), 2)
    stock["delta"] = round(stock["price"] - old, 2)
    state._news_seq += 1
    item = {"id": state._news_seq, "ts": now, "symbol": stock["name"],
            "headline": tmpl.format(sym=stock["name"]),
            "direction": direction,
            "change_pct": round(100 * (stock["price"] - old) / old, 2),
            "new_price": stock["price"]}
    news.append(item)
    del news[:-NEWS_MAX]
    return item

def news_feed(state, since=0, now=None):
    tick_news(state, now)
    news = _news(state)
    nxt = max(0, NEWS_INTERVAL - ((now or int(time.time())) - state._news_last))
    return {"news": [n for n in news if n["id"] > since][-NEWS_MAX:],
            "last_id": news[-1]["id"] if news else 0,
            "next_headline_in": nxt,
            "note": "Insider news moves stocks by phi. Trade early to profit."}


# ============================================================
# HEDGE FUND (auto-invest; phi-yield tied to the market index)
# ============================================================

HEDGE_LOCK = int(1800 * PHI)       # ~48.5 min per cycle
HEDGE_MGMT_FEE = (2 - PHI) / 10    # ~0.038 skim on gains (the "2 and 20" but phi)

def market_index(state):
    """Golden Index: phi-weighted average of stock prices (rebased ~1000)."""
    stocks = getattr(state, "stocks", [])
    if not stocks:
        return 1000.0
    # phi-weight the sorted prices so leaders dominate like a cap-weighted index
    sp = sorted((s["price"] for s in stocks), reverse=True)
    num = 0.0; den = 0.0
    for i, p in enumerate(sp):
        w = 1 / (PHI ** (i / PHI))
        num += p * w; den += w
    return round(num / den * PHI, 2)

def hedge_open(state, uid, amount, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    amount = int(amount)
    if amount <= 0:
        return {"error": "bad amount"}
    if me.get("gold", 0) < amount:
        return {"error": "not enough gold"}
    me["gold"] -= amount
    fund = {"id": now * 1000 + random.randint(0, 999),
            "principal": amount, "entry_index": market_index(state),
            "cb_leverage": round(PHI / central_rate(now), 4),
            "matures": now + HEDGE_LOCK}
    me.setdefault("hedge", []).append(fund)
    state.mark_dirty(uid)
    return {"ok": True, "fund": fund, "index": fund["entry_index"], "gold": me["gold"]}

def _hedge_value(state, f):
    """Return payout: principal scaled by index performance, phi-amplified,
    minus a phi mgmt fee on gains. Never below principal/phi (soft floor)."""
    cur = market_index(state)
    perf = cur / f["entry_index"] if f["entry_index"] else 1.0
    # phi-amplified: leverage set by the central rate at entry (dovish=more lev)
    amp = f.get("cb_leverage", PHI)
    lev = 1.0 + (perf - 1.0) * amp
    lev = max(1.0 / PHI, lev)
    gross = f["principal"] * lev
    gain = max(0.0, gross - f["principal"])
    return int(gross - gain * HEDGE_MGMT_FEE)

def hedge_status(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    cur = market_index(state)
    out = []
    for f in me.get("hedge", []):
        val = _hedge_value(state, f)
        out.append({**f, "current_value": val,
                    "pnl": val - f["principal"],
                    "index_now": cur,
                    "matured": now >= f["matures"],
                    "seconds_left": max(0, f["matures"] - now)})
    return {"funds": out, "index": cur, "gold": me.get("gold", 0),
            "lock_seconds": HEDGE_LOCK,
            "mgmt_fee_pct": round(HEDGE_MGMT_FEE * 100, 2),
            "note": "Hedge fund yields are in-game gold only, tied to the Golden Index."}

def hedge_redeem(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    funds = me.get("hedge", [])
    due = [f for f in funds if now >= f["matures"]]
    total = sum(_hedge_value(state, f) for f in due)
    me["hedge"] = [f for f in funds if now < f["matures"]]
    if total:
        me["gold"] = me.get("gold", 0) + int(total)
        state.mark_dirty(uid)
    return {"redeemed_count": len(due), "payout": int(total),
            "gold": me.get("gold", 0),
            "note": "Hedge fund yields are in-game gold only."}


# ============================================================
# MAGNATE LEADERBOARD (live richest players; phi crown tiers)
# ============================================================

def magnate_score(char):
    """Wealth score = net_worth + gold, phi-boosted by prestige."""
    base = char.get("net_worth", 0) + char.get("gold", 0)
    return int(base * (PHI ** char.get("prestige", 0)))

CROWN_TIERS = ["👑 φ-EMPEROR", "◆ TITAN", "★ MOGUL", "▲ BARON", "· TYCOON"]

def magnates(state, top=20, uid=None):
    ranked = sorted(state.chars.values(), key=magnate_score, reverse=True)
    out = []
    for i, c in enumerate(ranked[:top]):
        crown = CROWN_TIERS[i] if i < len(CROWN_TIERS) else ""
        out.append({
            "rank": i + 1,
            "uid": c.get("user_id"),
            "name": c.get("name", f"Player_{c.get('user_id')}"),
            "corp": CORPS[c.get("corp_id", 0) % len(CORPS)],
            "score": magnate_score(c),
            "net_worth": c.get("net_worth", 0),
            "gold": c.get("gold", 0),
            "prestige": c.get("prestige", 0),
            "crown": crown,
            # phi crown glow intensity (1.0 at top, decays by phi)
            "glow": round(1 / (PHI ** i), 4),
        })
    res = {"magnates": out, "total_players": len(state.chars),
           "note": "Rankings by in-game wealth only."}
    if uid is not None:
        me = state.chars.get(int(uid))
        if me:
            ms = magnate_score(me)
            rank = sum(1 for c in state.chars.values() if magnate_score(c) > ms) + 1
            res["you"] = {"uid": int(uid), "rank": rank, "score": ms,
                          "percentile": round(100 * (1 - rank / max(1, len(state.chars))), 1)}
    return res


# ============================================================
# MAGNATE OF THE YEAR (season award: exclusive phi crown artifact)
# ============================================================

MOY_CROWN = {"code": "PHI_CROWN", "rarity": 5, "cat": 11,
             "value": 1_000_000, "qty": 1, "name": "Crown of the Golden Magnate"}

def _moy(state):
    if not hasattr(state, "moy"):
        state.moy = {"last_awarded_season": -1, "hall": []}   # hall = past champions
    return state.moy

def magnate_of_year(state, now=None):
    """When a new season starts, crown last season's #1 magnate with the
    exclusive Crown of the Golden Magnate (a unique phi artifact)."""
    now = now or int(time.time())
    season, week = current_season(now)
    moy = _moy(state)
    prev_season = season - 1
    if prev_season < 0 or moy["last_awarded_season"] >= prev_season:
        return {"awarded": False, "current_season": season,
                "hall_of_fame": moy["hall"][-10:],
                "note": "Magnate of the Year is crowned when a season ends."}
    ranked = sorted(state.chars.values(), key=magnate_score, reverse=True)
    if not ranked:
        return {"awarded": False, "current_season": season}
    champ = ranked[0]
    crown = dict(MOY_CROWN)
    crown["season"] = prev_season
    champ.setdefault("loot", []).append(crown)
    champ["net_worth"] = champ.get("net_worth", 0) + crown["value"]
    champ["moy_titles"] = champ.get("moy_titles", 0) + 1
    state.mark_dirty(champ.get("user_id"))
    moy["last_awarded_season"] = prev_season
    entry = {"season": prev_season, "uid": champ.get("user_id"),
             "name": champ.get("name", f"Player_{champ.get('user_id')}"),
             "corp": CORPS[champ.get("corp_id", 0) % len(CORPS)],
             "score": magnate_score(champ)}
    moy["hall"].append(entry)
    return {"awarded": True, "champion": entry,
            "crown": crown, "current_season": season,
            "hall_of_fame": moy["hall"][-10:],
            "note": "The Golden Crown is a unique in-game artifact."}

def moy_status(state, now=None):
    """Poll: crowns pending champions and returns the hall of fame + the
    current front-runner for this season."""
    res = magnate_of_year(state, now)
    ranked = sorted(state.chars.values(), key=magnate_score, reverse=True)
    if ranked:
        lead = ranked[0]
        res["front_runner"] = {
            "uid": lead.get("user_id"),
            "name": lead.get("name", f"Player_{lead.get('user_id')}"),
            "corp": CORPS[lead.get("corp_id", 0) % len(CORPS)],
            "score": magnate_score(lead)}
    res["season_progress"] = season_progress(now)
    return res


# ============================================================
# BANK / LOANS (borrow gold at phi-interest; leverage w/ liquidation)
# ============================================================

# You post gold collateral and borrow up to (phi-1)*collateral*leverage.
# Interest accrues by phi over time. If debt > collateral * LIQ_RATIO -> liquidated.
LOAN_INTEREST = (PHI - 1) / 100        # ~0.618% per accrual tick
LOAN_TICK = 3600                        # interest compounds hourly
MAX_LEVERAGE = PHI                      # up to phi-x collateral
LIQ_RATIO = PHI                         # debt >= collateral*phi => margin call

def _loan(state, uid):
    me = state.chars.get(uid)
    if me is None:
        return None
    return me.get("loan")

def _accrue(loan, now):
    """Compound phi-interest for elapsed ticks, scaled by the central rate."""
    ticks = (now - loan["last_accrue"]) // LOAN_TICK
    if ticks > 0:
        rate_per_tick = 1 + LOAN_INTEREST * central_rate(now)
        loan["debt"] = int(loan["debt"] * (rate_per_tick ** ticks))
        loan["last_accrue"] += ticks * LOAN_TICK
    return loan

def loan_status(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    loan = me.get("loan")
    cbr = central_rate(now)
    info = {"has_loan": bool(loan), "gold": me.get("gold", 0),
            "max_leverage": round(MAX_LEVERAGE, 4),
            "interest_pct_per_hour": round(LOAN_INTEREST * cbr * 100, 3),
            "cb_rate": cbr,
            "liquidation_ratio": round(LIQ_RATIO, 4),
            "note": "Loans and interest are in-game gold only."}
    if loan:
        _accrue(loan, now)
        state.mark_dirty(uid)
        info.update({"collateral": loan["collateral"], "debt": loan["debt"],
                     "insured": bool(loan.get("insured")),
                     "health": round(loan["collateral"] * LIQ_RATIO / max(1, loan["debt"]), 3),
                     "liquidation_debt": int(loan["collateral"] * LIQ_RATIO),
                     "at_risk": loan["debt"] >= loan["collateral"] * LIQ_RATIO})
    return info

def take_loan(state, uid, collateral, leverage, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    if me.get("loan"):
        return {"error": "repay your existing loan first"}
    collateral = int(collateral)
    leverage = min(MAX_LEVERAGE, max(1.0, float(leverage)))
    if collateral <= 0:
        return {"error": "bad collateral"}
    if me.get("gold", 0) < collateral:
        return {"error": "not enough gold for collateral"}
    borrowed = int(collateral * (PHI - 1) * leverage)
    me["gold"] = me.get("gold", 0) - collateral + borrowed
    me["loan"] = {"collateral": collateral, "debt": borrowed,
                  "leverage": round(leverage, 4), "last_accrue": now,
                  "opened": now}
    state.mark_dirty(uid)
    return {"ok": True, "borrowed": borrowed, "collateral": collateral,
            "leverage": round(leverage, 4), "gold": me["gold"],
            **loan_status(state, uid, now)}

def repay_loan(state, uid, amount=None, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me or not me.get("loan"):
        return {"error": "no active loan"}
    loan = _accrue(me["loan"], now)
    amount = loan["debt"] if amount is None else min(int(amount), loan["debt"])
    if me.get("gold", 0) < amount:
        return {"error": "not enough gold to repay", "debt": loan["debt"]}
    me["gold"] -= amount
    loan["debt"] -= amount
    result = {"ok": True, "repaid": amount}
    if loan["debt"] <= 0:
        # return collateral
        me["gold"] += loan["collateral"]
        result["collateral_returned"] = loan["collateral"]
        me.pop("loan", None)
        result["cleared"] = True
    state.mark_dirty(uid)
    result.update(loan_status(state, uid, now) if me.get("loan") else {"gold": me["gold"], "has_loan": False})
    return result

# ---- POSITION INSURANCE (pay phi-premium; protect from liquidation/loss) ----
INSURANCE_PREMIUM_RATE = (PHI - 1) / PHI     # ~0.382 of collateral to insure

def buy_insurance(state, uid, now=None):
    """Insure your current loan against liquidation for one margin call.
    Premium = phi-fraction of collateral."""
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    loan = me.get("loan")
    if not loan:
        return {"error": "no active loan to insure"}
    if loan.get("insured"):
        return {"error": "loan already insured"}
    premium = int(loan["collateral"] * INSURANCE_PREMIUM_RATE)
    if me.get("gold", 0) < premium:
        return {"error": "not enough gold for premium", "premium": premium}
    me["gold"] -= premium
    loan["insured"] = True
    state.mark_dirty(uid)
    return {"ok": True, "premium": premium, "gold": me["gold"],
            "note": "Insurance covers one liquidation, then is consumed."}

def _liq_events(state):
    if not hasattr(state, "liq_events"):
        state.liq_events = []
    if not hasattr(state, "_liq_seq"):
        state._liq_seq = 0
    return state.liq_events

def check_liquidations(state, now=None):
    """Sweep all loans: if debt >= collateral*phi, seize collateral & wipe debt.
    Insured loans absorb one margin call (interest reset, insurance consumed).
    Records events to state.liq_events for overlay/chat notification."""
    now = now or int(time.time())
    events = _liq_events(state)
    liquidated = []
    saved = []
    for uid, me in state.chars.items():
        loan = me.get("loan")
        if not loan:
            continue
        _accrue(loan, now)
        if loan["debt"] >= loan["collateral"] * LIQ_RATIO:
            name = me.get("name", f"Player_{uid}")
            corp = me.get("corp_id", 0) % len(CORPS)
            if loan.get("insured"):
                # insurance absorbs: wipe excess debt back to collateral, consume cover
                loan["debt"] = int(loan["collateral"] * (LIQ_RATIO / PHI))
                loan["insured"] = False
                loan["last_accrue"] = now
                saved.append({"uid": uid, "name": name})
                state._liq_seq += 1
                events.append({"id": state._liq_seq, "ts": now, "uid": uid,
                               "name": name, "corp": corp, "type": "saved",
                               "text": f"{name} dodged liquidation — insurance paid out!"})
                state.mark_dirty(uid)
                continue
            liquidated.append({"uid": uid, "collateral_lost": loan["collateral"],
                               "debt": loan["debt"], "name": name, "corp": corp})
            state._liq_seq += 1
            events.append({"id": state._liq_seq, "ts": now, "uid": uid,
                           "name": name, "corp": corp, "type": "liquidated",
                           "collateral_lost": loan["collateral"],
                           "text": f"{name} was LIQUIDATED — {loan['collateral']:,}g collateral seized!"})
            me.pop("loan", None)
            state.mark_dirty(uid)
    del events[:-30]
    return {"liquidated": liquidated, "saved": saved, "count": len(liquidated)}

def check_short_squeezes(state, now=None):
    """Sweep all short positions: if spot >= entry*phi, force-cover and wipe
    the margin. Records a 'squeezed' event to the shared liq feed."""
    now = now or int(time.time())
    events = _liq_events(state)
    squeezed = []
    for uid, me in state.chars.items():
        shorts = me.get("shorts")
        if not shorts:
            continue
        keep = []
        for p in shorts:
            s = _stock_by_name(state, p["symbol"])
            spot = s["price"] if s else p["entry"]
            if spot >= p["entry"] * SHORT_SQUEEZE_MULT:
                name = me.get("name", f"Player_{uid}")
                corp = me.get("corp_id", 0) % len(CORPS)
                state._liq_seq += 1
                ev = {"id": state._liq_seq, "ts": now, "uid": uid,
                      "name": name, "corp": corp, "type": "squeezed",
                      "collateral_lost": p["margin"],
                      "text": f"{name}'s {p['symbol']} short got SQUEEZED — {p['margin']:,}g margin wiped!"}
                events.append(ev)
                squeezed.append(ev)
                record_trade_pnl(state, uid, -p["margin"], now=now)
                state.mark_dirty(uid)
            else:
                keep.append(p)
        me["shorts"] = keep
    del events[:-30]
    return {"squeezed": squeezed, "count": len(squeezed)}

def liq_feed(state, since=0):
    events = _liq_events(state)
    return {"events": [e for e in events if e["id"] > since][-30:],
            "last_id": events[-1]["id"] if events else 0}


# ============================================================
# CENTRAL BANK (global phi rate; affects loans/bonds/hedge)
# ============================================================

# The Golden Central Rate oscillates on a phi cycle between a dovish and a
# hawkish stance. High rate = costlier loans, richer bond yields, tamer hedge
# leverage. It is deterministic from the clock so all systems agree.
CB_CYCLE = int(3600 * PHI * PHI)   # full easing<->tightening cycle (~2.6 h)
CB_MID = 1.0
CB_AMPL = PHI - 1                  # swings +/- 0.618 around mid

def central_rate(now=None):
    """Return a global rate factor in ~[1/phi, phi]. 1.0 is neutral."""
    now = now or int(time.time())
    phase = (now % CB_CYCLE) / CB_CYCLE
    # smooth phi-amplitude cosine wave
    factor = CB_MID + CB_AMPL * math.cos(phase * 2 * math.pi)
    return round(max(1.0 / PHI, factor), 4)

def cb_status(now=None):
    now = now or int(time.time())
    rate = central_rate(now)
    if rate > 1.15:
        stance = "HAWKISH — tightening"
    elif rate < 0.9:
        stance = "DOVISH — easing"
    else:
        stance = "NEUTRAL"
    return {"rate": rate, "stance": stance,
            "loan_interest_pct_per_hour": round(LOAN_INTEREST * rate * 100, 3),
            "bond_yield_factor": round(rate, 4),
            "hedge_leverage_factor": round(1.0 / rate, 4),
            "cycle_seconds": CB_CYCLE,
            "phase_pct": round((now % CB_CYCLE) / CB_CYCLE * 100, 1),
            "note": "The Golden Central Rate scales all credit markets by phi."}


# ============================================================
# IPO (list your own micro-corp; players buy your shares)
# ============================================================

IPO_TOTAL_SHARES = 500
IPO_LISTING_FEE = 50_000          # gold to go public
IPO_DIVIDEND_RATE = (PHI - 1) / (PHI ** 2)   # founder shares earnings w/ holders

def _ipos(state):
    if not hasattr(state, "ipos"):
        # ipos[founder_uid] = {"name","price","held":{uid:qty},"raised"}
        state.ipos = {}
    return state.ipos

def _pay_ipo_dividends(state, founder_uid, gross):
    """When an IPO founder earns gold, divert a phi-fraction to their shareholders."""
    ipo = _ipos(state).get(str(founder_uid))
    if not ipo:
        return 0
    sold = sum(ipo["held"].values())
    if sold <= 0:
        return 0
    pool = int(gross * IPO_DIVIDEND_RATE)
    if pool <= 0:
        return 0
    paid = 0
    for u, q in ipo["held"].items():
        share = int(pool * q / IPO_TOTAL_SHARES)
        if share <= 0:
            continue
        ch = state.chars.get(int(u))
        if ch is not None:
            ch["gold"] = ch.get("gold", 0) + share
            state.mark_dirty(int(u))
            paid += share
    ipo["dividends_paid"] = ipo.get("dividends_paid", 0) + paid
    return paid

def ipo_price(state, founder_uid):
    ipo = _ipos(state).get(str(founder_uid))
    if not ipo:
        return 0
    sold = sum(ipo["held"].values())
    return int(ipo["base_price"] * (PHI ** (sold / IPO_TOTAL_SHARES * 3)))

def ipo_launch(state, uid, name, base_price, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    ipos = _ipos(state)
    if str(uid) in ipos:
        return {"error": "you already went public"}
    if me.get("gold", 0) < IPO_LISTING_FEE:
        return {"error": f"listing fee is {IPO_LISTING_FEE} gold"}
    me["gold"] -= IPO_LISTING_FEE
    name = (str(name).strip()[:16] or f"{me.get('name','P')}-CO").upper()
    ipos[str(uid)] = {"founder": uid, "name": name,
                      "base_price": max(10, int(base_price or 100)),
                      "held": {}, "raised": 0, "opened": now}
    state.mark_dirty(uid)
    return {"ok": True, "ticker": name, "listing_fee": IPO_LISTING_FEE,
            "total_shares": IPO_TOTAL_SHARES, "gold": me["gold"]}

def ipo_list(state, uid=None):
    ipos = _ipos(state)
    out = []
    for fu, ipo in ipos.items():
        sold = sum(ipo["held"].values())
        founder = state.chars.get(int(fu), {})
        e = {"founder": int(fu),
             "founder_name": founder.get("name", f"Player_{fu}"),
             "ticker": ipo["name"], "price": ipo_price(state, int(fu)),
             "shares_sold": sold, "total_shares": IPO_TOTAL_SHARES,
             "raised": ipo["raised"]}
        if uid is not None:
            e["your_shares"] = ipo["held"].get(str(uid), 0)
        out.append(e)
    out.sort(key=lambda x: -x["raised"])
    return {"ipos": out, "listing_fee": IPO_LISTING_FEE,
            "note": "IPO shares pay founder-linked dividends in in-game gold only."}

def ipo_buy(state, uid, founder_uid, qty, now=None):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    ipo = _ipos(state).get(str(founder_uid))
    if not ipo:
        return {"error": "no such IPO"}
    if int(founder_uid) == uid:
        return {"error": "cannot buy your own shares"}
    qty = max(1, int(qty))
    sold = sum(ipo["held"].values())
    if sold + qty > IPO_TOTAL_SHARES:
        return {"error": f"only {IPO_TOTAL_SHARES - sold} shares left"}
    total = 0
    for _ in range(qty):
        total += ipo_price(state, int(founder_uid))
        ipo["held"][str(uid)] = ipo["held"].get(str(uid), 0) + 1
    if me.get("gold", 0) < total:
        ipo["held"][str(uid)] -= qty
        if ipo["held"][str(uid)] <= 0:
            ipo["held"].pop(str(uid), None)
        return {"error": "not enough gold", "cost": total}
    me["gold"] -= total
    ipo["raised"] += total
    # founder receives the proceeds
    founder = state.chars.get(int(founder_uid))
    if founder is not None:
        founder["gold"] = founder.get("gold", 0) + total
        state.mark_dirty(int(founder_uid))
    state.mark_dirty(uid)
    return {"ok": True, "bought": qty, "cost": total, "ticker": ipo["name"],
            "your_shares": ipo["held"][str(uid)], "gold": me["gold"]}


# ============================================================
# SHORT SELLING (profit on price drops; phi margin; squeeze risk)
# ============================================================

SHORT_MARGIN_RATE = 1.0 / PHI          # margin = size_value / phi
SHORT_SQUEEZE_MULT = PHI               # if price rises to entry*phi -> forced liquidation
SHORT_FEE_RATE = (PHI - 1) / 100       # opening fee on notional

def _shorts(char):
    if "shorts" not in char:
        char["shorts"] = []
    return char["shorts"]

def _short_pnl(pos, spot):
    return int((pos["entry"] - spot) * pos["size"])

def short_status(state, uid):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    out = []
    for p in _shorts(me):
        s = _stock_by_name(state, p["symbol"])
        spot = s["price"] if s else p["entry"]
        squeeze_at = round(p["entry"] * SHORT_SQUEEZE_MULT, 2)
        out.append({"id": p["id"], "symbol": p["symbol"], "size": p["size"],
                    "entry": round(p["entry"], 2), "spot": round(spot, 2),
                    "margin": p["margin"], "pnl": _short_pnl(p, spot),
                    "squeeze_at": squeeze_at,
                    "danger": spot >= p["entry"] * (1 + (SHORT_SQUEEZE_MULT - 1) / PHI)})
    return {"positions": out, "margin_rate": round(SHORT_MARGIN_RATE, 4),
            "squeeze_mult": round(SHORT_SQUEEZE_MULT, 4),
            "note": "Shorts profit when price falls. If price hits entry*phi you get squeezed and lose margin. In-game gold only."}

def short_open(state, uid, symbol, size, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    s = _stock_by_name(state, symbol)
    if not s:
        return {"error": "no such symbol"}
    size = max(1, int(size))
    notional = s["price"] * size
    margin = int(notional * SHORT_MARGIN_RATE)
    fee = int(notional * SHORT_FEE_RATE)
    cost = margin + fee
    if me.get("gold", 0) < cost:
        return {"error": "not enough gold for margin+fee", "need": cost}
    me["gold"] -= cost
    seq = getattr(state, "_short_seq", 0) + 1
    state._short_seq = seq
    pos = {"id": seq, "symbol": symbol, "size": size,
           "entry": s["price"], "margin": margin, "opened": now}
    _shorts(me).append(pos)
    state.mark_dirty(uid)
    return {"ok": True, "id": seq, "symbol": symbol, "size": size,
            "entry": round(s["price"], 2), "margin": margin, "fee": fee,
            "squeeze_at": round(s["price"] * SHORT_SQUEEZE_MULT, 2),
            "gold": me["gold"]}

def short_close(state, uid, pos_id, now=None):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    shorts = _shorts(me)
    pos = next((p for p in shorts if p["id"] == int(pos_id)), None)
    if not pos:
        return {"error": "no such short"}
    s = _stock_by_name(state, pos["symbol"])
    spot = s["price"] if s else pos["entry"]
    pnl = _short_pnl(pos, spot)
    squeezed = spot >= pos["entry"] * SHORT_SQUEEZE_MULT
    shorts.remove(pos)
    if squeezed:
        # margin wiped on a squeeze; no return
        record_trade_pnl(state, uid, -pos["margin"], now=now)
        state.mark_dirty(uid)
        return {"ok": True, "squeezed": True, "symbol": pos["symbol"],
                "entry": round(pos["entry"], 2), "spot": round(spot, 2),
                "margin_lost": pos["margin"], "returned": 0, "gold": me["gold"]}
    payout = max(0, pos["margin"] + pnl)
    res = award_gold(state, uid, payout, now=now) if payout > 0 else {"gained": 0}
    record_trade_pnl(state, uid, pnl, now=now)
    state.mark_dirty(uid)
    return {"ok": True, "squeezed": False, "symbol": pos["symbol"],
            "entry": round(pos["entry"], 2), "spot": round(spot, 2),
            "pnl": pnl, "margin": pos["margin"], "returned": payout,
            "golden": res.get("golden", False), "gold": me["gold"]}


# ============================================================
# GOLDEN-500 INDEX (phi-weighted composite + candle history)
# ============================================================

def _index_hist(state):
    if not hasattr(state, "index_hist"):
        state.index_hist = []      # list of candles {t,o,h,l,c}
        state._index_last = None
    return state.index_hist

def golden_index_value(state):
    """phi-weighted composite of all stocks + IPO + M&A share prices."""
    stocks = getattr(state, "stocks", [])
    total = 0.0
    wsum = 0.0
    for i, s in enumerate(stocks):
        w = PHI ** (-(i % 8))       # phi-decaying weights
        total += s["price"] * w
        wsum += w
    base = (total / wsum) if wsum else 0.0
    # blend in IPO + M&A average valuations (phi-minor weight)
    ipo_avg = 0.0
    ipos = _ipos(state)
    if ipos:
        ipo_avg = sum(ipo_price(state, int(fu)) for fu in ipos) / len(ipos)
    ma_avg = 0.0
    n_corp = len(CORPS)
    if n_corp:
        ma_avg = sum(share_price(state, c) for c in range(n_corp)) / n_corp
    val = base * PHI + (ipo_avg + ma_avg) / PHI / 100.0
    return round(val, 2)

def tick_index(state, now=None):
    """Record the Golden-500 into a rolling candle series (call each market tick)."""
    now = now or int(time.time())
    hist = _index_hist(state)
    v = golden_index_value(state)
    CANDLE_SECS = int(60 * PHI)        # ~97s candles
    last = getattr(state, "_index_last", None)
    if last is None or now - last["t0"] >= CANDLE_SECS:
        candle = {"t": now, "o": v, "h": v, "l": v, "c": v, "t0": now}
        hist.append(candle)
        state._index_last = candle
        if len(hist) > 90:
            del hist[:len(hist) - 90]
    else:
        c = state._index_last
        c["h"] = max(c["h"], v)
        c["l"] = min(c["l"], v)
        c["c"] = v

IDX_OPT_EXPIRY = int(60 * PHI * PHI)     # ~157s to expiry
IDX_OPT_SIZE = PHI                        # payout leverage per point

def _idx_opts(char):
    if "idx_opts" not in char:
        char["idx_opts"] = []
    return char["idx_opts"]

def idx_option_chain(state):
    """Offer phi-spaced call/put strikes around the current index."""
    spot = golden_index_value(state)
    strikes = []
    for k in (-2, -1, 0, 1, 2):
        strike = round(spot * (PHI ** (k / 3.0)), 2)
        # premium scales with distance-from-money on a phi curve
        call_prem = int(max(1, (spot - strike) + spot / PHI) * IDX_OPT_SIZE)
        put_prem = int(max(1, (strike - spot) + spot / PHI) * IDX_OPT_SIZE)
        strikes.append({"strike": strike, "call_premium": call_prem,
                        "put_premium": put_prem})
    return {"spot": spot, "strikes": strikes,
            "expiry_secs": IDX_OPT_EXPIRY, "size": round(IDX_OPT_SIZE, 4),
            "note": "Golden-500 index options settle in in-game gold at expiry."}

def idx_option_open(state, uid, kind, strike, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    kind = (kind or "").lower()
    if kind not in ("call", "put"):
        return {"error": "kind must be call or put"}
    spot = golden_index_value(state)
    strike = round(float(strike), 2)
    if kind == "call":
        premium = int(max(1, (spot - strike) + spot / PHI) * IDX_OPT_SIZE)
    else:
        premium = int(max(1, (strike - spot) + spot / PHI) * IDX_OPT_SIZE)
    if me.get("gold", 0) < premium:
        return {"error": "not enough gold", "premium": premium}
    me["gold"] -= premium
    seq = getattr(state, "_idxopt_seq", 0) + 1
    state._idxopt_seq = seq
    pos = {"id": seq, "kind": kind, "strike": strike, "premium": premium,
           "opened": now, "expires": now + IDX_OPT_EXPIRY, "entry_spot": spot}
    _idx_opts(me).append(pos)
    state.mark_dirty(uid)
    return {"ok": True, "id": seq, "kind": kind, "strike": strike,
            "premium": premium, "expires_in": IDX_OPT_EXPIRY, "gold": me["gold"]}

def _idx_intrinsic(pos, spot):
    if pos["kind"] == "call":
        return max(0.0, spot - pos["strike"])
    return max(0.0, pos["strike"] - spot)

def idx_option_status(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    spot = golden_index_value(state)
    out = []
    for p in _idx_opts(me):
        intrinsic = _idx_intrinsic(p, spot)
        out.append({"id": p["id"], "kind": p["kind"], "strike": p["strike"],
                    "premium": p["premium"], "spot": round(spot, 2),
                    "intrinsic": round(intrinsic, 2),
                    "est_payout": int(intrinsic * IDX_OPT_SIZE),
                    "expires_in": max(0, p["expires"] - now),
                    "in_money": intrinsic > 0})
    return {"positions": out, "spot": round(spot, 2)}

def idx_option_settle(state, uid, pos_id, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    opts = _idx_opts(me)
    pos = next((p for p in opts if p["id"] == int(pos_id)), None)
    if not pos:
        return {"error": "no such option"}
    if now < pos["expires"]:
        return {"error": "not expired yet",
                "expires_in": pos["expires"] - now}
    spot = golden_index_value(state)
    payout = int(_idx_intrinsic(pos, spot) * IDX_OPT_SIZE)
    opts.remove(pos)
    res = award_gold(state, uid, payout, now=now) if payout > 0 else {"gained": 0, "golden": False}
    record_trade_pnl(state, uid, payout - pos["premium"], now=now)
    state.mark_dirty(uid)
    return {"ok": True, "kind": pos["kind"], "strike": pos["strike"],
            "spot": round(spot, 2), "payout": payout,
            "golden": res.get("golden", False), "gold": me["gold"]}

N_BOTS = 8                               # phi-agents that trade the tape
BOT_AGGRO = PHI - 1                       # ~0.618 base price nudge magnitude

def _bots(state):
    """Persistent phi-agents, each with a target stock, bias and horizon."""
    if not hasattr(state, "bots"):
        stocks = getattr(state, "stocks", [])
        n = len(stocks)
        state.bots = []
        for i in range(N_BOTS):
            # alternate momentum-chasers and mean-reverters, phi-scaled size
            state.bots.append({
                "id": i, "sym_idx": (i * 3) % max(1, n),
                "style": "momentum" if i % 2 == 0 else "revert",
                "size": PHI ** (i % 4), "anchor": None})
    return state.bots

def tick_bots(state, now=None):
    """Bots push prices around: momentum bots chase the last delta, mean-
    reverters fade extremes toward a phi-anchor. This animates the tape so
    player market-making, shorts and derivatives get organic fills."""
    stocks = getattr(state, "stocks", [])
    if not stocks:
        return
    bots = _bots(state)
    n = len(stocks)
    for b in bots:
        s = stocks[b["sym_idx"] % n]
        if b["anchor"] is None:
            b["anchor"] = s["price"]
        b["anchor"] = round(b["anchor"] * (1 / PHI) + s["price"] * (1 - 1 / PHI), 4)
        if b["style"] == "momentum":
            push = s.get("delta", 0) * BOT_AGGRO * 0.15 * b["size"]
        else:
            push = (b["anchor"] - s["price"]) * (BOT_AGGRO / PHI) * 0.1 * b["size"]
        s["price"] = round(max(0.01, s["price"] + push), 2)
        s["volume"] = max(100, int(s.get("volume", 1000) + abs(push) * 500 * b["size"]))
        # occasionally a bot rotates to a new target
        if random.random() < (1 / (PHI ** 5)):
            b["sym_idx"] = random.randrange(n)
            b["anchor"] = None

FLASH_CRASH_CHANCE = 1.0 / (PHI ** 12)   # ~0.0031 per market tick (rare)
FLASH_CRASH_DROP = 1.0 / PHI             # prices multiplied by 1/phi (~0.618)

def maybe_flash_crash(state, now=None):
    """Rare phi-event: the whole market plunges by 1/phi. Shorts win big,
    leveraged longs get margin-called. Records a global feed event."""
    now = now or int(time.time())
    if random.random() >= FLASH_CRASH_CHANCE:
        return {"crashed": False}
    stocks = getattr(state, "stocks", [])
    if not stocks:
        return {"crashed": False}
    for s in stocks:
        s["price"] = round(max(0.01, s["price"] * FLASH_CRASH_DROP), 2)
        s["delta"] = round(-s["price"] * (PHI - 1), 2)
    idx = golden_index_value(state)
    events = _liq_events(state)
    state._liq_seq += 1
    events.append({"id": state._liq_seq, "ts": now, "uid": 0,
                   "name": "MARKET", "corp": 0, "type": "flashcrash",
                   "collateral_lost": 0, "index": idx,
                   "text": f"FLASH CRASH! The Golden-500 plunged to {idx:,.0f} — shorts feast, the leveraged bleed!"})
    del events[:-30]
    return {"crashed": True, "index": idx}

def _stock_hist(state):
    if not hasattr(state, "stock_hist"):
        state.stock_hist = {}       # name -> list of candles
        state._stock_candle_last = {}
    return state.stock_hist

STOCK_CANDLE_SECS = int(60 * PHI)

def tick_stock_candles(state, now=None):
    """Roll a candle series for every stock (call each market tick)."""
    now = now or int(time.time())
    hist = _stock_hist(state)
    last = state._stock_candle_last
    for s in getattr(state, "stocks", []):
        name = s["name"]
        v = s["price"]
        series = hist.setdefault(name, [])
        cur = last.get(name)
        if cur is None or now - cur["t0"] >= STOCK_CANDLE_SECS:
            candle = {"t": now, "o": v, "h": v, "l": v, "c": v, "t0": now}
            series.append(candle)
            last[name] = candle
            if len(series) > 90:
                del series[:len(series) - 90]
        else:
            cur["h"] = max(cur["h"], v)
            cur["l"] = min(cur["l"], v)
            cur["c"] = v

def stock_candles(state, name):
    hist = _stock_hist(state)
    s = _stock_by_name(state, name)
    cur = s["price"] if s else 0
    series = hist.get(name, [])
    candles = [{"t": c["t"], "o": round(c["o"], 2), "h": round(c["h"], 2),
                "l": round(c["l"], 2), "c": round(c["c"], 2)} for c in series]
    prev = candles[0]["c"] if candles else cur
    chg = round(cur - prev, 2)
    return {"symbol": name, "price": round(cur, 2), "change": chg,
            "change_pct": round((chg / prev * 100) if prev else 0, 2),
            "delta": round(s.get("delta", 0), 2) if s else 0,
            "volume": s.get("volume", 0) if s else 0,
            "candles": candles, "count": len(candles)}

def golden_index(state):
    hist = _index_hist(state)
    cur = golden_index_value(state)
    candles = [{"t": c["t"], "o": round(c["o"], 2), "h": round(c["h"], 2),
                "l": round(c["l"], 2), "c": round(c["c"], 2)} for c in hist]
    prev = candles[0]["c"] if candles else cur
    chg = round(cur - prev, 2)
    chg_pct = round((chg / prev * 100) if prev else 0, 2)
    return {"value": cur, "change": chg, "change_pct": chg_pct,
            "candles": candles, "count": len(candles),
            "note": "GOLDEN-500: phi-weighted composite of all markets."}


# ============================================================
# MARKET MAKING (post limit orders; earn the phi-spread on fills)
# ============================================================

MM_SPREAD = PHI                          # ask = bid * phi (the phi-spread)
MM_MAX_ORDERS = 8

def _mm_orders(char):
    if "mm_orders" not in char:
        char["mm_orders"] = []
    return char["mm_orders"]

MM_MAX_LEVERAGE = PHI                     # up to phi-x leverage on market making
MM_LIQ_RATIO = 1.0 / PHI                  # inventory < debt/phi => margin call

def mm_place(state, uid, symbol, bid, size, leverage=1.0, now=None):
    """Post a market-making order: park gold at a bid; auto-buy when the
    market dips to it, auto-sell at bid*phi for the spread. Leverage borrows
    the extra notional (cascade liquidation risk on a crash)."""
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    s = _stock_by_name(state, symbol)
    if not s:
        return {"error": "no such symbol"}
    if len(_mm_orders(me)) >= MM_MAX_ORDERS:
        return {"error": f"max {MM_MAX_ORDERS} open orders"}
    bid = round(float(bid), 2)
    size = max(1, int(size))
    lev = max(1.0, min(float(leverage or 1.0), MM_MAX_LEVERAGE))
    if bid <= 0:
        return {"error": "bid must be positive"}
    notional = int(bid * size)
    equity = int(notional / lev)          # own gold posted
    debt = notional - equity              # borrowed
    if me.get("gold", 0) < equity:
        return {"error": "not enough gold for margin", "need": equity}
    me["gold"] -= equity
    seq = getattr(state, "_mm_seq", 0) + 1
    state._mm_seq = seq
    ask = round(bid * MM_SPREAD, 2)
    order = {"id": seq, "symbol": symbol, "bid": bid, "ask": ask,
             "size": size, "reserved": notional, "equity": equity, "debt": debt,
             "leverage": round(lev, 4), "state": "resting", "opened": now}
    _mm_orders(me).append(order)
    state.mark_dirty(uid)
    return {"ok": True, "id": seq, "symbol": symbol, "bid": bid, "ask": ask,
            "size": size, "reserved": notional, "equity": equity, "debt": debt,
            "leverage": round(lev, 4), "gold": me["gold"]}

def mm_status(state, uid):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    out = []
    for o in _mm_orders(me):
        s = _stock_by_name(state, o["symbol"])
        spot = s["price"] if s else o["bid"]
        debt = o.get("debt", 0)
        danger = (o["state"] == "filled" and debt > 0 and
                  spot * o["size"] <= debt * (1 + MM_LIQ_RATIO) * PHI)
        out.append({**o, "spot": round(spot, 2), "danger": danger})
    return {"orders": out, "spread": round(MM_SPREAD, 4),
            "max_leverage": round(MM_MAX_LEVERAGE, 4),
            "note": "Buy at your bid, auto-sell at bid*phi. Leverage borrows notional (crash = margin call). In-game gold only."}

def mm_cancel(state, uid, order_id):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    orders = _mm_orders(me)
    o = next((x for x in orders if x["id"] == int(order_id)), None)
    if not o:
        return {"error": "no such order"}
    refund = 0
    debt = o.get("debt", 0)
    if o["state"] == "resting":
        refund = o.get("equity", o["reserved"])   # return posted margin (debt never drawn)
        me["gold"] = me.get("gold", 0) + refund
    elif o["state"] == "filled":
        # sell inventory at spot, repay borrowed debt first
        s = _stock_by_name(state, o["symbol"])
        spot = s["price"] if s else o["bid"]
        proceeds = int(spot * o["size"])
        refund = max(0, proceeds - debt)
        me["gold"] = me.get("gold", 0) + refund
    orders.remove(o)
    state.mark_dirty(uid)
    return {"ok": True, "refund": refund, "gold": me.get("gold", 0)}

def tick_market_making(state, now=None):
    """Advance all resting/filled MM orders against current prices."""
    now = now or int(time.time())
    for uid, me in state.chars.items():
        orders = me.get("mm_orders")
        if not orders:
            continue
        keep = []
        events = _liq_events(state)
        for o in orders:
            s = _stock_by_name(state, o["symbol"])
            spot = s["price"] if s else o["bid"]
            debt = o.get("debt", 0)
            if o["state"] == "resting":
                if spot <= o["bid"]:
                    o["state"] = "filled"      # bought inventory at bid
                keep.append(o)
            elif o["state"] == "filled":
                inv_val = spot * o["size"]
                # leveraged margin call: inventory can't cover the borrowed debt
                if debt > 0 and inv_val <= debt * (1 + MM_LIQ_RATIO):
                    # margin call: inventory seized to repay debt, equity wiped
                    name = me.get("name", f"Player_{uid}")
                    corp = me.get("corp_id", 0) % len(CORPS)
                    state._liq_seq += 1
                    events.append({"id": state._liq_seq, "ts": now, "uid": uid,
                                   "name": name, "corp": corp, "type": "mm_liquidated",
                                   "collateral_lost": o.get("equity", 0),
                                   "text": f"{name}'s leveraged {o['symbol']} MM book got MARGIN-CALLED — {o.get('equity',0):,}g equity wiped!"})
                    record_trade_pnl(state, uid, -o.get("equity", 0), now=now)
                    state.mark_dirty(uid)
                    continue  # order removed
                if spot >= o["ask"]:
                    proceeds = int(o["ask"] * o["size"])
                    net = max(0, proceeds - debt)      # repay borrowed first
                    profit = proceeds - o["reserved"]
                    award_gold(state, uid, net, now=now)
                    if profit != 0:
                        record_trade_pnl(state, uid, profit, now=now)
                    state.mark_dirty(uid)
                    # order completes (removed)
                else:
                    keep.append(o)
        del events[:-30]
        me["mm_orders"] = keep


# ============================================================
# TRADER OF THE DAY (leaderboard by realized PnL)
# ============================================================

def _day_bucket(now=None):
    now = now or int(time.time())
    return now // 86400

def record_trade_pnl(state, uid, pnl, now=None):
    """Accumulate a player's realized trading PnL into today's bucket."""
    me = state.chars.get(uid)
    if not me:
        return
    day = _day_bucket(now)
    rec = me.get("trade_day")
    if not rec or rec.get("day") != day:
        rec = {"day": day, "pnl": 0, "trades": 0}
    rec["pnl"] = int(rec.get("pnl", 0)) + int(pnl)
    rec["trades"] = int(rec.get("trades", 0)) + 1
    me["trade_day"] = rec
    state.mark_dirty(uid)

TRADER_CROWN = {"code": "TRADER_CROWN", "rarity": 5, "cat": 12,
                "value": 618_034, "qty": 1, "name": "Golden Ticker Crown"}

def _tod(state):
    if not hasattr(state, "tod"):
        state.tod = {"last_awarded_day": -1, "hall": []}
    return state.tod

def award_trader_of_day(state, now=None):
    """At day rollover, crown yesterday's top realized-PnL trader with the
    exclusive Golden Ticker Crown artifact."""
    now = now or int(time.time())
    today = _day_bucket(now)
    tod = _tod(state)
    prev = today - 1
    if tod["last_awarded_day"] >= prev:
        return {"awarded": False, "hall_of_fame": tod["hall"][-10:]}
    best = None
    for uid, me in state.chars.items():
        rec = me.get("trade_day")
        if not rec or rec.get("day") != prev or rec.get("trades", 0) <= 0:
            continue
        if best is None or rec["pnl"] > best[1]["pnl"]:
            best = (uid, rec, me)
    tod["last_awarded_day"] = prev
    if not best or best[1]["pnl"] <= 0:
        return {"awarded": False, "hall_of_fame": tod["hall"][-10:]}
    uid, rec, champ = best
    crown = dict(TRADER_CROWN)
    crown["day"] = prev
    champ.setdefault("loot", []).append(crown)
    champ["net_worth"] = champ.get("net_worth", 0) + crown["value"]
    champ["trader_titles"] = champ.get("trader_titles", 0) + 1
    state.mark_dirty(uid)
    entry = {"day": prev, "uid": uid,
             "name": champ.get("name", f"Player_{uid}"),
             "corp": CORPS[champ.get("corp_id", 0) % len(CORPS)],
             "pnl": int(rec["pnl"]), "trades": int(rec["trades"])}
    tod["hall"].append(entry)
    return {"awarded": True, "champion": entry, "crown": crown,
            "hall_of_fame": tod["hall"][-10:]}

def trader_leaderboard(state, uid=None, now=None):
    award_trader_of_day(state, now)
    tod = _tod(state)
    day = _day_bucket(now)
    rows = []
    for u, me in state.chars.items():
        rec = me.get("trade_day")
        if not rec or rec.get("day") != day:
            continue
        if rec.get("trades", 0) <= 0:
            continue
        rows.append({"uid": u, "name": me.get("name", f"Player_{u}"),
                     "corp": me.get("corp_id", 0) % len(CORPS),
                     "pnl": int(rec["pnl"]), "trades": int(rec["trades"])})
    rows.sort(key=lambda r: -r["pnl"])
    top = rows[:20]
    out = {"leaders": top, "count": len(rows),
           "hall_of_fame": tod["hall"][-10:],
           "note": "Realized PnL from shorts, derivatives & index options today."}
    if top:
        out["crown"] = {"uid": top[0]["uid"], "name": top[0]["name"],
                        "pnl": top[0]["pnl"]}
    if uid is not None:
        for i, r in enumerate(rows):
            if r["uid"] == uid:
                out["your_rank"] = i + 1
                out["your_pnl"] = r["pnl"]
                break
    return out


# ============================================================
# PORTFOLIO (unified view of all assets; phi net-worth breakdown)
# ============================================================

def portfolio(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    gold = me.get("gold", 0)
    # loot value
    loot_val = sum(l.get("value", 0) * l.get("qty", 1) for l in me.get("loot", []))
    # stocks held (player buys via trade -> me["stocks"])
    stock_val = 0
    for h in me.get("stocks", []):
        s = _stock_by_name(state, h.get("name", ""))
        px = s["price"] if s else h.get("price", 0)
        stock_val += px * h.get("qty", 1) if "qty" in h else px
    # bonds (future payout)
    bond_val = sum(b.get("payout", 0) for b in me.get("bonds", []))
    # hedge funds (current value)
    hedge_val = sum(_hedge_value(state, f) for f in me.get("hedge", []))
    # derivatives (settle value)
    deriv_val = 0
    for p in me.get("derivs", []):
        s = _stock_by_name(state, p["symbol"])
        spot = s["price"] if s else p["entry_spot"]
        deriv_val += max(0, _settle_value(p, spot))
    # M&A corp shares owned
    ma_val = 0
    for cid in range(len(CORPS)):
        book = _corp_book(state, cid)
        q = book["held"].get(str(uid), 0)
        if q:
            ma_val += q * share_price(state, cid)
    # IPO shares owned (in others' companies)
    ipo_val = 0
    for fu, ipo in _ipos(state).items():
        q = ipo["held"].get(str(uid), 0)
        if q:
            ipo_val += q * ipo_price(state, int(fu))
    # own IPO equity (unsold founder stake value)
    own_ipo = _ipos(state).get(str(uid))
    own_ipo_val = 0
    if own_ipo:
        unsold = IPO_TOTAL_SHARES - sum(own_ipo["held"].values())
        own_ipo_val = unsold * ipo_price(state, uid)
    # short positions (margin + mark-to-market PnL, floored at 0)
    short_val = 0
    for p in me.get("shorts", []):
        s = _stock_by_name(state, p["symbol"])
        spot = s["price"] if s else p["entry"]
        short_val += max(0, p["margin"] + _short_pnl(p, spot))
    # market-making orders (posted equity, or inventory net of borrowed debt)
    mm_val = 0
    for o in me.get("mm_orders", []):
        if o["state"] == "resting":
            mm_val += o.get("equity", o["reserved"])
        else:
            s = _stock_by_name(state, o["symbol"])
            spot = s["price"] if s else o["bid"]
            mm_val += max(0, int(spot * o["size"]) - o.get("debt", 0))
    # index options (premium-at-risk, mark to intrinsic)
    idxopt_val = 0
    for p in me.get("idx_opts", []):
        idxopt_val += int(_idx_intrinsic(p, golden_index_value(state)) * IDX_OPT_SIZE)
    # loan debt (liability)
    debt = 0
    loan = me.get("loan")
    if loan:
        _accrue(loan, now)
        debt = loan["debt"]

    assets = {
        "gold": int(gold), "loot": int(loot_val), "stocks": int(stock_val),
        "bonds": int(bond_val), "hedge": int(hedge_val), "derivatives": int(deriv_val),
        "ma_stakes": int(ma_val), "ipo_shares": int(ipo_val), "own_equity": int(own_ipo_val),
        "shorts": int(short_val), "market_making": int(mm_val),
        "index_options": int(idxopt_val),
    }
    gross = sum(assets.values())
    net = gross - int(debt)
    # phi-weighted breakdown (share of gross)
    breakdown = []
    for k, v in sorted(assets.items(), key=lambda x: -x[1]):
        if v <= 0:
            continue
        breakdown.append({"asset": k, "value": v,
                          "pct": round(100 * v / gross, 2) if gross else 0})
    return {"assets": assets, "breakdown": breakdown,
            "gross": int(gross), "debt": int(debt), "net_worth": int(net),
            "magnate_score": magnate_score(me),
            "note": "All values are in-game gold."}


# ============================================================
# SELF-TEST (run: python golden_econ.py)
# ============================================================

if __name__ == "__main__":
    class FakeState:
        def __init__(self):
            self.chars = {
                1000: {"user_id":1000,"gold":1000,"xp":500,"level":3,
                       "hero_id":1,"corp_id":2,"floor":4,"net_worth":200000,
                       "hero_levels":[10,20,5,8,12,3,7,9,4,6,11,2],
                       "stocks":[]},
                1001: {"user_id":1001,"gold":800,"xp":200,"level":2,
                       "hero_id":0,"corp_id":0,"floor":1,"net_worth":150000,
                       "hero_levels":[5,5,5,5,5,5,5,5,5,5,5,5],"stocks":[]},
            }
        def mark_dirty(self, uid):
            pass
        stocks = [{"name":"ALPHA","price":50.0,"delta":1.2},
                  {"name":"PHI","price":161.8,"delta":-2.1}]
    st = FakeState()
    g = GuildSystem(st)
    print("corp totals:", g.corp_totals()[0])
    print("leaderboard top:", g.leaderboard(2)[0])
    print("market:", g.market_summary()["phi_band"])
    ar = Arena(st)
    print("duel:", ar.fight(1000))
    print("artifact:", roll_artifact())
    print("level_threshold(3):", level_threshold(3))
    print("hero_power(100,20):", hero_power(100, 20))
    print("season:", current_season(), "progress:", season_progress())
    print("season_points:", season_points(st.chars[1000]))
    print("passive_bonus:", passive_bonus([1,0,2,0,0,0,0,0,0,0,0,0]))
    print("unlock_cost(0,1):", unlock_cost(0, 1))
    st.chars[1000]["passives"] = [3,3,0,0,0,0,0,0,0,0,0,0]
    print("duel w/ passives:", ar.fight(1000))
    print("season_rewards:", g.season_rewards(2))
    pr = Prestige(st)
    st.chars[1000]["level"] = 30
    print("prestige status:", pr.status(1000))
    print("ascend:", pr.ascend(1000))
    rd = Raid(st)
    print("raid status:", rd.status(2)["pct"], rd.status(2)["boss"])
    for _ in range(3):
        s = rd.strike(1000)
    print("raid strike:", {k: s[k] for k in ("damage", "boss_hp")})
    print("daily_quests:", daily_quests(1000)["quests"][0])
    print("claim_quest:", claim_quest(st, 1000, 0))
    print("claim_again:", claim_quest(st, 1000, 0))
    st.chars[1000]["loot"] = [{"rarity": 5}]
    ach = evaluate_achievements(st.chars[1000])
    print("achievements unlocked:", sum(1 for a in ach if a["unlocked"]), "/", len(ach))
    print("claim_ach:", claim_achievements(st, 1000)["granted_gold"])
    print("ref code 1000:", referral_code(1000))
    print("accept_ref:", accept_referral(st, 1001, referral_code(1000)))
    print("ref_status:", referral_status(st, 1000)["referrals"])
    print("chest_status:", chest_status(st, 1000)["available"], chest_status(st, 1000)["reward_preview"])
    print("open_chest:", open_chest(st, 1000)["reward_gold"])
    print("open_again:", open_chest(st, 1000).get("error"))
    wb = WorldBoss(st)
    print("world boss:", wb.status()["boss"], wb.status()["pct"])
    for _ in range(3):
        s = wb.strike(1000)
    print("wb strike:", {k: s[k] for k in ("damage", "boss_hp")})
    print("OK")
