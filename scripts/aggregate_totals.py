import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parents[1]

OUTPUT_DIR = BASE_DIR / "public" / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AI_REPO_DIR = os.getenv("AI_REPO_DIR", "../Ai")
SOURCE_PREDICTIONS = Path(AI_REPO_DIR) / "data" / "tennis_totals_predictions.json"
SOURCE_RESULTS = Path(AI_REPO_DIR) / "data" / "tennis_totals_results.json"

PUBLIC_PICK_IDS_FILE = OUTPUT_DIR / "totals_public_pick_ids.json"
BACKTEST_REPORT_FILE = OUTPUT_DIR / "totals_backtest_report.json"

TZ = ZoneInfo("Europe/Ljubljana")

MIN_MINUTES_BEFORE_START = 15
MAX_DAYS_AHEAD = 3

ALLOWED_BUCKETS = {"total_games"}
ALLOWED_SIDES = {"under", "over"}
SETTLED_RESULTS = {"win", "loss", "push", "void"}

# Base public filter.
# UNDER je v praksi zdaj strožji, ker calculate_public_stake()
# pod confidence 82 vrne 0u in se tak pick ne objavi.
MIN_PUBLIC_EDGE = 0.025
MIN_PUBLIC_QUALITY_SCORE = 55
MIN_PUBLIC_CONFIDENCE = 74

# Overji ostanejo tiered kot do zdaj.
# Za zdaj over filtrov ne spreminjamo, ker so v AiB že precej strogi.
OVER_TIER_FILTERS = [
    {
        "max_line": 20.5,
        "min_edge": 0.080,
        "min_quality_score": 78,
        "min_confidence": 83,
        "min_expected_margin": 1.35,
        "min_combined_over_21_5_rate": 0.40,
        "max_market_gap": 0.55,
    },
    {
        "max_line": 21.5,
        "min_edge": 0.090,
        "min_quality_score": 82,
        "min_confidence": 86,
        "min_expected_margin": 1.75,
        "min_combined_over_21_5_rate": 0.55,
        "max_market_gap": 0.45,
    },
    {
        "max_line": 22.5,
        "min_edge": 0.110,
        "min_quality_score": 88,
        "min_confidence": 90,
        "min_expected_margin": 2.40,
        "min_combined_over_21_5_rate": 0.65,
        "max_market_gap": 0.30,
    },
]

MAX_OVER_LINE = 22.5


def load_json(path: Path, default=None):
    if default is None:
        default = []

    if not path.exists():
        print(f"Missing file: {path}")
        return default

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Could not read JSON: {path}")
        print(e)
        return default

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["predictions", "results", "picks", "data"]:
            if isinstance(data.get(key), list):
                return data[key]

    return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def to_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def normalize_side(value):
    return str(value or "").strip().lower()


def normalize_result_value(value):
    return str(value or "").strip().lower()


def load_public_pick_ids():
    data = load_json(PUBLIC_PICK_IDS_FILE, [])

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


def get_over_tier(line):
    if line is None:
        return None

    for tier in OVER_TIER_FILTERS:
        if line <= tier["max_line"]:
            return tier

    return None


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

        if line > MAX_OVER_LINE:
            return False

        tier = get_over_tier(line)

        if not tier:
            return False

        over_rate = combined_over_21_5_rate(item)
        gap = market_gap(item)

        # Če podatka ni, ga ne blokiramo.
        # Če obstaja, mora prestati prag.
        if over_rate is not None and over_rate < tier["min_combined_over_21_5_rate"]:
            return False

        if gap is not None and gap > tier["max_market_gap"]:
            return False

        return (
            edge >= tier["min_edge"]
            and quality_score >= tier["min_quality_score"]
            and confidence >= tier["min_confidence"]
            and expected_margin >= tier["min_expected_margin"]
        )

    return False


def stake_label_for_units(stake):
    if stake >= 1.0:
        return "Top Rated"

    if stake >= 0.75:
        return "Strong"

    return "Standard"


