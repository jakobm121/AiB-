import json
import math
import os
import statistics
import hashlib
import time
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

HOCKEY_API_KEY = os.getenv("HOCKEY_API_KEY")
HOCKEY_URL = "https://v1.hockey.api-sports.io"
TZ_NAME = "Europe/Ljubljana"
PRED_FILE = "hockey/hockey_predictions.json"
RESULTS_FILE = "hockey/hockey_results.json"
REQUEST_TIMEOUT = 20
TIME_WINDOW_MIN_HOURS = 0
TIME_WINDOW_MAX_HOURS = 10
MAX_GAMES_TO_PROCESS = 10

BUCKETS = {
    "over_main_total": {"limit": 6, "min_edge_prob": 0.035, "min_goal_edge": 0.45, "min_bookmakers": 3, "odds_min": 1.70, "odds_max": 2.30},
    "under_main_total": {"limit": 6, "min_edge_prob": 0.035, "min_goal_edge": 0.45, "min_bookmakers": 3, "odds_min": 1.70, "odds_max": 2.30},
}

TEAM_FORM_CACHE = {}
ODDS_CACHE = {}
FINAL_STATUSES = {"FT", "AOT", "AP", "PEN", "FINISHED"}
PREGAME_STATUSES = {"NS", "TBD", "PST", "POSTP", "SCHEDULED"}
LEAGUE_BASELINES = {
    "default": 5.40,
    "nhl": 6.05,
    "ahl": 6.15,
    "liiga": 5.45,
    "shl": 5.25,
    "del": 6.10,
    "national league": 5.85,
    "ice hockey league": 5.95,
    "allsvenskan": 5.35,
    "extraliga": 5.55,
    "world championship": 5.80,
}


def headers():
    return {"x-apisports-key": HOCKEY_API_KEY}


def debug(msg):
    print(msg)


def safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def median_or_none(values):
    cleaned = [safe_float(v) for v in values]
    cleaned = [v for v in cleaned if v is not None]
    return float(statistics.median(cleaned)) if cleaned else None


def normalize_name(text):
    return " ".join(str(text or "").strip().lower().split())


def build_pick_id(game_id, bucket, bet, line):
    raw = f"{game_id}|{bucket}|{bet}|{line}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    os.makedirs("hockey", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def api_get(endpoint, params, retries=3):
    url = f"{HOCKEY_URL}/{endpoint}"
    for attempt in range(retries):
        res = requests.get(url, headers=headers(), params=params, timeout=REQUEST_TIMEOUT)
        if res.status_code == 429:
            time.sleep(2 * (attempt + 1))
            continue
        res.raise_for_status()
        return res.json()
    raise RuntimeError(f"API rate-limited: {endpoint} {params}")


def get_game_id(game):
    return game.get("game", {}).get("id")


def get_game_dt(game):
    raw = game.get("game", {}).get("date")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def get_status(game):
    return str(game.get("game", {}).get("status", {}).get("short", "")).upper()


def get_team_id(game, side):
    return game.get("teams", {}).get(side, {}).get("id")


def get_team_name(game, side):
    return game.get("teams", {}).get(side, {}).get("name")


def get_score(game, side):
    scores = game.get("scores", {})
    goals = game.get("goals", {})
    return safe_int(scores.get(side, goals.get(side)))


def get_league_name(game):
    return game.get("league", {}).get("name", "Hockey")


def get_baseline(league_name):
    return LEAGUE_BASELINES.get(normalize_name(league_name), LEAGUE_BASELINES["default"])


def fetch_games_in_window(start_time, end_time):
    games = []
    current_date = start_time.date()
    end_date = end_time.date()
    while current_date <= end_date:
        try:
            data = api_get("games", {"date": current_date.strftime("%Y-%m-%d"), "timezone": TZ_NAME})
            daily = data.get("response", [])
            debug(f"GAMES {current_date}: {len(daily)}")
            games.extend(daily)
        except Exception as e:
            debug(f"GAMES ERROR {current_date}: {e}")
        current_date += timedelta(days=1)

    filtered = []
    tz = ZoneInfo(TZ_NAME)
    for game in games:
        dt = get_game_dt(game)
        if not dt:
            continue
        local_dt = dt.astimezone(tz)
        if local_dt < start_time or local_dt > end_time:
            continue
        if get_status(game) not in PREGAME_STATUSES:
            continue
        if not get_game_id(game) or not get_team_id(game, "home") or not get_team_id(game, "away"):
            continue
        filtered.append(game)
    debug(f"FILTERED GAMES: {len(filtered)}")
    return filtered


