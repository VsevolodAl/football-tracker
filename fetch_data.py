#!/usr/bin/env python3
"""
Fetches Arsenal (EPL), Spartak, and Fakel data → data/clubs.json
APIs used:
  - football-data.org       (free, EPL) → env FOOTBALLDATA_KEY
  - dashboard.api-football.com (free, RPL, but free plan has no access to current
    seasons — kept as a first try in case the plan is ever upgraded) → env APIFOOTBALL_KEY
  - TheSportsDB (free, RPL) → public test key "123", no signup needed;
    this is what actually carries the live РПЛ 26/27 / Кубок России 26/27 data today.
Club crests come straight from the API responses — no manual URLs needed.
"""

import os, json, time, urllib.request, urllib.error
from datetime import datetime, timezone

FD_KEY   = os.environ.get("FOOTBALLDATA_KEY", "")
AF_KEY   = os.environ.get("APIFOOTBALL_KEY", "")   # from dashboard.api-football.com
TSDB_KEY = os.environ.get("THESPORTSDB_KEY", "123")  # "123" = TheSportsDB's public test key
NOW      = datetime.now(timezone.utc).isoformat()
SEASON   = 2026
TSDB_SEASON = "2026-2027"

CLUBS_META = {
    "arsenal": {
        "name": "Арсенал",
        "league": "АПЛ · Сезон 2026/27",
        "bodyClass": "club-arsenal",
        "swatchColor": "#EF0107",
        "fd_team_id": 57,
        "fd_competition": "PL",
        "rf_team_id": 42,       # Arsenal on api-football
        "rf_league_id": 39,
        "tournaments": ["АПЛ 26/27"],
        "hasRussian": False,
        "noLeagueNote": None,
    },
    "spartak": {
        "name": "Спартак Москва",
        "league": "РПЛ · Сезон 2026/27",
        "bodyClass": "club-spartak",
        "swatchColor": "#C8102E",
        "rf_team_id": 2673,
        "rf_league_id": 235,
        "tsdb_team_name": "Spartak Moscow",
        "tournaments": ["Товарищеские матчи", "Суперкубок России", "РПЛ 26/27", "Кубок России 26/27"],
        "hasRussian": True,
        "noLeagueNote": None,
    },
    "fakel": {
        "name": "Факел Воронеж",
        "league": "РПЛ · Сезон 2026/27",
        "bodyClass": "club-fakel",
        "swatchColor": "#005B99",
        "rf_team_id": 2695,
        "rf_league_id": 235,
        "tsdb_team_name": "Fakel Voronezh",
        "tournaments": ["РПЛ 26/27", "Кубок России 26/27"],
        "hasRussian": True,
        "noLeagueNote": "По данным Wikipedia, Факел возвращается в РПЛ в сезоне 2026/27.",
    },
}

# ── helpers ──────────────────────────────────────────────────────────────────

def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [WARN] {url} → {e}")
        return None

def fmt_date(iso):
    MONTHS = ["янв","фев","мар","апр","май","июн",
              "июл","авг","сен","окт","ноя","дек"]
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f"{dt.day} {MONTHS[dt.month-1]}"
    except Exception:
        return iso[:10]

def result_tag(hs, as_, is_home):
    if hs is None or as_ is None:
        return None
    if is_home:
        return "win" if hs > as_ else "draw" if hs == as_ else "loss"
    return "win" if as_ > hs else "draw" if hs == as_ else "loss"

# ── football-data.org ────────────────────────────────────────────────────────

def fetch_fd_team_crest(team_id):
    """Returns crest URL from football-data.org team endpoint."""
    if not FD_KEY:
        return None
    data = fetch_json(
        f"https://api.football-data.org/v4/teams/{team_id}",
        {"X-Auth-Token": FD_KEY}
    )
    return data.get("crest") if data else None

def fetch_epl_fixtures(team_id, competition):
    if not FD_KEY:
        print("  [SKIP] No FOOTBALLDATA_KEY")
        return []
    data = fetch_json(
        f"https://api.football-data.org/v4/teams/{team_id}/matches"
        f"?competitions={competition}&season={SEASON}&status=SCHEDULED,FINISHED,LIVE",
        {"X-Auth-Token": FD_KEY}
    )
    if not data or "matches" not in data:
        return []
    games = []
    for m in data["matches"]:
        home   = m["homeTeam"]["shortName"] or m["homeTeam"]["name"]
        away   = m["awayTeam"]["shortName"] or m["awayTeam"]["name"]
        is_home = m["homeTeam"]["id"] == team_id
        hs     = m["score"]["fullTime"]["home"]
        as_    = m["score"]["fullTime"]["away"]
        done   = m["status"] == "FINISHED"
        games.append({
            "date":     fmt_date(m["utcDate"]),
            "home":     home,
            "away":     away,
            "homeGame": is_home,
            "score":    f"{hs}-{as_}" if done and hs is not None else None,
            "result":   result_tag(hs, as_, is_home) if done else None,
        })
    return games

