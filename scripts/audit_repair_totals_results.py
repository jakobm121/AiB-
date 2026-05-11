import json
import re
from pathlib import Path
from copy import deepcopy


RESULTS_FILE = Path("data/tennis_totals_results.json")
BACKUP_FILE = Path("data/tennis_totals_results.before_audit_repair.json")
REPORT_FILE = Path("data/tennis_totals_audit_repair_report.json")

SETTLED_RESULTS = {"win", "loss", "push", "void"}


def to_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def norm(value):
    return str(value or "").strip().lower()


def parse_score_sets(final_score):
    """
    Supports:
      6-4
      7-6
      7-6(5)
      6-7(10)
      6 - 7

    Tie-break number in parentheses is ignored.
    """
    if not final_score:
        return []

    pairs = re.findall(r"(\d+)\s*-\s*(\d+)", str(final_score))
    return [(int(a), int(b)) for a, b in pairs]


def calc_total_games(parsed_sets):
    return sum(a + b for a, b in parsed_sets)


def calc_result_and_profit(item, total_games):
    side = norm(item.get("side"))
    line = to_float(item.get("line"))
    odds = to_float(item.get("odds"))
    stake = to_float(item.get("stake"), 1.0)

    if side not in {"under", "over"}:
        return None, None

    if line is None or odds is None or stake is None:
        return None, None

    if total_games == line:
        return "push", 0.0

    if side == "under":
        if total_games < line:
            return "win", round(stake * (odds - 1), 3)
        return "loss", round(-stake, 3)

    if side == "over":
        if total_games > line:
            return "win", round(stake * (odds - 1), 3)
        return "loss", round(-stake, 3)

    return None, None


def should_touch_item(item):
    if not isinstance(item, dict):
        return False

    if item.get("bucket") != "total_games":
        return False

    result = norm(item.get("result"))

    # Popravljamo samo settled picke ali picke, ki imajo final_score.
    # Pending brez score-a pustimo pri miru.
    if result in SETTLED_RESULTS:
        return True

    if item.get("final_score"):
        return True

    return False


def main():
    if not RESULTS_FILE.exists():
        raise FileNotFoundError(f"Missing file: {RESULTS_FILE}")

    data = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("Expected tennis_totals_results.json to be a list.")

    if not BACKUP_FILE.exists():
        BACKUP_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    changed = []
    reset_to_pending = []
    untouched = 0

    for item in data:
        if not should_touch_item(item):
            untouched += 1
            continue

        old = deepcopy(item)

        final_score = item.get("final_score")
        parsed_sets = parse_score_sets(final_score)

        # Če ima settled/final_score samo en set, je to nepopolno.
        # Vrnemo v pending, da ga popravljeni settle ponovno obdela.
        if final_score and len(parsed_sets) < 2:
            item["result"] = "pending"
            item["profit"] = None
            item["settled_at"] = None
            item["settled_status"] = None
            item["event_winner"] = None
            item["final_score"] = None
            item["total_games"] = None

            reset_to_pending.append({
                "pick_id": old.get("pick_id"),
                "date": old.get("date"),
                "time": old.get("time"),
                "match": old.get("match"),
                "side": old.get("side"),
                "line": old.get("line"),
                "old_result": old.get("result"),
                "old_profit": old.get("profit"),
                "old_final_score": old.get("final_score"),
                "old_total_games": old.get("total_games"),
            })
            continue

        # Če nima score-a, ne moremo recalculat.
        if not parsed_sets:
            untouched += 1
            continue

        total_games = calc_total_games(parsed_sets)
        new_result, new_profit = calc_result_and_profit(item, total_games)

        if new_result is None:
            untouched += 1
            continue

        old_result = item.get("result")
        old_profit = item.get("profit")
        old_total_games = item.get("total_games")

        item["total_games"] = total_games
        item["result"] = new_result
        item["profit"] = new_profit

        if (
            norm(old_result) != new_result
            or to_float(old_profit) != new_profit
            or to_float(old_total_games) != float(total_games)
        ):
            changed.append({
                "pick_id": item.get("pick_id"),
                "date": item.get("date"),
                "time": item.get("time"),
                "match": item.get("match"),
                "side": item.get("side"),
                "line": item.get("line"),
                "odds": item.get("odds"),
                "stake": item.get("stake"),
                "final_score": final_score,
                "old_result": old_result,
                "new_result": new_result,
                "old_profit": old_profit,
                "new_profit": new_profit,
                "old_total_games": old_total_games,
                "new_total_games": total_games,
            })

    RESULTS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report = {
        "results_file": str(RESULTS_FILE),
        "backup_file": str(BACKUP_FILE),
        "changed_count": len(changed),
        "reset_to_pending_count": len(reset_to_pending),
        "untouched_count": untouched,
        "changed": changed,
        "reset_to_pending": reset_to_pending,
    }

    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Changed recalculated results: {len(changed)}")
    print(f"Reset incomplete one-set results to pending: {len(reset_to_pending)}")
    print(f"Untouched: {untouched}")
    print(f"Backup: {BACKUP_FILE}")
    print(f"Report: {REPORT_FILE}")

    if changed:
        print("\nRECALCULATED:")
        for x in changed:
            print(
                f"- {x['date']} {x['time']} {x['match']} "
                f"{x['side']} {x['line']} score={x['final_score']} "
                f"{x['old_result']}->{x['new_result']} "
                f"{x['old_profit']}->{x['new_profit']} "
                f"total {x['old_total_games']}->{x['new_total_games']}"
            )

    if reset_to_pending:
        print("\nRESET TO PENDING:")
        for x in reset_to_pending:
            print(
                f"- {x['date']} {x['time']} {x['match']} "
                f"{x['side']} {x['line']} score={x['old_final_score']} "
                f"old_result={x['old_result']}"
            )


if __name__ == "__main__":
    main()
