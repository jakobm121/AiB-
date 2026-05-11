import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

# Kam aggregator shrani podatke za uradno stran:
# AiB/public/data/...
OUTPUT_DIR = BASE_DIR / "public" / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Vir podatkov:
# V GitHub Actions bo AI_REPO_DIR=../Ai
# Lokalno lahko kasneje nastaviš drugače.
AI_REPO_DIR = os.getenv("AI_REPO_DIR", "../Ai")
SOURCE_PREDICTIONS = Path(AI_REPO_DIR) / "data" / "tennis_totals_predictions.json"
SOURCE_RESULTS = Path(AI_REPO_DIR) / "data" / "tennis_totals_results.json"

# Registry vseh pickov, ki so bili kdaj objavljeni na public strani.
# Results/statistika se potem računa samo za te picke.
PUBLIC_PICK_IDS_FILE = OUTPUT_DIR / "totals_public_pick_ids.json"

TZ = ZoneInfo("Europe/Ljubljana")

# Safety nastavitve
MIN_MINUTES_BEFORE_START = 15
MAX_DAYS_AHEAD = 3

ALLOWED_BUCKETS = {"total_games"}
ALLOWED_SIDES = {"under", "over"}

# Public quality filter
# Underje pustimo relativno normalno, ker delajo dobro.
MIN_PUBLIC_EDGE = 0.025
MIN_PUBLIC_QUALITY_SCORE = 55
MIN_PUBLIC_CONFIDENCE = 52

# Overji so premium-only.
OVER_MAX_LINE = 20.5
OVER_MIN_EDGE = 0.080
OVER_MIN_QUALITY_SCORE = 78
OVER_MIN_CONFIDENCE = 83
OVER_MIN_EXPECTED_MARGIN = 1.35
OVER_MIN_COMBINED_OVER_21_5_RATE = 0.40
OVER_MAX_MARKET_GAP = 0.55


def load_json(path: Path):
    if not path.exists():
        print(f"Missing file: {path}")
        return []

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Could not read JSON: {path}")
        print(e)
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["predictions", "results", "picks", "data"]:
            if isinstance(data.get(key), list):
                return data[key]

    print(f"Unsupported JSON structure: {path}")
    return []


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def to_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def normalize_side(value):
    return str(value or "").strip().lower()


def load_public_pick_ids():
    data = load_json(PUBLIC_PICK_IDS_FILE)

    if isinstance(data, list):
        return set(str(x) for x in data if x)

    return set()


def save_public_pick_ids(pick_ids):
    save_json(PUBLIC_PICK_IDS_FILE, sorted(str(x) for x in pick_ids if x))


def get_nested_float(item, path, default=None):
    cur = item

    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)

    return to_float(cur, default)


def combined_over_21_5_rate(item):
    first = get_nested_float(item, ("first_form", "last_10", "over_21_5_rate"), None)
    second = get_nested_float(item, ("second_form", "last_10", "over_21_5_rate"), None)

    values = [x for x in (first, second) if x is not None]

    if not values:
        return None

    return sum(values) / len(values)


def market_gap(item):
    direct = to_float(item.get("market_gap"), None)
    if direct is not None:
        return direct

    return get_nested_float(item, ("market_info", "market_gap"), None)


def passes_public_quality_filter(item):
    side = normalize_side(item.get("side"))

    edge = to_float(item.get("edge"), None)
    quality_score = to_float(item.get("quality_score"), None)
    confidence = to_float(item.get("confidence"), None)
    line = to_float(item.get("line"), None)
    expected_margin = to_float(item.get("expected_margin"), None)

    if edge is None or quality_score is None or confidence is None:
        return False

    if side == "under":
        return (
            edge >= MIN_PUBLIC_EDGE
            and quality_score >= MIN_PUBLIC_QUALITY_SCORE
            and confidence >= MIN_PUBLIC_CONFIDENCE
        )

    if side == "over":
        if line is None or expected_margin is None:
            return False

        if line > OVER_MAX_LINE:
            return False

        # Če prediction JSON ima form over rate, ga uporabimo.
        # Če ga nima, ga ne blokiramo, da ne ubijemo vseh overjev zaradi manjkajočega polja.
        over_rate = combined_over_21_5_rate(item)
        if over_rate is not None and over_rate < OVER_MIN_COMBINED_OVER_21_5_RATE:
            return False

        gap = market_gap(item)
        if gap is not None and gap > OVER_MAX_MARKET_GAP:
            return False

        return (
            edge >= OVER_MIN_EDGE
            and quality_score >= OVER_MIN_QUALITY_SCORE
            and confidence >= OVER_MIN_CONFIDENCE
            and expected_margin >= OVER_MIN_EXPECTED_MARGIN
        )

    return False


