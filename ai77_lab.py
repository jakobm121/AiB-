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

TIME_WINDOW_MIN_HOURS = 0
TIME_WINDOW_MAX_HOURS = 6
REQUEST_TIMEOUT = 20

MAX_PICKS_PER_FIXTURE = 3

MIN_LEAGUE_LEARNING_SAMPLE = 8
FULL_LEAGUE_LEARNING_SAMPLE = 30
MAX_LEAGUE_LEARNING_ADJUSTMENT = 0.04

BUCKETS = {
    "home": {"limit": 5, "min_edge": 0.018, "min_bookmakers": 3, "odds_min": 1.45, "odds_max": 4.80},
    "draw": {"limit": 3, "min_edge": 0.020, "min_bookmakers": 3, "odds_min": 2.60, "odds_max": 4.80},
    "away": {"limit": 5, "min_edge": 0.018, "min_bookmakers": 3, "odds_min": 1.45, "odds_max": 4.80},
    "over_2_5": {"limit": 5, "min_edge": 0.022, "min_bookmakers": 3, "odds_min": 1.50, "odds_max": 4.80},
    "under_2_5": {"limit": 5, "min_edge": 0.022, "min_bookmakers": 3, "odds_min": 1.50, "odds_max": 4.80},
    "btts_yes": {"limit": 5, "min_edge": 0.024, "min_bookmakers": 4, "odds_min": 1.50, "odds_max": 4.80},
    "btts_no": {"limit": 5, "min_edge": 0.024, "min_bookmakers": 4, "odds_min": 1.50, "odds_max": 4.80},
    "over_3_5": {"limit": 5, "min_edge": 0.026, "min_bookmakers": 3, "odds_min": 1.65, "odds_max": 5.50},
    "under_3_5": {"limit": 5, "min_edge": 0.024, "min_bookmakers": 3, "odds_min": 1.30, "odds_max": 3.80},
}

VALID_STATUSES = {"NS", "TBD", "PST"}

TEAM_FORM_CACHE = {}
FIXTURE_PRED_CACHE = {}
FIXTURE_ODDS_CACHE = {}

LEAGUE_BASELINES = {
    "default": {"goals": 2.45, "draw": 0.27, "home_adv": 0.16, "strength": 1.00, "variance": 1.00},
    "suomen cup": {"goals": 2.85, "draw": 0.24, "home_adv": 0.12, "strength": 0.94, "variance": 1.08},
    "liga 1": {"goals": 2.35, "draw": 0.29, "home_adv": 0.17, "strength": 0.98, "variance": 0.96},
    "liga de ascenso": {"goals": 2.30, "draw": 0.30, "home_adv": 0.16, "strength": 0.95, "variance": 0.95},
    "championship": {"goals": 2.42, "draw": 0.28, "home_adv": 0.17, "strength": 1.03, "variance": 0.98},
    "league one": {"goals": 2.48, "draw": 0.27, "home_adv": 0.16, "strength": 1.00, "variance": 1.00},
}

QUALITY_WEIGHTS = {
    "edge": 42,
    "bookmakers": 14,
    "odds_fit": 10,
    "confidence": 22,
    "market_alignment": 12,
}


def football_headers():
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
    return float(statistics.median(cleaned))


def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def normalize_name(text):
    return " ".join(str(text or "").strip().lower().split())


def poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def build_pick_id(fixture_id, bucket, bet, line):
    base = f"{fixture_id}|{bucket}|{bet}|{line}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def debug(msg):
    print(msg)


def api_get(endpoint, params):
    url = f"{FOOTBALL_URL}/{endpoint}"
    res = requests.get(url, headers=football_headers(), params=params, timeout=REQUEST_TIMEOUT)
    res.raise_for_status()
    return res.json()


def get_league_baseline(league_name):
    key = normalize_name(league_name)
    return LEAGUE_BASELINES.get(key, LEAGUE_BASELINES["default"])


def soft_market_blend(model_prob, market_odds, strength=0.18):
    median_odds = median_or_none(market_odds)
    if median_odds is None or median_odds <= 1:
        return model_prob
    implied = 1.0 / median_odds
    return (model_prob * (1 - strength)) + (implied * strength)


