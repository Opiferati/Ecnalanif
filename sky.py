"""Ecnalanif — the sky. Pure math, standard library only.

New moons: Meeus, Astronomical Algorithms (2nd ed.), ch. 49 — main periodic terms (error ~ minutes).
Mercury:   Keplerian elements from Standish, "Approximate Positions of the Planets" (JPL), Table 1,
           valid 1800–2050. Geocentric ecliptic longitude; retrograde = longitude decreasing.
Both are checked against PyEphem in tests/ (reference values baked in).
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

try:
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    NY = None

J2000 = 2451545.0
UNIX_JD = 2440587.5
LUNAR_HALF_WINDOW = 7          # Charter: within 7 days of a new moon (pre-committed)
SYNODIC = 29.530588861


def _rad(d): return math.radians(d % 360.0)


def jd_to_utc(jd: float) -> datetime:
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=jd - UNIX_JD)


def utc_to_jd(dt: datetime) -> float:
    return (dt - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds() / 86400.0 + UNIX_JD


def to_ny_date(dt: datetime) -> date:
    if NY is not None:
        return dt.astimezone(NY).date()
    return (dt - timedelta(hours=5)).date()


# ── Moon ────────────────────────────────────────────────────────────────
def new_moon_jde(k: int) -> float:
    T = k / 1236.85
    jde = (2451550.09766 + 29.530588861 * k + 0.00015437 * T**2
           - 0.000000150 * T**3 + 0.00000000073 * T**4)
    E = 1 - 0.002516 * T - 0.0000074 * T**2
    M = _rad(2.5534 + 29.10535670 * k - 0.0000014 * T**2 - 0.00000011 * T**3)
    Mp = _rad(201.5643 + 385.81693528 * k + 0.0107582 * T**2 + 0.00001238 * T**3 - 0.000000058 * T**4)
    F = _rad(160.7108 + 390.67050284 * k - 0.0016118 * T**2 - 0.00000227 * T**3 + 0.000000011 * T**4)
    Om = _rad(124.7746 - 1.56375588 * k + 0.0020672 * T**2 + 0.00000215 * T**3)
    s = math.sin
    jde += (-0.40720 * s(Mp) + 0.17241 * E * s(M) + 0.01608 * s(2 * Mp) + 0.01039 * s(2 * F)
            + 0.00739 * E * s(Mp - M) - 0.00514 * E * s(Mp + M) + 0.00208 * E * E * s(2 * M)
            - 0.00111 * s(Mp - 2 * F) - 0.00057 * s(Mp + 2 * F) + 0.00056 * E * s(2 * Mp + M)
            - 0.00042 * s(3 * Mp) + 0.00042 * E * s(M + 2 * F) + 0.00038 * E * s(M - 2 * F)
            - 0.00024 * E * s(2 * Mp - M) - 0.00017 * s(Om) - 0.00007 * s(Mp + 2 * M)
            + 0.00004 * s(2 * Mp - 2 * F) + 0.00004 * s(3 * M) + 0.00003 * s(Mp + M - 2 * F)
            + 0.00003 * s(2 * Mp + 2 * F) - 0.00003 * s(Mp + M + 2 * F) + 0.00003 * s(Mp - M + 2 * F)
            - 0.00002 * s(Mp - M - 2 * F) - 0.00002 * s(3 * Mp + M) + 0.00002 * s(4 * Mp))
    return jde


@lru_cache(maxsize=None)
def new_moons_ny(year_from: int = 1990, year_to: int = 2060) -> tuple[date, ...]:
    """New York calendar dates of every new moon in the span."""
    k0 = math.floor((year_from - 2000) * 12.3685) - 1
    k1 = math.ceil((year_to + 1 - 2000) * 12.3685) + 1
    return tuple(to_ny_date(jd_to_utc(new_moon_jde(k))) for k in range(k0, k1 + 1))


def days_from_new_moon(d: date) -> int:
    """Signed days to the nearest new moon (NY dates). 0 = new moon day."""
    best = None
    for nm in new_moons_ny():
        diff = (d - nm).days
        if best is None or abs(diff) < abs(best):
            best = diff
        if diff < -20:
            break
    return best


def lunar_hold(d: date) -> bool:
    """Lunar Tide holds SPY on days within 7 days of a new moon (the 15-day window)."""
    return abs(days_from_new_moon(d)) <= LUNAR_HALF_WINDOW


def moon_phase_name(d: date) -> str:
    x = days_from_new_moon(d)
    a = abs(x)
    if a <= 1: return "New Moon"
    if a >= 14: return "Full Moon"
    if a <= 6: return "Waxing Crescent" if x > 0 else "Waning Crescent"
    if a <= 8: return "First Quarter" if x > 0 else "Last Quarter"
    return "Waxing Gibbous" if x > 0 else "Waning Gibbous"


# ── Mercury ─────────────────────────────────────────────────────────────
#            a            a/cy         e            e/cy         I            I/cy          L              L/cy             varpi        varpi/cy     Omega        Omega/cy
MERCURY = (0.38709927, 0.00000037, 0.20563593, 0.00001906, 7.00497902, -0.00594749, 252.25032350, 149472.67411175, 77.45779628, 0.16047689, 48.33076593, -0.12534081)
EMBARY  = (1.00000261, 0.00000562, 0.01671123, -0.00004392, -0.00001531, -0.01294668, 100.46457166, 35999.37244981, 102.93768193, 0.32327364, 0.0, 0.0)


def _helio(el, T):
    a = el[0] + el[1] * T; e = el[2] + el[3] * T; I = math.radians(el[4] + el[5] * T)
    L = el[6] + el[7] * T; varpi = el[8] + el[9] * T; Om = el[10] + el[11] * T
    w = math.radians(varpi - Om); Om = math.radians(Om)
    M = math.radians(((L - varpi + 180) % 360) - 180)
    E = M + e * math.sin(M)
    for _ in range(30):
        dE = (M - (E - e * math.sin(E))) / (1 - e * math.cos(E))
        E += dE
        if abs(dE) < 1e-12:
            break
    xp = a * (math.cos(E) - e); yp = a * math.sqrt(1 - e * e) * math.sin(E)
    cw, sw, cO, sO, cI, sI = math.cos(w), math.sin(w), math.cos(Om), math.sin(Om), math.cos(I), math.sin(I)
    x = (cw * cO - sw * sO * cI) * xp + (-sw * cO - cw * sO * cI) * yp
    y = (cw * sO + sw * cO * cI) * xp + (-sw * sO + cw * cO * cI) * yp
    return x, y


def mercury_geo_longitude(jd: float) -> float:
    T = (jd - J2000) / 36525.0
    mx, my = _helio(MERCURY, T)
    ex, ey = _helio(EMBARY, T)
    return math.degrees(math.atan2(my - ey, mx - ex)) % 360.0


def _jd_of_close(d: date) -> float:
    # ~21:00 UTC: the US close (4 PM EST / 5 PM EDT, close enough at day resolution)
    return utc_to_jd(datetime(d.year, d.month, d.day, 21, tzinfo=timezone.utc))


def mercury_retrograde(d: date) -> bool:
    jd = _jd_of_close(d)
    diff = (mercury_geo_longitude(jd + 0.5) - mercury_geo_longitude(jd - 0.5) + 540) % 360 - 180
    return diff < 0


def mercury_hold(d: date) -> bool:
    """Retrograde Drive holds SPY while Mercury is direct."""
    return not mercury_retrograde(d)
