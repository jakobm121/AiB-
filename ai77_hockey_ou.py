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

# FREE PLAN MODE
# Free plan usually only allows current available dates, so this avoids wasting calls on inaccessible future dates.
FREE_PLAN_TODAY_ONLY = True

TIME_WINDOW_MIN_HOURS = 0
TIME_WINDOW_MAX_HOURS = 24

# Process more games because many hockey games have no odds on free plan.
MAX_GAMES_TO_PROCESS = 40

BUCKETS = {
    "over_main_total": {
        "limit": 6,
        "min_edge_prob": 0.010,
        "min_goal_edge": 0.12,
        "min_bookmakers": 2,
        "odds_min": 1.55,
        "odds_max": 2.65,
    },
    "under_main_total": {
        "limit": 6,
        "min_edge_prob": 0.010,
        "min_goal_edge": 0.12,
        "min_bookmakers": 2,
        "odds_min": 1.55,
        "odds_max": 2.65,
    },
}

ODDS_CACHE = {}

FINAL_STATUSES = {
    "FT",
    "AOT",
    "AP",
    "PEN",
    "FINISHED",
    "AFTER OVERTIME",
    "AFTER PENALTIES",
}

PREGAME_STATUSES = {
    "NS",
    "TBD",
    "PST",
    "POSTP",
    "SCHEDULED",
    "NOT STARTED",
    "NOT_STARTED",
}

