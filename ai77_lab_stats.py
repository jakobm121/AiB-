import json
import os

LAB_RESULTS_FILE = "lab_results.json"
LAB_STATS_FILE = "lab_stats.json"

ALL_BUCKETS = [
    "home", "draw", "away",
    "over_2_5", "under_2_5",
    "btts_yes", "btts_no",
    "over_3_5", "under_3_5"
]

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

def safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default

def get_pick_profit(item):
    result = str(item.get("result", "")).strip().lower()
    odds = safe_float(item.get("odds"))
    stake = safe_float(item.get("stake"), 1.0)
    if stake is None:
        stake = 1.0
    if result == "win":
        if odds is None:
            return 0.0
        return (odds - 1.0) * stake
    if result == "loss":
        return -1.0 * stake
    return 0.0

def build_bucket_template():
    return {
        "picks": 0, "settled_picks": 0, "wins": 0, "losses": 0, "storno": 0, "pending": 0,
        "avg_odds": 0.0, "avg_edge": 0.0, "profit": 0.0, "staked": 0.0, "hit_rate": 0.0, "roi": 0.0
    }

def calculate_stats(history):
    bucket_stats = {bucket: build_bucket_template() for bucket in ALL_BUCKETS}
    odds_sums = {bucket: 0.0 for bucket in ALL_BUCKETS}
    odds_counts = {bucket: 0 for bucket in ALL_BUCKETS}
    edge_sums = {bucket: 0.0 for bucket in ALL_BUCKETS}
    edge_counts = {bucket: 0 for bucket in ALL_BUCKETS}

    for item in history:
        if not isinstance(item, dict):
            continue
        bucket = item.get("bucket")
        if bucket not in bucket_stats:
            continue

        result = str(item.get("result", "")).strip().lower()
        odds = safe_float(item.get("odds"))
        edge = safe_float(item.get("edge"))
        stake = safe_float(item.get("stake"), 1.0)
        if stake is None:
            stake = 1.0

        bucket_stats[bucket]["picks"] += 1
        if odds is not None:
            odds_sums[bucket] += odds
            odds_counts[bucket] += 1
        if edge is not None:
            edge_sums[bucket] += edge
            edge_counts[bucket] += 1

        if result == "pending":
            bucket_stats[bucket]["pending"] += 1
            continue

        if result == "win":
            bucket_stats[bucket]["wins"] += 1
            bucket_stats[bucket]["settled_picks"] += 1
            bucket_stats[bucket]["staked"] += stake
            bucket_stats[bucket]["profit"] += get_pick_profit(item)
        elif result == "loss":
            bucket_stats[bucket]["losses"] += 1
            bucket_stats[bucket]["settled_picks"] += 1
            bucket_stats[bucket]["staked"] += stake
            bucket_stats[bucket]["profit"] += get_pick_profit(item)
        elif result == "storno":
            bucket_stats[bucket]["storno"] += 1
            bucket_stats[bucket]["settled_picks"] += 1

    for bucket in ALL_BUCKETS:
        stats = bucket_stats[bucket]
        if odds_counts[bucket] > 0:
            stats["avg_odds"] = round(odds_sums[bucket] / odds_counts[bucket], 2)
        if edge_counts[bucket] > 0:
            stats["avg_edge"] = round(edge_sums[bucket] / edge_counts[bucket], 4)

        settled_without_storno = stats["wins"] + stats["losses"]
        if settled_without_storno > 0:
            stats["hit_rate"] = round((stats["wins"] / settled_without_storno) * 100, 2)
        if stats["staked"] > 0:
            stats["roi"] = round((stats["profit"] / stats["staked"]) * 100, 2)

        stats["profit"] = round(stats["profit"], 2)
        stats["staked"] = round(stats["staked"], 2)

    total = build_bucket_template()
    total_odds_sum = total_edge_sum = 0.0
    total_odds_count = total_edge_count = 0

    for bucket in ALL_BUCKETS:
        stats = bucket_stats[bucket]
        total["picks"] += stats["picks"]
        total["settled_picks"] += stats["settled_picks"]
        total["wins"] += stats["wins"]
        total["losses"] += stats["losses"]
        total["storno"] += stats["storno"]
        total["pending"] += stats["pending"]
        total["profit"] += stats["profit"]
        total["staked"] += stats["staked"]

        total_odds_sum += odds_sums[bucket]
        total_odds_count += odds_counts[bucket]
        total_edge_sum += edge_sums[bucket]
        total_edge_count += edge_counts[bucket]

    if total_odds_count > 0:
        total["avg_odds"] = round(total_odds_sum / total_odds_count, 2)
    if total_edge_count > 0:
        total["avg_edge"] = round(total_edge_sum / total_edge_count, 4)

    total_settled_without_storno = total["wins"] + total["losses"]
    if total_settled_without_storno > 0:
        total["hit_rate"] = round((total["wins"] / total_settled_without_storno) * 100, 2)
    if total["staked"] > 0:
        total["roi"] = round((total["profit"] / total["staked"]) * 100, 2)

    total["profit"] = round(total["profit"], 2)
    total["staked"] = round(total["staked"], 2)

    return {
        "model": "AI77 Lab Buckets v1",
        "stats_generated": True,
        "overall": total,
        "by_bucket": bucket_stats
    }

def main():
    history = load_json_file(LAB_RESULTS_FILE, [])
    if not isinstance(history, list):
        history = []
    stats = calculate_stats(history)
    save_json_file(LAB_STATS_FILE, stats)
    print(f"Saved {LAB_STATS_FILE}")

if __name__ == "__main__":
    main()