def summarize_team_games(team_id):
    if team_id in TEAM_FORM_CACHE:
        return TEAM_FORM_CACHE[team_id]

    fallback = {
        "overall_scored_avg": 2.70,
        "overall_conceded_avg": 2.70,
        "home_scored_avg": 2.80,
        "home_conceded_avg": 2.60,
        "away_scored_avg": 2.60,
        "away_conceded_avg": 2.80,
        "over_5_5_rate": 0.47,
    }

    try:
        data = api_get("games", {"team": team_id, "last": 8})
        response = data.get("response", [])
        scored_all, conceded_all = [], []
        scored_home, conceded_home = [], []
        scored_away, conceded_away = [], []
        over55 = valid = 0

        for game in response:
            if get_status(game) not in FINAL_STATUSES:
                continue
            gh, ga = get_score(game, "home"), get_score(game, "away")
            if gh is None or ga is None:
                continue
            home_id, away_id = get_team_id(game, "home"), get_team_id(game, "away")
            if team_id == home_id:
                scored, conceded = gh, ga
                scored_home.append(scored)
                conceded_home.append(conceded)
            elif team_id == away_id:
                scored, conceded = ga, gh
                scored_away.append(scored)
                conceded_away.append(conceded)
            else:
                continue
            scored_all.append(scored)
            conceded_all.append(conceded)
            if gh + ga >= 6:
                over55 += 1
            valid += 1

        if not valid:
            TEAM_FORM_CACHE[team_id] = fallback
            return fallback

        result = {
            "overall_scored_avg": sum(scored_all) / len(scored_all),
            "overall_conceded_avg": sum(conceded_all) / len(conceded_all),
            "home_scored_avg": sum(scored_home) / len(scored_home) if scored_home else fallback["home_scored_avg"],
            "home_conceded_avg": sum(conceded_home) / len(conceded_home) if conceded_home else fallback["home_conceded_avg"],
            "away_scored_avg": sum(scored_away) / len(scored_away) if scored_away else fallback["away_scored_avg"],
            "away_conceded_avg": sum(conceded_away) / len(conceded_away) if conceded_away else fallback["away_conceded_avg"],
            "over_5_5_rate": over55 / valid,
        }
        TEAM_FORM_CACHE[team_id] = result
        return result
    except Exception:
        TEAM_FORM_CACHE[team_id] = fallback
        return fallback


def is_total_market_name(name):
    n = normalize_name(name)
    return "over/under" in n or "total goals" in n or "goals over/under" in n or "totals" in n or "over under" in n


def extract_total_side_and_line(value_name):
    parts = str(value_name or "").strip().split()
    if len(parts) < 2:
        return None, None
    side = parts[0].lower()
    line = safe_float(parts[-1])
    if side not in {"over", "under"}:
        return None, None
    return side, line


def get_main_total_market(game_id):
    if game_id in ODDS_CACHE:
        return ODDS_CACHE[game_id]
    result = {"line": None, "over_odds": [], "under_odds": [], "bookmakers_used": 0}
    try:
        data = api_get("odds", {"game": game_id})
        response = data.get("response", [])
        lines = defaultdict(lambda: {"over": [], "under": []})
        seen = set()
        for item in response:
            for bookmaker in item.get("bookmakers", []):
                bid = bookmaker.get("id")
                for bet in bookmaker.get("bets", []):
                    if not is_total_market_name(bet.get("name", "")):
                        continue
                    for value in bet.get("values", []):
                        odd = safe_float(value.get("odd"))
                        if odd is None:
                            continue
                        side, line = extract_total_side_and_line(value.get("value"))
                        if side is None or line is None:
                            continue
                        key = (bid, line, side)
                        if key in seen:
                            continue
                        seen.add(key)
                        lines[line][side].append(odd)
        best_line, best_support = None, -1
        for line, sides in lines.items():
            support = min(len(sides["over"]), len(sides["under"]))
            if support > best_support:
                best_line, best_support = line, support
        if best_line is not None:
            result = {
                "line": best_line,
                "over_odds": lines[best_line]["over"],
                "under_odds": lines[best_line]["under"],
                "bookmakers_used": min(len(lines[best_line]["over"]), len(lines[best_line]["under"])),
            }
    except Exception:
        pass
    ODDS_CACHE[game_id] = result
    return result