def is_settled_result(result_value):
    return result_value in {"win", "loss", "storno"}


def settled_profit_for_pick(pick):
    result_value = pick.get("result")
    odds = safe_float(pick.get("odds"), 0) or 0

    if result_value == "win":
        return odds - 1.0
    if result_value == "loss":
        return -1.0
    if result_value == "storno":
        return 0.0
    return None


def build_league_learning_table(history):
    league_bucket = defaultdict(lambda: defaultdict(lambda: {
        "settled_picks": 0,
        "wins": 0,
        "losses": 0,
        "storno": 0,
        "profit": 0.0
    }))

    for item in history:
        if not isinstance(item, dict):
            continue

        result_value = item.get("result")
        if not is_settled_result(result_value):
            continue

        league_name = normalize_name(item.get("league"))
        bucket = item.get("bucket")

        if not league_name or not bucket:
            continue

        profit = settled_profit_for_pick(item)
        if profit is None:
            continue

        row = league_bucket[league_name][bucket]
        row["settled_picks"] += 1
        row["profit"] += profit

        if result_value == "win":
            row["wins"] += 1
        elif result_value == "loss":
            row["losses"] += 1
        elif result_value == "storno":
            row["storno"] += 1

    final_table = defaultdict(dict)

    for league_name, bucket_map in league_bucket.items():
        for bucket, row in bucket_map.items():
            settled = row["settled_picks"]
            if settled <= 0:
                continue

            staked = settled - row["storno"]
            staked = max(staked, 1)

            roi = row["profit"] / staked
            hit_rate = row["wins"] / max((row["wins"] + row["losses"]), 1)

            sample_weight = clamp(
                (settled - MIN_LEAGUE_LEARNING_SAMPLE) / max((FULL_LEAGUE_LEARNING_SAMPLE - MIN_LEAGUE_LEARNING_SAMPLE), 1),
                0.0,
                1.0
            )

            roi_component = clamp(roi / 0.25, -1.0, 1.0)
            hit_component = clamp((hit_rate - 0.50) / 0.20, -1.0, 1.0)

            blended_signal = (roi_component * 0.70) + (hit_component * 0.30)
            adjustment = blended_signal * sample_weight * MAX_LEAGUE_LEARNING_ADJUSTMENT
            adjustment = clamp(adjustment, -MAX_LEAGUE_LEARNING_ADJUSTMENT, MAX_LEAGUE_LEARNING_ADJUSTMENT)

            final_table[league_name][bucket] = {
                "settled_picks": settled,
                "wins": row["wins"],
                "losses": row["losses"],
                "storno": row["storno"],
                "profit": round(row["profit"], 4),
                "roi": round(roi, 4),
                "hit_rate": round(hit_rate, 4),
                "learning_weight": round(sample_weight, 4),
                "adjustment": round(adjustment, 4),
            }

    return final_table


def get_league_bucket_adjustment(league_learning, league_name, bucket):
    league_key = normalize_name(league_name)
    row = league_learning.get(league_key, {}).get(bucket)
    if not row:
        return 0.0
    return safe_float(row.get("adjustment"), 0.0) or 0.0


def apply_league_learning(model_prob, league_learning, league_name, bucket):
    adjustment = get_league_bucket_adjustment(league_learning, league_name, bucket)
    return clamp(model_prob + adjustment, 0.02, 0.98)


def debug_league_learning(league_learning):
    for league_name, buckets in league_learning.items():
        for bucket, row in buckets.items():
            debug(
                f"LEARNING {league_name} | {bucket} | settled={row['settled_picks']} "
                f"roi={row['roi']} hit={row['hit_rate']} adj={row['adjustment']}"
            )


def calculate_confidence_score(model_prob, implied_prob, bookmakers_used, edge):
    edge_component = clamp(edge / 0.12, 0.0, 1.0) * 45
    separation_component = clamp(abs(model_prob - 0.5) / 0.30, 0.0, 1.0) * 18
    bookmaker_component = clamp(bookmakers_used / 12.0, 0.0, 1.0) * 20
    pricing_component = clamp((model_prob / max(implied_prob, 0.01)) - 1.0, 0.0, 1.0) * 17
    score = edge_component + separation_component + bookmaker_component + pricing_component
    return round(clamp(score, 1.0, 99.0), 1)


