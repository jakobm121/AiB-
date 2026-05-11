import json
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

AI_REPO_DIR = os.getenv("AI_REPO_DIR", "../Ai")
SOURCE_RESULTS = Path(AI_REPO_DIR) / "data" / "tennis_totals_results.json"

OUTPUT_DIR = BASE_DIR / "public" / "data"
PUBLIC_PICK_IDS_FILE = OUTPUT_DIR / "totals_public_pick_ids.json"

ALLOWED_BUCKETS = {"total_games"}
ALLOWED_SIDES = {"under", "over"}


def load_json(path, default):
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("results", "predictions", "picks", "data"):
            if isinstance(data.get(key), list):
                return data[key]

    return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def normalize_side(value):
    return str(value or "").strip().lower()


def is_total_pick(item):
    if not isinstance(item, dict):
        return False

    if not item.get("pick_id"):
        return False

    if item.get("bucket") not in ALLOWED_BUCKETS:
        return False

    if normalize_side(item.get("side")) not in ALLOWED_SIDES:
        return False

    if not (item.get("fixture_id") or item.get("event_key")):
        return False

    return True


def pick_sort_score(item):
    side = normalize_side(item.get("side"))
    line = to_float(item.get("line"), 0)

    # Enako kot v agregatorju:
    # underjev ne spreminjamo po line-u,
    # overji preferirajo nižji line.
    if side == "over":
        line_score = -line
    else:
        line_score = 0

    return (
        line_score,
        to_float(item.get("quality_score"), 0),
        to_float(item.get("confidence"), 0),
        to_float(item.get("edge"), 0),
        to_float(item.get("odds"), 0),
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


def main():
    existing_ids = set(str(x) for x in load_json(PUBLIC_PICK_IDS_FILE, []) if x)

    raw_results = load_json(SOURCE_RESULTS, [])
    total_results = [x for x in raw_results if is_total_pick(x)]

    deduped = dedupe_picks(total_results)
    backfill_ids = set(str(x["pick_id"]) for x in deduped if x.get("pick_id"))

    merged_ids = sorted(existing_ids | backfill_ids)

    save_json(PUBLIC_PICK_IDS_FILE, merged_ids)

    print(f"Raw results: {len(raw_results)}")
    print(f"Total-games results: {len(total_results)}")
    print(f"Deduped total-games picks: {len(deduped)}")
    print(f"Existing registry IDs: {len(existing_ids)}")
    print(f"Added IDs: {len(backfill_ids - existing_ids)}")
    print(f"Final registry IDs: {len(merged_ids)}")
    print(f"Wrote: {PUBLIC_PICK_IDS_FILE}")


if __name__ == "__main__":
    main()
