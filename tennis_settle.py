import json
import urllib.request
from pathlib import Path
from datetime import datetime

AI_RESULTS_URL = "https://raw.githubusercontent.com/jakobm121/Ai/refs/heads/main/data/tennis_results.json"

DATA_DIR = Path("public/data")
CORE_PICKS_FILE = DATA_DIR / "tennis_predictions.json"
CORE_RESULTS_FILE = DATA_DIR / "tennis_core_results.json"
CORE_STATS_FILE = DATA_DIR / "tennis_core_stats.json"

SETTLED = {"win", "loss", "void", "push"}


def load_json_file(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def load_remote_json(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fnum(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def pick_key(p):
    return str(
        p.get("pick_id")
        or p.get("fixture_id")
        or p.get("event_key")
        or f"{p.get('date')}|{p.get('match')}|{p.get('bet')}"
    )


def calc_profit(p):
    result = str(p.get("result", "pending")).lower()
    odds = fnum(p.get("odds"))
    stake = fnum(p.get("stake"), 1)

    if result == "win":
        return round((odds - 1) * stake, 2)
    if result == "loss":
        return round(-stake, 2)
    return 0.0


def normalize_result(p):
    r = str(p.get("result", "pending")).lower()
    if r in SETTLED:
        return r
    return "pending"


def summarize(items):
    settled = [p for p in items if normalize_result(p) in {"win", "loss"}]
    wins = sum(1 for p in settled if normalize_result(p) == "win")
    losses = sum(1 for p in settled if normalize_result(p) == "loss")
    staked = sum(fnum(p.get("stake"), 1) for p in settled)
    profit = sum(fnum(p.get("profit")) for p in settled)

    return {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "total_picks": len(items),
        "settled_picks": len(settled),
        "pending_picks": sum(1 for p in items if normalize_result(p) == "pending"),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(settled) * 100, 2) if settled else 0,
        "staked": round(staked, 2),
        "profit": round(profit, 2),
        "roi": round(profit / staked * 100, 2) if staked else 0,
    }


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    current_core = load_json_file(CORE_PICKS_FILE, [])
    existing_results = load_json_file(CORE_RESULTS_FILE, [])

    remote_payload = load_remote_json(AI_RESULTS_URL)

    if isinstance(remote_payload, dict):
        remote_results = remote_payload.get("results", remote_payload.get("picks", []))
    elif isinstance(remote_payload, list):
        remote_results = remote_payload
    else:
        remote_results = []

    remote_by_key = {pick_key(p): p for p in remote_results}
    merged_by_key = {pick_key(p): p for p in existing_results}

    for p in current_core:
        key = pick_key(p)

        base = merged_by_key.get(key, {})
        item = {**base, **p}

        item["core_added_at"] = base.get("core_added_at") or datetime.utcnow().isoformat() + "Z"
        item["settled_at"] = base.get("settled_at")
        item["result"] = base.get("result", "pending")
        item["profit"] = base.get("profit", 0)

        merged_by_key[key] = item

    for key, item in list(merged_by_key.items()):
        remote = remote_by_key.get(key)

        if not remote:
            continue

        remote_result = normalize_result(remote)

        if remote_result in SETTLED:
            item["result"] = remote_result
            item["final_score"] = remote.get("final_score", item.get("final_score"))
            item["settled_at"] = item.get("settled_at") or datetime.utcnow().isoformat() + "Z"
            item["profit"] = fnum(remote.get("profit"), calc_profit(item))

            merged_by_key[key] = item

    results = list(merged_by_key.values())
    results.sort(key=lambda p: f"{p.get('date', '')} {p.get('time', '')}", reverse=True)

    stats = summarize(results)

    CORE_RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    CORE_STATS_FILE.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Core results: {len(results)}")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
