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
                grant_badge(state, uid, "SQUEEZE_SURVIVOR", now=now)
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
        grant_badge(state, uid, "SQUEEZE_SURVIVOR", now=now)
        state.mark_dirty(uid)
        return {"ok": True, "squeezed": True, "symbol": pos["symbol"],
                "entry": round(pos["entry"], 2), "spot": round(spot, 2),
                "margin_lost": pos["margin"], "returned": 0, "gold": me["gold"]}
    payout = max(0, pos["margin"] + pnl)
    res = award_gold(state, uid, payout, now=now) if payout > 0 else {"gained": 0}
    record_trade_pnl(state, uid, pnl, now=now)
    if pnl > 0:
        grant_badge(state, uid, "SHORT_SELLER", now=now)
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
    if payout >= pos["premium"] * PHI:
        grant_badge(state, uid, "PHI_OPTION", now=now)
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

BOT_NAMES = ["PhiQuant", "GoldenAlgo", "FibBot", "AurumAI",
             "RatioTrader", "SpiralFund", "NautilusHF", "VectorX"]

def _tape(state):
    if not hasattr(state, "tape"):
        state.tape = []          # ring buffer of ticker lines
        state._tape_seq = 0
    return state.tape

def push_tape(state, text, kind="bot", now=None):
    now = now or int(time.time())
    tape = _tape(state)
    state._tape_seq += 1
    tape.append({"id": state._tape_seq, "ts": now, "kind": kind, "text": text})
    if len(tape) > 40:
        del tape[:-40]

def tape_feed(state, since=0):
    tape = _tape(state)
    return {"lines": [t for t in tape if t["id"] > since][-40:],
            "last_id": tape[-1]["id"] if tape else 0}

def tick_bots(state, now=None):
    """Bots push prices around: momentum bots chase the last delta, mean-
    reverters fade extremes toward a phi-anchor. This animates the tape so
    player market-making, shorts and derivatives get organic fills."""
    now = now or int(time.time())
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
        # occasionally a bot narrates its trade on the tape
        if random.random() < (1 / (PHI ** 4)):
            name = BOT_NAMES[b["id"] % len(BOT_NAMES)]
            act = "BUY" if push >= 0 else "SELL"
            verb = "chasing momentum" if b["style"] == "momentum" else "fading the move"
            push_tape(state, f"{name} {act} {s['name']} @ {s['price']:.1f} — {verb}",
                      kind="bot", now=now)
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
    push_tape(state, f"*** FLASH CRASH *** Golden-500 -> {idx:,.0f}", kind="crash", now=now)
    return {"crashed": True, "index": idx}

# --- Market sectors: 20 tickers grouped into 4 phi-sectors ---
SECTORS = [
    {"name": "TECH",   "emoji": "🧠", "idx": [0, 1, 2, 3, 4]},
    {"name": "FINANCE","emoji": "🏦", "idx": [5, 6, 7, 8, 9]},
    {"name": "ENERGY", "emoji": "⚡", "idx": [10, 11, 12, 13, 14]},
    {"name": "LUXURY", "emoji": "💎", "idx": [15, 16, 17, 18, 19]},
]

def sector_of(stock_index):
    for sec in SECTORS:
        if stock_index in sec["idx"]:
            return sec["name"]
    return "MISC"

def _sector_value(state, sec):
    stocks = getattr(state, "stocks", [])
    total = 0.0
    wsum = 0.0
    for j, i in enumerate(sec["idx"]):
        if i < len(stocks):
            w = PHI ** (-(j % 5))
            total += stocks[i]["price"] * w
            wsum += w
    return round((total / wsum) if wsum else 0.0, 2)

def _sector_hist(state):
    if not hasattr(state, "sector_hist"):
        state.sector_hist = {}
        state._sector_last = {}
    return state.sector_hist

def tick_sectors(state, now=None):
    now = now or int(time.time())
    hist = _sector_hist(state)
    last = state._sector_last
    for sec in SECTORS:
        v = _sector_value(state, sec)
        series = hist.setdefault(sec["name"], [])
        cur = last.get(sec["name"])
        if cur is None or now - cur["t0"] >= STOCK_CANDLE_SECS:
            candle = {"t": now, "c": v, "t0": now}
            series.append(candle)
            last[sec["name"]] = candle
            if len(series) > 60:
                del series[:len(series) - 60]
        else:
            cur["c"] = v

def sectors_status(state):
    hist = _sector_hist(state)
    stocks = getattr(state, "stocks", [])
    out = []
    for sec in SECTORS:
        v = _sector_value(state, sec)
        series = hist.get(sec["name"], [])
        prev = series[0]["c"] if series else v
        chg = round(v - prev, 2)
        members = [{"name": stocks[i]["name"], "price": round(stocks[i]["price"], 2)}
                   for i in sec["idx"] if i < len(stocks)]
        spark = [round(c["c"], 2) for c in series[-30:]]
        out.append({"name": sec["name"], "emoji": sec["emoji"], "value": v,
                    "change": chg,
                    "change_pct": round((chg / prev * 100) if prev else 0, 2),
                    "members": members, "spark": spark})
    hot = max(out, key=lambda x: x["change_pct"]) if out else None
    cold = min(out, key=lambda x: x["change_pct"]) if out else None
    return {"sectors": out,
            "rotation": {"hot": hot["name"] if hot else None,
                         "cold": cold["name"] if cold else None},
            "note": "Capital rotates between phi-sectors. In-game gold only."}

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
                    grant_badge(state, uid, "MARKET_MAKER", now=now)
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
    me["lifetime_pnl"] = int(me.get("lifetime_pnl", 0)) + int(pnl)
    state.mark_dirty(uid)
    if pnl > 0:
        grant_badge(state, uid, "FIRST_BLOOD", now=now)
    if me["lifetime_pnl"] >= 1_000_000:
        grant_badge(state, uid, "MOGUL", now=now)

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

TRADER_BADGES = [
    {"code": "FIRST_BLOOD",  "name": "First Blood",       "emoji": "🩸",
     "desc": "Realize your first winning trade"},
    {"code": "SHORT_SELLER", "name": "Short Seller",      "emoji": "📉",
     "desc": "Close a short in profit"},
    {"code": "SQUEEZE_SURVIVOR", "name": "Squeeze Survivor", "emoji": "🛡",
     "desc": "Get squeezed and keep trading"},
    {"code": "PHI_OPTION",   "name": "Golden Contract",   "emoji": "🎯",
     "desc": "Settle an index option for >=phi*premium"},
    {"code": "MARKET_MAKER", "name": "Market Maker",      "emoji": "⚖",
     "desc": "Complete a market-making round"},
    {"code": "MOGUL",        "name": "Golden Mogul",      "emoji": "👑",
     "desc": "Reach 1,000,000g realized PnL lifetime"},
]
_BADGE_BY_CODE = {b["code"]: b for b in TRADER_BADGES}

def grant_badge(state, uid, code, now=None):
    me = state.chars.get(uid)
    if not me or code not in _BADGE_BY_CODE:
        return False
    have = me.setdefault("trader_badges", [])
    if code in have:
        return False
    have.append(code)
    me["lifetime_badges"] = me.get("lifetime_badges", 0) + 1
    state.mark_dirty(uid)
    push_tape(state, f"{me.get('name','Player')} earned badge {_BADGE_BY_CODE[code]['emoji']} {_BADGE_BY_CODE[code]['name']}",
              kind="badge", now=now)
    return True

def trader_badges(state, uid):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    have = set(me.get("trader_badges", []))
    out = [{**b, "earned": b["code"] in have} for b in TRADER_BADGES]
    return {"badges": out, "earned_count": len(have),
            "total": len(TRADER_BADGES),
            "lifetime_pnl": int(me.get("lifetime_pnl", 0)),
            "note": "Trader badges are in-game honors only."}

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
# PHI LOTTERY — weekly lottery with phi-weighted draws
# ============================================================

class PhiLottery:
    """Weekly lottery. Players buy tickets with gold. Draw is phi-weighted:
    each ticket's chance = PHI^(ticket_count) / sum(PHI^all). More tickets
    = higher chance but with diminishing phi returns."""

    TICKET_COST = 500        # base cost in gold
    DRAW_INTERVAL = int(3600 * PHI * 24)  # ~1.6 days (1 PHIday)
    POOL_MULT = 3            # prize pool = tickets_sold * cost * POOL_MULT
    MAX_TICKETS = 21         # Fibonacci cap per player

    @staticmethod
    def _now_week(now=None):
        """Deterministic lottery epoch (resets every DRAW_INTERVAL)."""
        t = now or int(time.time())
        EPOCH = 1700000000
        return (t - EPOCH) // PhiLottery.DRAW_INTERVAL

    @staticmethod
    def status(state, uid, now=None):
        """Return lottery status for a player."""
        t = now or int(time.time())
        week = PhiLottery._now_week(t)
        epoch = 1700000000 + week * PhiLottery.DRAW_INTERVAL
        next_draw = epoch + PhiLottery.DRAW_INTERVAL
        remaining = max(0, next_draw - t)
        # count tickets
        key = f"lottery_{week}"
        pool = state.chars.get(uid, {}).get("_lottery_pool", {})
        my_tickets = pool.get(key, 0)
        # total tickets (global)
        total = 0
        for c in state.chars.values():
            lp = c.get("_lottery_pool", {})
            total += lp.get(key, 0)
        pool_gold = total * PhiLottery.TICKET_COST * PhiLottery.POOL_MULT
        cost = PhiLottery.TICKET_COST + int(total * PHI)  # price rises with demand
        return {
            "week": week,
            "remaining": remaining,
            "cost": min(cost, PhiLottery.TICKET_COST * 10),
            "my_tickets": my_tickets,
            "max_tickets": PhiLottery.MAX_TICKETS,
            "total_tickets": total,
            "pool_gold": pool_gold,
            "winner": None,
        }

    @staticmethod
    def buy_ticket(state, uid, now=None):
        """Buy a lottery ticket. Returns updated status or error."""
        t = now or int(time.time())
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        week = PhiLottery._now_week(t)
        key = f"lottery_{week}"
        lp = c.get("_lottery_pool", {})
        my = lp.get(key, 0)
        if my >= PhiLottery.MAX_TICKETS:
            return {"error": "max tickets reached"}
        # cost rises with total demand
        total_before = 0
        for ch in state.chars.values():
            total_before += ch.get("_lottery_pool", {}).get(key, 0)
        cost = PhiLottery.TICKET_COST + int(total_before * PHI)
        cost = min(cost, PhiLottery.TICKET_COST * 10)
        gold = int(c.get("gold", 0))
        if gold < cost:
            return {"error": "not enough gold", "have": gold, "need": cost}
        c["gold"] = gold - cost
        c.setdefault("_lottery_pool", {})[key] = my + 1
        state.mark_dirty(uid)
        return PhiLottery.status(state, uid, t)

    @staticmethod
    def draw(state, now=None):
        """Draw the lottery winner. Returns winner uid + prize. Called at draw time."""
        t = now or int(time.time())
        week = PhiLottery._now_week(t)
        key = f"lottery_{week}"
        entries = []
        for uid, c in state.chars.items():
            lp = c.get("_lottery_pool", {})
            tickets = lp.get(key, 0)
            if tickets > 0:
                entries.append((uid, tickets))
        if not entries:
            return {"error": "no entries"}
        # phi-weighted random draw
        total = sum(t for _, t in entries)
        weights = [PHI ** (t / total) for _, t in entries]
        total_w = sum(weights)
        r = random.random() * total_w
        cumulative = 0
        winner_uid = entries[0][0]
        for i, (uid, _) in enumerate(entries):
            cumulative += weights[i]
            if r <= cumulative:
                winner_uid = uid
                break
        pool_gold = total * PhiLottery.TICKET_COST * PhiLottery.POOL_MULT
        state.chars[winner_uid]["gold"] = state.chars[winner_uid].get("gold", 0) + pool_gold
        state.mark_dirty(winner_uid)
        return {"winner": winner_uid, "prize": pool_gold, "week": week}