def calculate_public_stake(item):
    """
    AI77 Public Stake - Profile C+ calibrated version.

    UNDER:
    - confidence < 82 = No Pick
    - confidence 82-85.99 = 1.00u
    - confidence 86-89.99 = 0.50u
    - confidence 86-89.99 + edge/quality support = 0.75u
    - confidence 90+ = 0.75u
    - confidence 90+ + edge/quality support = 1.00u

    OVER:
    - obstoječi over filter ostane
    - večinoma 0.50u
    - max 0.75u
    - za zdaj over nima 1.00u
    """
    side = normalize_side(item.get("side"))

    confidence = to_float(item.get("confidence"), 0) or 0
    quality_score = to_float(item.get("quality_score"), 0) or 0
    expected_margin = to_float(item.get("expected_margin"), 0) or 0
    edge = to_float(item.get("edge"), 0) or 0
    line = to_float(item.get("line"), 0) or 0

    if side == "under":
        if confidence < 82:
            return 0.0, "No Pick"

        # Profile C sweet spot.
        if confidence < 86:
            stake = 1.00
            label = "Top Rated"

        # 86-90 je bil slabši segment, zato baseline ostane 0.50u.
        elif confidence < 90:
            stake = 0.50
            label = "Standard"

            # Edge 0.10+ je tukaj boost signal, ne osnovni pogoj.
            if edge >= 0.10 and quality_score >= 82:
                stake = 0.75
                label = "Strong"

        # 90+ je pozitiven, ampak ne avtomatsko najboljši.
        else:
            stake = 0.75
            label = "Strong"

            # Top Rated samo, če ima dodaten value/quality support.
            if (edge >= 0.10 and quality_score >= 82) or quality_score >= 86:
                stake = 1.00
                label = "Top Rated"

        # Safety cap: če je margin prenizek, ne dovolimo agresivnega stake-a.
        if expected_margin > -1.50:
            stake = min(stake, 0.50)
            label = stake_label_for_units(stake)

        # 18.5 ima premalo vzorca.
        if line == 18.5:
            stake = min(stake, 0.50)
            label = stake_label_for_units(stake)

        return round(stake, 2), label

    if side == "over":
        # Overji so že filtrirani v passes_public_quality_filter.
        # Tukaj jih samo capped stakamo.
        stake = 0.50
        label = "Standard"

        # Over boost samo za najbolj čiste situacije.
        # Ne uporabljamo 1.00u za over, dokler ni več stabilne zgodovine.
        if (
            line <= 20.5
            and confidence >= 90
            and quality_score >= 82
            and expected_margin >= 2.50
            and edge >= 0.08
        ):
            stake = 0.75
            label = "Strong"

        return round(stake, 2), label

    return 0.0, "No Pick"


def is_public_pick_publishable(item):
    if not passes_public_quality_filter(item):
        return False

    public_stake, _ = calculate_public_stake(item)

    return public_stake > 0


def calculate_public_profit(item):
    result = normalize_result_value(item.get("result"))
    odds = to_float(item.get("odds"), None)
    public_stake, _ = calculate_public_stake(item)

    if result in {"push", "void"}:
        return 0.0

    if result == "win":
        if odds is None:
            return 0.0
        return round(public_stake * (odds - 1), 3)

    if result == "loss":
        return round(-public_stake, 3)

    return 0.0


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
    public_stake, public_stake_label = calculate_public_stake(item)

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

        # Original internal stake from Ai.
        "model_stake": item.get("stake"),
        "model_stake_label": item.get("stake_label"),

        # Public stake used by AiB.
        "stake": public_stake,
        "stake_label": public_stake_label,
        "public_stake": public_stake,
        "public_stake_label": public_stake_label,

        "tournament": item.get("tournament"),
        "round": item.get("round"),
        "event_type": item.get("event_type"),
        "tour_level": item.get("tour_level"),
        "gender": item.get("gender"),
        "created_at": item.get("created_at"),
    }


def normalize_result(item):
    base = normalize_pick(item)

    public_profit = calculate_public_profit(item)

    base.update({
        "result": normalize_result_value(item.get("result")),
        "profit": public_profit,
        "public_profit": public_profit,
        "model_profit": item.get("profit"),
        "settled_at": item.get("settled_at"),
        "settled_status": item.get("settled_status"),
        "event_winner": item.get("event_winner"),
        "final_score": item.get("final_score"),
        "total_games": item.get("total_games"),
    })

    return base


