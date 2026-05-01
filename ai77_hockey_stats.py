import json
import os
from collections import defaultdict

RESULTS_FILE = "hockey/hockey_results.json"
STATS_FILE = "hockey/hockey_stats.json"


def safe_float(value, default=0.0):
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


def pick_profit(item):
    result = item.get("result")
    odds = safe_float(item.get("odds"), 0.0)
    if result == "win":
        return odds - 1.0
    if result == "loss":
        return -1.0
    if result == "storno":
        return 0.0
    return None


def summarize(items):
    settled = [x for x in items if x.get("result") in {"win", "loss", "storno"}]
    graded = [x for x in settled if x.get("result") in {"win", "loss"}]
    wins = sum(1 for x in graded if x.get("result") == "win")
    losses = sum(1 for x in graded if x.get("result") == "loss")
    profit = sum((pick_profit(x) or 0.0) for x in settled)
    staked = wins + losses
    avg_odds = sum(safe_float(x.get("odds"), 0.0) for x in settled) / len(settled) if settled else 0.0
    return {
        "picks": len(items),
        "settled_picks": len(settled),
        "pending_picks": sum(1 for x in items if x.get("result") == "pending"),
        "wins": wins,
        "losses": losses,
        "storno": sum(1 for x in settled if x.get("result") == "storno"),
        "profit_units": round(profit, 2),
        "hit_rate_percent": round((wins / staked) * 100, 1) if staked else 0.0,
        "roi_percent": round((profit / staked) * 100, 1) if staked else 0.0,
        "avg_odds": round(avg_odds, 2),
    }


def main():
    history = load_json(RESULTS_FILE, [])
    if not isinstance(history, list):
        history = []

    bucket_map = defaultdict(list)
    league_map = defaultdict(list)
    for item in history:
        if not isinstance(item, dict):
            continue
        bucket_map[item.get("bucket", "unknown")].append(item)
        league_map[item.get("league", "Unknown")].append(item)

    totals = summarize(history)
    bucket_stats = []
    for bucket, rows in bucket_map.items():
        row = summarize(rows)
        row["bucket"] = bucket
        bucket_stats.append(row)
    bucket_stats.sort(key=lambda x: (x["roi_percent"], x["settled_picks"]), reverse=True)

    league_stats = []
    for league, rows in league_map.items():
        row = summarize(rows)
        row["league"] = league
        league_stats.append(row)
    league_stats.sort(key=lambda x: (x["roi_percent"], x["settled_picks"]), reverse=True)

    payload = {"totals": totals, "bucket_stats": bucket_stats, "league_stats": league_stats}
    save_json(STATS_FILE, payload)
    print(f"SAVED {STATS_FILE}")


if __name__ == "__main__":
    main()