def calculate_expected_total(home_stats, away_stats, league_name):
    raw_home = 0.35 * home_stats["home_scored_avg"] + 0.35 * away_stats["away_conceded_avg"] + 0.15 * home_stats["overall_scored_avg"] + 0.15 * away_stats["overall_conceded_avg"]
    raw_away = 0.35 * away_stats["away_scored_avg"] + 0.35 * home_stats["home_conceded_avg"] + 0.15 * away_stats["overall_scored_avg"] + 0.15 * home_stats["overall_conceded_avg"]
    total = ((raw_home + raw_away) * 0.80) + (get_baseline(league_name) * 0.20)
    if home_stats["over_5_5_rate"] >= 0.62 and away_stats["over_5_5_rate"] >= 0.62:
        total += 0.20
    if home_stats["over_5_5_rate"] <= 0.38 and away_stats["over_5_5_rate"] <= 0.38:
        total -= 0.20
    if home_stats["overall_scored_avg"] < 2.10 or away_stats["overall_scored_avg"] < 2.10:
        total -= 0.10
    if home_stats["overall_conceded_avg"] > 3.20 and away_stats["overall_conceded_avg"] > 3.20:
        total += 0.12
    return clamp(total, 3.60, 8.20)


def model_prob_from_goal_edge(goal_edge):
    return clamp(1.0 / (1.0 + math.exp(-(goal_edge / 0.55))), 0.08, 0.92)


def calculate_confidence_score(goal_edge, bookmakers_used, line):
    score = clamp(abs(goal_edge) / 0.90, 0.0, 1.0) * 50
    score += clamp(bookmakers_used / 10.0, 0.0, 1.0) * 28
    score += 12 if line in {5.5, 6.0, 6.5} else 0
    return round(clamp(score, 1.0, 99.0), 1)


def calculate_quality_score(goal_edge, confidence_score, bookmakers_used, odds):
    score = clamp(abs(goal_edge) / 0.90, 0.0, 1.0) * 40
    score += clamp(confidence_score / 100.0, 0.0, 1.0) * 30
    score += clamp(bookmakers_used / 10.0, 0.0, 1.0) * 20
    score += 10 if 1.80 <= odds <= 2.10 else (7 if 1.70 <= odds <= 2.25 else 0)
    return round(clamp(score, 1.0, 99.0), 1)


def build_candidate(bucket, game, odds_list, line, model_prob, expected_total, goal_edge, bookmakers_used):
    cfg = BUCKETS[bucket]
    median_odds = median_or_none(odds_list)
    if median_odds is None:
        return None
    implied_prob = 1 / median_odds
    edge_prob = model_prob - implied_prob
    if bookmakers_used < cfg["min_bookmakers"]:
        return None
    if median_odds < cfg["odds_min"] or median_odds > cfg["odds_max"]:
        return None
    if abs(goal_edge) < cfg["min_goal_edge"]:
        return None
    if edge_prob < cfg["min_edge_prob"]:
        return None

    confidence = calculate_confidence_score(goal_edge, bookmakers_used, line)
    quality = calculate_quality_score(goal_edge, confidence, bookmakers_used, median_odds)
    dt = get_game_dt(game)
    local_dt = dt.astimezone(ZoneInfo(TZ_NAME)) if dt else None
    home, away = get_team_name(game, "home"), get_team_name(game, "away")
    bet = f"Over {line}" if bucket == "over_main_total" else f"Under {line}"
    direction = "above" if bucket == "over_main_total" else "below"
    reasoning = f"{home} vs {away} projects {direction} the market total after recent team profile and league baseline adjustments."

    return {
        "pick_id": build_pick_id(get_game_id(game), bucket, bet, line),
        "game_id": get_game_id(game),
        "fixture_id": get_game_id(game),
        "bucket": bucket,
        "date": local_dt.strftime("%Y-%m-%d") if local_dt else "",
        "time": local_dt.strftime("%H:%M") if local_dt else "",
        "sport": "hockey",
        "league": get_league_name(game),
        "match": f"{home} - {away}",
        "bet": bet,
        "odds": round(median_odds, 2),
        "market_odds_median": round(median_odds, 2),
        "model_prob": round(model_prob, 4),
        "implied_prob": round(implied_prob, 4),
        "edge": round(edge_prob, 4),
        "goal_edge": round(goal_edge, 2),
        "expected_total": round(expected_total, 2),
        "bookmakers_used": bookmakers_used,
        "line": line,
        "stake": 1,
        "confidence_score": confidence,
        "quality_score": quality,
        "reasoning": reasoning,
        "result": "pending",
    }