def is_valid_base_pick(item):
    if not isinstance(item, dict):
        return False

    if not item.get("pick_id"):
        return False

    if not (item.get("event_key") or item.get("fixture_id")):
        return False

    if item.get("bucket") not in ALLOWED_BUCKETS:
        return False

    if normalize_side(item.get("side")) not in ALLOWED_SIDES:
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

    if event_dt <= now + timedelta(minutes=MIN_MINUTES_BEFORE_START):
        return False

    if event_dt > now + timedelta(days=MAX_DAYS_AHEAD):
        return False

    result = normalize_result_value(item.get("result"))

    if result and result != "pending":
        return False

    if item.get("settled_at"):
        return False

    if item.get("final_score"):
        return False

    if item.get("total_games") is not None:
        return False

    if not is_public_pick_publishable(item):
        return False

    return True


def is_valid_result_pick(item):
    if not is_valid_base_pick(item):
        return False

    result = normalize_result_value(item.get("result"))

    if result not in SETTLED_RESULTS:
        return False

    # Void/retired/cancelled ima lahko final_score null.
    if result in {"win", "loss", "push"}:
        if item.get("total_games") is None and not item.get("final_score"):
            return False

    if not is_public_pick_publishable(item):
        return False

    return True


def pick_sort_score(item):
    side = normalize_side(item.get("side"))
    line = to_float(item.get("line"), 0) or 0

    # Underjev ne spreminjamo po line-u.
    # Overji pri isti tekmi preferirajo nižji line.
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
    best = {}

    for item in items:
        key = (
            item.get("fixture_id") or item.get("event_key"),
            item.get("bucket"),
            normalize_side(item.get("side")),
        )

        old = best.get(key)

        if old is None:
            best[key] = item
            continue

        if pick_sort_score(item) > pick_sort_score(old):
            best[key] = item

    return list(best.values())


def sort_predictions(items):
    return sorted(
        items,
        key=lambda x: (
            parse_event_datetime(x) or datetime.max.replace(tzinfo=TZ),
            -(to_float(x.get("quality_score"), 0) or 0),
            -(to_float(x.get("confidence"), 0) or 0),
            -(to_float(x.get("edge"), 0) or 0),
        ),
    )


def sort_results(items):
    return sorted(
        items,
        key=lambda x: (
            x.get("date") or "",
            x.get("time") or "",
            x.get("match") or "",
        ),
        reverse=True,
    )


def load_settled_public_pick_ids():
    raw_results = load_json(SOURCE_RESULTS, [])
    public_pick_ids = load_public_pick_ids()

    settled_ids = set()

    for item in raw_results:
        if not isinstance(item, dict):
            continue

        pick_id = item.get("pick_id")

        if not pick_id:
            continue

        if str(pick_id) not in public_pick_ids:
            continue

        result = normalize_result_value(item.get("result"))

        if result in SETTLED_RESULTS:
            settled_ids.add(str(pick_id))

    return settled_ids


def merge_open_public_predictions(previous_items, new_items, settled_pick_ids):
    """
    AiB open pick memory.

    Namen:
    - če AI repo v novem runu prepiše predictions snapshot,
      AiB ne sme izgubiti pickov, ki so bili že javno objavljeni;
    - pick ostane v totals_predictions.json, dokler se ne pojavi kot settled v AI results;
    - novi safe picki posodobijo stare podatke, če imajo isti pick_id.
    """
    merged = {}

    for item in previous_items:
        if not isinstance(item, dict):
            continue

        pick_id = item.get("pick_id")

        if not pick_id:
            continue

        if str(pick_id) in settled_pick_ids:
            continue

        # Če je bil star pick objavljen, ga pustimo odprtega do settlementa.
        # Ne filtriramo ga ponovno po novih pravilih, ker je bil že public.
        merged[str(pick_id)] = item

    for item in new_items:
        if not isinstance(item, dict):
            continue

        pick_id = item.get("pick_id")

        if not pick_id:
            continue

        if str(pick_id) in settled_pick_ids:
            continue

        merged[str(pick_id)] = item

    return sort_predictions(list(merged.values()))