def parse_event_datetime(item):
    date_str = item.get("date")
    time_str = item.get("time")

    if not date_str or not time_str:
        return None

    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=TZ)
    except Exception:
        return None


def normalize_pick(item):
    event_dt = parse_event_datetime(item)

    return {
        "pick_id": item.get("pick_id"),
        "event_key": item.get("event_key") or item.get("fixture_id"),
        "fixture_id": item.get("fixture_id") or item.get("event_key"),
        "sport": item.get("sport", "tennis"),
        "model_version": item.get("model_version"),
        "date": item.get("date"),
        "time": item.get("time"),
        "event_ts": event_dt.isoformat() if event_dt else None,
        "match": item.get("match"),
        "bet": item.get("bet"),
        "bucket": item.get("bucket"),
        "side": item.get("side"),
        "market": item.get("market"),
        "line": item.get("line"),
        "odds": item.get("odds"),
        "best_bookmaker": item.get("best_bookmaker"),
        "market_median_odds": item.get("market_median_odds"),
        "bookmakers_used": item.get("bookmakers_used"),
        "model_prob": item.get("model_prob"),
        "implied_prob": item.get("implied_prob"),
        "edge": item.get("edge"),
        "expected_total_games": item.get("expected_total_games"),
        "expected_margin": item.get("expected_margin"),
        "confidence": item.get("confidence"),
        "quality_score": item.get("quality_score"),
        "stake": item.get("stake"),
        "stake_label": item.get("stake_label"),
        "tournament": item.get("tournament"),
        "round": item.get("round"),
        "event_type": item.get("event_type"),
        "tour_level": item.get("tour_level"),
        "gender": item.get("gender"),
        "created_at": item.get("created_at"),
    }


def is_valid_base_pick(item):
    if not item.get("pick_id"):
        return False

    if not (item.get("event_key") or item.get("fixture_id")):
        return False

    if item.get("bucket") not in ALLOWED_BUCKETS:
        return False

    if item.get("side") not in ALLOWED_SIDES:
        return False

    if not item.get("match"):
        return False

    if item.get("line") is None:
        return False

    if item.get("odds") is None:
        return False

    return True


def is_safe_upcoming_pick(item, now):
    if not is_valid_base_pick(item):
        return False

    event_dt = parse_event_datetime(item)

    if not event_dt:
        return False

    # Ne objavi tekem, ki so se že začele ali se začnejo prehitro.
    if event_dt <= now + timedelta(minutes=MIN_MINUTES_BEFORE_START):
        return False

    # Ne objavi predaleč v prihodnost.
    if event_dt > now + timedelta(days=MAX_DAYS_AHEAD):
        return False

    # Ne objavi, če je pick že settled ali ima rezultat.
    result = item.get("result")
    if result and result != "pending":
        return False

    if item.get("settled_at"):
        return False

    if item.get("final_score"):
        return False

    if item.get("total_games") is not None:
        return False

    if not passes_public_quality_filter(item):
        return False

    return True


def pick_sort_score(item):
    side = normalize_side(item.get("side"))
    line = to_float(item.get("line"), 0) or 0

    # Underjev NE spreminjamo po line-u, ker so trenutno dobri.
    # Overji pa naj pri isti tekmi preferirajo nižji line.
    if side == "over":
        line_score = -line
    else:
        line_score = 0

    return (
        line_score,
        to_float(item.get("quality_score"), 0) or 0,
        to_float(item.get("confidence"), 0) or 0,
        to_float(item.get("edge"), 0) or 0,
        to_float(item.get("odds"), 0) or 0,
    )