def calculate_quality_score(bucket, edge, bookmakers_used, odds, confidence_score, model_prob, implied_prob):
    cfg = BUCKETS[bucket]

    edge_score = clamp(edge / max(cfg["min_edge"] * 2.4, 0.01), 0.0, 1.0)
    bookmaker_score = clamp(bookmakers_used / 12.0, 0.0, 1.0)

    odds_mid = (cfg["odds_min"] + cfg["odds_max"]) / 2
    odds_span = max((cfg["odds_max"] - cfg["odds_min"]) / 2, 0.01)
    odds_fit = 1.0 - min(abs(odds - odds_mid) / odds_span, 1.0)

    confidence_component = clamp(confidence_score / 100.0, 0.0, 1.0)
    market_alignment = 1.0 - clamp(abs(model_prob - implied_prob) / 0.40, 0.0, 1.0)

    score = (
        edge_score * QUALITY_WEIGHTS["edge"] +
        bookmaker_score * QUALITY_WEIGHTS["bookmakers"] +
        odds_fit * QUALITY_WEIGHTS["odds_fit"] +
        confidence_component * QUALITY_WEIGHTS["confidence"] +
        market_alignment * QUALITY_WEIGHTS["market_alignment"]
    )

    return round(clamp(score, 1.0, 99.0), 1)


def get_bucket_family(bucket):
    if bucket in {"home", "draw", "away"}:
        return "h2h"
    if bucket in {"over_2_5", "under_2_5", "over_3_5", "under_3_5"}:
        return "totals"
    if bucket in {"btts_yes", "btts_no"}:
        return "btts"
    return "other"


def candidate_conflicts(existing_pick, new_pick):
    if existing_pick["fixture_id"] != new_pick["fixture_id"]:
        return False

    existing_bucket = existing_pick["bucket"]
    new_bucket = new_pick["bucket"]

    existing_family = get_bucket_family(existing_bucket)
    new_family = get_bucket_family(new_bucket)

    if existing_family == "h2h" and new_family == "h2h":
        return True

    correlated_pairs = {
        tuple(sorted(("under_2_5", "btts_no"))),
        tuple(sorted(("over_2_5", "btts_yes"))),
    }

    pair = tuple(sorted([existing_bucket, new_bucket]))
    return pair in correlated_pairs


def fetch_fixtures_in_window(start_time, end_time, tz_name):
    fixtures = []
    current_date = start_time.date()
    end_date = end_time.date()

    while current_date <= end_date:
        try:
            data = api_get("fixtures", {"date": current_date.strftime("%Y-%m-%d"), "timezone": tz_name})
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


def get_recent_team_form(team_id):
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
        home_scored, home_conceded, away_scored, away_conceded = [], [], [], []
        all_scored, all_conceded = [], []
        over25 = over35 = btts = wins = draws = losses = valid_games = 0

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
                scored, conceded = gh, ga
                home_scored.append(gh)
                home_conceded.append(ga)
                if gh > ga:
                    wins += 1
                elif gh == ga:
                    draws += 1
                else:
                    losses += 1
            elif away_team.get("id") == team_id:
                scored, conceded = ga, gh
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
        return result
    except Exception:
        TEAM_FORM_CACHE[team_id] = fallback
        return fallback


def get_fixture_prediction_data(fixture_id):
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
        return result
    except Exception:
        FIXTURE_PRED_CACHE[fixture_id] = result
        return result


def is_h2h_bet_name(name):
    return normalize_name(name) in {"match winner", "1x2", "winner", "fulltime result", "result", "match result"}


def is_total_bet_name(name):
    n = normalize_name(name)
    return "over/under" in n or "goals over/under" in n or "over under" in n or "total goals" in n


def is_btts_bet_name(name):
    n = normalize_name(name)
    return "both teams" in n or "btts" in n or "both team" in n