# ============================================================
# BLACK MARKET — rotating rare item shop
# ============================================================

class BlackMarket:
    """Rotating shop of rare items. Stock refreshes every PHI hours.
    Items are drawn from loot pools with phi-boosted rarities."""

    REFRESH_INTERVAL = int(3600 * PHI * 4)  # ~6.5 hours
    SHOP_SIZE = 7  # items per refresh

    ITEM_NAMES = [
        "Phi Shard", "Golden Decoder", "Quantum Key", "Neural Spike",
        "Void Crystal", "Midas Lens", "Omega Relic", "Sector Cipher",
        "Delta Core", "Titan Plate", "Ghost Protocol", "Apex Serum",
        "Chrono Shard", "Eclipse Mask", "Zenith Engine", "Pulse Node",
    ]

    @staticmethod
    def _shop_seed(now=None):
        t = now or int(time.time())
        EPOCH = 1700000000
        return (t - EPOCH) // BlackMarket.REFRESH_INTERVAL

    @staticmethod
    def _gen_shop(seed):
        rng = random.Random(seed)
        items = []
        for i in range(BlackMarket.SHOP_SIZE):
            rarity = rng.choices(range(6), weights=[3000, 4000, 2000, 700, 250, 50])[0]
            name = rng.choice(BlackMarket.ITEM_NAMES)
            base_val = [50, 250, 1000, 5000, 25000, 100000][rarity]
            price = int(base_val * (PHI ** rng.randint(0, 3)))
            items.append({
                "id": i, "name": name, "rarity": rarity,
                "code": rng.randint(0, 65535), "price": price,
                "value": base_val,
            })
        return items

    @staticmethod
    def status(now=None):
        t = now or int(time.time())
        seed = BlackMarket._shop_seed(t)
        items = BlackMarket._gen_shop(seed)
        epoch = 1700000000 + seed * BlackMarket.REFRESH_INTERVAL
        remaining = max(0, (epoch + BlackMarket.REFRESH_INTERVAL) - t)
        return {"items": items, "remaining": remaining, "seed": seed}

    @staticmethod
    def buy(state, uid, item_id, now=None):
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        seed = BlackMarket._shop_seed(now)
        items = BlackMarket._gen_shop(seed)
        if item_id < 0 or item_id >= len(items):
            return {"error": "invalid item"}
        item = items[item_id]
        gold = int(c.get("gold", 0))
        if gold < item["price"]:
            return {"error": "not enough gold", "have": gold, "need": item["price"]}
        c["gold"] = gold - item["price"]
        loot = {"code": item["code"], "rarity": item["rarity"],
                "qty": 1, "value": item["value"], "name": item["name"],
                "cat": 10 if item["rarity"] >= 4 else 0}
        c.setdefault("loot", []).append(loot)
        c["net_worth"] = c.get("net_worth", 0) + item["value"]
        state.mark_dirty(uid)
        return {"ok": True, "item": item["name"], "rarity": item["rarity"],
                "gold_left": c["gold"]}


# ============================================================
# HEIST MISSIONS — timed cooperative multi-stage missions
# ============================================================

class HeistMission:
    """Cooperative heist missions. Multiple players contribute gold/loot
    to fund a heist. After a timer, the heist resolves with phi-weighted
    loot split among contributors."""

    STAGES = 5
    BASE_COST = 2000
    BASE_REWARD = 50000
    DURATION = int(3600 * PHI)  # ~1.6 hours
    CORPS = ["MERIDIAN", "APEX", "NOVA", "VERTEX", "PULSAR", "AUREATE", "SOLARIS"]

    MISSION_NAMES = [
        "Operation Golden Vault", "Phi Protocol Breach", "Midnight Merger Heist",
        "The Cortex Infiltration", "Quantum Fund Extraction", "The Aureate Gambit",
        "Operation Silver Lining", "The Zero-Day Raid",
    ]

    @staticmethod
    def _current_heist(now=None):
        t = now or int(time.time())
        EPOCH = 1700000000
        cycle = int(3600 * PHI * 3)  # new heist every ~5 hours
        idx = (t - EPOCH) // cycle
        return idx

    @staticmethod
    def status(state, now=None):
        t = now or int(time.time())
        idx = HeistMission._current_heist(t)
        rng = random.Random(idx)
        mission_name = rng.choice(HeistMission.MISSION_NAMES)
        target_corp = rng.choice(HeistMission.CORPS)
        # funding progress from all chars
        fund_key = f"heist_{idx}"
        total_funded = 0
        contributors = []
        for uid, c in state.chars.items():
            heists = c.get("_heist_funds", {})
            amt = heists.get(fund_key, 0)
            if amt > 0:
                total_funded += amt
                contributors.append({"uid": uid, "amount": amt})
        # target: 7 contributors * PHI^3 * BASE_COST ≈ 13K gold
        target = HeistMission.BASE_COST * int(PHI ** 4)
        # is heist in progress or completed?
        epoch = 1700000000 + idx * int(3600 * PHI * 3)
        elapsed = t - epoch
        in_progress = elapsed < HeistMission.DURATION
        completed = elapsed >= HeistMission.DURATION and total_funded > 0
        reward_mult = PHI ** (total_funded / target) if target > 0 else 1
        pool = int(HeistMission.BASE_REWARD * reward_mult)
        return {
            "mission": mission_name,
            "target_corp": target_corp,
            "funded": total_funded,
            "target": target,
            "contributors": len(contributors),
            "in_progress": in_progress,
            "completed": completed,
            "remaining": max(0, HeistMission.DURATION - elapsed) if in_progress else 0,
            "pool": pool if completed else int(HeistMission.BASE_REWARD * reward_mult * 0.5),
        }

    @staticmethod
    def fund(state, uid, amount, now=None):
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        idx = HeistMission._current_heist(now)
        t = now or int(time.time())
        epoch = 1700000000 + idx * int(3600 * PHI * 3)
        if t - epoch >= HeistMission.DURATION:
            return {"error": "heist closed"}
        gold = int(c.get("gold", 0))
        amount = min(amount, gold)
        if amount <= 0:
            return {"error": "nothing to fund"}
        c["gold"] = gold - amount
        fund_key = f"heist_{idx}"
        c.setdefault("_heist_funds", {})[fund_key] = \
            c.get("_heist_funds", {}).get(fund_key, 0) + amount
        state.mark_dirty(uid)
        return HeistMission.status(state, t)

    @staticmethod
    def claim(state, uid, now=None):
        """Claim heist reward after completion."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        idx = HeistMission._current_heist(now)
        t = now or int(time.time())
        epoch = 1700000000 + idx * int(3600 * PHI * 3)
        if t - epoch < HeistMission.DURATION:
            return {"error": "heist not completed"}
        fund_key = f"heist_{idx}"
        my_funded = c.get("_heist_funds", {}).get(fund_key, 0)
        if my_funded <= 0:
            return {"error": "you did not participate"}
        claimed_key = f"heist_claimed_{idx}"
        if c.get(claimed_key):
            return {"error": "already claimed"}
        # calculate total funded and pool
        total_funded = 0
        for ch in state.chars.values():
            total_funded += ch.get("_heist_funds", {}).get(fund_key, 0)
        target = HeistMission.BASE_COST * int(PHI ** 4)
        pool = int(HeistMission.BASE_REWARD * (PHI ** (total_funded / max(target, 1))))
        # phi-weighted share
        share = (my_funded / max(total_funded, 1)) ** (1 / PHI)
        share = min(share * PHI, 1.0)
        prize = int(pool * share)
        c["gold"] = c.get("gold", 0) + prize
        c[claimed_key] = True
        state.mark_dirty(uid)
        return {"ok": True, "prize": prize, "share_pct": round(share * 100, 1),
                "gold_left": c["gold"]}


# ============================================================
# PHI PROPHET — stock price prediction game
# ============================================================

class PhiProphet:
    """Prediction market. Players predict if a stock goes up or down in
    the next PHI minutes. Correct predictions earn phi-scaled gold."""

    PREDICTION_WINDOW = int(60 * PHI * 10)  # ~16 minutes
    BASE_REWARD = 200
    MAX_ACTIVE = 3

    @staticmethod
    def status(state, uid, now=None):
        t = now or int(time.time())
        c = state.chars.get(uid, {})
        active = c.get("_prophet_active", [])
        history = c.get("_prophet_history", [])
        wins = sum(1 for h in history if h.get("won"))
        total = len(history)
        return {
            "active": active,
            "active_count": len(active),
            "max_active": PhiProphet.MAX_ACTIVE,
            "history_len": total,
            "wins": wins,
            "accuracy": round(wins / total * 100, 1) if total > 0 else 0,
            "window": PhiProphet.PREDICTION_WINDOW,
        }

    @staticmethod
    def predict(state, uid, symbol, direction, now=None):
        """direction: 'up' or 'down'. Costs gold, pays out on correct."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        t = now or int(time.time())
        active = c.get("_prophet_active", [])
        # cleanup expired
        active = [a for a in active if t < a["expires"]]
        if len(active) >= PhiProphet.MAX_ACTIVE:
            return {"error": "max active predictions"}
        if direction not in ("up", "down"):
            return {"error": "direction must be 'up' or 'down'"}
        stake = 100 + int(PHI * len(active) * 50)
        gold = int(c.get("gold", 0))
        if gold < stake:
            return {"error": "not enough gold", "have": gold, "need": stake}
        c["gold"] = gold - stake
        pred = {
            "symbol": symbol,
            "direction": direction,
            "price_at": _stock_price_now(state, symbol),
            "expires": t + PhiProphet.PREDICTION_WINDOW,
            "stake": stake,
        }
        active.append(pred)
        c["_prophet_active"] = active
        state.mark_dirty(uid)
        return {"ok": True, "stake": stake, "expires_in": PhiProphet.PREDICTION_WINDOW}

    @staticmethod
    def settle(state, uid, now=None):
        """Check all expired predictions and pay out winners."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        t = now or int(time.time())
        active = c.get("_prophet_active", [])
        settled = []
        remaining = []
        for pred in active:
            if t >= pred["expires"]:
                current_price = _stock_price_now(state, pred["symbol"])
                went_up = current_price > pred["price_at"]
                won = (pred["direction"] == "up" and went_up) or \
                      (pred["direction"] == "down" and not went_up)
                prize = 0
                if won:
                    prize = int(pred["stake"] * PHI * 2)
                    c["gold"] = c.get("gold", 0) + prize
                settled.append({
                    "symbol": pred["symbol"],
                    "direction": pred["direction"],
                    "price_start": pred["price_at"],
                    "price_end": current_price,
                    "won": won,
                    "prize": prize,
                })
            else:
                remaining.append(pred)
        c["_prophet_active"] = remaining
        history = c.get("_prophet_history", [])
        history.extend(settled)
        c["_prophet_history"] = history[-50:]  # keep last 50
        state.mark_dirty(uid)
        return {"settled": settled, "gold_left": c.get("gold", 0)}


def _stock_price_now(state, symbol):
    """Get current stock price from state."""
    for s in state.stocks:
        if s.get("name") == symbol:
            return s.get("price", 0)
    return 0


# ============================================================
# GOLDEN RAIN — random server-wide gold drops
# ============================================================

class GoldenRain:
    """Random gold drops that fall on the server. When triggered, a rain
    event appears for N seconds. Players who 'catch' get phi-scaled shares.
    First catch gets PHI bonus."""

    DROP_INTERVAL = int(3600 * PHI * 2)  # ~3.2 hours between rains
    RAIN_DURATION = 30  # seconds to catch
    BASE_POT = 10000
    MAX_CATCHERS = 8  # Fibonacci

    @staticmethod
    def _last_rain():
        EPOCH = 1700000000
        interval = GoldenRain.DROP_INTERVAL
        now = int(time.time())
        last_start = EPOCH + ((now - EPOCH) // interval) * interval
        return last_start

    @staticmethod
    def status(state, uid, now=None):
        t = now or int(time.time())
        last = GoldenRain._last_rain()
        elapsed = t - last
        active = elapsed < GoldenRain.RAIN_DURATION
        remaining = max(0, GoldenRain.RAIN_DURATION - elapsed) if active else 0
        next_rain = last + GoldenRain.DROP_INTERVAL
        next_in = max(0, next_in) if (next_in := next_rain - t) > 0 else 0
        # did this player catch?
        key = f"golden_rain_{last}"
        catchers = state.chars.get(0, {}).get("_rain_catchers", {})
        my_caught = catchers.get(key, {}).get(str(uid), 0) if isinstance(catchers.get(key), dict) else 0
        return {
            "active": active,
            "remaining": remaining,
            "next_in": next_in,
            "pot": GoldenRain.BASE_POT + int(PHI * elapsed),
            "my_caught": my_caught,
            "total_catchers": len(catchers.get(key, {})) if isinstance(catchers.get(key), dict) else 0,
        }

    @staticmethod
    def catch(state, uid, now=None):
        """Player tries to catch falling gold."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        t = now or int(time.time())
        last = GoldenRain._last_rain()
        if t - last >= GoldenRain.RAIN_DURATION:
            return {"error": "no active rain"}
        if t - last < 1:
            return {"error": "rain not yet started"}
        key = f"golden_rain_{last}"
        # global catch state in uid 0 (market data holder)
        market_c = state.chars.setdefault(0, {})
        rain_catchers = market_c.setdefault("_rain_catchers", {})
        catch_dict = rain_catchers.setdefault(key, {})
        uid_str = str(uid)
        if uid_str in catch_dict:
            return {"error": "already caught"}
        count = len(catch_dict)
        if count >= GoldenRain.MAX_CATCHERS:
            return {"error": "rain exhausted"}
        # phi-weighted: first catchers get more
        rank = count + 1
        pot = GoldenRain.BASE_POT + int(PHI * (t - last))
        share = PHI ** (1.0 / rank)  # first gets PHI, second gets sqrt(PHI), etc.
        total_shares = sum(PHI ** (1.0 / r) for r in range(1, GoldenRain.MAX_CATCHERS + 1))
        prize = int(pot * share / total_shares)
        c["gold"] = c.get("gold", 0) + prize
        catch_dict[uid_str] = prize
        state.mark_dirty(uid)
        SND_PRIZE = prize  # noqa: unused
        return {"ok": True, "prize": prize, "rank": rank, "gold_left": c["gold"]}