def fetch_epl_standings(competition, highlight_id):
    if not FD_KEY:
        return []
    data = fetch_json(
        f"https://api.football-data.org/v4/competitions/{competition}/standings?season={SEASON}",
        {"X-Auth-Token": FD_KEY}
    )
    if not data:
        return []
    try:
        table = data["standings"][0]["table"]
    except (KeyError, IndexError):
        return []
    CL = {1,2,3,4}; EL = {5,6,7}; REL = {18,19,20}
    rows = []
    for r in table:
        pos = r["position"]
        rows.append({
            "pos":       pos,
            "name":      r["team"]["shortName"] or r["team"]["name"],
            "crest":     r["team"].get("crest"),
            "pts":       r["points"],
            "w": r["won"], "d": r["draw"], "l": r["lost"],
            "zone":      "cl" if pos in CL else "el" if pos in EL else "rel" if pos in REL else None,
            "highlight": r["team"]["id"] == highlight_id,
        })
    return rows

# ── api-football (dashboard.api-football.com) ────────────────────────────────
# Same REST API as RapidAPI but authenticated via "x-apisports-key" header
# and served from v3.football.api-sports.io

def af_headers():
    return {"x-apisports-key": AF_KEY}

def fetch_af_team_crest(team_id):
    """Returns crest URL from api-football team endpoint."""
    if not AF_KEY:
        return None
    data = fetch_json(
        f"https://v3.football.api-sports.io/teams?id={team_id}",
        af_headers()
    )
    try:
        return data["response"][0]["team"]["logo"]
    except (TypeError, KeyError, IndexError):
        return None

def fetch_rpl_fixtures(team_id, league_id):
    if not AF_KEY:
        print("  [SKIP] No APIFOOTBALL_KEY")
        return []
    data = fetch_json(
        f"https://v3.football.api-sports.io/fixtures?team={team_id}&league={league_id}&season={SEASON}",
        af_headers()
    )
    if not data or "response" not in data:
        return []
    games = []
    for m in data["response"]:
        fix     = m["fixture"]
        home_t  = m["teams"]["home"]
        away_t  = m["teams"]["away"]
        goals   = m["goals"]
        is_home = home_t["id"] == team_id
        done    = fix["status"]["short"] == "FT"
        hs      = goals.get("home")
        as_     = goals.get("away")
        games.append({
            "date":     fmt_date(fix["date"]),
            "home":     home_t["name"],
            "away":     away_t["name"],
            "homeGame": is_home,
            "score":    f"{hs}-{as_}" if done and hs is not None else None,
            "result":   result_tag(hs, as_, is_home) if done else None,
        })
    games.sort(key=lambda g: g["date"])
    return games

def fetch_rpl_standings(league_id, highlight_id):
    if not AF_KEY:
        return []
    data = fetch_json(
        f"https://v3.football.api-sports.io/standings?league={league_id}&season={SEASON}",
        af_headers()
    )
    if not data or "response" not in data:
        return []
    try:
        table = data["response"][0]["league"]["standings"][0]
    except (KeyError, IndexError):
        return []
    CL = {1,2}; EL = {3}; REL = {14,15,16}
    rows = []
    for r in table:
        pos = r["rank"]
        rows.append({
            "pos":       pos,
            "name":      r["team"]["name"],
            "crest":     r["team"].get("logo"),
            "pts":       r["points"],
            "w": r["all"]["win"], "d": r["all"]["draw"], "l": r["all"]["lose"],
            "zone":      "cl" if pos in CL else "el" if pos in EL else "rel" if pos in REL else None,
            "highlight": r["team"]["id"] == highlight_id,
        })
    return rows

# ── TheSportsDB (free, no signup — public test key "123") ───────────────────
# api-football's free plan doesn't cover current seasons at all, so this is
# the actual live source for РПЛ 26/27 / Кубок России 26/27 right now.

TSDB_RPL_LEAGUE_ID = 4355   # Russian Football Premier League
TSDB_CUP_LEAGUE_ID = 5193   # Russia Cup
TSDB_RPL_ROUNDS = 30
TSDB_CUP_ROUNDS = 6

