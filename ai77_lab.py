import json
import math
import os
import statistics
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")
FOOTBALL_URL = "https://v3.football.api-sports.io"
TZ_NAME = "Europe/Ljubljana"

LAB_PREDICTIONS_FILE = "lab_predictions.json"
LAB_RESULTS_FILE = "lab_results.json"

TIME_WINDOW_MIN_HOURS = 1
TIME_WINDOW_MAX_HOURS = 6

REQUEST_TIMEOUT = 20

# -----------------------------
# BUCKET CONFIG
# -----------------------------
BUCKETS = {
    "home": {"limit": 5, "min_edge": 0.025, "min_bookmakers": 3, "odds_min": 1.55, "odds_max": 4.50},
    "draw": {"limit": 3, "min_edge": 0.035, "min_bookmakers": 3, "odds_min": 2.80, "odds_max": 4.50},
    "away": {"limit": 5, "min_edge": 0.025, "min_bookmakers": 3, "odds_min": 1.55, "odds_max": 4.50},
    "over_2_5": {"limit": 5, "min_edge": 0.025, "min_bookmakers": 3, "odds_min": 1.55, "odds_max": 4.50},
    "under_2_5": {"limit": 5, "min_edge": 0.025, "min_bookmakers": 3, "odds_min": 1.55, "odds_max": 4.50},
    "btts_yes": {"limit": 5, "min_edge": 0.030, "min_bookmakers": 4, "odds_min": 1.55, "odds_max": 4.50},
    "btts_no": {"limit": 5, "min_edge": 0.030, "min_bookmakers": 4, "odds_min": 1.55, "odds_max": 4.50},
    "over_3_5": {"limit": 5, "min_edge": 0.030, "min_bookmakers": 3, "odds_min": 1.70, "odds_max": 5.20},
    "under_3_5": {"limit": 5, "min_edge": 0.030, "min_bookmakers": 3, "odds_min": 1.35, "odds_max": 3.50},
}

VALID_STATUSES = {"NS", "TBD", "PST"}

# -----------------------------
# GLOBAL CACHES
# -----------------------------
TEAM_FORM_CACHE = {}
FIXTURE_PRED_CACHE = {}
FIXTURE_ODDS_CACHE = {}


# -----------------------------
# HELPERS
# -----------------------------
def football_headers() -> dict:
    return {"x-apisports-key": FOOTBALL_API_KEY}


def safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def median_or_none(values):
    cleaned = [safe_float(v) for v in values]
    cleaned = [v for v in cleaned if v is not None]
    if not cleaned:
        return None
    try:
        return float(statistics.median(cleaned))
    except Exception:
        return None


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def normalize_name(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def build_pick_id(fixture_id: int, bucket: str, bet: str, line: float | None) -> str:
    base = f"{fixture_id}|{bucket}|{bet}|{line}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def load_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return default


def save_json_file(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def debug(msg: str):
    print(msg)


# -----------------------------
# API CALLS
# -----------------------------
def api_get(endpoint: str, params: dict) -> dict:
    url = f"{FOOTBALL_URL}/{endpoint}"
    res = requests.get(url, headers=football_headers(), params=params, timeout=REQUEST_TIMEOUT)
    res.raise_for_status()
    return res.json()


def fetch_fixtures_in_window(start_time: datetime, end_time: datetime, tz_name: str) -> list:
    fixtures = []
    current_date = start_time.date()
    end_date = end_time.date()

    while current_date <= end_date:
        try:
            data = api_get("fixtures", {
                "date": current_date.strftime("%Y-%m-%d"),
                "timezone": tz_name
            })
            daily = data.get("response", [])
            debug(f"FIXTURES {current_date}: {len(daily)}")
            fixtures.extend(daily)
        except Exception as e:
            debug(f"FIXTURES ERROR {current_date}: {e}")
        current_date += timedelta(days=1)

    filtered = []
    tz = ZoneInfo(tz_name)

    for fixture in fixtures:
        try:
            fixture_dt_raw = fixture.get("fixture", {}).get("date")
            if not fixture_dt_raw:
                continue

            fixture_time = datetime.fromisoformat(fixture_dt_raw).astimezone(tz)
            status_short = fixture.get("fixture", {}).get("status", {}).get("short")

            if status_short not in VALID_STATUSES:
                continue

            if fixture_time < start_time or fixture_time > end_time:
                continue

            filtered.append(fixture)
        except Exception as e:
            debug(f"FIXTURE FILTER ERROR: {e}")

    debug(f"FILTERED FIXTURES: {len(filtered)}")
    return filtered


def get_recent_team_form(team_id: int) -> dict:
    if team_id in TEAM_FORM_CACHE:
        return TEAM_FORM_CACHE[team_id]

    fallback = {
        "home_scored_avg": 1.25,
        "home_conceded_avg": 1.15,
        "away_scored_avg": 1.15,
        "away_conceded_avg": 1.25,
        "overall_scored_avg": 1.20,
        "overall_conceded_avg": 1.20,
        "over25_rate": 0.50,
        "over35_rate": 0.25,
        "btts_rate": 0.50,
        "wins_rate": 0.33,
        "draws_rate": 0.28,
        "losses_rate": 0.39,
        "games_used": 0
    }

    try:
        data = api_get("fixtures", {"team": team_id, "last": 10})
        fixtures = data.get("response", [])

        home_scored, home_conceded = [], []
        away_scored, away_conceded = [], []
        all_scored, all_conceded = [], []

        over25 = 0
        over35 = 0
        btts = 0
        wins = 0
        draws = 0
        losses = 0
        valid_games = 0

        for f in fixtures:
            status = f.get("fixture", {}).get("status", {}).get("short")
            if status not in {"FT", "AET", "PEN"}:
                continue

            gh = f.get("goals", {}).get("home")
            ga = f.get("goals", {}).get("away")
            if gh is None or ga is None:
                continue

            home_team = f.get("teams", {}).get("home", {})
            away_team = f.get("teams", {}).get("away", {})

            valid_games += 1

            total_goals = gh + ga
            if total_goals > 2.5:
                over25 += 1
            if total_goals > 3.5:
                over35 += 1
            if gh > 0 and ga > 0:
                btts += 1

            if home_team.get("id") == team_id:
                scored = gh
                conceded = ga
                home_scored.append(gh)
                home_conceded.append(ga)
                if gh > ga:
                    wins += 1
                elif gh == ga:
                    draws += 1
                else:
                    losses += 1
            elif away_team.get("id") == team_id:
                scored = ga
                conceded = gh
                away_scored.append(ga)
                away_conceded.append(gh)
                if ga > gh:
                    wins += 1
                elif ga == gh:
                    draws += 1
                else:
                    losses += 1
            else:
                continue

            all_scored.append(scored)
            all_conceded.append(conceded)

        if valid_games == 0:
            TEAM_FORM_CACHE[team_id] = fallback
            debug(f"TEAM FORM FALLBACK team={team_id}")
            return fallback

        result = {
            "home_scored_avg": sum(home_scored) / len(home_scored) if home_scored else fallback["home_scored_avg"],
            "home_conceded_avg": sum(home_conceded) / len(home_conceded) if home_conceded else fallback["home_conceded_avg"],
            "away_scored_avg": sum(away_scored) / len(away_scored) if away_scored else fallback["away_scored_avg"],
            "away_conceded_avg": sum(away_conceded) / len(away_conceded) if away_conceded else fallback["away_conceded_avg"],
            "overall_scored_avg": sum(all_scored) / len(all_scored) if all_scored else fallback["overall_scored_avg"],
            "overall_conceded_avg": sum(all_conceded) / len(all_conceded) if all_conceded else fallback["overall_conceded_avg"],
            "over25_rate": over25 / valid_games,
            "over35_rate": over35 / valid_games,
            "btts_rate": btts / valid_games,
            "wins_rate": wins / valid_games,
            "draws_rate": draws / valid_games,
            "losses_rate": losses / valid_games,
            "games_used": valid_games
        }

        TEAM_FORM_CACHE[team_id] = result
        debug(f"TEAM FORM USED team={team_id}: {result}")
        return result

    except Exception as e:
        debug(f"TEAM FORM ERROR team={team_id}: {e}")
        TEAM_FORM_CACHE[team_id] = fallback
        return fallback


def get_fixture_prediction_data(fixture_id: int) -> dict:
    if fixture_id in FIXTURE_PRED_CACHE:
        return FIXTURE_PRED_CACHE[fixture_id]

    result = {
        "advice": "",
        "goals_home": None,
        "goals_away": None,
        "winner_name": None,
        "winner_comment": None,
        "percent_home": None,
        "percent_draw": None,
        "percent_away": None
    }

    try:
        data = api_get("predictions", {"fixture": fixture_id})
        response = data.get("response", [])
        if not response:
            FIXTURE_PRED_CACHE[fixture_id] = result
            debug(f"PREDICTION EMPTY fixture={fixture_id}")
            return result

        pred = response[0].get("predictions", {})
        result["advice"] = pred.get("advice", "")

        goals = pred.get("goals", {})
        result["goals_home"] = safe_float(goals.get("home"))
        result["goals_away"] = safe_float(goals.get("away"))

        winner = pred.get("winner", {})
        result["winner_name"] = winner.get("name")
        result["winner_comment"] = winner.get("comment")

        percent = pred.get("percent", {})
        result["percent_home"] = safe_float(str(percent.get("home", "")).replace("%", ""))
        result["percent_draw"] = safe_float(str(percent.get("draw", "")).replace("%", ""))
        result["percent_away"] = safe_float(str(percent.get("away", "")).replace("%", ""))

        FIXTURE_PRED_CACHE[fixture_id] = result
        debug(f"PREDICTION USED fixture={fixture_id}: {result}")
        return result

    except Exception as e:
        debug(f"PREDICTION ERROR fixture={fixture_id}: {e}")
        FIXTURE_PRED_CACHE[fixture_id] = result
        return result


# -----------------------------
# ODDS PARSING
# -----------------------------
def is_h2h_bet_name(name: str) -> bool:
    n = normalize_name(name)
    return n in {
        "match winner",
        "1x2",
        "winner",
        "fulltime result",
        "result",
        "match result"
    }


def is_total_bet_name(name: str) -> bool:
    n = normalize_name(name)
    return (
        "over/under" in n
        or "goals over/under" in n
        or "over under" in n
        or "total goals" in n
    )


def is_btts_bet_name(name: str) -> bool:
    n = normalize_name(name)
    return "both teams" in n or "btts" in n or "both team" in n


def get_fixture_odds_markets(fixture_id: int, home_name: str, away_name: str) -> dict:
    if fixture_id in FIXTURE_ODDS_CACHE:
        return FIXTURE_ODDS_CACHE[fixture_id]

    result = {
        "h2h": {
            "home": [],
            "draw": [],
            "away": []
        },
        "totals": {
            2.5: {"over": [], "under": []},
            3.5: {"over": [], "under": []}
        },
        "btts": {
            "yes": [],
            "no": []
        },
        "counts": {
            "h2h_home": 0,
            "h2h_draw": 0,
            "h2h_away": 0,
            "over_2_5": 0,
            "under_2_5": 0,
            "over_3_5": 0,
            "under_3_5": 0,
            "btts_yes": 0,
            "btts_no": 0
        }
    }

    try:
        data = api_get("odds", {"fixture": fixture_id})
        response = data.get("response", [])
        if not response:
            debug(f"ODDS EMPTY fixture={fixture_id}")
            FIXTURE_ODDS_CACHE[fixture_id] = result
            return result

        seen_bookmaker_market = set()

        for item in response:
            bookmakers = item.get("bookmakers", [])
            for bookmaker in bookmakers:
                bookmaker_id = bookmaker.get("id")
                bets = bookmaker.get("bets", [])

                for bet in bets:
                    bet_name = bet.get("name", "")
                    values = bet.get("values", [])

                    # H2H
                    if is_h2h_bet_name(bet_name):
                        local_seen = set()
                        for v in values:
                            value_name = str(v.get("value", "")).strip()
                            odd = safe_float(v.get("odd"))
                            if odd is None:
                                continue

                            norm = normalize_name(value_name)
                            mapped = None

                            if normalize_name(value_name) == normalize_name(home_name):
                                mapped = "home"
                            elif normalize_name(value_name) == normalize_name(away_name):
                                mapped = "away"
                            elif norm in {"draw", "x"}:
                                mapped = "draw"

                            if not mapped:
                                continue

                            unique_key = (bookmaker_id, "h2h", mapped)
                            if unique_key in local_seen or unique_key in seen_bookmaker_market:
                                continue

                            local_seen.add(unique_key)
                            seen_bookmaker_market.add(unique_key)
                            result["h2h"][mapped].append(odd)

                    # TOTALS
                    elif is_total_bet_name(bet_name):
                        for v in values:
                            value_name = str(v.get("value", "")).strip()
                            odd = safe_float(v.get("odd"))
                            if odd is None:
                                continue

                            parts = value_name.split()
                            if len(parts) < 2:
                                continue

                            side_raw = parts[0].strip().lower()
                            line = safe_float(parts[-1])
                            if line not in {2.5, 3.5}:
                                continue

                            side = None
                            if side_raw == "over":
                                side = "over"
                            elif side_raw == "under":
                                side = "under"
                            if not side:
                                continue

                            unique_key = (bookmaker_id, "totals", line, side)
                            if unique_key in seen_bookmaker_market:
                                continue

                            seen_bookmaker_market.add(unique_key)
                            result["totals"][line][side].append(odd)

                    # BTTS
                    elif is_btts_bet_name(bet_name):
                        local_seen = set()
                        for v in values:
                            value_name = str(v.get("value", "")).strip().lower()
                            odd = safe_float(v.get("odd"))
                            if odd is None:
                                continue

                            if value_name not in {"yes", "no"}:
                                continue

                            unique_key = (bookmaker_id, "btts", value_name)
                            if unique_key in local_seen or unique_key in seen_bookmaker_market:
                                continue

                            local_seen.add(unique_key)
                            seen_bookmaker_market.add(unique_key)
                            result["btts"][value_name].append(odd)

        result["counts"]["h2h_home"] = len(result["h2h"]["home"])
        result["counts"]["h2h_draw"] = len(result["h2h"]["draw"])
        result["counts"]["h2h_away"] = len(result["h2h"]["away"])
        result["counts"]["over_2_5"] = len(result["totals"][2.5]["over"])
        result["counts"]["under_2_5"] = len(result["totals"][2.5]["under"])
        result["counts"]["over_3_5"] = len(result["totals"][3.5]["over"])
        result["counts"]["under_3_5"] = len(result["totals"][3.5]["under"])
        result["counts"]["btts_yes"] = len(result["btts"]["yes"])
        result["counts"]["btts_no"] = len(result["btts"]["no"])

        debug(
            f"ODDS fixture={fixture_id} | "
            f"h={result['counts']['h2h_home']} d={result['counts']['h2h_draw']} a={result['counts']['h2h_away']} | "
            f"o25={result['counts']['over_2_5']} u25={result['counts']['under_2_5']} | "
            f"o35={result['counts']['over_3_5']} u35={result['counts']['under_3_5']} | "
            f"btts_yes={result['counts']['btts_yes']} btts_no={result['counts']['btts_no']}"
        )

        FIXTURE_ODDS_CACHE[fixture_id] = result
        return result

    except Exception as e:
        debug(f"ODDS ERROR fixture={fixture_id}: {e}")
        FIXTURE_ODDS_CACHE[fixture_id] = result
        return result


# -----------------------------
# MODEL PROBABILITIES
# -----------------------------
def calculate_expected_goals(home_stats: dict, away_stats: dict, pred: dict) -> tuple[float, float, float]:
    expected_home = (home_stats["home_scored_avg"] + away_stats["away_conceded_avg"]) / 2
    expected_away = (away_stats["away_scored_avg"] + home_stats["home_conceded_avg"]) / 2

    # form adjustments
    if home_stats["wins_rate"] >= 0.50:
        expected_home += 0.08
    if away_stats["wins_rate"] >= 0.50:
        expected_away += 0.08

    if home_stats["overall_scored_avg"] < 0.95:
        expected_home -= 0.07
    if away_stats["overall_scored_avg"] < 0.95:
        expected_away -= 0.07

    # scoring environment
    if home_stats["over25_rate"] >= 0.60 and away_stats["over25_rate"] >= 0.60:
        expected_home += 0.05
        expected_away += 0.05

    if home_stats["over35_rate"] >= 0.35 and away_stats["over35_rate"] >= 0.35:
        expected_home += 0.04
        expected_away += 0.04

    if home_stats["over25_rate"] <= 0.35 and away_stats["over25_rate"] <= 0.35:
        expected_home -= 0.05
        expected_away -= 0.05

    pred_home = pred.get("goals_home")
    pred_away = pred.get("goals_away")
    if pred_home is not None and pred_away is not None:
        expected_home = (expected_home * 0.75) + (pred_home * 0.25)
        expected_away = (expected_away * 0.75) + (pred_away * 0.25)

    expected_home = clamp(expected_home, 0.35, 3.20)
    expected_away = clamp(expected_away, 0.35, 3.20)
    expected_total = expected_home + expected_away

    return expected_home, expected_away, expected_total


def get_h2h_probs(expected_home: float, expected_away: float, pred: dict) -> dict:
    max_goals = 8

    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = poisson_pmf(h, expected_home) * poisson_pmf(a, expected_away)
            if h > a:
                home_win += p
            elif h == a:
                draw += p
            else:
                away_win += p

    total = home_win + draw + away_win
    if total <= 0:
        return {"home": 0.40, "draw": 0.28, "away": 0.32}

    home_win /= total
    draw /= total
    away_win /= total

    # Blend with API prediction percentages if available
    ph = pred.get("percent_home")
    pd = pred.get("percent_draw")
    pa = pred.get("percent_away")
    if ph is not None and pd is not None and pa is not None:
        ph /= 100.0
        pd /= 100.0
        pa /= 100.0

        sum_pred = ph + pd + pa
        if sum_pred > 0.95 and sum_pred < 1.05:
            home_win = home_win * 0.75 + ph * 0.25
            draw = draw * 0.75 + pd * 0.25
            away_win = away_win * 0.75 + pa * 0.25

    # small draw calibration
    if abs(expected_home - expected_away) < 0.18:
        draw += 0.02
        home_win -= 0.01
        away_win -= 0.01

    home_win = clamp(home_win, 0.15, 0.70)
    draw = clamp(draw, 0.14, 0.38)
    away_win = clamp(away_win, 0.15, 0.70)

    total = home_win + draw + away_win
    return {
        "home": home_win / total,
        "draw": draw / total,
        "away": away_win / total
    }


def get_total_probs(expected_total: float) -> dict:
    max_goals = 10
    probs = {}

    over25 = 0.0
    over35 = 0.0
    for g in range(max_goals + 1):
        p = poisson_pmf(g, expected_total)
        if g >= 3:
            over25 += p
        if g >= 4:
            over35 += p

    under25 = 1 - over25
    under35 = 1 - over35

    probs["over_2_5"] = clamp(over25, 0.10, 0.90)
    probs["under_2_5"] = clamp(under25, 0.10, 0.90)
    probs["over_3_5"] = clamp(over35, 0.05, 0.80)
    probs["under_3_5"] = clamp(under35, 0.20, 0.95)

    return probs


def get_btts_probs(expected_home: float, expected_away: float, home_stats: dict, away_stats: dict) -> dict:
    p_home_scores = 1 - math.exp(-expected_home)
    p_away_scores = 1 - math.exp(-expected_away)

    btts_yes = p_home_scores * p_away_scores

    form_btts = (home_stats["btts_rate"] + away_stats["btts_rate"]) / 2
    btts_yes = btts_yes * 0.75 + form_btts * 0.25

    if home_stats["overall_scored_avg"] < 0.95 or away_stats["overall_scored_avg"] < 0.95:
        btts_yes -= 0.04
    if home_stats["overall_scored_avg"] > 1.60 and away_stats["overall_scored_avg"] > 1.40:
        btts_yes += 0.03

    btts_yes = clamp(btts_yes, 0.12, 0.88)
    btts_no = 1 - btts_yes

    return {
        "btts_yes": btts_yes,
        "btts_no": btts_no
    }


# -----------------------------
# REASONING
# -----------------------------
def h2h_reasoning(home: str, away: str, bet: str, edge: float, model_prob: float, implied_prob: float) -> str:
    if bet == home:
        return (
            f"{home} grades better in the home-side model than the market median implies. "
            f"The edge is modest but playable, with a stronger projected control profile than the current price suggests."
        )
    if bet == away:
        return (
            f"{away} looks slightly undervalued away from home. "
            f"The model sees a better win probability than the market median, which keeps this as a live value side."
        )
    return (
        f"This matchup projects fairly balanced, which is exactly why the draw price becomes interesting. "
        f"It remains a variance-heavy market, but the median line still leaves measurable value."
    )


def totals_reasoning(home: str, away: str, bet: str, expected_total: float) -> str:
    if "Over" in bet:
        return (
            f"{home} vs {away} projects with enough scoring volume to justify an aggressive totals angle. "
            f"The expected goals profile supports the market line being slightly too low."
        )
    return (
        f"{home} vs {away} projects as a more controlled scoring environment than the market median suggests. "
        f"The expected goals profile supports a lower-event outcome."
    )


def btts_reasoning(home: str, away: str, bet: str, model_prob: float) -> str:
    if bet == "BTTS Yes":
        return (
            f"Both teams rate with enough attacking involvement to keep a two-sided scoring game live. "
            f"Recent BTTS tendencies and projected scoring output both support the Yes side."
        )
    return (
        f"The matchup does not rate as strong enough for reliable two-sided scoring. "
        f"At least one attack looks weaker than the market median is pricing."
    )


# -----------------------------
# CANDIDATE BUILDERS
# -----------------------------
def build_h2h_candidate(bucket: str, fixture: dict, market_odds: list, model_prob: float) -> dict | None:
    cfg = BUCKETS[bucket]
    median_odds = median_or_none(market_odds)
    if median_odds is None:
        return None

    bookmakers_used = len(market_odds)
    implied_prob = 1 / median_odds
    edge = model_prob - implied_prob

    if bookmakers_used < cfg["min_bookmakers"]:
        return None
    if median_odds < cfg["odds_min"] or median_odds > cfg["odds_max"]:
        return None
    if edge < cfg["min_edge"]:
        return None

    fixture_info = fixture["fixture"]
    teams = fixture["teams"]
    league = fixture["league"]

    fixture_id = fixture_info["id"]
    home = teams["home"]["name"]
    away = teams["away"]["name"]

    bet = home if bucket == "home" else ("Draw" if bucket == "draw" else away)
    reasoning = h2h_reasoning(home, away, bet, edge, model_prob, implied_prob)

    return {
        "pick_id": build_pick_id(fixture_id, bucket, bet, None),
        "fixture_id": fixture_id,
        "bucket": bucket,
        "date": datetime.fromisoformat(fixture_info["date"]).astimezone(ZoneInfo(TZ_NAME)).strftime("%Y-%m-%d"),
        "time": datetime.fromisoformat(fixture_info["date"]).astimezone(ZoneInfo(TZ_NAME)).strftime("%H:%M"),
        "league": league.get("name", "Football"),
        "match": f"{home} - {away}",
        "bet": bet,
        "odds": round(median_odds, 2),
        "market_odds_median": round(median_odds, 2),
        "model_prob": round(model_prob, 4),
        "implied_prob": round(implied_prob, 4),
        "edge": round(edge, 4),
        "bookmakers_used": bookmakers_used,
        "line": None,
        "stake": 1,
        "reasoning": reasoning,
        "result": "pending"
    }


def build_total_candidate(bucket: str, fixture: dict, market_odds: list, model_prob: float, line: float, expected_total: float) -> dict | None:
    cfg = BUCKETS[bucket]
    median_odds = median_or_none(market_odds)
    if median_odds is None:
        return None

    bookmakers_used = len(market_odds)
    implied_prob = 1 / median_odds
    edge = model_prob - implied_prob

    if bookmakers_used < cfg["min_bookmakers"]:
        return None
    if median_odds < cfg["odds_min"] or median_odds > cfg["odds_max"]:
        return None
    if edge < cfg["min_edge"]:
        return None

    fixture_info = fixture["fixture"]
    teams = fixture["teams"]
    league = fixture["league"]
    fixture_id = fixture_info["id"]
    home = teams["home"]["name"]
    away = teams["away"]["name"]

    bet = f"Over {line}" if "over" in bucket else f"Under {line}"
    reasoning = totals_reasoning(home, away, bet, expected_total)

    return {
        "pick_id": build_pick_id(fixture_id, bucket, bet, line),
        "fixture_id": fixture_id,
        "bucket": bucket,
        "date": datetime.fromisoformat(fixture_info["date"]).astimezone(ZoneInfo(TZ_NAME)).strftime("%Y-%m-%d"),
        "time": datetime.fromisoformat(fixture_info["date"]).astimezone(ZoneInfo(TZ_NAME)).strftime("%H:%M"),
        "league": league.get("name", "Football"),
        "match": f"{home} - {away}",
        "bet": bet,
        "odds": round(median_odds, 2),
        "market_odds_median": round(median_odds, 2),
        "model_prob": round(model_prob, 4),
        "implied_prob": round(implied_prob, 4),
        "edge": round(edge, 4),
        "bookmakers_used": bookmakers_used,
        "line": line,
        "stake": 1,
        "reasoning": reasoning,
        "result": "pending"
    }


def build_btts_candidate(bucket: str, fixture: dict, market_odds: list, model_prob: float) -> dict | None:
    cfg = BUCKETS[bucket]
    median_odds = median_or_none(market_odds)
    if median_odds is None:
        return None

    bookmakers_used = len(market_odds)
    implied_prob = 1 / median_odds
    edge = model_prob - implied_prob

    if bookmakers_used < cfg["min_bookmakers"]:
        return None
    if median_odds < cfg["odds_min"] or median_odds > cfg["odds_max"]:
        return None
    if edge < cfg["min_edge"]:
        return None

    fixture_info = fixture["fixture"]
    teams = fixture["teams"]
    league = fixture["league"]
    fixture_id = fixture_info["id"]
    home = teams["home"]["name"]
    away = teams["away"]["name"]

    bet = "BTTS Yes" if bucket == "btts_yes" else "BTTS No"
    reasoning = btts_reasoning(home, away, bet, model_prob)

    return {
        "pick_id": build_pick_id(fixture_id, bucket, bet, None),
        "fixture_id": fixture_id,
        "bucket": bucket,
        "date": datetime.fromisoformat(fixture_info["date"]).astimezone(ZoneInfo(TZ_NAME)).strftime("%Y-%m-%d"),
        "time": datetime.fromisoformat(fixture_info["date"]).astimezone(ZoneInfo(TZ_NAME)).strftime("%H:%M"),
        "league": league.get("name", "Football"),
        "match": f"{home} - {away}",
        "bet": bet,
        "odds": round(median_odds, 2),
        "market_odds_median": round(median_odds, 2),
        "model_prob": round(model_prob, 4),
        "implied_prob": round(implied_prob, 4),
        "edge": round(edge, 4),
        "bookmakers_used": bookmakers_used,
        "line": None,
        "stake": 1,
        "reasoning": reasoning,
        "result": "pending"
    }


# -----------------------------
# MAIN BUILD
# -----------------------------
def build_lab_predictions() -> dict:
    if not FOOTBALL_API_KEY:
        raise RuntimeError("Missing FOOTBALL_API_KEY environment variable.")

    tz = ZoneInfo(TZ_NAME)
    now = datetime.now(tz)
    start_time = now + timedelta(hours=TIME_WINDOW_MIN_HOURS)
    end_time = now + timedelta(hours=TIME_WINDOW_MAX_HOURS)

    fixtures = fetch_fixtures_in_window(start_time, end_time, TZ_NAME)

    candidates = defaultdict(list)

    for fixture in fixtures:
        try:
            fixture_info = fixture.get("fixture", {})
            fixture_id = fixture_info.get("id")
            fixture_time = fixture_info.get("date")
            if not fixture_id or not fixture_time:
                continue

            teams = fixture.get("teams", {})
            home_team = teams.get("home", {})
            away_team = teams.get("away", {})
            home = home_team.get("name")
            away = away_team.get("name")
            home_id = home_team.get("id")
            away_id = away_team.get("id")

            if not home or not away or not home_id or not away_id:
                continue

            home_stats = get_recent_team_form(home_id)
            away_stats = get_recent_team_form(away_id)
            pred = get_fixture_prediction_data(fixture_id)
            odds = get_fixture_odds_markets(fixture_id, home, away)

            expected_home, expected_away, expected_total = calculate_expected_goals(home_stats, away_stats, pred)
            h2h_probs = get_h2h_probs(expected_home, expected_away, pred)
            total_probs = get_total_probs(expected_total)
            btts_probs = get_btts_probs(expected_home, expected_away, home_stats, away_stats)

            debug(
                f"MODEL fixture={fixture_id} {home} vs {away} | "
                f"EH={expected_home:.2f} EA={expected_away:.2f} ET={expected_total:.2f} | "
                f"H={h2h_probs['home']:.3f} D={h2h_probs['draw']:.3f} A={h2h_probs['away']:.3f}"
            )

            # H2H
            for bucket, side in [("home", "home"), ("draw", "draw"), ("away", "away")]:
                c = build_h2h_candidate(bucket, fixture, odds["h2h"][side], h2h_probs[side])
                if c:
                    candidates[bucket].append(c)
                    debug(f"CANDIDATE {bucket}: {c['match']} | odds={c['odds']} edge={c['edge']}")

            # Totals 2.5 / 3.5
            total_map = [
                ("over_2_5", odds["totals"][2.5]["over"], total_probs["over_2_5"], 2.5),
                ("under_2_5", odds["totals"][2.5]["under"], total_probs["under_2_5"], 2.5),
                ("over_3_5", odds["totals"][3.5]["over"], total_probs["over_3_5"], 3.5),
                ("under_3_5", odds["totals"][3.5]["under"], total_probs["under_3_5"], 3.5),
            ]
            for bucket, market_odds, prob, line in total_map:
                c = build_total_candidate(bucket, fixture, market_odds, prob, line, expected_total)
                if c:
                    candidates[bucket].append(c)
                    debug(f"CANDIDATE {bucket}: {c['match']} | odds={c['odds']} edge={c['edge']}")

            # BTTS
            for bucket, side in [("btts_yes", "yes"), ("btts_no", "no")]:
                c = build_btts_candidate(bucket, fixture, odds["btts"][side], btts_probs[bucket])
                if c:
                    candidates[bucket].append(c)
                    debug(f"CANDIDATE {bucket}: {c['match']} | odds={c['odds']} edge={c['edge']}")

        except Exception as e:
            debug(f"FIXTURE BUILD ERROR: {e}")

    # sort each bucket by edge desc, then odds desc
    final_buckets = {}
    for bucket_name, cfg in BUCKETS.items():
        bucket_candidates = candidates.get(bucket_name, [])
        bucket_candidates = sorted(
            bucket_candidates,
            key=lambda x: (x["edge"], x["odds"]),
            reverse=True
        )

        # avoid duplicates inside same bucket by match
        filtered = []
        used_matches = set()
        for c in bucket_candidates:
            if c["match"] in used_matches:
                continue
            filtered.append(c)
            used_matches.add(c["match"])
            if len(filtered) >= cfg["limit"]:
                break

        final_buckets[bucket_name] = filtered
        debug(f"FINAL BUCKET {bucket_name}: {len(filtered)} picks")

    return {
        "generated_at": datetime.now(tz).isoformat(),
        "model": "AI77 Lab Buckets v1",
        "stake_mode": "flat_1_unit",
        "source": "API-Football",
        "timezone": TZ_NAME,
        "window_hours": {
            "min": TIME_WINDOW_MIN_HOURS,
            "max": TIME_WINDOW_MAX_HOURS
        },
        "buckets": final_buckets
    }


# -----------------------------
# RESULTS APPEND
# -----------------------------
def append_to_lab_results(predictions_payload: dict):
    history = load_json_file(LAB_RESULTS_FILE, [])
    if not isinstance(history, list):
        history = []

    existing_ids = {item.get("pick_id") for item in history if isinstance(item, dict)}

    added = 0
    for bucket, picks in predictions_payload.get("buckets", {}).items():
        for pick in picks:
            if pick["pick_id"] in existing_ids:
                continue
            history.append(pick.copy())
            existing_ids.add(pick["pick_id"])
            added += 1

    save_json_file(LAB_RESULTS_FILE, history)
    debug(f"RESULTS APPEND: added={added} total_history={len(history)}")


# -----------------------------
# MAIN
# -----------------------------
def main():
    predictions_payload = build_lab_predictions()
    save_json_file(LAB_PREDICTIONS_FILE, predictions_payload)
    append_to_lab_results(predictions_payload)

    total_picks = sum(len(v) for v in predictions_payload["buckets"].values())
    debug(f"SAVED {LAB_PREDICTIONS_FILE} with {total_picks} picks.")
    debug(f"SAVED/UPDATED {LAB_RESULTS_FILE}.")


if __name__ == "__main__":
    main()