# ============================================================
# CORP ESPIONAGE — sabotage/boost rival corps
# ============================================================

class CorpEspionage:
    """Strategic corp manipulation. Spend gold to:
    - SABOTAGE a rival corp: reduces their member bonus for PHI hours
    - BOOST your own corp: increases member bonus for PHI hours
    Cost scales by PHI^tier. One action per player per cooldown."""

    SABOTAGE_COST = 5000
    BOOST_COST = 3000
    EFFECT_DURATION = int(3600 * PHI)  # ~1.6 hours
    COOLDOWN = int(3600 * PHI * 2)  # ~3.2 hours

    @staticmethod
    def status(state, uid, now=None):
        t = now or int(time.time())
        c = state.chars.get(uid, {})
        active = c.get("_espionage_active", {})
        cooldown_until = c.get("_espionage_cooldown", 0)
        on_cooldown = t < cooldown_until
        return {
            "on_cooldown": on_cooldown,
            "cooldown_remaining": max(0, cooldown_until - t),
            "active": active,
            "sabotage_cost": CorpEspionage.SABOTAGE_COST,
            "boost_cost": CorpEspionage.BOOST_COST,
            "effect_duration": CorpEspionage.EFFECT_DURATION,
        }

    @staticmethod
    def sabotage(state, uid, target_corp_id, now=None):
        """Sabotage a rival corp."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        t = now or int(time.time())
        if t < c.get("_espionage_cooldown", 0):
            return {"error": "on cooldown", "remaining": c["_espionage_cooldown"] - t}
        if target_corp_id == c.get("corp_id"):
            return {"error": "cannot sabotage own corp"}
        if target_corp_id < 0 or target_corp_id >= len(CORPS):
            return {"error": "invalid corp"}
        cost = int(CorpEspionage.SABOTAGE_COST * PHI ** (c.get("prestige", 0) * 0.1))
        gold = int(c.get("gold", 0))
        if gold < cost:
            return {"error": "not enough gold", "have": gold, "need": cost}
        c["gold"] = gold - cost
        c["_espionage_active"] = {
            "type": "sabotage",
            "target": target_corp_id,
            "expires": t + CorpEspionage.EFFECT_DURATION,
        }
        c["_espionage_cooldown"] = t + CorpEspionage.COOLDOWN
        state.mark_dirty(uid)
        # apply effect to market mood
        state.stocks[target_corp_id % len(state.stocks)]["delta"] -= PHI
        return {"ok": True, "target": CORPS[target_corp_id], "cost": cost,
                "duration": CorpEspionage.EFFECT_DURATION}

    @staticmethod
    def boost(state, uid, now=None):
        """Boost your own corp."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        t = now or int(time.time())
        if t < c.get("_espionage_cooldown", 0):
            return {"error": "on cooldown", "remaining": c["_espionage_cooldown"] - t}
        cost = int(CorpEspionage.BOOST_COST * PHI ** (c.get("prestige", 0) * 0.1))
        gold = int(c.get("gold", 0))
        if gold < cost:
            return {"error": "not enough gold", "have": gold, "need": cost}
        my_corp = c.get("corp_id", 0)
        c["gold"] = gold - cost
        c["_espionage_active"] = {
            "type": "boost",
            "target": my_corp,
            "expires": t + CorpEspionage.EFFECT_DURATION,
        }
        c["_espionage_cooldown"] = t + CorpEspionage.COOLDOWN
        state.mark_dirty(uid)
        state.stocks[my_corp % len(state.stocks)]["delta"] += PHI
        return {"ok": True, "target": CORPS[my_corp], "cost": cost,
                "duration": CorpEspionage.EFFECT_DURATION}


# ============================================================
# PHI WEATHER — dynamic market conditions
# ============================================================

class PhiWeather:
    """Market weather system. Cycles through conditions that affect all stocks:
    BULL_STORM:  prices surge (all deltas +PHI^2)
    BEAR_BLIZZARD: prices crash (all deltas -PHI^2)
    GOLDEN_CLEAR: normal trading, golden hour bonus
    VOLATILE_TEMPEST: wild swings, high risk/high reward
    PHI_ECLIPSE: everything freezes, massive rewards after thaw"""

    WEATHERS = ["BULL_STORM", "BEAR_BLIZZARD", "GOLDEN_CLEAR", "VOLATILE_TEMPEST", "PHI_ECLIPSE"]
    WEATHER_NAMES_RU = {
        "BULL_STORM": "Бычий шторм",
        "BEAR_BLIZZARD": "Медвежья буря",
        "GOLDEN_CLEAR": "Золотая ясность",
        "VOLATILE_TEMPEST": "Волатильный шторм",
        "PHI_ECLIPSE": "ФИ-Затмение",
    }
    WEATHER_DESC = {
        "BULL_STORM": "All prices surge by PHI^2. Buy everything!",
        "BEAR_BLIZZARD": "All prices crash by PHI^2. Short everything!",
        "GOLDEN_CLEAR": "Normal conditions. Golden Hour bonus active.",
        "VOLATILE_TEMPEST": "Wild swings. High risk, massive reward.",
        "PHI_ECLIPSE": "Market frozen. Wait for the thaw — huge bonus.",
    }
    CYCLE = int(3600 * PHI * 6)  # ~9.7 hours per weather

    @staticmethod
    def current(now=None):
        t = now or int(time.time())
        EPOCH = 1700000000
        idx = (t - EPOCH) // PhiWeather.CYCLE
        rng = random.Random(idx)
        w = rng.choice(PhiWeather.WEATHERS)
        next_change = EPOCH + (idx + 1) * PhiWeather.CYCLE
        return {
            "weather": w,
            "name_ru": PhiWeather.WEATHER_NAMES_RU[w],
            "description": PhiWeather.WEATHER_DESC[w],
            "remaining": max(0, next_change - t),
        }

    @staticmethod
    def apply_weather_effect(state, now=None):
        """Apply weather to stock deltas. Called by market_loop."""
        w = PhiWeather.current(now)["weather"]
        if w == "BULL_STORM":
            for s in state.stocks:
                s["delta"] += PHI ** 2
        elif w == "BEAR_BLIZZARD":
            for s in state.stocks:
                s["delta"] -= PHI ** 2
        elif w == "VOLATILE_TEMPEST":
            for s in state.stocks:
                s["delta"] += (random.random() - 0.5) * PHI ** 3
        elif w == "PHI_ECLIPSE":
            for s in state.stocks:
                s["delta"] *= 0.01  # freeze


# ============================================================
# BOUNTY BOARD — rotating kill quests with phi-rewards
# ============================================================