def get_fixture_odds_markets(fixture_id, home_name, away_name):
    if fixture_id in FIXTURE_ODDS_CACHE:
        return FIXTURE_ODDS_CACHE[fixture_id]

    result = {
        "h2h": {"home": [], "draw": [], "away": []},
        "totals": {2.5: {"over": [], "under": []}, 3.5: {"over": [], "under": []}},
        "btts": {"yes": [], "no": []},
    }

    try:
        data = api_get("odds", {"fixture": fixture_id})
        response = data.get("response", [])
        if not response:
            FIXTURE_ODDS_CACHE[fixture_id] = result
            return result

        seen_bookmaker_market = set()

        for item in response:
            for bookmaker in item.get("bookmakers", []):
                bookmaker_id = bookmaker.get("id")
                for bet in bookmaker.get("bets", []):
                    bet_name = bet.get("name", "")
                    values = bet.get("values", [])

                    if is_h2h_bet_name(bet_name):
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
                            key = (bookmaker_id, "h2h", mapped)
                            if key in seen_bookmaker_market:
                                continue
                            seen_bookmaker_market.add(key)
                            result["h2h"][mapped].append(odd)

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
                            side = "over" if side_raw == "over" else ("under" if side_raw == "under" else None)
                            if not side:
                                continue
                            key = (bookmaker_id, "totals", line, side)
                            if key in seen_bookmaker_market:
                                continue
                            seen_bookmaker_market.add(key)
                            result["totals"][line][side].append(odd)

                    elif is_btts_bet_name(bet_name):
                        for v in values:
                            value_name = str(v.get("value", "")).strip().lower()
                            odd = safe_float(v.get("odd"))
                            if odd is None or value_name not in {"yes", "no"}:
                                continue
                            key = (bookmaker_id, "btts", value_name)
                            if key in seen_bookmaker_market:
                                continue
                            seen_bookmaker_market.add(key)
                            result["btts"][value_name].append(odd)

        FIXTURE_ODDS_CACHE[fixture_id] = result
        return result
    except Exception:
        FIXTURE_ODDS_CACHE[fixture_id] = result
        return result


def calculate_expected_goals(home_stats, away_stats, pred, league_name):
    baseline = get_league_baseline(league_name)
    league_goals = baseline["goals"]
    home_adv = baseline["home_adv"]
    league_strength = baseline["strength"]
    league_variance = baseline["variance"]

    home_attack = (home_stats["home_scored_avg"] * 0.60) + (away_stats["away_conceded_avg"] * 0.40)
    away_attack = (away_stats["away_scored_avg"] * 0.60) + (home_stats["home_conceded_avg"] * 0.40)

    expected_home = home_attack + home_adv
    expected_away = away_attack

    home_form_delta = home_stats["wins_rate"] - home_stats["losses_rate"]
    away_form_delta = away_stats["wins_rate"] - away_stats["losses_rate"]

    expected_home += home_form_delta * 0.11
    expected_away += away_form_delta * 0.11

    if home_stats["overall_scored_avg"] < 0.95:
        expected_home -= 0.08
    if away_stats["overall_scored_avg"] < 0.95:
        expected_away -= 0.08

    if home_stats["over25_rate"] >= 0.60 and away_stats["over25_rate"] >= 0.60:
        expected_home += 0.06
        expected_away += 0.06

    if home_stats["over25_rate"] <= 0.35 and away_stats["over25_rate"] <= 0.35:
        expected_home -= 0.06
        expected_away -= 0.06

    current_total = expected_home + expected_away
    if current_total > 0:
        scale = league_goals / current_total
        expected_home *= (0.80 + 0.20 * scale)
        expected_away *= (0.80 + 0.20 * scale)

    expected_home *= league_strength
    expected_away *= league_strength

    pred_home = pred.get("goals_home")
    pred_away = pred.get("goals_away")
    if pred_home is not None and pred_away is not None:
        pred_weight = 0.16 if league_variance < 1.0 else 0.20
        expected_home = (expected_home * (1 - pred_weight)) + (pred_home * pred_weight)
        expected_away = (expected_away * (1 - pred_weight)) + (pred_away * pred_weight)

    expected_home = clamp(expected_home, 0.28, 2.90)
    expected_away = clamp(expected_away, 0.28, 2.80)

    return expected_home, expected_away, expected_home + expected_away


