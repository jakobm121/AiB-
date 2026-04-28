import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")
FOOTBALL_URL = "https://v3.football.api-sports.io"
TZ_NAME = "Europe/Ljubljana"
REQUEST_TIMEOUT = 20

LAB_RESULTS_FILE = "lab_results.json"
LAB_STATS_FILE = "lab_stats.json"


def football_headers():
    return {"x-apisports-key": FOOTBALL_API_KEY}


def safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


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


def api_get(endpoint, params):
    url = f"{FOOTBALL_URL}/{endpoint}"
    res = requests.get(url, headers=football_headers(), params=params, timeout=REQUEST_TIMEOUT)
    res.raise_for_status()
    return res.json()


def fetch_recent_finished_fixtures(days_back=5):
    tz = ZoneInfo(TZ_NAME)
    now = datetime.now(tz)
    start_date = (now - timedelta(days=days_back)).date()
    end_date = now.date()

    fixture_map = {}
    current_date = start_date

    while current_date <= end_date:
        try:
            data = api_get("fixtures", {
                "date": current_date.strftime("%Y-%m-%d"),
                "timezone": TZ_NAME
            })
            for item in data.get("response", []):
                fixture = item.get("fixture", {})
                fixture_id = fixture.get("id")
                status = fixture.get("status", {}).get("short")
                if fixture_id and status in {"FT", "AET", "PEN", "CANC", "ABD", "AWD", "WO"}:
                    fixture_map[fixture_id] = item
        except Exception as e:
            print(f"SETTLE FETCH ERROR {current_date}: {e}")
        current_date += timedelta(days=1)

    print(f"SETTLE FIXTURES LOADED: {len(fixture_map)}")
    return fixture_map


def settle_h2h_pick(pick, fixture):
    home = fixture.get("teams", {}).get("home", {}).get("name")
    away = fixture.get("teams", {}).get("away", {}).get("name")
    gh = fixture.get("goals", {}).get("home")
    ga = fixture.get("goals", {}).get("away")
    if gh is None or ga is None:
        return "pending"

    bet = pick.get("bet")
    if gh == ga:
        winner = "Draw"
    elif gh > ga:
        winner = home
    else:
        winner = away

    return "win" if bet == winner else "loss"


def settle_total_pick(pick, fixture):
    gh = fixture.get("goals", {}).get("home")
    ga = fixture.get("goals", {}).get("away")
    if gh is None or ga is None:
        return "pending"

    total = gh + ga
    line = safe_float(pick.get("line"))
    if line is None:
        return "pending"

    bet = str(pick.get("bet", "")).lower()

    if abs(line - 2.5) < 0.001 or abs(line - 3.5) < 0.001:
        if "over" in bet:
            return "win" if total > line else "loss"
        if "under" in bet:
            return "win" if total < line else "loss"

    return "pending"


def settle_btts_pick(pick, fixture):
    gh = fixture.get("goals", {}).get("home")
    ga = fixture.get("goals", {}).get("away")
    if gh is None or ga is None:
        return "pending"

    both = gh > 0 and ga > 0
    bet = str(pick.get("bet", "")).strip().lower()

    if bet == "btts yes":
        return "win" if both else "loss"
    if bet == "btts no":
        return "win" if not both else "loss"
    return "pending"


def settle_pick(pick, fixture):
    status = fixture.get("fixture", {}).get("status", {}).get("short")
    if status in {"CANC", "ABD", "AWD", "WO"}:
        return "storno"

    bucket = str(pick.get("bucket", ""))
    if bucket in {"home", "draw", "away"}:
        return settle_h2h_pick(pick, fixture)
    if bucket in {"over_2_5", "under_2_5", "over_3_5", "under_3_5"}:
        return settle_total_pick(pick, fixture)
    if bucket in {"btts_yes", "btts_no"}:
        return settle_btts_pick(pick, fixture)

    return "pending"


def main():
    if not FOOTBALL_API_KEY:
        raise RuntimeError("Missing FOOTBALL_API_KEY environment variable.")

    history = load_json_file(LAB_RESULTS_FILE, [])
    if not isinstance(history, list):
        history = []

    fixture_map = fetch_recent_finished_fixtures(days_back=5)

    updated = 0
    for item in history:
        if not isinstance(item, dict):
            continue
        if item.get("result") != "pending":
            continue

        fixture_id = item.get("fixture_id")
        if not fixture_id or fixture_id not in fixture_map:
            continue

        new_result = settle_pick(item, fixture_map[fixture_id])
        if new_result != "pending":
            item["result"] = new_result
            updated += 1
            print(f"SETTLED: {item.get('match')} | {item.get('bet')} -> {new_result}")

    save_json_file(LAB_RESULTS_FILE, history)
    print(f"SETTLE DONE: updated={updated}")


if __name__ == "__main__":
    main()