RU_TEAM_NAMES = {
    "Spartak Moscow": "Спартак",
    "Zenit Saint Petersburg": "Зенит",
    "CSKA Moscow": "ЦСКА",
    "Dynamo Moscow": "Динамо",
    "Dynamo Makhachkala": "Динамо Мх",
    "Rostov": "Ростов",
    "Lokomotiv Moscow": "Локомотив",
    "Akron Tolyatti": "Акрон",
    "Krylia Sovetov Samara": "Крылья Советов",
    "Rubin Kazan": "Рубин",
    "Akhmat Grozny": "Ахмат",
    "Krasnodar": "Краснодар",
    "Baltika Kaliningrad": "Балтика",
    "Orenburg": "Оренбург",
    "Rodina Moscow": "Родина",
    "Fakel Voronezh": "Факел",
}

def tsdb_ru(name):
    return RU_TEAM_NAMES.get(name, name)

def fetch_tsdb_league_events(league_id, rounds):
    """Pulls every round of a TheSportsDB league/season, one request per round
    (there's no reliable single-shot 'whole season' endpoint). Throttled to stay
    under the free key's 30 req/min limit."""
    events = []
    for r in range(1, rounds + 1):
        data = fetch_json(
            f"https://www.thesportsdb.com/api/v1/json/{TSDB_KEY}/eventsround.php"
            f"?id={league_id}&r={r}&s={TSDB_SEASON}"
        )
        if data and data.get("events"):
            events.extend(data["events"])
        time.sleep(2.5)
    return events

def tsdb_event_to_game(ev, team_en):
    is_home = ev["strHomeTeam"] == team_en
    hs, as_ = ev.get("intHomeScore"), ev.get("intAwayScore")
    done = ev.get("strStatus") == "FT" and hs is not None and as_ is not None
    return {
        "date":     fmt_date(ev["dateEvent"]),
        "home":     tsdb_ru(ev["strHomeTeam"]),
        "away":     tsdb_ru(ev["strAwayTeam"]),
        "homeGame": is_home,
        "score":    f"{hs}-{as_}" if done else None,
        "result":   result_tag(int(hs), int(as_), is_home) if done else None,
        "_sortkey": ev["dateEvent"],
    }

def tsdb_team_games(events, team_en):
    games = [tsdb_event_to_game(e, team_en) for e in events
             if team_en in (e.get("strHomeTeam"), e.get("strAwayTeam"))]
    games.sort(key=lambda g: g.pop("_sortkey"))
    return games

# ── static fallback crests (Wikipedia / public domain SVG) ──────────────────
# Used when API keys are absent or API is down.
FALLBACK_CRESTS = {
    "arsenal": "https://upload.wikimedia.org/wikipedia/en/5/53/Arsenal_FC.svg",
    "spartak":  "https://upload.wikimedia.org/wikipedia/en/5/50/FC_Spartak_Moscow.svg",
    "fakel":    "https://upload.wikimedia.org/wikipedia/en/f/f6/FC_Fakel_Voronezh.svg",
}

# ── static fallback fixtures ─────────────────────────────────────────────────
# api-football's free tier doesn't carry RPL 26/27 fixtures yet, so these are
# hand-entered from official RPL/RFS schedule announcements (July 2026) and
# used whenever the live API returns nothing.
def _g(date, home, away, home_game):
    return {"date": date, "home": home, "away": away, "homeGame": home_game, "score": None, "result": None}