def get_h2h_probs(expected_home, expected_away, pred, league_name):
    baseline = get_league_baseline(league_name)
    max_goals = 8
    home_win = draw = away_win = 0.0

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
        return {"home": 0.40, "draw": baseline["draw"], "away": 0.33}

    home_win /= total
    draw /= total
    away_win /= total

    gap = abs(expected_home - expected_away)
    target_draw = baseline["draw"]

    if gap < 0.10:
        draw += 0.020
    elif gap < 0.18:
        draw += 0.010
    elif gap > 0.55:
        draw -= 0.020
    elif gap > 0.40:
        draw -= 0.012

    draw = draw * 0.86 + target_draw * 0.14

    ph = pred.get("percent_home")
    pd = pred.get("percent_draw")
    pa = pred.get("percent_away")

    if ph is not None and pd is not None and pa is not None:
        ph /= 100.0
        pd /= 100.0
        pa /= 100.0
        sum_pred = ph + pd + pa
        if 0.95 < sum_pred < 1.05:
            home_win = home_win * 0.85 + ph * 0.15
            draw = draw * 0.88 + pd * 0.12
            away_win = away_win * 0.85 + pa * 0.15

    home_win = clamp(home_win, 0.16, 0.68)
    draw = clamp(draw, 0.11, 0.34)
    away_win = clamp(away_win, 0.16, 0.68)

    total = home_win + draw + away_win
    return {
        "home": home_win / total,
        "draw": draw / total,
        "away": away_win / total
    }


def get_total_probs(expected_total, league_name):
    baseline = get_league_baseline(league_name)
    variance = baseline["variance"]

    max_goals = 10
    over25 = over35 = 0.0
    adjusted_total = expected_total * variance

    for g in range(max_goals + 1):
        p = poisson_pmf(g, adjusted_total)
        if g >= 3:
            over25 += p
        if g >= 4:
            over35 += p

    under25 = 1 - over25
    under35 = 1 - over35

    return {
        "over_2_5": clamp(over25, 0.08, 0.82),
        "under_2_5": clamp(under25, 0.08, 0.82),
        "over_3_5": clamp(over35, 0.04, 0.70),
        "under_3_5": clamp(under35, 0.18, 0.88),
    }


def get_btts_probs(expected_home, expected_away, home_stats, away_stats, league_name):
    baseline = get_league_baseline(league_name)
    variance = baseline["variance"]

    p_home_scores = 1 - math.exp(-expected_home)
    p_away_scores = 1 - math.exp(-expected_away)

    btts_yes = p_home_scores * p_away_scores
    form_btts = (home_stats["btts_rate"] + away_stats["btts_rate"]) / 2

    blend_weight = 0.22 if variance > 1.0 else 0.18
    btts_yes = (btts_yes * (1 - blend_weight)) + (form_btts * blend_weight)

    if home_stats["overall_scored_avg"] < 0.95 or away_stats["overall_scored_avg"] < 0.95:
        btts_yes -= 0.03

    if home_stats["overall_scored_avg"] > 1.60 and away_stats["overall_scored_avg"] > 1.40:
        btts_yes += 0.025

    btts_yes = clamp(btts_yes, 0.16, 0.80)

    return {"btts_yes": btts_yes, "btts_no": 1 - btts_yes}


def h2h_reasoning(home, away, bet):
    if bet == home:
        return f"{home} grades better in the home-side model than the market median implies. The edge is modest but playable, with a stronger projected control profile than the current price suggests."
    if bet == away:
        return f"{away} looks slightly undervalued away from home. The model sees a better win probability than the market median, which keeps this as a live value side."
    return "This matchup projects fairly balanced, which is exactly why the draw price becomes interesting. It remains a variance-heavy market, but the median line still leaves measurable value."


