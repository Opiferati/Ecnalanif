"""Ecnalanif — scoring math. Standard library only."""
from __future__ import annotations

import math


def daily_returns(equity: list[float]) -> list[float]:
    return [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity))]


def sharpe(equity: list[float]) -> float | None:
    r = daily_returns(equity)
    if len(r) < 2:
        return None
    m = sum(r) / len(r)
    sd = math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))
    return None if sd == 0 else m / sd * math.sqrt(252)


def max_drawdown(equity: list[float]) -> float:
    peak, dd = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        dd = max(dd, 1 - v / peak)
    return dd


def _betacf(a, b, x):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(c) > 1e-300 else 1 + aa / 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(c) > 1e-300 else 1 + aa / 1e-300
        de = d * c; h *= de
        if abs(de - 1) < 1e-14:
            break
    return h


def _betainc(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1 - math.exp(lbt) * _betacf(b, a, 1 - x) / b


def t_sf(t: float, df: float) -> float:
    """P(T > t) for Student's t."""
    p = 0.5 * _betainc(df / 2, 0.5, df / (df + t * t))
    return p if t > 0 else 1 - p


def welch_one_sided(a: list[float], b: list[float]) -> dict:
    """H1: mean(a) > mean(b)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return {"n_hold": na, "n_cash": nb, "t": None, "df": None, "p": None}
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    se2 = va / na + vb / nb
    t = (ma - mb) / math.sqrt(se2)
    df = se2 ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    return {"n_hold": na, "n_cash": nb, "mean_hold": ma, "mean_cash": mb, "t": t, "df": df, "p": t_sf(t, df)}


# ── Law 8: error bars ────────────────────────────────────────────────────
# "Every verdict reports the paired difference against the benchmark AND its
#  uncertainty. A gap inside its own error bar is UNTESTED, not a PASS."
# Added 2026-11-10. Display-only on charters signed before this date.
# Kept byte-identical to C:\Cavalier\stats.py — the Cavalier's copy came from
# here, and the two must not drift.


def sharpe_se(equity: list[float], periods: int = 252) -> float | None:
    """Standard error of an ANNUALISED Sharpe ratio (Lo 2002, IID returns).

        SE(SR_a) = sqrt(periods * (1 + SR_a**2 / (2*periods)) / n)

    Sanity anchor: n=504 trading days and SR=0 gives +/-0.71. That is the whole
    argument for this function — a Sharpe gap of 0.1 over two years of data is
    not a finding, it is the measurement noise of the instrument.
    """
    r = daily_returns(equity)
    n = len(r)
    if n < 2:
        return None
    sr = sharpe(equity)
    if sr is None:
        return None
    return math.sqrt(periods * (1 + sr * sr / (2 * periods)) / n)


def paired_diff(a: list[float], b: list[float], periods: int = 252) -> dict:
    """The paired difference a - b, day by day, with its uncertainty.

    Why paired and not two Sharpes differenced: the riders hold the SAME asset
    at different exposures, so their daily returns are strongly correlated.
    Pairing cancels the shared market move and leaves only what the rule did
    differently. That is a far more powerful test on identical data, and it is
    why law 8 asks for the paired difference by name.

    One-sided throughout: the claim under test is "a beats b", never "a differs
    from b". `decisive` is True only when the difference is positive AND outside
    its own 95% bar.
    """
    n = min(len(a), len(b))
    if n < 2:
        return {"n": n, "mean_daily": None, "se_daily": None, "t": None,
                "df": None, "p": None, "annual_mean": None,
                "annual_ci95": None, "decisive": None}
    d = [a[i] - b[i] for i in range(n)]
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    se = sd / math.sqrt(n)
    t = (m / se) if se > 0 else None
    p = t_sf(t, n - 1) if t is not None else None
    half = 1.96 * se * periods
    return {"n": n, "mean_daily": m, "se_daily": se, "t": t, "df": n - 1, "p": p,
            "annual_mean": m * periods,
            "annual_ci95": [m * periods - half, m * periods + half],
            "decisive": bool(p is not None and p < 0.05 and m > 0)}