def aggregate_predictions():
    now = datetime.now(TZ)

    raw = load_json(SOURCE_PREDICTIONS, [])

    safe = [item for item in raw if is_safe_upcoming_pick(item, now)]
    safe = dedupe_picks(safe)
    safe = sort_predictions(safe)

    new_public_items = [normalize_pick(item) for item in safe]

    previous_public_items = load_json(OUTPUT_DIR / "totals_predictions.json", [])

    public_pick_ids = load_public_pick_ids()

    for item in new_public_items:
        pick_id = item.get("pick_id")
        if pick_id:
            public_pick_ids.add(str(pick_id))

    save_public_pick_ids(public_pick_ids)

    settled_pick_ids = load_settled_public_pick_ids()

    public_items = merge_open_public_predictions(
        previous_items=previous_public_items,
        new_items=new_public_items,
        settled_pick_ids=settled_pick_ids,
    )

    save_json(OUTPUT_DIR / "totals_predictions.json", public_items)

    print(f"Loaded predictions: {len(raw)}")
    print(f"New safe predictions: {len(new_public_items)}")
    print(f"Previous open predictions: {len(previous_public_items)}")
    print(f"Open public predictions: {len(public_items)}")
    print(f"Settled public pick ids: {len(settled_pick_ids)}")
    print(f"Public registry size: {len(public_pick_ids)}")


def group_key(item, key):
    value = item.get(key)

    if value is None or value == "":
        return "unknown"

    return str(value)


def group_line_key(item):
    line = to_float(item.get("line"), None)

    if line is None:
        return "unknown"

    return str(line)


def empty_stats_bucket():
    return {
        "total_picks": 0,
        "settled_picks": 0,
        "wins": 0,
        "losses": 0,
        "pushes": 0,
        "win_rate": 0,
        "profit": 0,
        "roi": 0,
        "total_staked": 0,
        "avg_odds": 0,
        "avg_stake": 0,
    }


def calculate_stats(items):
    bucket = empty_stats_bucket()

    odds_values = []
    stake_values = []

    for item in items:
        result = normalize_result_value(item.get("result"))
        odds = to_float(item.get("odds"), None)
        stake = to_float(item.get("public_stake") or item.get("stake"), 0) or 0
        profit = to_float(item.get("public_profit") or item.get("profit"), 0) or 0

        if result not in SETTLED_RESULTS:
            continue

        if stake <= 0 and result in {"win", "loss"}:
            continue

        bucket["total_picks"] += 1

        if odds is not None:
            odds_values.append(odds)

        if result in {"win", "loss"}:
            bucket["settled_picks"] += 1
            bucket["total_staked"] += stake
            stake_values.append(stake)

            if result == "win":
                bucket["wins"] += 1
            elif result == "loss":
                bucket["losses"] += 1

            bucket["profit"] += profit

        elif result in {"push", "void"}:
            bucket["pushes"] += 1

    settled = bucket["settled_picks"]
    total_staked = bucket["total_staked"]

    bucket["profit"] = round(bucket["profit"], 3)
    bucket["total_staked"] = round(total_staked, 3)
    bucket["win_rate"] = round((bucket["wins"] / settled) * 100, 2) if settled else 0
    bucket["roi"] = round((bucket["profit"] / total_staked) * 100, 2) if total_staked else 0
    bucket["avg_odds"] = round(sum(odds_values) / len(odds_values), 3) if odds_values else 0
    bucket["avg_stake"] = round(sum(stake_values) / len(stake_values), 3) if stake_values else 0

    return bucket


def calculate_grouped_stats(items, key_func):
    groups = {}

    for item in items:
        key = key_func(item)
        groups.setdefault(key, []).append(item)

    return {
        key: calculate_stats(value)
        for key, value in sorted(groups.items(), key=lambda x: str(x[0]))
    }