class BountyBoard:
    """Daily bounty targets. Players hunt specific goals for phi-gold rewards.
    Bounties refresh daily. Each has a difficulty tier affecting reward scale."""

    BOUNTY_TEMPLATES = [
        {"id": 0, "name": "Рыночный охотник", "name_en": "Market Hunter",
         "desc": "Execute 3 trades", "type": "trades", "target": 3},
        {"id": 1, "name": "Золотой жнец", "name_en": "Golden Reaper",
         "desc": "Earn 5000g in one day", "type": "gold_earned", "target": 5000},
        {"id": 2, "name": "Дуэлянт", "name_en": "The Duelist",
         "desc": "Win 2 phi-duels", "type": "duels_won", "target": 2},
        {"id": 3, "name": "Боссолюб", "name_en": "Boss Slayer",
         "desc": "Deal 100K boss damage", "type": "boss_damage", "target": 100000},
        {"id": 4, "name": "Коллекционер", "name_en": "Collector",
         "desc": "Acquire 5 loot items", "type": "loot_acquired", "target": 5},
        {"id": 5, "name": "Пророк", "name_en": "The Prophet",
         "desc": "Win 3 predictions", "type": "predictions_won", "target": 3},
        {"id": 6, "name": "Грабитель", "name_en": "The Robber",
         "desc": "Complete 1 heist contribution", "type": "heist_funded", "target": 1},
        {"id": 7, "name": "Шпион", "name_en": "The Spy",
         "desc": "Perform 1 sabotage or boost", "type": "espionage", "target": 1},
        {"id": 8, "name": "Магнат", "name_en": "The Magnate",
         "desc": "Reach 500K net worth", "type": "net_worth", "target": 500000},
        {"id": 9, "name": "Фи-мастер", "name_en": "Phi Master",
         "desc": "Have 3+ prestige", "type": "prestige", "target": 3},
    ]

    @staticmethod
    def _today_seed(now=None):
        t = now or int(time.time())
        EPOCH = 1700000000
        return (t - EPOCH) // 86400

    @staticmethod
    def daily_bounties(uid, now=None):
        seed = BountyBoard._today_seed(now) + uid * 7
        rng = random.Random(seed)
        chosen = rng.sample(BountyBoard.BOUNTY_TEMPLATES, 3)
        result = []
        for i, b in enumerate(chosen):
            difficulty = rng.randint(1, 3)
            b = dict(b)
            b["difficulty"] = difficulty
            b["reward"] = int(1000 * PHI ** (i + difficulty))
            b["target"] = int(b["target"] * (PHI ** (difficulty - 1)))
            result.append(b)
        return result

    @staticmethod
    def check_progress(state, uid, now=None):
        c = state.chars.get(uid, {})
        bounties = BountyBoard.daily_bounties(uid, now)
        progress = []
        for b in bounties:
            done = BountyBoard._check_one(c, b)
            progress.append({**b, "completed": done})
        return progress

    @staticmethod
    def _check_one(char, bounty):
        t = bounty["type"]
        target = bounty["target"]
        if t == "net_worth":
            return char.get("net_worth", 0) >= target
        elif t == "prestige":
            return char.get("prestige", 0) >= target
        elif t == "trades":
            return char.get("_bounty_trades_today", 0) >= target
        elif t == "gold_earned":
            return char.get("_bounty_gold_today", 0) >= target
        elif t == "duels_won":
            return char.get("_bounty_duels_today", 0) >= target
        elif t == "boss_damage":
            return char.get("_bounty_boss_dmg_today", 0) >= target
        elif t == "loot_acquired":
            return char.get("_bounty_loot_today", 0) >= target
        elif t == "predictions_won":
            return char.get("_bounty_predictions_today", 0) >= target
        elif t == "heist_funded":
            return char.get("_bounty_heist_today", 0) >= target
        elif t == "espionage":
            return char.get("_bounty_espionage_today", 0) >= target
        return False

    @staticmethod
    def claim(state, uid, slot, now=None):
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        if slot < 0 or slot > 2:
            return {"error": "invalid slot"}
        bounties = BountyBoard.daily_bounties(uid, now)
        b = bounties[slot]
        claim_key = f"_bounty_claimed_{BountyBoard._today_seed(now)}_{slot}"
        if c.get(claim_key):
            return {"error": "already claimed"}
        if not BountyBoard._check_one(c, b):
            return {"error": "bounty not completed"}
        c["gold"] = c.get("gold", 0) + b["reward"]
        c[claim_key] = True
        state.mark_dirty(uid)
        return {"ok": True, "bounty": b["name"], "reward": b["reward"],
                "gold_left": c["gold"]}


# ============================================================
# PHI WHEEL — spin the wheel casino game
# ============================================================

class PhiWheel:
    """Casino wheel with phi-weighted segments. Costs gold to spin.
    Prizes scale by phi-power. Rare jackpots for lucky spins."""

    SPIN_COST = 200
    SEGMENTS = [
        {"label": "x0 (MISS)", "mult": 0, "weight": 30},
        {"label": "x1 (EVEN)", "mult": 1, "weight": 25},
        {"label": "xPHI", "mult": PHI, "weight": 20},
        {"label": "xPHI^2", "mult": PHI ** 2, "weight": 12},
        {"label": "xPHI^3", "mult": PHI ** 3, "weight": 8},
        {"label": "xPHI^4 (JACKPOT)", "mult": PHI ** 4, "weight": 3},
        {"label": "xPHI^5 (MEGA)", "mult": PHI ** 5, "weight": 1.5},
        {"label": "FREE SPIN", "mult": -1, "weight": 0.5},
    ]

    @staticmethod
    def spin(state, uid):
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        gold = int(c.get("gold", 0))
        if gold < PhiWheel.SPIN_COST:
            return {"error": "not enough gold", "have": gold, "need": PhiWheel.SPIN_COST}
        total_w = sum(s["weight"] for s in PhiWheel.SEGMENTS)
        r = random.random() * total_w
        cumulative = 0
        result = PhiWheel.SEGMENTS[0]
        for seg in PhiWheel.SEGMENTS:
            cumulative += seg["weight"]
            if r <= cumulative:
                result = seg
                break
        c["gold"] = gold - PhiWheel.SPIN_COST
        prize = 0
        free_spin = False
        if result["mult"] == -1:
            free_spin = True
        elif result["mult"] > 0:
            prize = int(PhiWheel.SPIN_COST * result["mult"])
            c["gold"] = c.get("gold", 0) + prize
        state.mark_dirty(uid)
        spins_today = c.get("_wheel_spins_today", 0) + 1
        c["_wheel_spins_today"] = spins_today
        return {
            "label": result["label"],
            "mult": result["mult"],
            "prize": prize,
            "free_spin": free_spin,
            "cost": PhiWheel.SPIN_COST if not free_spin else 0,
            "gold_left": c["gold"],
            "spins_today": spins_today,
        }


# ============================================================
# MARKET FRENZY — random volatility events
# ============================================================

class MarketFrenzy:
    """Random market frenzy periods. A random stock goes hyper-volatile:
    price swings by PHI^4 for 10 minutes. Traders who catch the wave
    get bonus gold."""

    FRENZY_INTERVAL = int(3600 * PHI * 3)  # ~4.8 hours
    FRENZY_DURATION = 600  # 10 minutes
    BONUS_POOL = 50000

    @staticmethod
    def status(now=None):
        t = now or int(time.time())
        EPOCH = 1700000000
        cycle = (t - EPOCH) // MarketFrenzy.FRENZY_INTERVAL
        rng = random.Random(cycle)
        stock_idx = rng.randint(0, 19)
        stock_name = ["ALPHA","BETA","GAMMA","DELTA","OMEGA","SIGMA","THETA",
                       "ZETA","PI","RHO","KAPPA","LAMBDA","MU","NU","XI",
                       "OMIKRON","CHI","PSI","PHI","TAU"][stock_idx]
        start = EPOCH + cycle * MarketFrenzy.FRENZY_INTERVAL
        elapsed = t - start
        active = elapsed < MarketFrenzy.FRENZY_DURATION
        remaining = max(0, MarketFrenzy.FRENZY_DURATION - elapsed) if active else 0
        next_in = max(0, (start + MarketFrenzy.FRENZY_INTERVAL) - t)
        return {
            "active": active,
            "stock": stock_name,
            "remaining": remaining,
            "next_in": next_in,
            "bonus_pool": MarketFrenzy.BONUS_POOL,
            "multiplier": PHI ** 4,
        }

    @staticmethod
    def apply_frenzy(state, now=None):
        f = MarketFrenzy.status(now)
        if not f["active"]:
            return
        for s in state.stocks:
            if s["name"] == f["stock"]:
                s["delta"] += (random.random() - 0.5) * f["multiplier"]
                s["volume"] = int(s["volume"] * PHI)
                break

    @staticmethod
    def claim_bonus(state, uid, now=None):
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        t = now or int(time.time())
        EPOCH = 1700000000
        cycle = (t - EPOCH) // MarketFrenzy.FRENZY_INTERVAL
        claim_key = f"_frenzy_claimed_{cycle}"
        if c.get(claim_key):
            return {"error": "already claimed"}
        trades = c.get("_frenzy_trades", 0)
        if trades <= 0:
            return {"error": "no frenzy trades"}
        bonus = int(MarketFrenzy.BONUS_POOL * (PHI ** min(trades - 1, 7)) / (PHI ** 7))
        bonus = min(bonus, MarketFrenzy.BONUS_POOL)
        c["gold"] = c.get("gold", 0) + bonus
        c[claim_key] = True
        c["_frenzy_trades"] = 0
        state.mark_dirty(uid)
        return {"ok": True, "bonus": bonus, "trades": trades, "gold_left": c["gold"]}


# ============================================================
# WHALE CHASE — track bot whales, predict their moves
# ============================================================

class WhaleChase:
    """Track the bot traders (whales). Predict which stock a whale will
    buy next. Correct prediction earns phi-scaled gold."""

    WHALE_NAMES = ["Leviathan", "Megalodon", "Kraken", "Hydra", "Chimera"]
    PREDICTION_COST = 300
    STOCKS = ["ALPHA","BETA","GAMMA","DELTA","OMEGA","SIGMA","THETA",
              "ZETA","PI","RHO","KAPPA","LAMBDA","MU","NU","XI",
              "OMIKRON","CHI","PSI","PHI","TAU"]

    @staticmethod
    def _whale_stock(whale_id, cycle):
        rng = random.Random(whale_id * 1000 + cycle)
        return rng.choice(WhaleChase.STOCKS)

    @staticmethod
    def status(state, uid, now=None):
        t = now or int(time.time())
        interval = int(3600 * PHI * 2)
        cycle = t // interval
        whales = []
        for i, name in enumerate(WhaleChase.WHALE_NAMES):
            target = WhaleChase._whale_stock(i, cycle)
            whales.append({"id": i, "name": name, "hint": target[0] + "???"})
        my_preds = state.chars.get(uid, {}).get("_whale_preds", {})
        return {
            "whales": whales,
            "prediction_cost": WhaleChase.PREDICTION_COST,
            "my_predictions": my_preds,
        }

    @staticmethod
    def predict(state, uid, whale_id, stock):
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        if whale_id < 0 or whale_id >= len(WhaleChase.WHALE_NAMES):
            return {"error": "invalid whale"}
        gold = int(c.get("gold", 0))
        if gold < WhaleChase.PREDICTION_COST:
            return {"error": "not enough gold", "have": gold, "need": WhaleChase.PREDICTION_COST}
        t = int(time.time())
        interval = int(3600 * PHI * 2)
        cycle = t // interval
        pred_key = f"{whale_id}_{cycle}"
        preds = c.get("_whale_preds", {})
        if pred_key in preds:
            return {"error": "already predicted this whale"}
        c["gold"] = gold - WhaleChase.PREDICTION_COST
        preds[pred_key] = stock.upper()
        c["_whale_preds"] = preds
        state.mark_dirty(uid)
        return {"ok": True, "whale": WhaleChase.WHALE_NAMES[whale_id],
                "predicted": stock.upper()}

    @staticmethod
    def settle(state, uid, now=None):
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        t = now or int(time.time())
        interval = int(3600 * PHI * 2)
        cycle = (t - 1) // interval
        preds = c.get("_whale_preds", {})
        results = []
        total_won = 0
        for i, name in enumerate(WhaleChase.WHALE_NAMES):
            pred_key = f"{i}_{cycle}"
            predicted = preds.pop(pred_key, None)
            if predicted is None:
                continue
            actual = WhaleChase._whale_stock(i, cycle)
            won = predicted == actual
            prize = 0
            if won:
                prize = int(WhaleChase.PREDICTION_COST * PHI ** 3)
                c["gold"] = c.get("gold", 0) + prize
                total_won += prize
            results.append({"whale": name, "predicted": predicted,
                            "actual": actual, "won": won, "prize": prize})
        c["_whale_preds"] = preds
        state.mark_dirty(uid)
        return {"results": results, "total_won": total_won, "gold_left": c.get("gold", 0)}


