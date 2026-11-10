#!/usr/bin/env python3
"""Ecnalanif — the Black Boxes. Each opens ONCE and seals itself (THESIS_D.md).

    python3 blackbox.py --historical   # Black Box 1: 2007-01-01 to the latest close
    python3 blackbox.py --forward      # Black Box 2: after 252 trading days of forward flight
    python3 blackbox.py --show         # print whatever is sealed
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import charter  # noqa: E402
import fleet  # noqa: E402
import sources  # noqa: E402
import stats  # noqa: E402
from scan import BB1, BB2, FORWARD_DAYS, LAUNCH, STATE  # noqa: E402

HIST_START = "2007-01-01"
P_MAX = 0.05 / 3


def judge(prices, pos, start, end=None, need_bb1=None) -> dict:
    eq = {s: fleet.simulate(prices[: end or len(prices)], pos[s], start)["equity"] for s in pos if s != "grounded"}
    earth_sharpe = stats.sharpe(eq["earth"])
    out = {"earth": {"sharpe": earth_sharpe, "return": eq["earth"][-1] / fleet.START_CASH - 1,
                     "max_dd": stats.max_drawdown(eq["earth"])}, "verdicts": {}}
    for s in fleet.TESTED:
        hold, cash = fleet.hold_cash_returns(prices, pos[s], start, end)
        w = stats.welch_one_sided(hold, cash)
        sh = stats.sharpe(eq[s])
        res = {**w, "sharpe": sh, "return": eq[s][-1] / fleet.START_CASH - 1, "max_dd": stats.max_drawdown(eq[s]),
               "trades": len(fleet.simulate(prices, pos[s], start)["trades"])}
        if need_bb1 is None:      # Black Box 1
            ok = w["p"] is not None and w["p"] < P_MAX and sh is not None and earth_sharpe is not None and sh >= earth_sharpe
        else:                     # Black Box 2
            ok = (need_bb1.get(s) == "PASS" and w.get("mean_hold") is not None
                  and w["mean_hold"] > w["mean_cash"] and sh is not None and sh >= earth_sharpe)
        out[s] = res
        out["verdicts"][s] = "PASS" if ok else "KILL"
    if "jester" in eq:      # Amendment 2: the honesty column. Display only, it never changes a verdict.
        js = stats.sharpe(eq["jester"])
        out["jester"] = {"sharpe": js, "return": eq["jester"][-1] / fleet.START_CASH - 1,
                         "max_dd": stats.max_drawdown(eq["jester"]),
                         "trades": len(fleet.simulate(prices, pos["jester"], start)["trades"])}
        out["beat_the_jester"] = {s: (None if js is None or stats.sharpe(eq[s]) is None else stats.sharpe(eq[s]) > js)
                                  for s in ("earth", *fleet.TESTED)}

    # ── Law 8: error bars (added 2026-11-10) ──────────────────────────────
    # "Every verdict reports the paired difference against the benchmark AND its
    #  uncertainty. A gap inside its own error bar is UNTESTED, not a PASS."
    #
    # The verdict above turns on `sh >= earth_sharpe`, a BARE INEQUALITY between
    # two Sharpe ratios. The standard error of a Sharpe over 504 days is near
    # 0.7, so a gap of 0.1 clears that test on noise alone. That is the hole.
    #
    # Display only, it never changes a verdict — the same standing Amendment 2's
    # honesty column has in this file. THESIS_D is signed and stays as signed
    # (law 2). From Thesis G onward, error bars bind.
    try:
        rets = {s: stats.daily_returns(e) for s, e in eq.items()}
        benches = tuple(b for b in ("earth", "jester") if b in rets)
        for s in eq:
            out.setdefault(s, {})["sharpe_se"] = stats.sharpe_se(eq[s])
        for s in fleet.TESTED:
            vs = {b: stats.paired_diff(rets[s], rets[b]) for b in benches if b != s}
            inside = sorted(b for b, d in vs.items() if not d["decisive"])
            out[s]["paired_vs"] = vs
            out[s]["law8"] = "UNTESTED" if inside else "DECISIVE"
            out[s]["law8_note"] = ("gap vs " + ", ".join(inside) + " is inside its own error bar"
                                   if inside else "every gap is outside its own error bar")
        out["error_bars"] = {
            "binding": False, "law": "8", "added": "2026-11-10",
            "note": ("Display-only, like Amendment 2's honesty column. THESIS_D is signed "
                     "and stays as signed. Read law8 to see whether a PASS rests on a gap "
                     "wider than its own error bar."),
        }
    except Exception as e:      # noqa: BLE001 — a display-only reading must never break a box
        out["error_bars"] = {"binding": False, "law": "8", "error": str(e)}
    return out


def _seal(path, payload):
    payload["sealed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(payload, indent=2))


def historical() -> int:
    if os.path.exists(BB1):
        print("Black Box 1 is already sealed. It cannot be opened twice.  (--show to read it)"); return 1
    ok, _ = charter.signed()
    if not ok:
        print("The Mission Charter is unsigned. Sign THESIS_D.md first."); return 1
    fin = sources.finalance_spy()
    rows = sources.yahoo_spy()
    shared = sources.cross_check(rows, fin)
    sources.check_integrity(rows)
    kp = sources.kp_definitive()
    start = next(i for i, (d, _) in enumerate(rows) if d >= HIST_START)
    pos = fleet.positions(rows, kp)
    res = judge(rows, pos, start)
    h = hashlib.sha256(json.dumps(rows[start:]).encode()).hexdigest()[:16]
    os.makedirs(STATE, exist_ok=True)
    _seal(BB1, {"box": 1, "span": [rows[start][0], rows[-1][0]], "data_hash": h, "shared_days_checked": shared,
                "charter_hash": charter.body_hash(), "p_max": P_MAX, **res})
    return 0


def forward() -> int:
    if os.path.exists(BB2):
        print("Black Box 2 is already sealed."); return 1
    if not os.path.exists(LAUNCH):
        print("The fleet hasn't launched."); return 1
    with open(LAUNCH) as f:
        ld = json.load(f)["launch_date"]
    prices = sources.finalance_spy()
    start = next(i for i, (d, _) in enumerate(prices) if d == ld)
    if len(prices) - 1 - start < FORWARD_DAYS:
        print(f"Not yet: {len(prices) - 1 - start}/{FORWARD_DAYS} trading days flown."); return 1
    end = start + FORWARD_DAYS + 1
    bb1 = {}
    if os.path.exists(BB1):
        with open(BB1) as f:
            bb1 = json.load(f)["verdicts"]
    pos = fleet.positions(prices, sources.load_frozen_kp(), jester=charter.amendment_initialed(2))
    res = judge(prices, pos, start, end, need_bb1=bb1)
    live, back = sources.read_scan_log(os.path.join(STATE, "scan_log.jsonl"))
    tally = sources.scan_tally([d for d, _ in prices[start + 1:end]], live, back, charter.amendment_initialed(1))
    missed = tally["missed"]
    _seal(BB2, {"box": 2, "span": [prices[start][0], prices[end - 1][0]], "missed_scans": missed,
                "backfilled_scans": tally["backfilled"], "missed_rule": tally["rule"],
                "integrity_flag": missed > 0.10 * FORWARD_DAYS, **res})
    return 0


def show() -> int:
    for p in (BB1, BB2):
        if os.path.exists(p):
            with open(p) as f:
                print(f.read())
        else:
            print(f"{os.path.basename(p)}: still closed")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:] or ["--show"]
    try:
        sys.exit({"--historical": historical, "--forward": forward}.get(a[0], show)())
    except sources.SourceError as e:
        print(f"STOPPED: {e}"); sys.exit(1)
