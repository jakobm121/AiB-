import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

HOCKEY_API_KEY = os.getenv("HOCKEY_API_KEY")
HOCKEY_URL = "https://v1.hockey.api-sports.io"
REQUEST_TIMEOUT = 20
RESULTS_FILE = "hockey/hockey_results.json"
TZ_NAME = "Europe/Ljubljana"

FINAL_STATUSES = {
    "FT",
    "AOT",
    "AP",
    "PEN",
    "FINISHED",
    "AFTER OT",
    "AFTER PEN",
    "FINAL",
    "ENDED"
}

VOID_STATUSES = {
    "CANC",
    "CANCELLED",
    "ABD",
    "ABANDONED",
    "AWD",
    "WO",
    "POSTP",
    "POSTPONED"
}

LIVE_STATUSES = {
    "LIVE",
    "1P",
    "2P",
    "3P",
    "OT",
    "SO",
    "HT",
    "BT",
    "ET"
}

DEBUG = True


def debug(msg):
    if DEBUG:
        print(msg)


def headers():
    return {"x-apisports-key": HOCKEY_API_KEY}


def safe_int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def normalize_id(value):
    if value is None:
        return ""
    return str(value).strip()


def load_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)

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
            timeout=REQUEST_TIMEOUT
        )

        if res.status_code == 429:
            wait = 2 * (attempt + 1)
            debug(f"RATE LIMIT. Waiting {wait}s...")
            time.sleep(wait)
            continue

        res.raise_for_status()
        return res.json()

    raise RuntimeError(f"API rate-limited: {endpoint} {params}")


def get_status(game):
    status = game.get("game", {}).get("status", {})

    short = str(status.get("short", "") or "").upper().strip()
    long = str(status.get("long", "") or "").upper().strip()

    return short, long


def extract_score_value(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, str):
        return safe_int(value)

    if isinstance(value, dict):
        for key in [
            "total",
            "score",
            "goals",
            "current",
            "fulltime",
            "final"
        ]:
            if key in value:
                parsed = safe_int(value.get(key))
                if parsed is not None:
                    return parsed

    return None


def get_score(game, side):
    scores = game.get("scores", {})
    goals = game.get("goals", {})

    score = extract_score_value(scores.get(side))
    if score is not None:
        return score

    score = extract_score_value(goals.get(side))
    if score is not None:
        return score

    return None


def settle_total(pick, home_score, away_score):
    total = home_score + away_score

    line = safe_float(pick.get("line"))

    if line is None:
        parts = str(pick.get("bet", "")).split()
        if parts:
            line = safe_float(parts[-1])

    if line is None:
        return "pending"

    bet = str(pick.get("bet", "")).lower()

    if "over" in bet:
        if total > line:
            return "win"
        if total == line:
            return "storno"
        return "loss"

    if "under" in bet:
        if total < line:
            return "win"
        if total == line:
            return "storno"
        return "loss"

    return "pending"


def settle_h2h(pick, game, home_score, away_score):
    teams = game.get("teams", {})
    home_name = teams.get("home", {}).get("name") or game.get("teams", {}).get("home")
    away_name = teams.get("away", {}).get("name") or game.get("teams", {}).get("away")

    bet = str(pick.get("bet", "")).strip()

    if home_score > away_score:
        winner = str(home_name).strip()
    elif away_score > home_score:
        winner = str(away_name).strip()
    else:
        winner = "Draw"

    return "win" if bet == winner else "loss"


def settle_pick(pick, game):
    short_status, long_status = get_status(game)

    home_score = get_score(game, "home")
    away_score = get_score(game, "away")

    debug(
        f"CHECK game_id={pick.get('game_id') or pick.get('fixture_id')} | "
        f"status_short={short_status} | status_long={long_status} | "
        f"score={home_score}:{away_score} | pick={pick.get('bet')}"
    )

    if short_status in LIVE_STATUSES or long_status in LIVE_STATUSES:
        return "pending"

    if short_status in VOID_STATUSES or long_status in VOID_STATUSES:
        return "storno"

    if short_status not in FINAL_STATUSES and long_status not in FINAL_STATUSES:
        return "pending"

    if home_score is None or away_score is None:
        return "pending"

    bucket = str(pick.get("bucket", "")).lower()
    bet = str(pick.get("bet", "")).lower()

    if "over" in bucket or "under" in bucket or "over" in bet or "under" in bet:
        return settle_total(pick, home_score, away_score)

    if bucket in {"home", "away", "draw", "h2h", "moneyline"}:
        return settle_h2h(pick, game, home_score, away_score)

    return "pending"


def main():
    if not HOCKEY_API_KEY:
        raise RuntimeError("Missing HOCKEY_API_KEY environment variable.")

    history = load_json(RESULTS_FILE, [])
    if not isinstance(history, list):
        history = []

    pending_ids = sorted({
        normalize_id(x.get("game_id") or x.get("fixture_id"))
        for x in history
        if isinstance(x, dict)
        and str(x.get("result", "")).lower() == "pending"
        and normalize_id(x.get("game_id") or x.get("fixture_id"))
    })

    print(f"PENDING UNIQUE GAME IDS: {len(pending_ids)}")

    game_map = {}

    for game_id in pending_ids:
        try:
            data = api_get("games", {"id": game_id})
            response = data.get("response", [])

            if response:
                game = response[0]
                api_game_id = normalize_id(game.get("game", {}).get("id") or game_id)
                game_map[api_game_id] = game
                game_map[game_id] = game

                short_status, long_status = get_status(game)
                home_score = get_score(game, "home")
                away_score = get_score(game, "away")

                debug(
                    f"FETCHED game_id={game_id} | api_id={api_game_id} | "
                    f"status={short_status}/{long_status} | score={home_score}:{away_score}"
                )
            else:
                debug(f"NO API RESPONSE for game_id={game_id}")

            time.sleep(1.1)

        except Exception as e:
            print(f"SETTLE FETCH ERROR game_id={game_id}: {e}")

    updated = 0
    still_pending = 0
    not_found = 0

    for item in history:
        if not isinstance(item, dict):
            continue

        if str(item.get("result", "")).lower() != "pending":
            continue

        game_id = normalize_id(item.get("game_id") or item.get("fixture_id"))

        if not game_id:
            not_found += 1
            continue

        game = game_map.get(game_id)

        if not game:
            not_found += 1
            debug(f"NO MATCH FOUND IN API MAP for game_id={game_id} | {item.get('match')}")
            continue

        new_result = settle_pick(item, game)

        if new_result != "pending":
            item["result"] = new_result
            item["settled_at"] = datetime.now(ZoneInfo(TZ_NAME)).isoformat()

            home_score = get_score(game, "home")
            away_score = get_score(game, "away")
            item["final_score"] = f"{home_score}:{away_score}"

            updated += 1

            print(
                f"SETTLED: {item.get('match')} | {item.get('bet')} | "
                f"{item.get('final_score')} -> {new_result}"
            )
        else:
            still_pending += 1

    save_json(RESULTS_FILE, history)

    print(
        f"SETTLE DONE: updated={updated} "
        f"still_pending={still_pending} not_found={not_found}"
    )


if __name__ == "__main__":
    main()