# ============================================================
# CORP TRIAL — weekly corp challenges
# ============================================================

class CorpTrial:
    """Weekly challenge for each corp. All members contribute toward
    a shared goal. If the corp completes it, everyone gets a phi-reward."""

    TRIALS = [
        {"name": "Торговый марафон", "name_en": "Trading Marathon",
         "desc": "Corp trades 50 times", "type": "trades", "target": 50},
        {"name": "Золотой штурм", "name_en": "Golden Assault",
         "desc": "Earn 1M gold collectively", "type": "gold_earned", "target": 1000000},
        {"name": "Охота на боссов", "name_en": "Boss Hunt",
         "desc": "Deal 5M total boss damage", "type": "boss_damage", "target": 5000000},
        {"name": "Финансовый хаос", "name_en": "Financial Chaos",
         "desc": "Execute 20 short positions", "type": "shorts", "target": 20},
        {"name": "Шпионская сеть", "name_en": "Spy Network",
         "desc": "Perform 10 espionage actions", "type": "espionage", "target": 10},
        {"name": "Казино-ночь", "name_en": "Casino Night",
         "desc": "Spin Phi Wheel 30 times", "type": "wheel_spins", "target": 30},
    ]
    REWARD_POOL = 500000

    @staticmethod
    def _week_seed(now=None):
        t = now or int(time.time())
        EPOCH = 1700000000
        return (t - EPOCH) // (86400 * 7)

    @staticmethod
    def current_trial(corp_id, now=None):
        seed = CorpTrial._week_seed(now) + corp_id * 3
        rng = random.Random(seed)
        return rng.choice(CorpTrial.TRIALS)

    @staticmethod
    def status(state, corp_id, uid, now=None):
        c = state.chars.get(uid, {})
        trial = CorpTrial.current_trial(corp_id, now)
        corp_progress = 0
        for ch in state.chars.values():
            if ch.get("corp_id") == corp_id:
                corp_progress += ch.get(f"_trial_{trial['type']}", 0)
        completed = corp_progress >= trial["target"]
        claim_key = f"_trial_claimed_{CorpTrial._week_seed(now)}_{corp_id}"
        my_claimed = c.get(claim_key, False)
        return {
            "trial": trial["name"], "trial_en": trial["name_en"],
            "desc": trial["desc"],
            "progress": corp_progress, "target": trial["target"],
            "pct": round(corp_progress / max(trial["target"], 1) * 100, 1),
            "completed": completed, "reward": CorpTrial.REWARD_POOL,
            "my_claimed": my_claimed,
        }

    @staticmethod
    def claim(state, uid, now=None):
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        corp_id = c.get("corp_id", 0)
        trial = CorpTrial.current_trial(corp_id, now)
        claim_key = f"_trial_claimed_{CorpTrial._week_seed(now)}_{corp_id}"
        if c.get(claim_key):
            return {"error": "already claimed"}
        corp_progress = 0
        for ch in state.chars.values():
            if ch.get("corp_id") == corp_id:
                corp_progress += ch.get(f"_trial_{trial['type']}", 0)
        if corp_progress < trial["target"]:
            return {"error": "trial not completed", "progress": corp_progress,
                    "target": trial["target"]}
        corp_members = [ch for ch in state.chars.values() if ch.get("corp_id") == corp_id]
        n = max(len(corp_members), 1)
        share = int(CorpTrial.REWARD_POOL / (n * PHI))
        c["gold"] = c.get("gold", 0) + share
        c[claim_key] = True
        state.mark_dirty(uid)
        return {"ok": True, "trial": trial["name"], "share": share,
                "members": n, "gold_left": c["gold"]}


# ============================================================
# PHI CASINO — blackjack with phi-betting
# ============================================================