def totals_reasoning(home, away, bet):
    if "Over" in bet:
        return f"{home} vs {away} projects with enough scoring volume to justify an aggressive totals angle. The expected goals profile supports the market line being slightly too low."
    return f"{home} vs {away} projects as a more controlled scoring environment than the market median suggests. The expected goals profile supports a lower-event outcome."


def btts_reasoning(home, away, bet):
    if bet == "BTTS Yes":
        return f"Both teams rate with enough attacking involvement to keep a two-sided scoring game live. Recent BTTS tendencies and projected scoring output both support the Yes side."
    return f"The matchup does not rate as strong enough for reliable two-sided scoring. At least one attack looks weaker than the market median is pricing."


def build_generic_candidate(bucket, fixture, market_odds, model_prob, bet, line, reasoning):
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

    confidence_score = calculate_confidence_score(model_prob, implied_prob, bookmakers_used, edge)
    quality_score = calculate_quality_score(
        bucket=bucket,
        edge=edge,
        bookmakers_used=bookmakers_used,
        odds=median_odds,
        confidence_score=confidence_score,
        model_prob=model_prob,
        implied_prob=implied_prob
    )

    fixture_info = fixture["fixture"]
    teams = fixture["teams"]
    league = fixture["league"]
    fixture_id = fixture_info["id"]

    local_dt = datetime.fromisoformat(fixture_info["date"]).astimezone(ZoneInfo(TZ_NAME))

    return {
        "pick_id": build_pick_id(fixture_id, bucket, bet, line),
        "fixture_id": fixture_id,
        "bucket": bucket,
        "date": local_dt.strftime("%Y-%m-%d"),
        "time": local_dt.strftime("%H:%M"),
        "league": league.get("name", "Football"),
        "match": f"{teams['home']['name']} - {teams['away']['name']}",
        "bet": bet,
        "odds": round(median_odds, 2),
        "market_odds_median": round(median_odds, 2),
        "model_prob": round(model_prob, 4),
        "implied_prob": round(implied_prob, 4),
        "edge": round(edge, 4),
        "bookmakers_used": bookmakers_used,
        "line": line,
        "stake": 1,
        "confidence_score": confidence_score,
        "quality_score": quality_score,
        "reasoning": reasoning,
        "result": "pending"
    }


