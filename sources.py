"""Ecnalanif — data in. No mock data, ever: a failed source raises, it is never filled in.

- SPY forward: Finalance's data/v2_prices/SPY.csv, opened read-only.
- SPY history (Black Box 1 only): Yahoo daily closes, split-adjusted like Finalance's,
  cross-checked against Finalance on every shared day.
- Kp: GFZ Potsdam. A day's max Kp is frozen the first time all eight 3-hour values exist,
  so a later revision can never change a decision already made.
"""
from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def _wsl(p: str) -> str:
    if len(p) > 2 and p[1] == ":" and p[0].isalpha():
        return "/mnt/" + p[0].lower() + "/" + p[3:].replace("\\", "/")
    return p


FINALANCE_DIR = _wsl(os.environ.get("FINALANCE_DIR", r"C:\Finalance"))
IMPERIUM_DIR = _wsl(os.environ.get("IMPERIUM_DIR", r"C:\Imperium"))
KP_DEFINITIVE = "https://kp.gfz.de/app/files/Kp_ap_since_1932.txt"
KP_NOWCAST = "https://kp.gfz.de/app/files/Kp_ap_nowcast.txt"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/SPY"
UA = {"User-Agent": "Mozilla/5.0 (Ecnalanif)"}
KP_FROZEN = os.path.join(DATA, "kp_daily.csv")


class SourceError(RuntimeError):
    pass


def _get(url: str, tries: int = 3) -> bytes:
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(2 * (i + 1))
    raise SourceError(f"{urllib.parse.urlsplit(url).netloc}: {last}")


# ── SPY ─────────────────────────────────────────────────────────────────
def finalance_spy() -> list[tuple[str, float]]:
    p = os.path.join(FINALANCE_DIR, "data", "v2_prices", "SPY.csv")
    if not os.path.exists(p):
        raise SourceError(f"Finalance SPY prices not found at {p}")
    with open(p, newline="") as f:
        rows = sorted((r["date"], float(r["close"])) for r in csv.DictReader(f))
    if len(rows) < 250:
        raise SourceError("Finalance SPY file is too short")
    return rows


def yahoo_spy() -> list[tuple[str, float]]:
    q = urllib.parse.urlencode({"period1": 0, "period2": int(time.time()), "interval": "1d", "events": "split"})
    j = json.loads(_get(YAHOO + "?" + q))
    res = (j.get("chart") or {}).get("result") or []
    if not res:
        raise SourceError("Yahoo returned no SPY data")
    r = res[0]
    off = r["meta"].get("gmtoffset", -18000)
    out = {}
    for t, c in zip(r.get("timestamp") or [], r["indicators"]["quote"][0].get("close") or []):
        if c and c > 0:
            out[datetime.fromtimestamp(t + off, tz=timezone.utc).date().isoformat()] = round(float(c), 4)
    return sorted(out.items())


def cross_check(long_rows, fin_rows, tol: float = 0.001) -> int:
    fin = dict(fin_rows)
    shared = 0
    for d, c in long_rows:
        if d in fin:
            shared += 1
            if abs(c / fin[d] - 1) > tol:
                raise SourceError(f"SPY {d}: Yahoo {c} vs Finalance {fin[d]} differ by more than {tol:.1%}")
    if shared < 250:
        raise SourceError(f"only {shared} shared days between Yahoo and Finalance")
    return shared


def check_integrity(rows, max_gap_days: int = 5, max_jump: float = 0.25):
    for (d0, c0), (d1, c1) in zip(rows, rows[1:]):
        gap = (datetime.fromisoformat(d1) - datetime.fromisoformat(d0)).days
        if gap > max_gap_days:
            raise SourceError(f"SPY gap of {gap} days after {d0}")
        if abs(c1 / c0 - 1) > max_jump:
            raise SourceError(f"SPY jump of {c1 / c0 - 1:+.0%} on {d1}")


# ── Kp ──────────────────────────────────────────────────────────────────
def parse_kp(text: str) -> dict[str, float]:
    """UTC day -> max Kp, only for days with all eight 3-hour values present."""
    vals: dict[str, list[float]] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        p = line.split()
        if len(p) < 8:
            continue
        d = f"{p[0]}-{int(p[1]):02d}-{int(p[2]):02d}"
        k = float(p[7])
        vals.setdefault(d, []).append(k)
    return {d: max(v) for d, v in vals.items() if len(v) == 8 and min(v) >= 0}


def kp_definitive() -> dict[str, float]:
    return parse_kp(_get(KP_DEFINITIVE).decode("utf-8", "replace"))


def load_frozen_kp() -> dict[str, float]:
    if not os.path.exists(KP_FROZEN):
        return {}
    with open(KP_FROZEN, newline="") as f:
        return {r["date"]: float(r["kp_max"]) for r in csv.DictReader(f)}


def update_frozen_kp(since: str) -> dict[str, float]:
    """Fetch the nowcast, freeze any newly complete days on or after `since`, return everything frozen."""
    frozen = load_frozen_kp()
    fresh = parse_kp(_get(KP_NOWCAST).decode("utf-8", "replace"))
    new = {d: k for d, k in fresh.items() if d >= since and d not in frozen}
    if new:
        os.makedirs(DATA, exist_ok=True)
        exists = os.path.exists(KP_FROZEN)
        with open(KP_FROZEN, "a", newline="") as f:
            w = csv.writer(f)
            if not exists:
                w.writerow(["date", "kp_max", "frozen_at"])
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            for d in sorted(new):
                w.writerow([d, new[d], stamp])
        frozen.update(new)
    return frozen


# ── Skald (telemetry only) ──────────────────────────────────────────────
def skald_moods() -> dict[str, dict]:
    p = os.path.join(IMPERIUM_DIR, "data", "skald-mood.csv")
    if not os.path.exists(p):
        return {}
    with open(p, newline="") as f:
        return {r["date"]: {"crypto": r.get("crypto_mood"), "stock": r.get("stock_mood")} for r in csv.DictReader(f)}