STATIC_FIXTURES = {
    "spartak": {
        "Товарищеские матчи": [
            _g("11 июл", "Локомотив", "Спартак", False),
        ],
        "Суперкубок России": [
            _g("18 июл", "Зенит", "Спартак", False),
        ],
        "РПЛ 26/27": [
            _g("25 июл", "Спартак", "Родина", True),
            _g("2 авг", "Ахмат", "Спартак", False),
            _g("9 авг", "Спартак", "Краснодар", True),
            _g("16 авг", "Балтика", "Спартак", False),
            _g("23 авг", "Спартак", "Зенит", True),
            _g("29 авг", "Спартак", "Оренбург", True),
            _g("6 сен", "Динамо", "Спартак", False),
            _g("13 сен", "Спартак", "Ростов", True),
            _g("16 сен", "Спартак", "Факел", True),
            _g("11 окт", "Крылья Советов", "Спартак", False),
            _g("18 окт", "Спартак", "Рубин", True),
            _g("25 окт", "ЦСКА", "Спартак", False),
            _g("1 ноя", "Локомотив", "Спартак", False),
            _g("8 ноя", "Спартак", "Акрон", True),
            _g("22 ноя", "Динамо Мх", "Спартак", False),
            _g("29 ноя", "Факел", "Спартак", False),
            _g("6 дек", "Спартак", "Динамо", True),
            _g("28 фев", "Краснодар", "Спартак", False),
            _g("7 мар", "Акрон", "Спартак", False),
            _g("14 мар", "Спартак", "Ахмат", True),
            _g("21 мар", "Рубин", "Спартак", False),
            _g("4 апр", "Спартак", "Динамо Мх", True),
            _g("11 апр", "Оренбург", "Спартак", False),
            _g("18 апр", "Спартак", "ЦСКА", True),
            _g("25 апр", "Родина", "Спартак", False),
            _g("2 май", "Спартак", "Балтика", True),
            _g("9 май", "Спартак", "Локомотив", True),
            _g("16 май", "Зенит", "Спартак", False),
            _g("23 май", "Спартак", "Крылья Советов", True),
            _g("29 май", "Ростов", "Спартак", False),
        ],
        "Кубок России 26/27": [
            _g("4 авг", "Спартак", "Оренбург", True),
            _g("18 авг", "Рубин", "Спартак", False),
            _g("1 сен", "Спартак", "Родина", True),
            _g("13 окт", "Родина", "Спартак", False),
            _g("27 окт", "Спартак", "Рубин", True),
            _g("24 ноя", "Оренбург", "Спартак", False),
        ],
    },
    "fakel": {
        "РПЛ 26/27": [
            _g("25 июл", "Факел", "Динамо Мх", True),
            _g("2 авг", "Краснодар", "Факел", False),
            _g("10 авг", "Факел", "Ахмат", True),
            _g("15 авг", "ЦСКА", "Факел", False),
            _g("22 авг", "Факел", "Оренбург", True),
            _g("29 авг", "Факел", "Зенит", True),
            _g("5 сен", "Ростов", "Факел", False),
            _g("12 сен", "Факел", "Балтика", True),
            _g("16 сен", "Спартак", "Факел", False),
            _g("11 окт", "Факел", "Локомотив", True),
            _g("18 окт", "Крылья Советов", "Факел", False),
            _g("25 окт", "Факел", "Родина", True),
            _g("1 ноя", "Рубин", "Факел", False),
            _g("8 ноя", "Факел", "Динамо", True),
            _g("22 ноя", "Акрон", "Факел", False),
            _g("29 ноя", "Факел", "Спартак", True),
            _g("6 дек", "Факел", "Ростов", True),
            _g("28 фев", "Зенит", "Факел", False),
            _g("7 мар", "Динамо Мх", "Факел", False),
            _g("14 мар", "Факел", "ЦСКА", True),
            _g("21 мар", "Локомотив", "Факел", False),
            _g("4 апр", "Ахмат", "Факел", False),
            _g("11 апр", "Факел", "Акрон", True),
            _g("18 апр", "Динамо", "Факел", False),
            _g("25 апр", "Оренбург", "Факел", False),
            _g("2 май", "Факел", "Рубин", True),
            _g("9 май", "Балтика", "Факел", False),
            _g("16 май", "Факел", "Крылья Советов", True),
            _g("23 май", "Факел", "Краснодар", True),
            _g("29 май", "Родина", "Факел", False),
        ],
        "Кубок России 26/27": [
            _g("4 авг", "Факел", "Динамо", True),
            _g("18 авг", "Ахмат", "Факел", False),
            _g("1 сен", "Факел", "Краснодар", True),
            _g("13 окт", "Краснодар", "Факел", False),
            _g("27 окт", "Факел", "Ахмат", True),
            _g("24 ноя", "Динамо", "Факел", False),
        ],
    },
}

# ── assemble ─────────────────────────────────────────────────────────────────