class PhiCasino:
    """Blackjack card game. Player competes against dealer (phi-bot).
    Cards are standard 2-11. Ace=11 or 1. Dealer stands on 17+.
    Payout: win = 2x bet, blackjack (21 on first 2) = PHI * bet."""

    BET_MIN = 100
    BET_MAX = 50000

    @staticmethod
    def _deal_card(rng):
        """Deal a card 2-11. Face cards = 10, Ace = 11."""
        card = rng.randint(2, 14)
        if card >= 12:
            card = 10
        elif card == 14:
            card = 11
        return card

    @staticmethod
    def _hand_value(hand):
        """Calculate best hand value (handles aces)."""
        total = sum(hand)
        aces = hand.count(11)
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        return total

    @staticmethod
    def play(state, uid, bet, action="deal", player_hand=None, dealer_hand=None):
        """Play a blackjack hand.
        action: 'deal' (new hand), 'hit' (take card), 'stand' (finish).
        Returns game state."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        bet = max(PhiCasino.BET_MIN, min(bet, PhiCasino.BET_MAX))
        gold = int(c.get("gold", 0))

        if action == "deal":
            if gold < bet:
                return {"error": "not enough gold", "have": gold, "need": bet}
            rng = random.Random(int(time.time() * PHI) + uid)
            p_hand = [PhiCasino._deal_card(rng), PhiCasino._deal_card(rng)]
            d_hand = [PhiCasino._deal_card(rng), PhiCasino._deal_card(rng)]
            c["gold"] = gold - bet
            state.mark_dirty(uid)
            p_val = PhiCasino._hand_value(p_hand)
            d_val = PhiCasino._hand_value(d_hand)
            # auto-win on blackjack
            if p_val == 21:
                prize = int(bet * PHI)
                c["gold"] = c.get("gold", 0) + prize
                state.mark_dirty(uid)
                return {"player": p_hand, "dealer": d_hand,
                        "player_val": p_val, "dealer_val": d_val,
                        "result": "blackjack", "prize": prize,
                        "gold_left": c["gold"]}
            return {"player": p_hand, "dealer": d_hand,
                    "player_val": p_val, "dealer_val": d_hand[0],
                    "dealer_hidden": d_hand[1], "bet": bet,
                    "gold_left": c["gold"]}

        elif action == "hit":
            if not player_hand or not dealer_hand:
                return {"error": "no active hand"}
            rng = random.Random(int(time.time() * PHI * 2) + uid)
            p_hand = list(player_hand) + [PhiCasino._deal_card(rng)]
            p_val = PhiCasino._hand_value(p_hand)
            if p_val > 21:
                return {"player": p_hand, "dealer": dealer_hand,
                        "player_val": p_val, "result": "bust", "prize": 0,
                        "gold_left": c.get("gold", 0)}
            return {"player": p_hand, "dealer": dealer_hand,
                    "player_val": p_val, "dealer_val": dealer_hand[0],
                    "bet": bet}

        elif action == "stand":
            if not player_hand or not dealer_hand:
                return {"error": "no active hand"}
            rng = random.Random(int(time.time() * PHI * 3) + uid)
            d_hand = list(dealer_hand)
            while PhiCasino._hand_value(d_hand) < 17:
                d_hand.append(PhiCasino._deal_card(rng))
            p_val = PhiCasino._hand_value(player_hand)
            d_val = PhiCasino._hand_value(d_hand)
            if d_val > 21 or p_val > d_val:
                prize = bet * 2
            elif p_val == d_val:
                prize = bet  # push
            else:
                prize = 0
            c["gold"] = c.get("gold", 0) + prize
            state.mark_dirty(uid)
            result = "win" if prize >= bet * 2 else ("push" if prize == bet else "lose")
            return {"player": player_hand, "dealer": d_hand,
                    "player_val": p_val, "dealer_val": d_val,
                    "result": result, "prize": prize,
                    "gold_left": c["gold"]}
        return {"error": "invalid action"}


# ============================================================
# MARKET ORACLE — AI prediction system
# ============================================================

class MarketOracle:
    """The Oracle makes predictions about market direction.
    Players can follow or fade the Oracle's calls.
    Oracle accuracy tracked over time. Accurate oracles earn followers gold."""

    PREDICTION_COST = 250
    TEMPLATES = [
        {"call": "up", "text": "Зелёный луч пронзает тьму — ставь на рост"},
        {"call": "down", "text": "Красная тень нависает — ставь на падение"},
        {"call": "volatile", "text": "Фи-шторм предвидится — волатильность взлетит"},
        {"call": "calm", "text": "Золотое затишье — рынок уснет на часы"},
    ]

    @staticmethod
    def _oracle_seed(now=None):
        t = now or int(time.time())
        EPOCH = 1700000000
        return (t - EPOCH) // int(3600 * PHI * 1.5)  # new prediction ~2.4h

    @staticmethod
    def status(state, uid, now=None):
        t = now or int(time.time())
        seed = MarketOracle._oracle_seed(t)
        rng = random.Random(seed)
        oracle = rng.choice(MarketOracle.TEMPLATES)
        stock_idx = rng.randint(0, 19)
        stock = ["ALPHA","BETA","GAMMA","DELTA","OMEGA","SIGMA","THETA",
                 "ZETA","PI","RHO","KAPPA","LAMBDA","MU","NU","XI",
                 "OMIKRON","CHI","PSI","PHI","TAU"][stock_idx]
        # accuracy
        c = state.chars.get(uid, {})
        history = c.get("_oracle_history", [])
        wins = sum(1 for h in history if h.get("won"))
        total = len(history)
        return {
            "oracle_text": oracle["text"],
            "call": oracle["call"],
            "stock": stock,
            "accuracy": round(wins / total * 100, 1) if total > 0 else 0,
            "history_len": total,
            "cost": MarketOracle.PREDICTION_COST,
        }

    @staticmethod
    def follow(state, uid, stock_override=None, now=None):
        """Follow the Oracle's prediction. Costs gold, pays on correct."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        t = now or int(time.time())
        seed = MarketOracle._oracle_seed(t)
        rng = random.Random(seed)
        oracle = rng.choice(MarketOracle.TEMPLATES)
        default_stock = ["ALPHA","BETA","GAMMA","DELTA","OMEGA","SIGMA","THETA",
                         "ZETA","PI","RHO","KAPPA","LAMBDA","MU","NU","XI",
                         "OMIKRON","CHI","PSI","PHI","TAU"][rng.randint(0, 19)]
        stock = stock_override or default_stock

        gold = int(c.get("gold", 0))
        if gold < MarketOracle.PREDICTION_COST:
            return {"error": "not enough gold"}
        c["gold"] = gold - MarketOracle.PREDICTION_COST
        c.setdefault("_oracle_pending", []).append({
            "seed": seed, "stock": stock, "call": oracle["call"],
            "expires": t + int(3600 * PHI),
        })
        state.mark_dirty(uid)
        return {"ok": True, "oracle": oracle["text"], "stock": stock,
                "call": oracle["call"], "cost": MarketOracle.PREDICTION_COST}

    @staticmethod
    def settle(state, uid, now=None):
        """Check pending oracle predictions."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        t = now or int(time.time())
        pending = c.get("_oracle_pending", [])
        results = []
        remaining = []
        for pred in pending:
            if t > pred.get("expires", 0):
                # check: did the oracle predict correctly?
                # "up" -> stock delta > 0 at seed end, "down" -> delta < 0
                rng = random.Random(pred["seed"] + 1000)
                correct = rng.random() > 0.4  # oracle is 60% accurate
                won = correct if pred["call"] in ("up", "down") else (rng.random() > 0.5)
                prize = 0
                if won:
                    prize = int(MarketOracle.PREDICTION_COST * PHI ** 2)
                    c["gold"] = c.get("gold", 0) + prize
                results.append({
                    "stock": pred["stock"], "call": pred["call"],
                    "won": won, "prize": prize,
                })
                hist = c.get("_oracle_history", [])
                hist.append({"won": won})
                c["_oracle_history"] = hist[-30:]
            else:
                remaining.append(pred)
        c["_oracle_pending"] = remaining
        state.mark_dirty(uid)
        return {"results": results, "gold_left": c.get("gold", 0)}


# ============================================================
# PHI ARENA RANKINGS — seasonal PvP ladder
# ============================================================

class PhiArenaRankings:
    """Competitive PvP ladder. Players climb tiers by winning duels.
    Tiers: Bronze -> Silver -> Gold -> Platinum -> Diamond -> PHImaster.
    Seasonal reset with top rewards."""

    TIERS = [
        {"name": "Bronze", "name_ru": "Бронза", "min_elo": 0, "reward": 5000},
        {"name": "Silver", "name_ru": "Серебро", "min_elo": 100, "reward": 15000},
        {"name": "Gold", "name_ru": "Золото", "min_elo": 250, "reward": 40000},
        {"name": "Platinum", "name_ru": "Платина", "min_elo": 500, "reward": 100000},
        {"name": "Diamond", "name_ru": "Бриллиант", "min_elo": 800, "reward": 250000},
        {"name": "PHImaster", "name_ru": "ФИ-Мастер", "min_elo": 1200, "reward": 1000000},
    ]

    @staticmethod
    def status(state, uid, now=None):
        c = state.chars.get(uid, {})
        elo = c.get("_arena_elo", 0)
        wins = c.get("_arena_wins", 0)
        losses = c.get("_arena_losses", 0)
        streak = c.get("_arena_streak", 0)
        # determine tier
        tier = PhiArenaRankings.TIERS[0]
        for t in PhiArenaRankings.TIERS:
            if elo >= t["min_elo"]:
                tier = t
        # leaderboard
        lb = []
        for ch in state.chars.values():
            if ch.get("_arena_elo", 0) > 0:
                lb.append({"uid": ch.get("user_id", 0),
                           "elo": ch.get("_arena_elo", 0),
                           "wins": ch.get("_arena_wins", 0)})
        lb.sort(key=lambda x: x["elo"], reverse=True)
        my_rank = next((i + 1 for i, e in enumerate(lb) if e["uid"] == uid), len(lb) + 1)
        return {
            "elo": elo, "wins": wins, "losses": losses, "streak": streak,
            "tier": tier["name"], "tier_ru": tier["name_ru"],
            "tier_reward": tier["reward"],
            "next_tier": next((t["name"] for t in PhiArenaRankings.TIERS if t["min_elo"] > elo), None),
            "rank": my_rank,
            "leaderboard": lb[:10],
        }

    @staticmethod
    def record_match(state, uid, won, now=None):
        """Record a duel result in the arena ranking."""
        c = state.chars.get(uid)
        if not c:
            return
        elo = c.get("_arena_elo", 0)
        wins = c.get("_arena_wins", 0)
        losses = c.get("_arena_losses", 0)
        streak = c.get("_arena_streak", 0)
        if won:
            gains = int(PHI * 20 * (1 + streak * 0.1))
            elo += gains
            wins += 1
            streak += 1
        else:
            losses += 1
            elo = max(0, elo - int(15 / PHI))
            streak = 0
        c["_arena_elo"] = elo
        c["_arena_wins"] = wins
        c["_arena_losses"] = losses
        c["_arena_streak"] = streak

    @staticmethod
    def claim_season_reward(state, uid, now=None):
        """Claim end-of-season arena reward."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        elo = c.get("_arena_elo", 0)
        claim_key = f"_arena_reward_{current_season()[0]}"
        if c.get(claim_key):
            return {"error": "already claimed"}
        tier = PhiArenaRankings.TIERS[0]
        for t in PhiArenaRankings.TIERS:
            if elo >= t["min_elo"]:
                tier = t
        # bonus for top 10
        bonus = 0
        lb = sorted(state.chars.values(), key=lambda x: x.get("_arena_elo", 0), reverse=True)
        for i, ch in enumerate(lb[:10]):
            if ch.get("user_id") == uid:
                bonus = int(tier["reward"] * PHI ** (10 - i) / PHI ** 10)
                break
        prize = tier["reward"] + bonus
        c["gold"] = c.get("gold", 0) + prize
        c[claim_key] = True
        state.mark_dirty(uid)
        return {"ok": True, "tier": tier["name"], "prize": prize,
                "gold_left": c["gold"]}


# ============================================================
# CRASH INSURANCE — hedge against flash crashes
# ============================================================

class CrashInsurance:
    """Players buy insurance against flash crashes. If a crash happens
    while insured, they receive a payout proportional to their net worth.
    Insurance lasts 24 hours. Cost = net_worth / PHI^5."""

    DURATION = 86400  # 24 hours

    @staticmethod
    def status(state, uid, now=None):
        t = now or int(time.time())
        c = state.chars.get(uid, {})
        insured_until = c.get("_insurance_until", 0)
        insured = t < insured_until
        nw = c.get("net_worth", 0)
        cost = max(100, int(nw / PHI ** 5)) if nw > 0 else 100
        return {
            "insured": insured,
            "remaining": max(0, insured_until - t),
            "cost": cost,
            "payout_if_crash": int(nw / PHI),
        }

    @staticmethod
    def buy(state, uid, now=None):
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        t = now or int(time.time())
        if t < c.get("_insurance_until", 0):
            return {"error": "already insured"}
        nw = c.get("net_worth", 0)
        cost = max(100, int(nw / PHI ** 5)) if nw > 0 else 100
        gold = int(c.get("gold", 0))
        if gold < cost:
            return {"error": "not enough gold", "have": gold, "need": cost}
        c["gold"] = gold - cost
        c["_insurance_until"] = t + CrashInsurance.DURATION
        state.mark_dirty(uid)
        return {"ok": True, "cost": cost, "expires_in": CrashInsurance.DURATION,
                "gold_left": c["gold"]}

    @staticmethod
    def payout(state, uid, now=None):
        """Called after a flash crash to pay insured players."""
        c = state.chars.get(uid)
        if not c:
            return 0
        t = now or int(time.time())
        if t >= c.get("_insurance_until", 0):
            return 0
        nw = c.get("net_worth", 0)
        payout = int(nw / PHI)
        c["gold"] = c.get("gold", 0) + payout
        state.mark_dirty(uid)
        return payout


# ============================================================
# PHI ARTIFACTS — collectible sets with bonuses
# ============================================================

class PhiArtifacts:
    """Collectible artifact sets. Each set has 3 artifacts. Collecting
    the full set grants a permanent bonus multiplier."""

    SETS = [
        {"name": "Golden Triad", "name_ru": "Золотая Триада",
         "artifacts": ["Golden Eye", "Golden Hand", "Golden Heart"],
         "bonus": "gold_mult", "bonus_val": PHI,
         "desc": "+PHI% gold from all sources"},
        {"name": "Phi Trinity", "name_ru": "ФИ-Троица",
         "artifacts": ["Phi Shard", "Phi Crystal", "Phi Core"],
         "bonus": "trade_mult", "bonus_val": PHI ** 0.5,
         "desc": "+sqrt(PHI)% trade profits"},
        {"name": "Void Set", "name_ru": "Пустота",
         "artifacts": ["Void Mask", "Void Cloak", "Void Blade"],
         "bonus": "duel_power", "bonus_val": PHI * 10,
         "desc": "+PHI*10 duel power"},
        {"name": "Crown Collection", "name_ru": "Корона",
         "artifacts": ["PHI_CROWN", "TRADER_CROWN", "Philosopher Stone"],
         "bonus": "prestige_mult", "bonus_val": PHI ** 2,
         "desc": "+PHI^2 prestige points"},
        {"name": "Market Masters", "name_ru": "Мастера Рынка",
         "artifacts": ["Bull Token", "Bear Token", "Crash Token"],
         "bonus": "hedge_bonus", "bonus_val": PHI,
         "desc": "+PHI% hedge fund returns"},
    ]

    @staticmethod
    def get_sets(state, uid):
        c = state.chars.get(uid, {})
        loot = c.get("loot", [])
        artifact_codes = [l.get("code", -1) for l in loot if l.get("cat") == 10 or l.get("rarity", 0) >= 5]
        result = []
        for s in PhiArtifacts.SETS:
            owned = [a for a in s["artifacts"] if a in artifact_codes]
            complete = len(owned) == len(s["artifacts"])
            result.append({
                "name": s["name"], "name_ru": s["name_ru"],
                "artifacts": s["artifacts"], "owned": len(owned),
                "complete": complete,
                "bonus": s["bonus"], "desc": s["desc"],
            })
        return result

    @staticmethod
    def get_total_bonuses(state, uid):
        """Calculate total artifact set bonuses."""
        sets = PhiArtifacts.get_sets(state, uid)
        bonuses = {}
        for s in sets:
            if s["complete"]:
                b = s["bonus"]
                bonuses[b] = bonuses.get(b, 0) + PhiArtifacts._bonus_value(s["bonus"])
        return bonuses

    @staticmethod
    def _bonus_value(bonus_type):
        for s in PhiArtifacts.SETS:
            if s["bonus"] == bonus_type:
                return s["bonus_val"]
        return 1.0


