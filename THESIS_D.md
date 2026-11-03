# ECNALANIF — MISSION CHARTER (THESIS D, PRE-REGISTERED)
**Date signed:** _____11/3/2026_________ &nbsp;&nbsp;|&nbsp;&nbsp; **Signed by:** _____Opie_________ (Opie)
**Drafted:** 2026-11-03 by Digi, before any Ecnalanif data was examined.
**Rule:** Written before any results exist. Never edited after signing; amendments are new dated sections, never deletions.
**Relationship to Finalance:** Ecnalanif is Finalance's mirror-dimension twin. It lives in its own folder (C:\Ecnalanif) and its own git repo. It reads Finalance's price files and never writes to them. Measurement only: no broker, no orders, no real money.

---

## THE CLAIM
Signals from outside the market (the Moon, space weather, the planets) predict SPY's daily returns. The proposed mechanism isn't the sky moving prices directly. It's the sky moving human mood, and mood moving prices. Each ship below tests one signal. Each lives or dies on its own.

## THE FLEET
Every ship starts with **$50,000** on SPY. Fees and slippage match Finalance config.py: **0.05% fee + 5 bps slippage per side**. Cash earns 0%. Sharpe uses 252 days and a 0% risk-free rate.

| Ship | Role | Holds SPY when… | Cash when… |
|---|---|---|---|
| **Earth Standard** | Benchmark | always | never |
| **The Echo** | Display only (its thesis died 2026-11-01) | SPY close > its 200-day SMA | close < 200-day SMA |
| **Lunar Tide** | Test D1 | within 7 days of a new moon (the 15-day window centered on new moon) | the other half of the cycle (around full moon) |
| **Solar Weather** | Test D2 | normal days | the 6 trading days after any UTC day with planetary Kp ≥ 6 (NOAA G2 storm or stronger) |
| **Retrograde Drive** | Test D3 | Mercury direct | Mercury retrograde (geocentric apparent longitude decreasing) |

**Fills.** The Moon and Mercury are known years ahead, so Lunar Tide and Retrograde Drive set each trading day's position from that day's sky and fill at the prior trading day's close. For the newest bar, the next trading day is taken as the next weekday, since holidays aren't known in the price file. Storms are not known ahead, so Solar Weather and The Echo decide at day t's close and fill at day t+1's close, the same as Finalance v2. A storm day counts only once its UTC day is complete, so a storm on day t first counts at day t+1's close.
**Sky definitions.** The new moon instant comes from Meeus (*Astronomical Algorithms*, ch. 49), converted to its New York calendar date. Mercury's geocentric ecliptic longitude comes from JPL's Keplerian elements (Standish, valid 1800–2050), taken at 21:00 UTC; retrograde means that longitude is falling over the surrounding 24 hours. Both were checked against PyEphem for 1993–2026: every new moon lands within 2.5 minutes, and Mercury differs on 1 day out of 12,418.
**Parameters are pre-committed and will not be swept:** 7-day lunar half-window, Kp ≥ 6, 6-day storm exit. If another value looks better afterwards, it goes in the post-mortem, not the rules.

## DATA (no mock data, ever)
- **SPY forward:** Finalance data/v2_prices/SPY.csv, read-only. Closes are split-adjusted, not dividend-adjusted (Finalance's convention), so no ship is paid dividends. Ignoring dividends slightly understates Earth Standard, which is always invested; this is declared here, not corrected.
- **SPY history:** daily closes from 1993, cross-checked against Finalance's file on every shared day; any difference over 0.1% stops the run.
- **Moon phase and Mercury:** computed in sky.py, standard library only (see Sky definitions above).
- **Kp:** GFZ Potsdam. History uses the definitive file (since 1932). For the forward flight, each UTC day's max Kp is frozen the first time all eight 3-hour values appear in GFZ's nowcast, so a later revision can never change a decision already made.
- Missing, stale or jumpy SPY data stops the scan and says why. Missing Kp **grounds** Solar Weather: it holds its last position and makes no decision until Kp is back. Grounded days are counted on the Bridge. Data is never filled in.

## BLACK BOX 1 — the historical test (one look, sealed)
- **Span:** 2007-01-01 (after both lunar papers were published) to the latest close on the day it runs. It runs once and seals itself.
- **Per ship (D1–D3):** a one-sided Welch t-test of SPY daily returns on "hold" days vs "cash" days, in the predicted direction (hold > cash).
- **PASS:** p < 0.0167 (0.05 split across three ships) **AND** the ship's Sharpe ≥ Earth Standard's over the same span.
- **KILL:** anything else.

## BLACK BOX 2 — the forward test (one look, sealed)
- **Launch:** the first daily scan after signing. The checkpoint is at **252 trading days** (about a year).
- **PASS** (only ships that passed Black Box 1): hold-day mean return > cash-day mean return **AND** the ship's Sharpe ≥ Earth Standard's over the forward period.
- **KILL:** anything else. A ship killed in Black Box 1 keeps flying for display but cannot pass.
- **Integrity flag:** if more than 10% of scheduled scans are missing, the verdict is recorded with the flag.

## THE STATION (names, not rules)
- **The Bridge:** the side-by-side dashboard. Five flight paths (equity curves), the scoreboard (return, Sharpe, drawdown, trades), and telemetry along the bottom (moon phase, Kp, Mercury, Skald mood).
- **The drones**, mirroring Imperium's ravens. Plain code, $0, read-only:
  - **Drone Cogito** (thought): now. Each ship's position and equity, today's sky, last scan, data freshness.
  - **Drone Memoria** (memory): history. Recent trades, Black Box status, missed scans.
- **Long-Range Sensors** (the per-stock news watch): reserved for its own charter. Not part of Thesis D.

## KNOWN WEAKNESSES (declared upfront)
- The lunar effect was found in pre-2006 data and may have faded once published. That is exactly what Black Box 1 tests.
- Storms at Kp ≥ 6 come in clusters and can be rare in quiet solar years, so D2 may have few events.
- Mercury retrograde has no academic basis that we know of. D3 is the pure astrology test.
- Three tests run at once, hence the split p-value.
- One forward year is a short window, so Black Box 2 is a confirmation, not a discovery.

## STANDING KILL SIGNAL
Wanting to peek early, tweak a window "just slightly," or add a planet after seeing results is itself the signal to stop and re-read this page.

---
*Ecnalanif · Thesis D · Simulated / measurement only · Not investment advice*
