import json
import urllib.request
from pathlib import Path
from datetime import datetime

SOURCE_URL = "https://raw.githubusercontent.com/jakobm121/Ai/refs/heads/main/data/tennis_predictions.json"

OUT_DIR = Path("public/data")
CORE_FILE = OUT_DIR / "tennis_predictions.json"
WATCHLIST_FILE = OUT_DIR / "tennis_watchlist.json"
REJECTED_FILE = OUT_DIR / "tennis_rejected.json"

MAX_CORE_PICKS = 8


def fnum(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def load_remote_json(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def pick_key(p):
    return f"{p.get('date')}|{p.get('match')}|{p.get('bet')}"


def strategy_tag(p):
    odds = fnum(p.get("odds"))
    edge = fnum(p.get("edge"))
    tour = str(p.get("tour_level", "")).lower()
    fav = str(p.get("favorite_type", "")).lower()
    stake_label = str(p.get("stake_label", ""))

    if tour == "wta" and fav == "favorite" and 1.70 <= odds <= 2.09 and stake_label != "Top Rated":
        return "core_wta_favorite_1.70_2.09"

    if tour == "atp" and fav == "favorite" and 1.70 <= odds <= 2.09:
        return "core_atp_favorite_1.70_2.09"

    if tour == "itf" and fav == "favorite" and 1.70 <= odds < 1.90:
        return "core_itf_favorite_1.70_1.89"

    if tour == "challenger" and fav == "underdog" and 2.10 <= odds <= 2.39 and edge >= 0.12:
        return "core_challenger_dog_2.10_2.39_edge12"

    return None


def watchlist_tag(p):
    odds = fnum(p.get("odds"))
    edge = fnum(p.get("edge"))
    tour = str(p.get("tour_level", "")).lower()
    fav = str(p.get("favorite_type", "")).lower()
    stake_label = str(p.get("stake_label", ""))

    if tour == "challenger" and fav == "underdog" and 2.40 <= odds <= 2.70 and edge >= 0.12:
        return "watch_challenger_dog_2.40_2.70_edge12"

    if tour == "challenger" and fav == "underdog" and 2.10 <= odds <= 2.70:
        return "watch_challenger_dog_2.10_2.70"

    if 1.70 <= odds <= 2.09 and stake_label != "Top Rated":
        return "watch_old_core_1.70_2.09_no_top_rated"

    return None


def reject_reasons(p):
    reasons = []

    odds = fnum(p.get("odds"))
    edge = fnum(p.get("edge"))
    tour = str(p.get("tour_level", "")).lower()
    fav = str(p.get("favorite_type", "")).lower()
    stake_label = str(p.get("stake_label", ""))

    if strategy_tag(p):
        return reasons

    if odds < 1.70:
        reasons.append("odds_below_1.70")

    if odds > 2.70:
        reasons.append("odds_above_2.70")

    if stake_label == "Top Rated" and not (
        tour == "challenger" and fav == "underdog" and 2.10 <= odds <= 2.39
    ):
        reasons.append("top_rated_disabled_outside_challenger_dog_zone")

    if fav == "underdog" and tour in ["atp", "wta", "itf"] and odds >= 2.10:
        reasons.append("bad_historical_underdog_zone")

    if tour in ["atp", "wta"] and fav == "underdog":
        reasons.append("atp_wta_underdog_disabled")

    if tour == "itf" and fav == "underdog":
        reasons.append("itf_underdog_disabled")

    if tour == "wta" and fav == "underdog":
        reasons.append("wta_underdog_disabled")

    if tour == "atp" and fav == "underdog":
        reasons.append("atp_underdog_disabled")

    if tour == "itf" and fav == "favorite" and odds >= 1.90:
        reasons.append("itf_favorite_above_1.89_weak")

    if tour == "challenger" and fav == "favorite" and odds < 1.90:
        reasons.append("challenger_favorite_1.70_1.89_weak")

    if tour == "challenger" and fav == "favorite" and odds > 2.09:
        reasons.append("challenger_favorite_high_odds_disabled")

    if edge >= 0.12 and tour != "challenger" and odds >= 2.10:
        reasons.append("inflated_high_edge_non_challenger")

    if not reasons:
        reasons.append("no_approved_strategy")

    return reasons


def score_pick(p):
    odds = fnum(p.get("odds"))
    edge = fnum(p.get("edge"))
    confidence = fnum(p.get("confidence"))
    quality = fnum(p.get("quality_score"))
    tag = strategy_tag(p)
    watch = watchlist_tag(p)

    score = 0

    if tag == "core_challenger_dog_2.10_2.39_edge12":
        score += 70
    elif tag == "core_wta_favorite_1.70_2.09":
        score += 62
    elif tag == "core_atp_favorite_1.70_2.09":
        score += 58
    elif tag == "core_itf_favorite_1.70_1.89":
        score += 48
    elif watch:
        score += 25

    if 1.70 <= odds <= 1.89:
        score += 12
    elif 1.90 <= odds <= 2.09:
        score += 10
    elif 2.10 <= odds <= 2.39:
        score += 14
    elif 2.40 <= odds <= 2.70:
        score += 4

    if 0.065 <= edge < 0.08:
        score += 8
    elif 0.08 <= edge < 0.10:
        score += 2
    elif 0.10 <= edge < 0.12:
        score += 7
    elif edge >= 0.12:
        score += 10

    if 82 <= confidence < 86:
        score += 5
    elif confidence >= 86:
        score += 3

    score += min(quality / 15, 6)

    return round(score, 2)


def normalize_stake(p):
    tag = p.get("strategy_tag") or strategy_tag(p)

    if tag == "core_challenger_dog_2.10_2.39_edge12":
        return 1.0

    if tag == "core_wta_favorite_1.70_2.09":
        return 0.75

    if tag == "core_atp_favorite_1.70_2.09":
        return 0.75

    if tag == "core_itf_favorite_1.70_1.89":
        return 0.5

    return 0.5


def dedupe(picks):
    best = {}

    for p in picks:
        key = pick_key(p)
        current = best.get(key)

        if current is None:
            best[key] = p
            continue

        if score_pick(p) > score_pick(current):
            best[key] = p

    return list(best.values())


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_payload = load_remote_json(SOURCE_URL)

    if isinstance(raw_payload, dict):
        raw = raw_payload.get("picks", [])
    elif isinstance(raw_payload, list):
        raw = raw_payload
    else:
        raw = []

    if not isinstance(raw, list):
        raw = []

    print(f"Loaded raw picks: {len(raw)}")

    raw = dedupe(raw)

    core = []
    watchlist = []
    rejected = []

    for p in raw:
        p = dict(p)
        p["aggregated_at"] = datetime.utcnow().isoformat() + "Z"

        tag = strategy_tag(p)
        watch_tag = watchlist_tag(p)

        p["strategy_tag"] = tag
        p["watchlist_tag"] = watch_tag
        p["ai77_score"] = score_pick(p)

        if tag:
            p["stake"] = normalize_stake(p)
            p["stake_label"] = "AI77 Core"
            core.append(p)
            continue

        reasons = reject_reasons(p)
        p["reject_reasons"] = reasons

        if watch_tag:
            watchlist.append(p)
        else:
            rejected.append(p)

    core.sort(key=lambda x: x.get("ai77_score", 0), reverse=True)
    watchlist.sort(key=lambda x: x.get("ai77_score", 0), reverse=True)
    rejected.sort(key=lambda x: x.get("ai77_score", 0), reverse=True)

    core = core[:MAX_CORE_PICKS]

    CORE_FILE.write_text(json.dumps(core, indent=2, ensure_ascii=False), encoding="utf-8")
    WATCHLIST_FILE.write_text(json.dumps(watchlist, indent=2, ensure_ascii=False), encoding="utf-8")
    REJECTED_FILE.write_text(json.dumps(rejected, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Core picks: {len(core)}")
    print(f"Watchlist: {len(watchlist)}")
    print(f"Rejected: {len(rejected)}")


if __name__ == "__main__":
    main()
