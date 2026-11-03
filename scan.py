#!/usr/bin/env python3
"""Ecnalanif — the daily scan. Run any time after the US close (Imperium runs it after the Skald).

    python3 scan.py            # human summary (the drones)
    python3 scan.py --json     # one JSON line for Imperium

Every run recomputes the whole forward flight from the price file, so a missed day is caught up
by the same rules. Kp is frozen the first time it is seen, so history never shifts under a ship.
Measurement only: no broker, no orders, no real money.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bridge  # noqa: E402
import charter  # noqa: E402
import drones  # noqa: E402
import fleet  # noqa: E402
import sky  # noqa: E402
import sources  # noqa: E402
import stats  # noqa: E402

STATE = os.path.join(HERE, "state")
LAUNCH = os.path.join(STATE, "launch.json")
SCAN_LOG = os.path.join(STATE, "scan_log.jsonl")
BB1 = os.path.join(STATE, "blackbox1_SEALED.json")
BB2 = os.path.join(STATE, "blackbox2_SEALED.json")
FORWARD_DAYS = 252


def ny_today() -> date:
    return sky.to_ny_date(datetime.now(timezone.utc))


def telemetry(d: date, kp: dict, moods: dict) -> dict:
    kp_days = sorted(k for k in kp if k <= d.isoformat())
    kd = kp_days[-1] if kp_days else None
    m = moods.get(d.isoformat()) or (moods[max(moods)] if moods else {})
    return {"date": d.isoformat(), "moon": sky.moon_phase_name(d), "days_from_new_moon": sky.days_from_new_moon(d),
            "mercury_retrograde": sky.mercury_retrograde(d), "kp": kp.get(kd) if kd else None, "kp_date": kd,
            "skald_stock": (m or {}).get("stock"), "skald_crypto": (m or {}).get("crypto")}


def sky_strip(start: date, days: int = 45) -> list[dict]:
    return [{"date": (start + timedelta(days=i)).isoformat(),
             "lunar": sky.lunar_hold(start + timedelta(days=i)),
             "retro": sky.mercury_retrograde(start + timedelta(days=i))} for i in range(days)]


def _bb_label(path: str, ready: bool, what: str) -> str:
    if os.path.exists(path):
        with open(path) as f:
            v = json.load(f).get("verdicts", {})
        return "SEALED — " + ", ".join(f"{k} {x}" for k, x in v.items())
    return f"ready to open ({what})" if ready else "closed"


def run() -> dict:
    os.makedirs(STATE, exist_ok=True)
    text = charter.read()
    is_signed, sig = charter.signed(text)
    moods = sources.skald_moods()
    today = ny_today()

    if not is_signed:
        st = {"status": "docked", "message": "Mission Charter unsigned — the fleet is docked.",
              "telemetry": telemetry(today, sources.load_frozen_kp(), moods), "sky_strip": sky_strip(today),
              "ships_meta": fleet.SHIPS}
        st["cogito"], st["memoria"] = drones.cogito(st), drones.memoria(st)
        bridge.write(st)
        return st

    prices = sources.finalance_spy()
    sources.check_integrity(prices[-400:])
    warnings = []

    if os.path.exists(LAUNCH):
        with open(LAUNCH) as f:
            launch = json.load(f)
        if launch["charter_hash"] != charter.body_hash(text):
            warnings.append("Charter text changed since launch — changes must be dated amendments")
    else:
        # Never launch on stale prices: a launch on an old close would backdate the flight to before signing.
        now = datetime.now(timezone.utc)
        expect = sky.to_ny_date(now - timedelta(hours=17))        # the latest session that should be closed
        while expect.weekday() >= 5:
            expect -= timedelta(days=1)
        if prices[-1][0] < expect.isoformat():
            st = {"status": "docked", "message": f"Signed, waiting for fresh prices: newest close {prices[-1][0]}, "
                  f"expected {expect.isoformat()}. Press Treasury in Imperium, or wait for tonight's refresh.",
                  "telemetry": telemetry(today, sources.load_frozen_kp(), moods), "sky_strip": sky_strip(today),
                  "ships_meta": fleet.SHIPS}
            st["cogito"] = "DRONE COGITO — " + st["message"]
            st["memoria"] = drones.memoria(st)
            bridge.write(st)
            return st
        launch = {"launch_date": prices[-1][0], "charter_hash": charter.body_hash(text), "signed": sig,
                  "launched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        with open(LAUNCH, "w") as f:
            json.dump(launch, f, indent=2)

    ld = launch["launch_date"]
    idx = {d: i for i, (d, _) in enumerate(prices)}
    if ld not in idx:
        raise sources.SourceError(f"launch date {ld} is missing from the price file")
    start = idx[ld]
    since = (date.fromisoformat(ld) - timedelta(days=fleet.KP_LOOKBACK_DAYS + 3)).isoformat()
    try:
        kp = sources.update_frozen_kp(since)
    except sources.SourceError as e:
        kp = sources.load_frozen_kp()
        warnings.append(f"Kp fetch failed ({e}); Solar Weather uses frozen Kp only")

    pos = fleet.positions(prices, kp)
    ships = []
    for s in fleet.SHIPS:
        p = pos[s["id"]]
        sim = fleet.simulate(prices, p, start)
        eq = sim["equity"]
        nxt = p[-1] if p[-1] is not None else sim["position"]
        ships.append({**s, "equity": eq[-1], "return": eq[-1] / fleet.START_CASH - 1, "sharpe": stats.sharpe(eq),
                      "max_dd": stats.max_drawdown(eq), "trades": sim["trades"], "n_trades": len(sim["trades"]),
                      "position": sim["position"], "next": "IN SPY" if nxt == 1 else "CASH",
                      "curve": [round(x, 2) for x in eq]})

    days_flown = len(prices) - 1 - start
    with open(SCAN_LOG, "a") as f:
        f.write(json.dumps({"scan_date": today.isoformat(), "as_of": prices[-1][0],
                            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}) + "\n")
    with open(SCAN_LOG) as f:
        scan_dates = {json.loads(l)["as_of"] for l in f if l.strip()}
    flown = [d for d, _ in prices[start + 1:]]
    missed = sum(1 for d in flown if d not in scan_dates)

    st = {"status": "flying", "as_of": prices[-1][0], "launch_date": ld, "days_flown": days_flown,
          "dates": [d for d, _ in prices[start:]], "ships": ships, "ships_meta": fleet.SHIPS,
          "telemetry": telemetry(date.fromisoformat(prices[-1][0]), kp, moods),
          "sky_strip": sky_strip(date.fromisoformat(prices[-1][0])),
          "scans": len(scan_dates), "missed_scans": missed,
          "grounded_days": [d for d in pos["grounded"]["solar"] if d > ld],
          "blackbox1": _bb_label(BB1, True, "python3 blackbox.py --historical"),
          "blackbox2": _bb_label(BB2, days_flown >= FORWARD_DAYS, "python3 blackbox.py --forward")
          + ("" if os.path.exists(BB2) else f" · {days_flown}/{FORWARD_DAYS} trading days"),
          "warnings": warnings}
    st["cogito"], st["memoria"] = drones.cogito(st), drones.memoria(st)
    with open(os.path.join(STATE, "state.json"), "w") as f:
        json.dump(st, f, indent=1)
    bridge.write(st)
    return st


def main() -> int:
    as_json = "--json" in sys.argv
    try:
        st = run()
    except sources.SourceError as e:
        msg = {"status": "error", "message": str(e)}
        print(json.dumps(msg) if as_json else f"SCAN STOPPED: {e}")
        return 1
    if as_json:
        print(json.dumps({"status": st["status"], "as_of": st.get("as_of"), "cogito": st["cogito"],
                          "memoria": st["memoria"], "bridge": os.path.join(HERE, "Bridge.html")}))
    else:
        print(st["cogito"]); print(); print(st["memoria"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