# ============================================================
# MARKET INSIDER — anonymous tip system
# ============================================================

class MarketInsider:
    """Anonymous tips about market moves. Players read a tip, decide
    to bet on it or fade it. Correct bets earn phi-rewards.
    Tips generated from actual market patterns."""

    TIP_COST = 150
    TIPS = [
        {"id": 0, "text": "Инсайд: АНОНИМНЫЙисточник сообщает о слиянии TECH-сектора", "stock_sector": 0, "direction": "up"},
        {"id": 1, "text": "Слито: Гигант FINANCE терпит убытки", "stock_sector": 1, "direction": "down"},
        {"id": 2, "text": "Течь: ENERGY найдет новое месторождение", "stock_sector": 2, "direction": "up"},
        {"id": 3, "text": "Слух: LUXURY теряет эксклюзивность", "stock_sector": 3, "direction": "down"},
        {"id": 4, "text": "Анонимка: Роботы скупают TECH-акции", "stock_sector": 0, "direction": "up"},
        {"id": 5, "text": "Записка: FINANCE перед收购ом", "stock_sector": 1, "direction": "up"},
        {"id": 6, "text": "Сообщение: ENERGY кризис в Азии", "stock_sector": 2, "direction": "down"},
        {"id": 7, "text": "Письмо: LUXURY запускает PHI-линейку", "stock_sector": 3, "direction": "up"},
    ]

    @staticmethod
    def _current_tip(now=None):
        t = now or int(time.time())
        EPOCH = 1700000000
        idx = (t - EPOCH) // int(3600 * PHI)  # new tip every ~1.6h
        rng = random.Random(idx)
        tip = dict(rng.choice(MarketInsider.TIPS))
        tip["stock"] = ["ALPHA","BETA","GAMMA","DELTA"][tip["stock_sector"] % 4]
        return tip

    @staticmethod
    def status(state, uid, now=None):
        tip = MarketInsider._current_tip(now)
        c = state.chars.get(uid, {})
        bets = c.get("_insider_bets", {})
        my_bet = bets.get(str(tip["id"]))
        history = c.get("_insider_history", [])
        wins = sum(1 for h in history if h.get("won"))
        return {
            "tip_text": tip["text"],
            "tip_stock": tip["stock"],
            "cost": MarketInsider.TIP_COST,
            "my_bet": my_bet,
            "accuracy": round(wins / len(history) * 100, 1) if history else 0,
            "history_len": len(history),
        }

    @staticmethod
    def bet(state, uid, side, now=None):
        """side: 'follow' (bet with tip) or 'fade' (bet against tip)"""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        t = now or int(time.time())
        tip = MarketInsider._current_tip(t)
        bets = c.get("_insider_bets", {})
        if str(tip["id"]) in bets:
            return {"error": "already bet on this tip"}
        gold = int(c.get("gold", 0))
        if gold < MarketInsider.TIP_COST:
            return {"error": "not enough gold"}
        if side not in ("follow", "fade"):
            return {"error": "side must be 'follow' or 'fade'"}
        c["gold"] = gold - MarketInsider.TIP_COST
        bets[str(tip["id"])] = {"side": side, "tip": tip}
        c["_insider_bets"] = bets
        state.mark_dirty(uid)
        return {"ok": True, "side": side, "stock": tip["stock"],
                "cost": MarketInsider.TIP_COST}

    @staticmethod
    def settle(state, uid, now=None):
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        bets = c.get("_insider_bets", {})
        t = now or int(time.time())
        EPOCH = 1700000000
        current_idx = (t - EPOCH) // int(3600 * PHI)
        results = []
        remaining = {}
        for tip_id_str, bet in bets.items():
            tip_idx = int(tip_id_str)
            if tip_idx < current_idx:
                # expired — resolve
                rng = random.Random(tip_idx)
                tip = rng.choice(MarketInsider.TIPS)
                # was the tip correct?
                tip_correct = rng.random() > 0.35  # 65% accurate
                player_correct = (bet["side"] == "follow" and tip_correct) or \
                                 (bet["side"] == "fade" and not tip_correct)
                prize = 0
                if player_correct:
                    prize = int(MarketInsider.TIP_COST * PHI * 2)
                    c["gold"] = c.get("gold", 0) + prize
                results.append({
                    "tip_id": tip_id_str, "side": bet["side"],
                    "won": player_correct, "prize": prize,
                })
                hist = c.get("_insider_history", [])
                hist.append({"won": player_correct})
                c["_insider_history"] = hist[-30:]
            else:
                remaining[tip_id_str] = bet
        c["_insider_bets"] = remaining
        state.mark_dirty(uid)
        return {"results": results, "gold_left": c.get("gold", 0)}


# ============================================================
# PHI CANDLE BET — buy position under candle close, always return
# ============================================================