def aggregate_results():
    raw = load_json(SOURCE_RESULTS, [])
    public_pick_ids = load_public_pick_ids()

    valid = [
        item for item in raw
        if is_valid_result_pick(item)
        and str(item.get("pick_id")) in public_pick_ids
    ]

    valid = dedupe_picks(valid)
    valid = sort_results(valid)

    public_items = [normalize_result(item) for item in valid]

    save_json(OUTPUT_DIR / "totals_results.json", public_items)

    overall = calculate_stats(public_items)

    stats = {
        **overall,
        "public_registry_size": len(public_pick_ids),
        "updated_at": datetime.now(TZ).isoformat(),
        "profit_mode": "public_stake_recalculated_profile_c_plus",
        "by_side": calculate_grouped_stats(
            public_items,
            lambda x: normalize_side(x.get("side")) or "unknown",
        ),
        "by_line": calculate_grouped_stats(public_items, group_line_key),
        "by_tour_level": calculate_grouped_stats(
            public_items,
            lambda x: group_key(x, "tour_level"),
        ),
        "by_stake_label": calculate_grouped_stats(
            public_items,
            lambda x: group_key(x, "public_stake_label") or group_key(x, "stake_label"),
        ),
    }

    save_json(OUTPUT_DIR / "totals_stats.json", stats)

    print(f"Loaded results: {len(raw)}")
    print(f"Published results: {len(public_items)}")
    print(f"Public registry size: {len(public_pick_ids)}")
    print(f"Stats: {overall}")


def build_filtered_historical_items():
    raw = load_json(SOURCE_RESULTS, [])

    candidates = [
        item for item in raw
        if is_valid_result_pick(item)
        and is_public_pick_publishable(item)
    ]

    deduped = dedupe_picks(candidates)
    deduped = sort_results(deduped)

    return raw, candidates, deduped


def backfill_public_registry(write_registry=True):
    raw, candidates, deduped = build_filtered_historical_items()

    backfill_ids = set(str(item.get("pick_id")) for item in deduped if item.get("pick_id"))

    existing_ids = load_public_pick_ids()
    final_ids = set(backfill_ids)

    if write_registry:
        save_public_pick_ids(final_ids)

    normalized = [normalize_result(item) for item in deduped]
    backtest_stats = {
        "generated_at": datetime.now(TZ).isoformat(),
        "mode": "filtered_historical_public_backfill_profile_c_plus",
        "raw_results": len(raw),
        "filtered_candidates_before_dedupe": len(candidates),
        "filtered_after_dedupe": len(deduped),
        "existing_registry_size_before": len(existing_ids),
        "registry_size_after": len(final_ids),
        "profit_mode": "public_stake_recalculated_profile_c_plus",
        "overall": calculate_stats(normalized),
        "by_side": calculate_grouped_stats(
            normalized,
            lambda x: normalize_side(x.get("side")) or "unknown",
        ),
        "by_line": calculate_grouped_stats(normalized, group_line_key),
        "by_tour_level": calculate_grouped_stats(
            normalized,
            lambda x: group_key(x, "tour_level"),
        ),
        "by_stake_label": calculate_grouped_stats(
            normalized,
            lambda x: group_key(x, "public_stake_label") or group_key(x, "stake_label"),
        ),
        "pick_ids": sorted(backfill_ids),
    }

    save_json(BACKTEST_REPORT_FILE, backtest_stats)

    print("Filtered historical backfill")
    print(f"Raw results: {len(raw)}")
    print(f"Filtered candidates before dedupe: {len(candidates)}")
    print(f"Filtered after dedupe: {len(deduped)}")
    print(f"Existing registry before: {len(existing_ids)}")
    print(f"Registry after: {len(final_ids)}")
    print(f"Wrote backtest report: {BACKTEST_REPORT_FILE}")

    if write_registry:
        print(f"Wrote registry: {PUBLIC_PICK_IDS_FILE}")
    else:
        print("Dry run only. Registry was not changed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backfill-public-registry",
        action="store_true",
        help="Fill totals_public_pick_ids.json from historical Ai results using the current public filter.",
    )
    parser.add_argument(
        "--backtest-only",
        action="store_true",
        help="Run historical filtered backtest and write totals_backtest_report.json without changing registry.",
    )

    args = parser.parse_args()

    if args.backtest_only:
        backfill_public_registry(write_registry=False)
        return

    if args.backfill_public_registry:
        backfill_public_registry(write_registry=True)

    aggregate_predictions()
    aggregate_results()


if __name__ == "__main__":
    main()