def build():
    out = {}

    # ── Arsenal ──
    print("Fetching Arsenal / EPL …")
    apl_crest   = fetch_fd_team_crest(CLUBS_META["arsenal"]["fd_team_id"]) \
                  or fetch_af_team_crest(CLUBS_META["arsenal"]["rf_team_id"]) \
                  or FALLBACK_CRESTS["arsenal"]
    apl_games   = fetch_epl_fixtures(CLUBS_META["arsenal"]["fd_team_id"], "PL")
    apl_st      = fetch_epl_standings("PL", CLUBS_META["arsenal"]["fd_team_id"])
    out["arsenal"] = {
        **{k: v for k, v in CLUBS_META["arsenal"].items()
           if k not in ("fd_team_id","fd_competition","rf_team_id","rf_league_id")},
        "crest":    apl_crest,
        "hasData":  bool(apl_games),
        "games":    {"АПЛ 26/27": apl_games or []},
        "standings": {
            "note":  "Таблица актуальна на момент последнего обновления" if apl_st
                     else "Сезон 26/27 стартует 21 августа — таблица пустая",
            "teams": apl_st or [],
        },
    }

    # ── RPL / Cup events from TheSportsDB, fetched once and reused for both clubs ──
    print("Fetching РПЛ 26/27 + Кубок России 26/27 from TheSportsDB …")
    tsdb_rpl_events = fetch_tsdb_league_events(TSDB_RPL_LEAGUE_ID, TSDB_RPL_ROUNDS)
    tsdb_cup_events = fetch_tsdb_league_events(TSDB_CUP_LEAGUE_ID, TSDB_CUP_ROUNDS)

    # ── Spartak ──
    print("Fetching Spartak / RPL …")
    sp_crest  = fetch_af_team_crest(CLUBS_META["spartak"]["rf_team_id"]) \
                or FALLBACK_CRESTS["spartak"]
    sp_tsdb_name = CLUBS_META["spartak"]["tsdb_team_name"]
    sp_games  = fetch_rpl_fixtures(CLUBS_META["spartak"]["rf_team_id"], CLUBS_META["spartak"]["rf_league_id"]) \
                or tsdb_team_games(tsdb_rpl_events, sp_tsdb_name) \
                or STATIC_FIXTURES["spartak"]["РПЛ 26/27"]
    sp_cup_games = tsdb_team_games(tsdb_cup_events, sp_tsdb_name) \
                or STATIC_FIXTURES["spartak"]["Кубок России 26/27"]
    sp_st     = fetch_rpl_standings(CLUBS_META["spartak"]["rf_league_id"], CLUBS_META["spartak"]["rf_team_id"])
    out["spartak"] = {
        **{k: v for k, v in CLUBS_META["spartak"].items()
           if k not in ("rf_team_id","rf_league_id","tsdb_team_name")},
        "crest":   sp_crest,
        "hasData": bool(sp_games),
        "games":   {
            "Товарищеские матчи": STATIC_FIXTURES["spartak"]["Товарищеские матчи"],
            "Суперкубок России":  STATIC_FIXTURES["spartak"]["Суперкубок России"],
            "РПЛ 26/27":          sp_games or [],
            "Кубок России 26/27": sp_cup_games or [],
        },
        "standings": {
            "note":  "Таблица актуальна на момент последнего обновления" if sp_st
                     else "Сезон 2026/27 стартует 25 июля — таблица пустая",
            "teams": sp_st or [],
        },
    }

    # ── Fakel ──
    print("Fetching Fakel / RPL …")
    fk_crest  = fetch_af_team_crest(CLUBS_META["fakel"]["rf_team_id"]) \
                or FALLBACK_CRESTS["fakel"]
    fk_tsdb_name = CLUBS_META["fakel"]["tsdb_team_name"]
    fk_games  = fetch_rpl_fixtures(CLUBS_META["fakel"]["rf_team_id"], CLUBS_META["fakel"]["rf_league_id"]) \
                or tsdb_team_games(tsdb_rpl_events, fk_tsdb_name) \
                or STATIC_FIXTURES["fakel"]["РПЛ 26/27"]
    fk_cup_games = tsdb_team_games(tsdb_cup_events, fk_tsdb_name) \
                or STATIC_FIXTURES["fakel"]["Кубок России 26/27"]
    fk_st     = fetch_rpl_standings(CLUBS_META["fakel"]["rf_league_id"], CLUBS_META["fakel"]["rf_team_id"])
    out["fakel"] = {
        **{k: v for k, v in CLUBS_META["fakel"].items()
           if k not in ("rf_team_id","rf_league_id","tsdb_team_name")},
        "crest":   fk_crest,
        "hasData": bool(fk_games),
        "games":   {
            "РПЛ 26/27":          fk_games or [],
            "Кубок России 26/27": fk_cup_games or [],
        },
        "standings": {
            "note":  "Таблица актуальна на момент последнего обновления" if fk_st
                     else "Сезон 2026/27 стартует 25 июля — таблица пустая",
            "teams": fk_st or [],
        },
    }

    return {"updated": NOW, "clubs": out}


if __name__ == "__main__":
    payload = build()
    out_path = os.path.join(os.path.dirname(__file__), "data", "clubs.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✓  data/clubs.json  ({NOW})")
