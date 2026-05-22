import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

import yaml


CONFIG_FILE = Path(__file__).resolve().parent / "config.yml"
ROOT_DIR = Path(__file__).resolve().parents[1]

SETTLED = {"win", "loss"}


def load_config():
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fnum(x, default=0.0):
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def sval(x):
    return str(x or "").strip().lower()


def result(p):
    return sval(p.get("result"))


def read_json_from_url(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AiB-tennis-totals-premium-settle"
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")

    return json.loads(raw)


def read_json_file(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def output_path(relative_path):
    return ROOT_DIR / relative_path


def key_for_pick(p):
    return (
        str(p.get("fixture_id") or p.get("event_key") or p.get("match") or "").strip(),
        sval(p.get("side")),
        fnum(p.get("line")),
    )


def sort_key_from_wrapped(x):
    p = x["pick"]
    return (
        str(p.get("date") or ""),
        str(p.get("time") or ""),
        str(p.get("match") or ""),
        sval(p.get("side")),
        fnum(p.get("line")),
    )


def profit(p, stake):
    r = result(p)
    odds = fnum(p.get("odds"))

    if r == "win":
        return stake * (odds - 1)

    if r == "loss":
        return -stake

    return 0.0


def summarize(rows):
    settled = [x for x in rows if result(x["pick"]) in SETTLED]

    wins = sum(1 for x in settled if result(x["pick"]) == "win")
    losses = sum(1 for x in settled if result(x["pick"]) == "loss")
    staked = sum(fnum(x.get("stake")) for x in settled)
    prof = sum(profit(x["pick"], fnum(x.get("stake"))) for x in settled)

    bank = 0.0
    peak = 0.0
    max_dd = 0.0
    streak = 0
    max_streak = 0

    for x in sorted(settled, key=sort_key_from_wrapped):
        p = x["pick"]
        stake = fnum(x.get("stake"))

        bank += profit(p, stake)
        peak = max(peak, bank)
        max_dd = max(max_dd, peak - bank)

        if result(p) == "loss":
            streak += 1
            max_streak = max(max_streak, streak)
        elif result(p) == "win":
            streak = 0

    by_tier = {}

    for tier in sorted(set(x.get("tier", "Unknown") for x in settled)):
        tier_rows = [x for x in settled if x.get("tier") == tier]

        tier_wins = sum(1 for x in tier_rows if result(x["pick"]) == "win")
        tier_losses = sum(1 for x in tier_rows if result(x["pick"]) == "loss")
        tier_staked = sum(fnum(x.get("stake")) for x in tier_rows)
        tier_profit = sum(profit(x["pick"], fnum(x.get("stake"))) for x in tier_rows)

        by_tier[tier] = {
            "picks": len(tier_rows),
            "wins": tier_wins,
            "losses": tier_losses,
            "win_rate": round(tier_wins / len(tier_rows) * 100, 2) if tier_rows else 0,
            "staked": round(tier_staked, 2),
            "profit": round(tier_profit, 2),
            "roi": round(tier_profit / tier_staked * 100, 2) if tier_staked else 0,
            "avg_odds": round(
                sum(fnum(x["pick"].get("odds")) for x in tier_rows) / len(tier_rows),
                3,
            ) if tier_rows else 0,
        }

    return {
        "picks": len(settled),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(settled) * 100, 2) if settled else 0,
        "staked": round(staked, 2),
        "profit": round(prof, 2),
        "roi": round(prof / staked * 100, 2) if staked else 0,
        "avg_odds": round(
            sum(fnum(x["pick"].get("odds")) for x in settled) / len(settled),
            3,
        ) if settled else 0,
        "max_drawdown_units": round(max_dd, 2),
        "longest_loss_streak": max_streak,
        "by_tier": by_tier,
    }


def main():
    cfg = load_config()

    source_url = cfg["source"]["results_url"]
    latest_source = read_json_from_url(source_url)

    latest_by_key = {
        key_for_pick(p): p
        for p in latest_source
    }

    picks_file = output_path(cfg["output"]["picks_file"])
    settled_file = output_path(cfg["output"]["settled_file"])
    report_file = output_path(cfg["output"]["report_file"])

    current_picks = read_json_file(picks_file, default=[])
    previous_settled = read_json_file(settled_file, default=[])

    previous_by_id = {
        x.get("id"): x
        for x in previous_settled
        if x.get("id")
    }

    updated = []
    newly_settled = []

    for item in current_picks:
        p = item.get("pick", {})
        k = key_for_pick(p)

        latest = latest_by_key.get(k)

        if latest is not None:
            old_result = result(p)
            new_result = result(latest)

            item["pick"] = latest
            item["result"] = new_result

            if old_result not in SETTLED and new_result in SETTLED:
                newly_settled.append(item)

        updated.append(item)

    for item in updated:
        if item.get("id"):
            previous_by_id[item["id"]] = item

    all_known = sorted(previous_by_id.values(), key=sort_key_from_wrapped)

    settled_rows = [x for x in all_known if result(x["pick"]) in SETTLED]
    open_rows = [x for x in all_known if result(x["pick"]) not in SETTLED]

    report = {
        "settled_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": cfg["strategy"]["name"],
        "source_results_url": source_url,
        "known_total": len(all_known),
        "open_total": len(open_rows),
        "settled_total": len(settled_rows),
        "newly_settled_count": len(newly_settled),
        "summary": summarize(all_known),
        "newly_settled": newly_settled,
        "open_picks": open_rows,
        "settled_picks": settled_rows,
    }

    settled_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)

    settled_file.write_text(
        json.dumps(all_known, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report_file.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Saved settled:", settled_file)
    print("Saved report:", report_file)
    print("Known total:", len(all_known))
    print("Open:", len(open_rows))
    print("Settled:", len(settled_rows))
    print("Newly settled:", len(newly_settled))
    print()
    print("Summary:")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
