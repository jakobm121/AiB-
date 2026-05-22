import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

import yaml


CONFIG_FILE = Path(__file__).resolve().parent / "config.yml"
ROOT_DIR = Path(__file__).resolve().parents[1]

SETTLED = {"win", "loss"}
UNSETTLED = {"", "pending", "open", "void", "push", "cancelled", "canceled", "unknown", "none", "null"}


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
            "User-Agent": "AiB-tennis-totals-premium-aggregator"
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")

    return json.loads(raw)


def output_path(relative_path):
    return ROOT_DIR / relative_path


def key_for_pick(p):
    return (
        str(p.get("fixture_id") or p.get("event_key") or p.get("match") or "").strip(),
        sval(p.get("side")),
        fnum(p.get("line")),
    )


def sort_key(p):
    return (
        str(p.get("date") or ""),
        str(p.get("time") or ""),
        str(p.get("match") or ""),
        sval(p.get("side")),
        fnum(p.get("line")),
    )


def dedupe(items):
    best = {}

    for p in items:
        k = key_for_pick(p)

        old = best.get(k)
        if old is None:
            best[k] = p
            continue

        score_new = (
            fnum(p.get("quality_score")),
            fnum(p.get("confidence")),
            fnum(p.get("edge")),
            fnum(p.get("odds")),
        )
        score_old = (
            fnum(old.get("quality_score")),
            fnum(old.get("confidence")),
            fnum(old.get("edge")),
            fnum(old.get("odds")),
        )

        if score_new > score_old:
            best[k] = p

    return list(best.values())


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

    for x in sorted(settled, key=lambda y: sort_key(y["pick"])):
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


def is_premium(p, cfg):
    premium = cfg["strategy"]["premium"]

    if not premium.get("enabled", True):
        return False

    side = sval(p.get("side"))
    conf = fnum(p.get("confidence"))
    books = fnum(p.get("bookmakers_used"))
    label = str(p.get("stake_label") or "").strip()

    excluded_min = fnum(premium.get("exclude_bookmakers_min", 6))
    excluded_max = fnum(premium.get("exclude_bookmakers_max", 8))
    books_excluded = excluded_min <= books < excluded_max

    return (
        side == sval(premium.get("side", "under"))
        and conf >= fnum(premium.get("min_confidence", 82))
        and not books_excluded
        and label == str(premium.get("stake_label", "Strong")).strip()
    )


def is_volume_b(p, cfg):
    volume_b = cfg["strategy"]["volume_b"]

    if not volume_b.get("enabled", False):
        return False

    line = fnum(p.get("line"))
    conf = fnum(p.get("confidence"))
    label = str(p.get("stake_label") or "").strip()

    return (
        line == fnum(volume_b.get("line", 20.5))
        and conf >= fnum(volume_b.get("min_confidence", 82))
        and label != str(volume_b.get("excluded_stake_label", "Top Rated")).strip()
    )


def wrap_pick(p, tier, stake):
    return {
        "id": "|".join(str(x) for x in key_for_pick(p)),
        "tier": tier,
        "stake": stake,
        "result": result(p),
        "pick": p,
    }


def main():
    cfg = load_config()

    source_url = cfg["source"]["results_url"]
    raw = read_json_from_url(source_url)

    if not isinstance(raw, list):
        raise ValueError("Source results JSON must be a list.")

    if cfg.get("dedupe", {}).get("enabled", True):
        raw = dedupe(raw)

    selected = []
    seen = set()

    for p in raw:
        if is_premium(p, cfg):
            item = wrap_pick(
                p,
                tier="Premium",
                stake=fnum(cfg["strategy"]["premium"].get("stake", 1.0)),
            )
        elif is_volume_b(p, cfg):
            item = wrap_pick(
                p,
                tier="Volume B",
                stake=fnum(cfg["strategy"]["volume_b"].get("stake", 0.25)),
            )
        else:
            continue

        if item["id"] in seen:
            continue

        seen.add(item["id"])
        selected.append(item)

    selected = sorted(selected, key=lambda x: sort_key(x["pick"]))

    open_picks = [x for x in selected if result(x["pick"]) not in SETTLED]
    settled_picks = [x for x in selected if result(x["pick"]) in SETTLED]

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": cfg["strategy"]["name"],
        "source_results_url": source_url,
        "raw_source_count_after_dedupe": len(raw),
        "selected_total": len(selected),
        "selected_open": len(open_picks),
        "selected_settled": len(settled_picks),
        "summary": summarize(selected),
        "open_picks": open_picks,
        "settled_picks": settled_picks,
    }

    picks_file = output_path(cfg["output"]["picks_file"])
    report_file = output_path(cfg["output"]["report_file"])

    picks_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)

    picks_file.write_text(
        json.dumps(selected, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report_file.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Saved picks:", picks_file)
    print("Saved report:", report_file)
    print("Source count after dedupe:", len(raw))
    print("Selected total:", len(selected))
    print("Open:", len(open_picks))
    print("Settled:", len(settled_picks))
    print()
    print("Summary:")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