LEAGUE_BASELINES = {
    "default": 5.40,

    # North America
    "nhl": 6.05,
    "ahl": 6.15,
    "echl": 6.05,
    "ohl": 6.20,
    "whl": 6.25,
    "qmjhl": 6.35,
    "ushl": 6.10,
    "sphl": 6.20,

    # Europe
    "liiga": 5.45,
    "shl": 5.25,
    "allsvenskan": 5.35,
    "del": 6.10,
    "national league": 5.85,
    "ice hockey league": 5.95,
    "extraliga": 5.55,
    "czech extraliga": 5.55,
    "slovakia extraliga": 5.70,
    "metal ligaen": 5.80,
    "fjordkraft-ligaen": 5.95,
    "eliteserien": 5.95,
    "mestis": 5.70,
    "hockeyallsvenskan": 5.35,

    # International
    "world championship": 5.80,
    "world championship u20": 6.15,
    "olympic games": 5.40,

    # Australia / lower liquidity
    "aihl": 6.50,
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
        res = requests.get(
            url,
            headers=headers(),
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        if res.status_code == 429:
            wait_time = 2 * (attempt + 1)
            debug(f"RATE LIMIT {endpoint} {params} -> sleeping {wait_time}s")
            time.sleep(wait_time)
            continue

        res.raise_for_status()
        data = res.json()

        debug(f"API {endpoint} params={params}")
        debug(f"API errors={data.get('errors')}")
        debug(f"API results={data.get('results')}")
        debug(
            f"API response_len="
            f"{len(data.get('response', [])) if isinstance(data.get('response'), list) else 'n/a'}"
        )

        return data

    raise RuntimeError(f"API rate-limited: {endpoint} {params}")


def get_game_core(game):
    nested = game.get("game")

    if isinstance(nested, dict) and nested:
        return nested

    return game


def get_game_id(game):
    core = get_game_core(game)
    return core.get("id")


def get_game_dt(game):
    core = get_game_core(game)

    raw = (
        core.get("date")
        or core.get("datetime")
        or core.get("time")
    )

    if not raw:
        return None

    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def get_status(game):
    core = get_game_core(game)
    status_obj = core.get("status", {})

    if isinstance(status_obj, dict):
        short_status = str(status_obj.get("short", "") or "").strip().upper()
        long_status = str(status_obj.get("long", "") or "").strip().upper()

        if short_status:
            return short_status

        return long_status

    return str(status_obj or "").strip().upper()


def get_status_debug(game):
    core = get_game_core(game)
    status_obj = core.get("status", {})

    if isinstance(status_obj, dict):
        return {
            "short": status_obj.get("short"),
            "long": status_obj.get("long"),
            "raw": status_obj,
        }

    return {
        "short": None,
        "long": None,
        "raw": status_obj,
    }


def get_team_id(game, side):
    return game.get("teams", {}).get(side, {}).get("id")


def get_team_name(game, side):
    return game.get("teams", {}).get(side, {}).get("name")


def get_league_name(game):
    return game.get("league", {}).get("name", "Hockey")


def get_baseline(league_name):
    key = normalize_name(league_name)
    return LEAGUE_BASELINES.get(key, LEAGUE_BASELINES["default"])


def fetch_games_in_window(start_time, end_time):
    games = []

    if FREE_PLAN_TODAY_ONLY:
        dates_to_fetch = [start_time.date()]
    else:
        dates_to_fetch = []
        current_date = start_time.date()
        end_date = end_time.date()

        while current_date <= end_date:
            dates_to_fetch.append(current_date)
            current_date += timedelta(days=1)

    for date_value in dates_to_fetch:
        try:
            data = api_get(
                "games",
                {
                    "date": date_value.strftime("%Y-%m-%d"),
                    "timezone": TZ_NAME,
                },
            )

            daily = data.get("response", [])
            debug(f"GAMES {date_value}: {len(daily)}")
            games.extend(daily)

        except Exception as e:
            debug(f"GAMES ERROR {date_value}: {e}")

    filtered = []
    tz = ZoneInfo(TZ_NAME)

    debug(f"WINDOW START: {start_time}")
    debug(f"WINDOW END: {end_time}")

    status_counts = defaultdict(int)
    time_rejected = 0
    status_rejected = 0
    missing_rejected = 0
    sample_games = []

    for game in games:
        dt = get_game_dt(game)
        status = get_status(game)
        status_counts[status] += 1

        game_id = get_game_id(game)
        home = get_team_name(game, "home")
        away = get_team_name(game, "away")
        league = get_league_name(game)

        local_dt = dt.astimezone(tz) if dt else None

        if len(sample_games) < 12:
            sample_games.append(
                {
                    "id": game_id,
                    "league": league,
                    "status": status,
                    "status_raw": get_status_debug(game),
                    "time": str(local_dt),
                    "match": f"{home} - {away}",
                }
            )

        if not dt:
            missing_rejected += 1
            continue

        if local_dt < start_time or local_dt > end_time:
            time_rejected += 1
            continue

        if status not in PREGAME_STATUSES:
            status_rejected += 1
            continue

        if (
            not get_game_id(game)
            or not get_team_id(game, "home")
            or not get_team_id(game, "away")
        ):
            missing_rejected += 1
            continue

        filtered.append(game)

    debug(f"SAMPLE GAMES: {sample_games}")
    debug(f"STATUS COUNTS: {dict(status_counts)}")
    debug(f"REJECTED BY TIME: {time_rejected}")
    debug(f"REJECTED BY STATUS: {status_rejected}")
    debug(f"REJECTED BY MISSING DATA: {missing_rejected}")
    debug(f"FILTERED GAMES: {len(filtered)}")

    return filtered


def is_total_market_name(name):
    n = normalize_name(name)

    return (
        "over/under" in n
        or "total goals" in n
        or "goals over/under" in n
        or "totals" in n
        or "over under" in n
    )


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

    result = {
        "line": None,
        "over_odds": [],
        "under_odds": [],
        "bookmakers_used": 0,
    }

    try:
        data = api_get("odds", {"game": game_id})
        response = data.get("response", [])

        lines = defaultdict(lambda: {"over": [], "under": []})
        seen = set()

        for item in response:
            for bookmaker in item.get("bookmakers", []):
                bookmaker_id = bookmaker.get("id")

                for bet in bookmaker.get("bets", []):
                    bet_name = bet.get("name", "")

                    if not is_total_market_name(bet_name):
                        continue

                    for value in bet.get("values", []):
                        odd = safe_float(value.get("odd"))

                        if odd is None:
                            continue

                        side, line = extract_total_side_and_line(value.get("value"))

                        if side is None or line is None:
                            continue

                        key = (bookmaker_id, line, side)

                        if key in seen:
                            continue

                        seen.add(key)
                        lines[line][side].append(odd)

        best_line = None
        best_support = -1

        for line, sides in lines.items():
            support = min(len(sides["over"]), len(sides["under"]))

            if support > best_support:
                best_line = line
                best_support = support

        if best_line is not None:
            result = {
                "line": best_line,
                "over_odds": lines[best_line]["over"],
                "under_odds": lines[best_line]["under"],
                "bookmakers_used": min(
                    len(lines[best_line]["over"]),
                    len(lines[best_line]["under"]),
                ),
            }

    except Exception as e:
        debug(f"ODDS ERROR game_id={game_id}: {e}")

    ODDS_CACHE[game_id] = result
    return result


def league_total_adjustment(league_name):
    """
    Small free-plan correction layer.
    Because we do not have team form on free API,
    league identity and market line are the main signal.
    """
    league_key = normalize_name(league_name)

    high_total_leagues = {
        "qmjhl",
        "ohl",
        "whl",
        "ahl",
        "echl",
        "sphl",
        "aihl",
    }

    low_total_leagues = {
        "shl",
        "allsvenskan",
        "liiga",
    }

    if league_key in high_total_leagues:
        return 0.15

    if league_key in low_total_leagues:
        return -0.10

    return 0.0


def calculate_expected_total_free_plan(league_name, line, over_odds, under_odds):
    baseline = get_baseline(league_name)
    expected_total = baseline + league_total_adjustment(league_name)

    over_median = median_or_none(over_odds)
    under_median = median_or_none(under_odds)

    # Market-pressure correction.
    # If over is shorter than under, market leans over. If under is shorter, market leans under.
    if over_median and under_median and over_median > 1 and under_median > 1:
        over_implied = 1 / over_median
        under_implied = 1 / under_median
        market_lean = over_implied - under_implied
        expected_total += clamp(market_lean * 0.75, -0.18, 0.18)

    # Line-shape correction.
    # Very low totals are easier over candidates. High totals are easier under candidates.
    if line <= 4.5:
        expected_total += 0.12

    if line >= 6.5:
        expected_total -= 0.12

    return clamp(expected_total, 3.80, 7.40)


def model_prob_from_goal_edge(goal_edge):
    """
    Softer curve than paid-plan model because free-plan model has less information.
    """
    return clamp(
        1.0 / (1.0 + math.exp(-(goal_edge / 0.80))),
        0.12,
        0.88,
    )


def calculate_confidence_score(goal_edge, bookmakers_used, line, odds):
    edge_component = clamp(abs(goal_edge) / 0.85, 0.0, 1.0) * 45
    bookmaker_component = clamp(bookmakers_used / 8.0, 0.0, 1.0) * 30

    line_component = 0
    if line in {5.0, 5.5, 6.0, 6.5}:
        line_component = 12
    elif line in {4.5, 7.0}:
        line_component = 8

    odds_component = 0
    if 1.75 <= odds <= 2.15:
        odds_component = 13
    elif 1.60 <= odds <= 2.45:
        odds_component = 8

    score = edge_component + bookmaker_component + line_component + odds_component
    return round(clamp(score, 1.0, 99.0), 1)


def calculate_quality_score(goal_edge, confidence_score, bookmakers_used, odds, edge_prob):
    edge_component = clamp(abs(goal_edge) / 0.85, 0.0, 1.0) * 34
    prob_edge_component = clamp(edge_prob / 0.10, 0.0, 1.0) * 24
    confidence_component = clamp(confidence_score / 100.0, 0.0, 1.0) * 22
    bookmaker_component = clamp(bookmakers_used / 8.0, 0.0, 1.0) * 12

    odds_component = 0
    if 1.75 <= odds <= 2.15:
        odds_component = 8
    elif 1.60 <= odds <= 2.45:
        odds_component = 5

    score = (
        edge_component
        + prob_edge_component
        + confidence_component
        + bookmaker_component
        + odds_component
    )

    return round(clamp(score, 1.0, 99.0), 1)


def build_candidate(
    bucket,
    game,
    odds_list,
    line,
    model_prob,
    expected_total,
    goal_edge,
    bookmakers_used,
):
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

    confidence = calculate_confidence_score(
        goal_edge=goal_edge,
        bookmakers_used=bookmakers_used,
        line=line,
        odds=median_odds,
    )

    quality = calculate_quality_score(
        goal_edge=goal_edge,
        confidence_score=confidence,
        bookmakers_used=bookmakers_used,
        odds=median_odds,
        edge_prob=edge_prob,
    )

    dt = get_game_dt(game)
    local_dt = dt.astimezone(ZoneInfo(TZ_NAME)) if dt else None

    home = get_team_name(game, "home")
    away = get_team_name(game, "away")

    bet = f"Over {line}" if bucket == "over_main_total" else f"Under {line}"
    direction = "above" if bucket == "over_main_total" else "below"

    reasoning = (
        f"{home} vs {away} projects {direction} the market total in the free-plan model. "
        f"The signal is based on league baseline, main total line, bookmaker coverage, "
        f"and median market pricing."
    )

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

    existing = {item.get("pick_id") for item in history if isinstance(item, dict)}

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
        debug(f"PROCESSING ONLY FIRST {len(games)} GAMES (free-plan mode)")

    candidates = defaultdict(list)

    for game in games:
        try:
            game_id = get_game_id(game)

            if not game_id:
                continue

            home_id = get_team_id(game, "home")
            away_id = get_team_id(game, "away")

            if not home_id or not away_id:
                continue

            home = get_team_name(game, "home")
            away = get_team_name(game, "away")
            league = get_league_name(game)

            market = get_main_total_market(game_id)

            line = market.get("line")
            over_odds = market.get("over_odds", [])
            under_odds = market.get("under_odds", [])
            bookmakers_used = safe_int(market.get("bookmakers_used"), 0) or 0

            debug(
                f"MARKET game_id={game_id} | {home} - {away} | {league} | "
                f"line={line} over_odds={len(over_odds)} under_odds={len(under_odds)} "
                f"bookmakers={bookmakers_used}"
            )

            if line is None or not over_odds or not under_odds:
                continue

            expected_total = calculate_expected_total_free_plan(
                league_name=league,
                line=line,
                over_odds=over_odds,
                under_odds=under_odds,
            )

            over_goal_edge = expected_total - line
            under_goal_edge = line - expected_total

            over_prob = model_prob_from_goal_edge(over_goal_edge)
            under_prob = model_prob_from_goal_edge(under_goal_edge)

            over_pick = build_candidate(
                bucket="over_main_total",
                game=game,
                odds_list=over_odds,
                line=line,
                model_prob=over_prob,
                expected_total=expected_total,
                goal_edge=over_goal_edge,
                bookmakers_used=bookmakers_used,
            )

            under_pick = build_candidate(
                bucket="under_main_total",
                game=game,
                odds_list=under_odds,
                line=line,
                model_prob=under_prob,
                expected_total=expected_total,
                goal_edge=under_goal_edge,
                bookmakers_used=bookmakers_used,
            )

            if over_pick:
                candidates["over_main_total"].append(over_pick)

            if under_pick:
                candidates["under_main_total"].append(under_pick)

            debug(
                f"MODEL game_id={game_id} | line={line} expected={round(expected_total, 2)} "
                f"over_edge={round(over_goal_edge, 2)} under_edge={round(under_goal_edge, 2)}"
            )

        except Exception as e:
            debug(f"GAME BUILD ERROR: {e}")

    final = {}

    for bucket_name, cfg in BUCKETS.items():
        ranked = sorted(
            candidates.get(bucket_name, []),
            key=lambda x: (
                x["quality_score"],
                x["confidence_score"],
                abs(x["goal_edge"]),
                x["bookmakers_used"],
                x["odds"],
            ),
            reverse=True,
        )

        picked = []
        used_matches = set()

        for item in ranked:
            if item["match"] in used_matches:
                continue

            picked.append(item)
            used_matches.add(item["match"])

            if len(picked) >= cfg["limit"]:
                break

        final[bucket_name] = picked

        debug(
            f"FINAL BUCKET {bucket_name}: {len(picked)} picks "
            f"(raw candidates: {len(candidates.get(bucket_name, []))})"
        )

    return {
        "generated_at": datetime.now(tz).isoformat(),
        "model": "AI77 Hockey Totals Free Plan v1",
        "stake_mode": "flat_1_unit",
        "source": "API-Hockey",
        "timezone": TZ_NAME,
        "window_hours": {
            "min": TIME_WINDOW_MIN_HOURS,
            "max": TIME_WINDOW_MAX_HOURS,
        },
        "free_plan_mode": True,
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
