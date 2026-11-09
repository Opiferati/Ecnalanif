"""Ecnalanif — the fleet. Five ships, one engine, rules exactly as written in THESIS_D.md.

Positions are 1 (all in SPY) or 0 (all cash). pos[i] = the position held from close i to close i+1.
- Sky ships (Lunar Tide, Retrograde Drive): the sky is known years ahead, so pos[i] is set from the
  sky on the NEXT trading day and filled at close i.
- Solar Weather and The Echo: decide from what is known at close t, fill at close t+1, so pos[i] uses
  the decision made at close i-1.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta

import sky

START_CASH = 50_000.0
FEE, SLIP = 0.0005, 0.0005          # Finalance config.py: 0.05% fee + 5 bps slippage per side
KP_STORM, STORM_DAYS, SMA_N = 6.0, 6, 200
KP_LOOKBACK_DAYS = 12               # calendar days of Kp the Solar Weather decision needs

SHIPS = [
    {"id": "earth",   "name": "Earth Standard",   "role": "Benchmark",            "color": "#9fb3c8"},
    {"id": "echo",    "name": "The Echo",         "role": "Display only",         "color": "#c49bff"},
    {"id": "lunar",   "name": "Lunar Tide",       "role": "Test D1",              "color": "#5ee7ff"},
    {"id": "solar",   "name": "Solar Weather",    "role": "Test D2",              "color": "#ffb347"},
    {"id": "mercury", "name": "Retrograde Drive", "role": "Test D3",              "color": "#ff6b9d"},
]
TESTED = ("lunar", "solar", "mercury")

# The Jester (Amendment 2, 2026-11-08): a control, not a test. Each trading day he is in SPY or cash by a
# coin flip fixed in advance by a seeded hash of the date, so a flip never depends on data, never changes on
# a rerun or a backfill, and cannot be tuned after the fact. The seed was chosen once, before any flip was
# looked at, and is written into Amendment 2. Any ship that can't beat him convincingly was luck in a costume.
JESTER = {"id": "jester", "name": "The Jester", "role": "Control (coin flip)", "color": "#e8d36a"}
JESTER_SEED = "ecnalanif-jester-2026-11-08"


def jester_flip(day: date) -> int:
    """1 = in SPY, 0 = cash, for the interval that ends on `day`. Pure function of the seed and the date."""
    return hashlib.sha256(f"{JESTER_SEED}|{day.isoformat()}".encode()).digest()[0] & 1


def ships(jester: bool = False) -> list[dict]:
    return SHIPS + ([JESTER] if jester else [])


def _d(s: str) -> date:
    return date.fromisoformat(s)


def next_trading_day(prices, i) -> date:
    if i + 1 < len(prices):
        return _d(prices[i + 1][0])
    d = _d(prices[i][0]) + timedelta(days=1)       # last bar: next weekday (holidays not known here)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def storm_days(kp_daily: dict) -> list[str]:
    return sorted(d for d, k in kp_daily.items() if k is not None and k >= KP_STORM)


def positions(prices, kp_daily: dict | None = None, jester: bool = False) -> dict:
    """{ship_id: [pos per bar]} plus {'grounded': {ship_id: [dates]}}. None = no decision possible yet."""
    n = len(prices)
    closes = [c for _, c in prices]
    dates = [d for d, _ in prices]
    out = {s["id"]: [None] * n for s in ships(jester)}
    grounded = {"solar": []}

    # Echo: close > 200-day SMA, decided at close t
    echo_sig = [None] * n
    run = 0.0
    for t in range(n):
        run += closes[t]
        if t >= SMA_N:
            run -= closes[t - SMA_N]
        if t >= SMA_N - 1:
            echo_sig[t] = 1 if closes[t] > run / SMA_N else 0

    # Solar Weather: cash during the 6 trading days after any UTC day with Kp >= 6, decided at close t
    solar_sig = [None] * n
    if kp_daily is not None:
        storms = storm_days(kp_daily)
        for t in range(n):
            dt = _d(dates[t])
            need = [(dt - timedelta(days=k)).isoformat() for k in range(1, KP_LOOKBACK_DAYS + 1)]
            if any(x not in kp_daily for x in need):
                continue                                   # grounded: Kp missing, no decision
            out_of_market = False
            for s in storms:
                if s >= dates[t] or s < need[-1]:
                    continue
                after = sum(1 for j in range(max(0, t - 15), t + 1) if dates[j] > s)
                if 1 <= after <= STORM_DAYS:
                    out_of_market = True
                    break
            solar_sig[t] = 0 if out_of_market else 1

    for i in range(n):
        nxt = next_trading_day(prices, i)
        out["earth"][i] = 1
        out["lunar"][i] = 1 if sky.lunar_hold(nxt) else 0
        out["mercury"][i] = 1 if sky.mercury_hold(nxt) else 0
        if jester:
            out["jester"][i] = jester_flip(nxt)          # like the sky ships: known ahead, filled at close i
        out["echo"][i] = echo_sig[i - 1] if i >= 1 else None
        if i >= 1:
            out["solar"][i] = solar_sig[i - 1]
            if solar_sig[i - 1] is None and kp_daily is not None:
                grounded["solar"].append(dates[i])
    out["grounded"] = grounded
    return out


def simulate(prices, pos: list, start: int) -> dict:
    """Run one ship from close `start`. A None position keeps the previous one (grounded)."""
    cash, shares, held = START_CASH, 0.0, 0
    equity, trades = [], []
    for i in range(start, len(prices)):
        d, px = prices[i]
        want = pos[i] if pos[i] is not None else held
        if want != held:
            if want == 1:
                shares = cash / (px * (1 + FEE + SLIP)); cash = 0.0
                trades.append({"date": d, "side": "BUY", "price": px})
            else:
                cash = shares * px * (1 - FEE - SLIP); shares = 0.0
                trades.append({"date": d, "side": "SELL", "price": px})
            held = want
        equity.append(cash + shares * px)
    return {"equity": equity, "dates": [d for d, _ in prices[start:]], "trades": trades,
            "position": held}


def hold_cash_returns(prices, pos: list, start: int, end: int | None = None):
    """SPY's daily returns split by the ship's position over each interval (i-1, i]."""
    end = len(prices) if end is None else end
    hold, cash = [], []
    for i in range(start + 1, end):
        p = pos[i - 1]
        if p is None:
            continue
        r = prices[i][1] / prices[i - 1][1] - 1
        (hold if p == 1 else cash).append(r)
    return hold, cash