def dedupe_picks(items):
    """
    Če se ista tekma pojavi večkrat, pustimo najboljši pick.

    Ključ namenoma NE vključuje line, ker nočemo na strani prikazati iste tekme dvakrat,
    recimo:
    OVER 20.5 in OVER 21.5 za isti match.

    Under:
    - ostane po obstoječi logiki quality/confidence/edge/odds.

    Over:
    - najprej preferira nižji line,
    - potem quality/confidence/edge/odds.
    """
    best = {}

    for item in items:
        key = (
            item.get("fixture_id") or item.get("event_key"),
            item.get("bucket"),
            item.get("side"),
        )

        old = best.get(key)

        if old is None:
            best[key] = item
            continue

        if pick_sort_score(item) > pick_sort_score(old):
            best[key] = item

    return list(best.values())


def aggregate_predictions():
    now = datetime.now(TZ)

    raw = load_json(SOURCE_PREDICTIONS)

    safe = [item for item in raw if is_safe_upcoming_pick(item, now)]
    safe = dedupe_picks(safe)

    safe.sort(
        key=lambda x: (
            parse_event_datetime(x) or datetime.max.replace(tzinfo=TZ),
            -(to_float(x.get("quality_score"), 0) or 0),
            -(to_float(x.get("confidence"), 0) or 0),
            -(to_float(x.get("edge"), 0) or 0),
        )
    )

    public_items = [normalize_pick(item) for item in safe]

    # Shrani registry pickov, ki so bili dejansko objavljeni.
    # To je ključno, da results/statistika ne vključuje vseh Ai rezultatov,
    # ampak samo public picke.
    public_pick_ids = load_public_pick_ids()

    for item in public_items:
        pick_id = item.get("pick_id")
        if pick_id:
            public_pick_ids.add(str(pick_id))

    save_public_pick_ids(public_pick_ids)

    save_json(OUTPUT_DIR / "totals_predictions.json", public_items)

    print(f"Loaded predictions: {len(raw)}")
    print(f"Published predictions: {len(public_items)}")
    print(f"Public registry size: {len(public_pick_ids)}")


def is_valid_result_pick(item):
    if not is_valid_base_pick(item):
        return False

    result = item.get("result")
    if result not in {"win", "loss", "void", "push"}:
        return False

    if not item.get("settled_at"):
        return False

    return True


def normalize_result(item):
    base = normalize_pick(item)

    base.update({
        "result": item.get("result"),
        "profit": item.get("profit"),
        "settled_at": item.get("settled_at"),
        "settled_status": item.get("settled_status"),
        "event_winner": item.get("event_winner"),
        "final_score": item.get("final_score"),
        "total_games": item.get("total_games"),
    })

    return base


def aggregate_results():
    raw = load_json(SOURCE_RESULTS)

    public_pick_ids = load_public_pick_ids()

    valid = [
        item for item in raw
        if is_valid_result_pick(item)
        and str(item.get("pick_id")) in public_pick_ids
    ]

    valid = dedupe_picks(valid)

    valid.sort(
        key=lambda x: (
            x.get("date") or "",
            x.get("time") or "",
            x.get("match") or "",
        ),
        reverse=True,
    )

    public_items = [normalize_result(item) for item in valid]

    save_json(OUTPUT_DIR / "totals_results.json", public_items)

    wins = sum(1 for x in public_items if x.get("result") == "win")
    losses = sum(1 for x in public_items if x.get("result") == "loss")
    pushes = sum(1 for x in public_items if x.get("result") in {"push", "void"})

    settled_total = wins + losses
    all_total = wins + losses + pushes

    profit = round(sum(float(x.get("profit") or 0) for x in public_items), 3)
    roi = round((profit / settled_total) * 100, 2) if settled_total else 0
    win_rate = round((wins / settled_total) * 100, 2) if settled_total else 0

    stats = {
        "total_picks": all_total,
        "settled_picks": settled_total,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": win_rate,
        "profit": profit,
        "roi": roi,
        "public_registry_size": len(public_pick_ids),
        "updated_at": datetime.now(TZ).isoformat(),
    }

    save_json(OUTPUT_DIR / "totals_stats.json", stats)

    print(f"Loaded results: {len(raw)}")
    print(f"Published results: {len(public_items)}")
    print(f"Public registry size: {len(public_pick_ids)}")
    print(f"Stats: {stats}")


def main():
    aggregate_predictions()
    aggregate_results()


if __name__ == "__main__":
    main()