class PhiCandleBet:
    """Свечковая ставка. Игрок ставит на закрытие дневной свечи.
    Можно вернуть ставку в любой момент (велосипед — едешь и возвращаешься).
    Минимальный выигрыш guaranteed: вернёшь至少 ставку + phi-бонус.
    Определение свечи детерминировано по seed дня.

    Direction: 'green' (close > open) or 'red' (close < open).
    Sector stock chosen from player's home sector (uid % 4)."""

    MIN_BET = 50
    MAX_BET = 100000
    RETURN_FEE_PCT = 0.10  # 10% fee on early return (自行车 tax)

    @staticmethod
    def _day_seed(now=None):
        t = now or int(time.time())
        DAY = 86400
        return t // DAY

    @staticmethod
    def _candle_result(seed, stock_idx):
        """Deterministic candle result for given day+stock."""
        rng = random.Random(seed * 1000 + stock_idx)
        open_p = rng.randint(100, 5000)
        # candle delta: up or down by phi-weighted amount
        delta_pct = rng.uniform(-0.15 * PHI, 0.12 * PHI)
        close_p = int(open_p * (1 + delta_pct))
        direction = "green" if close_p >= open_p else "red"
        return {"open": open_p, "close": close_p, "direction": direction,
                "delta_pct": round(delta_pct * 100, 2)}

    @staticmethod
    def day_info(state, now=None):
        """Get today's candle preview (open known, close predicted)."""
        seed = PhiCandleBet._day_seed(now)
        result = PhiCandleBet._candle_result(seed, 0)
        sectors_info = []
        for sec_idx in range(4):
            cr = PhiCandleBet._candle_result(seed, sec_idx)
            sectors_info.append({
                "sector": SECTORS[sec_idx]["name"],
                "emoji": SECTORS[sec_idx]["emoji"],
                "open": cr["open"], "direction": cr["direction"],
                "delta_pct": cr["delta_pct"],
            })
        return {"day_seed": seed, "main_candle": result, "sectors": sectors_info}

    @staticmethod
    def status(state, uid, now=None):
        c = state.chars.get(uid, {})
        seed = PhiCandleBet._day_seed(now)
        sector_idx = uid % 4
        cr = PhiCandleBet._candle_result(seed, sector_idx)
        bet_data = c.get("_candle_bet", {})
        active = bet_data.get("day_seed") == seed
        bet = bet_data.get("bet", 0) if active else 0
        direction = bet_data.get("direction", "") if active else ""
        returned = bet_data.get("returned", False)
        return {
            "active": active and not returned,
            "bet": bet,
            "direction": direction,
            "sector": SECTORS[sector_idx]["name"],
            "candle_direction": cr["direction"],
            "candle_delta_pct": cr["delta_pct"],
            "day_seed": seed,
            "returned": returned,
            "min_bet": PhiCandleBet.MIN_BET,
            "max_bet": PhiCandleBet.MAX_BET,
        }

    @staticmethod
    def buy(state, uid, bet, direction, now=None):
        """Buy a candle bet. direction='green' or 'red'."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        seed = PhiCandleBet._day_seed(now)
        # check if already active today
        existing = c.get("_candle_bet", {})
        if existing.get("day_seed") == seed and not existing.get("returned", True):
            return {"error": "already bet today"}
        bet = max(PhiCandleBet.MIN_BET, min(bet, PhiCandleBet.MAX_BET))
        if direction not in ("green", "red"):
            return {"error": "direction must be green or red"}
        gold = int(c.get("gold", 0))
        if gold < bet:
            return {"error": "not enough gold", "have": gold, "need": bet}
        c["gold"] = gold - bet
        c["_candle_bet"] = {
            "day_seed": seed, "bet": bet, "direction": direction,
            "bought_at": now or int(time.time()),
            "returned": False, "settled": False,
        }
        state.mark_dirty(uid)
        return {"ok": True, "bet": bet, "direction": direction,
                "gold_left": c["gold"]}

    @staticmethod
    def return_bet(state, uid, now=None):
        """Return (cancel) a candle bet before settlement. You lose RETURN_FEE_PCT."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        seed = PhiCandleBet._day_seed(now)
        bet_data = c.get("_candle_bet", {})
        if bet_data.get("day_seed") != seed:
            return {"error": "no active bet today"}
        if bet_data.get("returned") or bet_data.get("settled"):
            return {"error": "already returned/settled"}
        bet = bet_data["bet"]
        fee = int(bet * PhiCandleBet.RETURN_FEE_PCT)
        refund = bet - fee
        c["gold"] = c.get("gold", 0) + refund
        c["_candle_bet"]["returned"] = True
        state.mark_dirty(uid)
        return {"ok": True, "bet": bet, "fee": fee, "refund": refund,
                "gold_left": c["gold"]}

    @staticmethod
    def settle(state, uid, now=None):
        """Settle at end of day. If player guessed correctly → big win.
        If wrong → still get minimum return (bicycle principle: always win something)."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        seed = PhiCandleBet._day_seed(now)
        bet_data = c.get("_candle_bet", {})
        if bet_data.get("day_seed") != seed:
            return {"error": "no bet today"}
        if bet_data.get("settled"):
            return {"error": "already settled"}
        bet = bet_data["bet"]
        direction = bet_data["direction"]
        sector_idx = uid % 4
        cr = PhiCandleBet._candle_result(seed, sector_idx)
        correct = direction == cr["direction"]

        if correct:
            # correct guess: win PHI * bet * delta
            prize = int(bet * PHI * (1 + abs(cr["delta_pct"]) / 100))
        else:
            # wrong guess: guaranteed minimum return (bicycle principle)
            prize = int(bet * (1 + 1 / PHI))  # always get back bet + ~61.8%

        c["gold"] = c.get("gold", 0) + prize
        c["_candle_bet"]["settled"] = True
        state.mark_dirty(uid)
        return {"ok": True, "correct": correct, "direction": direction,
                "candle": cr["direction"], "delta_pct": cr["delta_pct"],
                "bet": bet, "prize": prize,
                "won": prize >= bet,
                "gold_left": c["gold"]}


# ============================================================
# CANDLE SHOP — daily pre-selected items aligned with candle
# ============================================================

class CandleShop:
    """Daily магазин под свечку. На старте дня генерируются предметы
    под сектор свечки. Предметы продаются по спец-ценам.
    Если купил предмет не из своего сектора — можно обменять.
    Всё детерминировано по seed дня."""

    ITEMS_PER_DAY = 6

    # item templates per sector
    TEMPLATES = {
        "TECH": [
            {"name": "Нейро-процессор", "name_en": "Neuro CPU", "base": 2000, "emoji": "🧠"},
            {"name": "Квантовый чип", "name_en": "Quantum Chip", "base": 5000, "emoji": "💎"},
            {"name": "Фрактальный код", "name_en": "Fractal Code", "base": 1200, "emoji": "🔮"},
            {"name": "ФИ-сервер", "name_en": "PHI Server", "base": 8000, "emoji": "🖥"},
            {"name": "Кибер-имплант", "name_en": "Cyber Implant", "base": 3500, "emoji": "⚡"},
            {"name": "Дрон-разведчик", "name_en": "Scout Drone", "base": 1500, "emoji": "🛸"},
        ],
        "FINANCE": [
            {"name": "Золотой слиток", "name_en": "Gold Bar", "base": 3000, "emoji": "🏅"},
            {"name": "Облигация PHI", "name_en": "PHI Bond", "base": 1500, "emoji": "📜"},
            {"name": "Акция кита", "name_en": "Whale Share", "base": 6000, "emoji": "🐋"},
            {"name": "Дериватив-щит", "name_en": "Derivative Shield", "base": 4000, "emoji": "🛡"},
            {"name": "Фонд ФИ", "name_en": "PHI Fund", "base": 10000, "emoji": "💰"},
            {"name": "Биржевой терминал", "name_en": "Trading Terminal", "base": 2000, "emoji": "📊"},
        ],
        "ENERGY": [
            {"name": "ФИ-батарея", "name_en": "PHI Battery", "base": 2500, "emoji": "🔋"},
            {"name": "Плазменный генератор", "name_en": "Plasma Gen", "base": 7000, "emoji": "⚡"},
            {"name": "Энерго-щит", "name_en": "Energy Shield", "base": 3000, "emoji": "🛡"},
            {"name": "Реактор", "name_en": "Reactor", "base": 9000, "emoji": "☢"},
            {"name": "Солнечный панель", "name_en": "Solar Panel", "base": 1800, "emoji": "☀"},
            {"name": "ФИ-конденсатор", "name_en": "PHI Capacitor", "base": 4500, "emoji": "🔌"},
        ],
        "LUXURY": [
            {"name": "Диадема ФИ", "name_en": "PHI Crown", "base": 5000, "emoji": "👑"},
            {"name": "Бриллиантовый ключ", "name_en": "Diamond Key", "base": 8000, "emoji": "💎"},
            {"name": "Элитный костюм", "name_en": "Elite Suit", "base": 3000, "emoji": "👔"},
            {"name": "Золотые часы", "name_en": "Golden Watch", "base": 4000, "emoji": "⌚"},
            {"name": "ФИ-кулон", "name_en": "PHI Pendant", "base": 2000, "emoji": "📿"},
            {"name": "Фрактальная ваза", "name_en": "Fractal Vase", "base": 6000, "emoji": "🏺"},
        ],
    }

    @staticmethod
    def _day_items(seed, sector_name, now=None):
        """Generate 6 items for today's shop aligned with sector."""
        rng = random.Random(seed * 31 + hash(sector_name) % 10000)
        templates = CandleShop.TEMPLATES.get(sector_name, CandleShop.TEMPLATES["TECH"])
        chosen = rng.sample(templates, min(CandleShop.ITEMS_PER_DAY, len(templates)))
        items = []
        for i, t in enumerate(chosen):
            # price variance: +/- PHI^0.5 around base
            variance = 1 + rng.uniform(-1 / PHI, 1 / PHI) * 0.3
            price = int(t["base"] * variance)
            # discount for wrong-sector items: 30% off if not player's home sector
            items.append({
                "idx": i,
                "name": t["name"],
                "name_en": t["name_en"],
                "price": price,
                "emoji": t["emoji"],
                "sector": sector_name,
            })
        return items

    @staticmethod
    def status(state, uid, now=None):
        seed = PhiCandleBet._day_seed(now)
        sector_idx = uid % 4
        sector_name = SECTORS[sector_idx]["name"]
        items = CandleShop._day_items(seed, sector_name, now)
        c = state.chars.get(uid, {})
        purchased = c.get("_candle_shop_bought", [])
        purchased_today = [p for p in purchased if p.get("day_seed") == seed]
        return {
            "sector": sector_name,
            "items": items,
            "purchased_today": purchased_today,
            "day_seed": seed,
        }

    @staticmethod
    def buy_item(state, uid, item_idx, now=None):
        """Buy an item from today's candle shop."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        seed = PhiCandleBet._day_seed(now)
        sector_idx = uid % 4
        sector_name = SECTORS[sector_idx]["name"]
        items = CandleShop._day_items(seed, sector_name, now)
        if item_idx < 0 or item_idx >= len(items):
            return {"error": "invalid item index"}
        item = items[item_idx]
        gold = int(c.get("gold", 0))
        if gold < item["price"]:
            return {"error": "not enough gold", "have": gold, "need": item["price"]}
        c["gold"] = gold - item["price"]
        c.setdefault("_candle_shop_bought", []).append({
            "day_seed": seed, "item": item, "bought_at": now or int(time.time()),
        })
        state.mark_dirty(uid)
        return {"ok": True, "item": item, "gold_left": c["gold"]}

    @staticmethod
    def exchange_item(state, uid, item_idx, now=None):
        """Exchange a previously purchased item if it's wrong sector.
        Player always gets back a percentage (bicycle principle)."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        seed = PhiCandleBet._day_seed(now)
        purchased = c.get("_candle_shop_bought", [])
        # find today's purchase at this index
        today_bought = [p for p in purchased if p.get("day_seed") == seed]
        if item_idx < 0 or item_idx >= len(today_bought):
            return {"error": "invalid item index"}
        bought = today_bought[item_idx]
        item = bought["item"]
        # exchange: return item and get back PHI-adjusted price
        refund = int(item["price"] * (1 + 1 / PHI))
        c["gold"] = c.get("gold", 0) + refund
        # remove the item
        purchased.remove(bought)
        c["_candle_shop_bought"] = purchased
        state.mark_dirty(uid)
        return {"ok": True, "item": item, "refund": refund,
                "gold_left": c["gold"]}


# ============================================================
# CANDLE SETTLEMENT — end-of-day ledger + gifts
# ============================================================

class CandleSettlement:
    """Сальдовая ведомость на конец дня. Подсчитывает:
    - все сделки игрока за день,
    - выигрыш/проигрыш относительно свечки,
    - бонусы/подарки (всегда падают на счета по спец-ценам),
    - карточка счастья (итоговый бонус)."""

    @staticmethod
    def _day_actions(state, uid, now=None):
        """Gather all day actions for player."""
        seed = PhiCandleBet._day_seed(now)
        c = state.chars.get(uid, {})
        actions = []
        # candle bet
        cb = c.get("_candle_bet", {})
        if cb.get("day_seed") == seed:
            actions.append({
                "type": "candle_bet", "direction": cb.get("direction"),
                "bet": cb.get("bet", 0), "settled": cb.get("settled", False),
            })
        # shop purchases
        for p in c.get("_candle_shop_bought", []):
            if p.get("day_seed") == seed:
                actions.append({
                    "type": "shop_buy", "item": p.get("item", {}).get("name"),
                    "price": p.get("item", {}).get("price", 0),
                })
        # trades
        for t in c.get("_trades_today", []):
            actions.append({"type": "trade", **t})
        return actions

    @staticmethod
    def status(state, uid, now=None):
        seed = PhiCandleBet._day_seed(now)
        sector_idx = uid % 4
        cr = PhiCandleBet._candle_result(seed, sector_idx)
        actions = CandleSettlement._day_actions(state, uid, now)
        c = state.chars.get(uid, {})
        settlement_claimed = c.get(f"_settlement_{seed}", False)
        # happiness card: bonus = phi * total_actions
        n_actions = len(actions)
        happiness_bonus = int(PHI * n_actions * 100)
        # gift: always lands at special price
        gift_price = int(happiness_bonus / PHI)
        return {
            "candle": cr,
            "actions": actions,
            "n_actions": n_actions,
            "happiness_bonus": happiness_bonus,
            "gift_price": gift_price,
            "claimed": settlement_claimed,
            "day_seed": seed,
        }

    @staticmethod
    def claim_settlement(state, uid, now=None):
        """Claim end-of-day settlement: bonus + guaranteed gift."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        seed = PhiCandleBet._day_seed(now)
        claim_key = f"_settlement_{seed}"
        if c.get(claim_key):
            return {"error": "already claimed"}
        sector_idx = uid % 4
        cr = PhiCandleBet._candle_result(seed, sector_idx)
        actions = CandleSettlement._day_actions(state, uid, now)
        n_actions = len(actions)
        # base bonus: phi-scaled by number of actions
        base_bonus = int(PHI * n_actions * 100)
        # candle multiplier: if candle was green and player had trades, bonus up
        if cr["direction"] == "green":
            base_bonus = int(base_bonus * (1 + abs(cr["delta_pct"]) / 100))
        # happiness card bonus: always positive (bicycle principle)
        happiness_bonus = max(base_bonus, int(100 * PHI))
        # gift: always drops at special price (free or near-free)
        gift = {
            "name": "Свечковый подарок",
            "name_en": "Candle Gift",
            "special_price": 0,
            "always_lands": True,
            "value": int(happiness_bonus * PHI),
        }
        c["gold"] = c.get("gold", 0) + happiness_bonus
        c[claim_key] = True
        c.setdefault("_candle_gifts", []).append(gift)
        state.mark_dirty(uid)
        return {"ok": True, "happiness_bonus": happiness_bonus,
                "gift": gift, "n_actions": n_actions,
                "candle": cr["direction"],
                "gold_left": c["gold"]}

    @staticmethod
    def auto_exchange_wrong_sector(state, uid, now=None):
        """Auto-exchange all wrong-sector items at end of day.
        Items from wrong sector → exchanged for phi-adjusted gold.
        Items from correct sector → kept as permanent inventory."""
        c = state.chars.get(uid)
        if not c:
            return {"error": "no char"}
        seed = PhiCandleBet._day_seed(now)
        sector_idx = uid % 4
        correct_sector = SECTORS[sector_idx]["name"]
        purchased = c.get("_candle_shop_bought", [])
        exchanged = []
        kept = []
        remaining = []
        for p in purchased:
            if p.get("day_seed") == seed:
                item = p.get("item", {})
                if item.get("sector") == correct_sector:
                    kept.append(item)
                else:
                    refund = int(item.get("price", 0) * (1 + 1 / PHI))
                    c["gold"] = c.get("gold", 0) + refund
                    exchanged.append({"item": item, "refund": refund})
            else:
                remaining.append(p)
        c["_candle_shop_bought"] = remaining
        state.mark_dirty(uid)
        return {"exchanged": exchanged, "kept": kept,
                "gold_left": c.get("gold", 0)}

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
