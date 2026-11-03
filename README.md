# Ecnalanif — the mirror-dimension Finalance

An observation station that tests whether the sky (the Moon, solar storms, Mercury) predicts SPY.
Rules, pass/kill criteria and the Black Boxes are in **THESIS_D.md** (the Mission Charter). Measurement only:
no broker, no orders, no real money. Standard-library Python 3, nothing to install.

## Launch
1. Read THESIS_D.md and fill in **Date signed** and **Signed by**. Until then the fleet stays docked.
2. Run a scan (or let Imperium do it after the Skald's evening reading):

       python3 /mnt/c/Ecnalanif/scan.py

   The first scan after signing sets launch day. All five ships start with $50,000 at that close.
3. Open **Bridge.html** (double-click it in C:\Ecnalanif). It is rewritten after every scan.

## The fleet
| Ship | What it does |
|---|---|
| Earth Standard | holds SPY, always (benchmark) |
| The Echo | Finalance's killed 200-day trend rule on SPY (display only) |
| Lunar Tide | SPY within 7 days of a new moon, cash around full moon (D1) |
| Solar Weather | cash for 6 trading days after a Kp ≥ 6 storm (D2) |
| Retrograde Drive | cash while Mercury is retrograde (D3) |

## The drones
**Cogito** reports now (positions, sky, data freshness). **Memoria** covers history (trades, missed scans,
Black Box status). Both are plain code, cost $0, and appear on the Bridge and in Imperium.

## Black Boxes (each opens once, then seals itself)
    python3 blackbox.py --historical   # Black Box 1: 2007 → today. Run it once, after signing.
    python3 blackbox.py --forward      # Black Box 2: after 252 trading days of flight
    python3 blackbox.py --show

## Tests
    python3 -m unittest discover -s tests      # synthetic prices only

## Files
- `sky.py` moon and Mercury math · `fleet.py` ship rules and engine · `sources.py` data in (read-only from Finalance)
- `scan.py` daily scan · `blackbox.py` the sealed tests · `drones.py` Cogito and Memoria · `bridge.py` + `bridge_template.html` the Bridge
- `state/` launch, scan log, sealed boxes (tracked in git) · `data/kp_daily.csv` frozen Kp (tracked in git)
