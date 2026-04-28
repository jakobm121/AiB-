import json
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")
FOOTBALL_URL = "https://v3.football.api-sports.io"
TZ_NAME = "Europe/Ljubljana"
REQUEST_TIMEOUT = 20

LAB_RESULTS_FILE = "lab_results.json"


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


def api_get(endpoint, params, retries=3, sleep_seconds=2):
    url = f"{FOOTBALL_URL}/{endpoint}"

    for attempt in range(retries):
        res = requests.get(url, headers=football_headers(), params=params, timeout=REQUEST_TIMEOUT)

        if res.status_code == 429:
            wait_time = sleep_seconds * (attempt + 1)
            print(f"RATE LIMIT hit for {endpoint} {params} -> sleeping {wait_time}s")
            time.sleep(wait_time)
            continue

        res.raise_for_status()
        return res.json()

    raise RuntimeError(f"API rate-limited too many times for {endpoint} {params}")


def fetch_finished_pending_fixtures(pending_fixture_ids):
    fixture_map = {}

    unique_ids = sorted({fid for fid in pending_fixture_ids if fid})
    print(f"PENDING UNIQUE FIXTURE IDS: {len(unique_ids)}")

    for fixture_id in unique_ids:
        try:
            data = api_get("fixtures", {"id": fixture_id})
            response = data.get("response", [])
            if response:
                fixture_map[fixture_id] = response[0]
            time.sleep(1.2)
        except Exception as e:
            print(f"SETTLE FETCH ERROR fixture_id={fixture_id}: {e}")

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

    if status in {"NS", "TBD", "PST", "1H", "HT", "2H", "ET", "BT", "LIVE"}:
        return "pending"

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

    pending_fixture_ids = [
        item.get("fixture_id")
        for item in history
        if isinstance(item, dict) and item.get("result") == "pending"
    ]

    if not pending_fixture_ids:
        print("NO PENDING PICKS TO SETTLE")
        return

    fixture_map = fetch_finished_pending_fixtures(pending_fixture_ids)

    updated = 0

    for item in history:
        if not isinstance(item, dict):
            continue
        if item.get("result") != "pending":
            continue

        fixture_id = item.get("fixture_id")
        if not fixture_id:
            continue

        fixture = fixture_map.get(fixture_id)
        if not fixture:
            continue

        new_result = settle_pick(item, fixture)
        if new_result != "pending":
            item["result"] = new_result
            updated += 1
            print(f"SETTLED: {item.get('match')} | {item.get('bet')} -> {new_result}")

    save_json_file(LAB_RESULTS_FILE, history)
    print(f"SETTLE DONE: updated={updated}")


if __name__ == "__main__":
    main()
