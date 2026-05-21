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


def reject_reasons(p):
    reasons = []

    odds = fnum(p.get("odds"))
    stake_label = str(p.get("stake_label", ""))
    fav = str(p.get("favorite_type", "")).lower()
    tour = str(p.get("tour_level", "")).lower()
    edge = fnum(p.get("edge"))

    if odds < 1.70:
        reasons.append("odds_below_1.70")

    if odds > 2.09:
        reasons.append("odds_above_2.09")

    if stake_label == "Top Rated":
        reasons.append("top_rated_disabled")

    if fav == "underdog" and odds >= 2.10:
        reasons.append("high_underdog")

    if tour in ["atp", "wta", "itf"] and odds >= 2.10:
        reasons.append("high_odds_non_challenger")

    if edge >= 0.12 and odds >= 2.10:
        reasons.append("inflated_high_edge_zone")

    return reasons


def score_pick(p):
    odds = fnum(p.get("odds"))
    edge = fnum(p.get("edge"))
    confidence = fnum(p.get("confidence"))
    quality = fnum(p.get("quality_score"))
    tour = str(p.get("tour_level", "")).lower()
    fav = str(p.get("favorite_type", "")).lower()
    stake_label = str(p.get("stake_label", ""))

    score = 0

    if 1.70 <= odds <= 1.89:
        score += 35
    elif 1.90 <= odds <= 2.09:
        score += 30

    if 0.065 <= edge < 0.08:
        score += 20
    elif 0.10 <= edge < 0.12:
        score += 18
    elif 0.08 <= edge < 0.10:
        score += 5

    if tour == "challenger":
        score += 12
    elif tour in ["atp", "wta"]:
        score += 4

    if fav == "favorite":
        score += 10
    elif fav == "underdog" and odds <= 2.09:
        score += 5

    if stake_label == "Strong":
        score += 10
    elif stake_label == "Standard":
        score += 6
    elif stake_label == "Small Value":
        score += 4

    if 82 <= confidence < 86:
        score += 8
    elif confidence >= 86:
        score += 3

    score += min(quality / 10, 10)

    return round(score, 2)


def normalize_stake(p):
    odds = fnum(p.get("odds"))
    stake_label = str(p.get("stake_label", ""))

    if 1.70 <= odds < 1.90 and stake_label == "Strong":
        return 1.0

    if 1.90 <= odds <= 2.09 and stake_label in ["Standard", "Strong"]:
        return 0.75

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
        source_meta = {
            "generated_at": raw_payload.get("generated_at"),
            "source": raw_payload.get("source"),
            "model": raw_payload.get("model"),
            "summary": raw_payload.get("summary")
        }
        raw = raw_payload.get("picks", [])
    elif isinstance(raw_payload, list):
        source_meta = {}
        raw = raw_payload
    else:
        source_meta = {}
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
        p["ai77_score"] = score_pick(p)

        reasons = reject_reasons(p)

        if reasons:
            p["reject_reasons"] = reasons

            if fnum(p.get("odds")) <= 2.40 and p.get("stake_label") != "Top Rated":
                watchlist.append(p)
            else:
                rejected.append(p)

            continue

        p["stake"] = normalize_stake(p)
        p["stake_label"] = "AI77 Core"
        core.append(p)

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