def build_lab_predictions():
    if not FOOTBALL_API_KEY:
        raise RuntimeError("Missing FOOTBALL_API_KEY environment variable.")

    tz = ZoneInfo(TZ_NAME)
    now = datetime.now(tz)
    start_time = now + timedelta(hours=TIME_WINDOW_MIN_HOURS)
    end_time = now + timedelta(hours=TIME_WINDOW_MAX_HOURS)

    history = load_json_file(LAB_RESULTS_FILE, [])
    if not isinstance(history, list):
        history = []

    league_learning = build_league_learning_table(history)
    debug(f"LEAGUE LEARNING LEAGUES: {len(league_learning)}")
    debug_league_learning(league_learning)

    fixtures = fetch_fixtures_in_window(start_time, end_time, TZ_NAME)
    candidates = defaultdict(list)

    for fixture in fixtures:
        try:
            fixture_id = fixture.get("fixture", {}).get("id")
            teams = fixture.get("teams", {})
            league = fixture.get("league", {})
            league_name = league.get("name", "Football")

            home = teams.get("home", {}).get("name")
            away = teams.get("away", {}).get("name")
            home_id = teams.get("home", {}).get("id")
            away_id = teams.get("away", {}).get("id")

            if not fixture_id or not home or not away or not home_id or not away_id:
                continue

            home_stats = get_recent_team_form(home_id)
            away_stats = get_recent_team_form(away_id)
            pred = get_fixture_prediction_data(fixture_id)
            odds = get_fixture_odds_markets(fixture_id, home, away)

            expected_home, expected_away, expected_total = calculate_expected_goals(home_stats, away_stats, pred, league_name)

            h2h_probs = get_h2h_probs(expected_home, expected_away, pred, league_name)
            total_probs = get_total_probs(expected_total, league_name)
            btts_probs = get_btts_probs(expected_home, expected_away, home_stats, away_stats, league_name)

            h2h_probs["home"] = soft_market_blend(h2h_probs["home"], odds["h2h"]["home"], strength=0.08)
            h2h_probs["draw"] = soft_market_blend(h2h_probs["draw"], odds["h2h"]["draw"], strength=0.06)
            h2h_probs["away"] = soft_market_blend(h2h_probs["away"], odds["h2h"]["away"], strength=0.08)

            total_probs["over_2_5"] = soft_market_blend(total_probs["over_2_5"], odds["totals"][2.5]["over"], strength=0.16)
            total_probs["under_2_5"] = soft_market_blend(total_probs["under_2_5"], odds["totals"][2.5]["under"], strength=0.16)
            total_probs["over_3_5"] = soft_market_blend(total_probs["over_3_5"], odds["totals"][3.5]["over"], strength=0.14)
            total_probs["under_3_5"] = soft_market_blend(total_probs["under_3_5"], odds["totals"][3.5]["under"], strength=0.14)

            btts_probs["btts_yes"] = soft_market_blend(btts_probs["btts_yes"], odds["btts"]["yes"], strength=0.15)
            btts_probs["btts_no"] = soft_market_blend(btts_probs["btts_no"], odds["btts"]["no"], strength=0.15)

            h2h_probs["home"] = apply_league_learning(h2h_probs["home"], league_learning, league_name, "home")
            h2h_probs["draw"] = apply_league_learning(h2h_probs["draw"], league_learning, league_name, "draw")
            h2h_probs["away"] = apply_league_learning(h2h_probs["away"], league_learning, league_name, "away")

            total_probs["over_2_5"] = apply_league_learning(total_probs["over_2_5"], league_learning, league_name, "over_2_5")
            total_probs["under_2_5"] = apply_league_learning(total_probs["under_2_5"], league_learning, league_name, "under_2_5")
            total_probs["over_3_5"] = apply_league_learning(total_probs["over_3_5"], league_learning, league_name, "over_3_5")
            total_probs["under_3_5"] = apply_league_learning(total_probs["under_3_5"], league_learning, league_name, "under_3_5")

            btts_probs["btts_yes"] = apply_league_learning(btts_probs["btts_yes"], league_learning, league_name, "btts_yes")
            btts_probs["btts_no"] = apply_league_learning(btts_probs["btts_no"], league_learning, league_name, "btts_no")

            h = build_generic_candidate("home", fixture, odds["h2h"]["home"], h2h_probs["home"], home, None, h2h_reasoning(home, away, home))
            d = build_generic_candidate("draw", fixture, odds["h2h"]["draw"], h2h_probs["draw"], "Draw", None, h2h_reasoning(home, away, "Draw"))
            a = build_generic_candidate("away", fixture, odds["h2h"]["away"], h2h_probs["away"], away, None, h2h_reasoning(home, away, away))
            if h:
                candidates["home"].append(h)
            if d:
                candidates["draw"].append(d)
            if a:
                candidates["away"].append(a)

            o25 = build_generic_candidate("over_2_5", fixture, odds["totals"][2.5]["over"], total_probs["over_2_5"], "Over 2.5", 2.5, totals_reasoning(home, away, "Over 2.5"))
            u25 = build_generic_candidate("under_2_5", fixture, odds["totals"][2.5]["under"], total_probs["under_2_5"], "Under 2.5", 2.5, totals_reasoning(home, away, "Under 2.5"))
            o35 = build_generic_candidate("over_3_5", fixture, odds["totals"][3.5]["over"], total_probs["over_3_5"], "Over 3.5", 3.5, totals_reasoning(home, away, "Over 3.5"))
            u35 = build_generic_candidate("under_3_5", fixture, odds["totals"][3.5]["under"], total_probs["under_3_5"], "Under 3.5", 3.5, totals_reasoning(home, away, "Under 3.5"))
            if o25:
                candidates["over_2_5"].append(o25)
            if u25:
                candidates["under_2_5"].append(u25)
            if o35:
                candidates["over_3_5"].append(o35)
            if u35:
                candidates["under_3_5"].append(u35)

            by = build_generic_candidate("btts_yes", fixture, odds["btts"]["yes"], btts_probs["btts_yes"], "BTTS Yes", None, btts_reasoning(home, away, "BTTS Yes"))
            bn = build_generic_candidate("btts_no", fixture, odds["btts"]["no"], btts_probs["btts_no"], "BTTS No", None, btts_reasoning(home, away, "BTTS No"))
            if by:
                candidates["btts_yes"].append(by)
            if bn:
                candidates["btts_no"].append(bn)

        except Exception as e:
            debug(f"FIXTURE BUILD ERROR: {e}")

    selected_by_bucket = {bucket_name: [] for bucket_name in BUCKETS}
    selected_all = []
    fixture_pick_counts = defaultdict(int)

    ordered_bucket_candidates = {
        bucket_name: sorted(
            candidates.get(bucket_name, []),
            key=lambda x: (x["quality_score"], x["confidence_score"], x["edge"], x["odds"]),
            reverse=True
        )
        for bucket_name in BUCKETS
    }

    for bucket_name, cfg in BUCKETS.items():
        for candidate in ordered_bucket_candidates[bucket_name]:
            if len(selected_by_bucket[bucket_name]) >= cfg["limit"]:
                break

            fixture_id = candidate["fixture_id"]
            if fixture_pick_counts[fixture_id] >= MAX_PICKS_PER_FIXTURE:
                continue

            conflict = any(candidate_conflicts(existing, candidate) for existing in selected_all)
            if conflict:
                continue

            selected_by_bucket[bucket_name].append(candidate)
            selected_all.append(candidate)
            fixture_pick_counts[fixture_id] += 1

    for bucket_name, cfg in BUCKETS.items():
        already_ids = {p["pick_id"] for p in selected_by_bucket[bucket_name]}
        for candidate in ordered_bucket_candidates[bucket_name]:
            if len(selected_by_bucket[bucket_name]) >= cfg["limit"]:
                break

            if candidate["pick_id"] in already_ids:
                continue

            fixture_id = candidate["fixture_id"]
            if fixture_pick_counts[fixture_id] >= (MAX_PICKS_PER_FIXTURE + 1):
                continue

            selected_by_bucket[bucket_name].append(candidate)
            selected_all.append(candidate)
            fixture_pick_counts[fixture_id] += 1
            already_ids.add(candidate["pick_id"])

    for bucket_name in BUCKETS:
        debug(
            f"FINAL BUCKET {bucket_name}: {len(selected_by_bucket[bucket_name])} picks "
            f"(raw candidates: {len(candidates.get(bucket_name, []))})"
        )

    return {
        "generated_at": datetime.now(tz).isoformat(),
        "model": "AI77 Lab Buckets v3 + auto-learning",
        "stake_mode": "flat_1_unit",
        "source": "API-Football",
        "timezone": TZ_NAME,
        "window_hours": {"min": TIME_WINDOW_MIN_HOURS, "max": TIME_WINDOW_MAX_HOURS},
        "learning": {
            "enabled": True,
            "min_sample": MIN_LEAGUE_LEARNING_SAMPLE,
            "full_sample": FULL_LEAGUE_LEARNING_SAMPLE,
            "max_adjustment": MAX_LEAGUE_LEARNING_ADJUSTMENT,
            "league_count": len(league_learning)
        },
        "buckets": selected_by_bucket
    }


def append_to_lab_results(predictions_payload):
    history = load_json_file(LAB_RESULTS_FILE, [])
    if not isinstance(history, list):
        history = []

    existing_ids = {item.get("pick_id") for item in history if isinstance(item, dict)}

    for picks in predictions_payload.get("buckets", {}).values():
        for pick in picks:
            if pick["pick_id"] in existing_ids:
                continue
            history.append(pick.copy())
            existing_ids.add(pick["pick_id"])

    save_json_file(LAB_RESULTS_FILE, history)


def main():
    payload = build_lab_predictions()
    save_json_file(LAB_PREDICTIONS_FILE, payload)
    append_to_lab_results(payload)
    total_picks = sum(len(v) for v in payload["buckets"].values())
    debug(f"SAVED {LAB_PREDICTIONS_FILE} with {total_picks} picks.")


if __name__ == "__main__":
    main()
