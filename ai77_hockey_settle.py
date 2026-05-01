import json
import os
import time
import requests

HOCKEY_API_KEY = os.getenv("HOCKEY_API_KEY")
HOCKEY_URL = "https://v1.hockey.api-sports.io"
REQUEST_TIMEOUT = 20
RESULTS_FILE = "hockey/hockey_results.json"

FINAL_STATUSES = {"FT", "AOT", "AP", "PEN", "FINISHED"}
VOID_STATUSES = {"CANC", "ABD", "AWD", "WO"}
LIVE_STATUSES = {"LIVE", "1P", "2P", "3P", "OT", "SO", "HT", "BT", "ET"}


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


def get_status(game):
    return str(game.get("game", {}).get("status", {}).get("short", "")).upper()


def get_score(game, side):
    scores = game.get("scores", {})
    goals = game.get("goals", {})
    return safe_int(scores.get(side, goals.get(side)))


def settle_pick(pick, game):
    status = get_status(game)
    if status in LIVE_STATUSES:
        return "pending"
    if status in VOID_STATUSES:
        return "storno"
    if status not in FINAL_STATUSES:
        return "pending"

    gh = get_score(game, "home")
    ga = get_score(game, "away")
    if gh is None or ga is None:
        return "pending"

    total = gh + ga
    line = safe_float(pick.get("line"))
    if line is None:
        return "pending"
    bet = str(pick.get("bet", "")).lower()
    if "over" in bet:
        return "win" if total > line else "loss"
    if "under" in bet:
        return "win" if total < line else "loss"
    return "pending"


def main():
    if not HOCKEY_API_KEY:
        raise RuntimeError("Missing HOCKEY_API_KEY environment variable.")
    history = load_json(RESULTS_FILE, [])
    if not isinstance(history, list):
        history = []

    pending_ids = sorted({x.get("game_id") or x.get("fixture_id") for x in history if isinstance(x, dict) and x.get("result") == "pending"})
    pending_ids = [x for x in pending_ids if x]
    print(f"PENDING UNIQUE GAME IDS: {len(pending_ids)}")

    game_map = {}
    for game_id in pending_ids:
        try:
            data = api_get("games", {"id": game_id})
            response = data.get("response", [])
            if response:
                game_map[game_id] = response[0]
            time.sleep(1.1)
        except Exception as e:
            print(f"SETTLE FETCH ERROR game_id={game_id}: {e}")

    updated = 0
    for item in history:
        if not isinstance(item, dict) or item.get("result") != "pending":
            continue
        game_id = item.get("game_id") or item.get("fixture_id")
        game = game_map.get(game_id)
        if not game:
            continue
        new_result = settle_pick(item, game)
        if new_result != "pending":
            item["result"] = new_result
            updated += 1
            print(f"SETTLED: {item.get('match')} | {item.get('bet')} -> {new_result}")

    save_json(RESULTS_FILE, history)
    print(f"SETTLE DONE: updated={updated}")


if __name__ == "__main__":
    main()