def append_to_results(payload):
    history = load_json(RESULTS_FILE, [])
    if not isinstance(history, list):
        history = []
    existing = {x.get("pick_id") for x in history if isinstance(x, dict)}
    for picks in payload.get("buckets", {}).values():
        for pick in picks:
            if pick["pick_id"] not in existing:
                history.append(pick.copy())
                existing.add(pick["pick_id"])
    save_json(RESULTS_FILE, history)


def build_predictions():
    if not HOCKEY_API_KEY:
        raise RuntimeError("Missing HOCKEY_API_KEY environment variable.")
    tz = ZoneInfo(TZ_NAME)
    now = datetime.now(tz)
    start_time = now + timedelta(hours=TIME_WINDOW_MIN_HOURS)
    end_time = now + timedelta(hours=TIME_WINDOW_MAX_HOURS)
    games = fetch_games_in_window(start_time, end_time)
    if MAX_GAMES_TO_PROCESS > 0 and len(games) > MAX_GAMES_TO_PROCESS:
        games = games[:MAX_GAMES_TO_PROCESS]
        debug(f"PROCESSING ONLY FIRST {len(games)} GAMES (starter mode)")

    candidates = defaultdict(list)
    for game in games:
        try:
            gid = get_game_id(game)
            home_id, away_id = get_team_id(game, "home"), get_team_id(game, "away")
            if not gid or not home_id or not away_id:
                continue
            league = get_league_name(game)
            home_stats, away_stats = summarize_team_games(home_id), summarize_team_games(away_id)
            market = get_main_total_market(gid)
            line = market.get("line")
            over_odds, under_odds = market.get("over_odds", []), market.get("under_odds", [])
            bookmakers_used = safe_int(market.get("bookmakers_used"), 0) or 0
            if line is None or not over_odds or not under_odds:
                continue
            expected_total = calculate_expected_total(home_stats, away_stats, league)
            over_goal_edge, under_goal_edge = expected_total - line, line - expected_total
            over_prob, under_prob = model_prob_from_goal_edge(over_goal_edge), model_prob_from_goal_edge(under_goal_edge)
            over_pick = build_candidate("over_main_total", game, over_odds, line, over_prob, expected_total, over_goal_edge, bookmakers_used)
            under_pick = build_candidate("under_main_total", game, under_odds, line, under_prob, expected_total, under_goal_edge, bookmakers_used)
            if over_pick:
                candidates["over_main_total"].append(over_pick)
            if under_pick:
                candidates["under_main_total"].append(under_pick)
        except Exception as e:
            debug(f"GAME BUILD ERROR: {e}")

    final = {}
    for bucket_name, cfg in BUCKETS.items():
        ranked = sorted(candidates.get(bucket_name, []), key=lambda x: (x["quality_score"], x["confidence_score"], abs(x["goal_edge"]), x["odds"]), reverse=True)
        picked, used = [], set()
        for item in ranked:
            if item["match"] in used:
                continue
            picked.append(item)
            used.add(item["match"])
            if len(picked) >= cfg["limit"]:
                break
        final[bucket_name] = picked
        debug(f"FINAL BUCKET {bucket_name}: {len(picked)} picks (raw candidates: {len(candidates.get(bucket_name, []))})")

    return {
        "generated_at": datetime.now(tz).isoformat(),
        "model": "AI77 Hockey Totals Research v1",
        "stake_mode": "flat_1_unit",
        "source": "API-Hockey",
        "timezone": TZ_NAME,
        "window_hours": {"min": TIME_WINDOW_MIN_HOURS, "max": TIME_WINDOW_MAX_HOURS},
        "buckets": final,
    }


def main():
    payload = build_predictions()
    save_json(PRED_FILE, payload)
    append_to_results(payload)
    total_picks = sum(len(v) for v in payload["buckets"].values())
    debug(f"SAVED {PRED_FILE} with {total_picks} picks.")


if __name__ == "__main__":
    main()
