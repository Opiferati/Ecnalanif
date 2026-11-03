"""Ecnalanif — the drones. Plain code, $0, read-only. Mirrors Imperium's ravens.

Drone Cogito (thought): now.   Drone Memoria (memory): history.
"""
from __future__ import annotations


def _pct(x): return "—" if x is None else f"{x:+.2%}"
def _num(x, f="{:.2f}"): return "—" if x is None else f.format(x)


def cogito(state: dict) -> str:
    if state.get("status") == "docked":
        t = state["telemetry"]
        return ("DRONE COGITO — the fleet is DOCKED. The Mission Charter is unsigned, so no ship has launched.\n"
                f"Sky over the station: {t['moon']} ({t['days_from_new_moon']:+d} d from new moon), "
                f"Mercury {'RETROGRADE' if t['mercury_retrograde'] else 'direct'}.")
    t, lines = state["telemetry"], []
    lines.append(f"DRONE COGITO — {state['as_of']} close, day {state['days_flown']} of 252.")
    for s in state["ships"]:
        now = "SPY " if s["position"] == 1 else "cash"
        nxt = "SPY" if s["next"] == "IN SPY" else "cash"
        lines.append(f"  {s['name']:<17}{_pct(s['return']):>8}  {now} → {nxt}")
    lines.append(f"Sky: {t['moon']} ({t['days_from_new_moon']:+d} d from new moon) · Mercury "
                 f"{'RETROGRADE' if t['mercury_retrograde'] else 'direct'} · Kp {_num(t['kp'], '{:.1f}')} ({t['kp_date'] or '—'})"
                 f" · Skald stocks {t['skald_stock'] or '—'}")
    if state.get("warnings"):
        lines.append("Warnings: " + " | ".join(state["warnings"]))
    return "\n".join(lines)


def memoria(state: dict) -> str:
    if state.get("status") == "docked":
        return "DRONE MEMORIA — nothing to remember yet. The log begins at launch."
    lines = [f"DRONE MEMORIA — launched {state['launch_date']}, {state['scans']} scan(s) logged, "
             f"{state['missed_scans']} missed."]
    recent = sorted(((tr["date"], s["name"], tr["side"], tr["price"]) for s in state["ships"] for tr in s["trades"]),
                    reverse=True)[:8]
    if recent:
        lines.append("Recent trades:")
        lines += [f"  {d}  {n:<17} {side:<4} @ {p:,.2f}" for d, n, side, p in recent]
    else:
        lines.append("No trades yet.")
    b1, b2 = state["blackbox1"], state["blackbox2"]
    lines.append(f"Black Box 1 (historical): {b1}.  Black Box 2 (forward): {b2}.")
    if state.get("grounded_days"):
        lines.append(f"Solar Weather grounded on {len(state['grounded_days'])} day(s) for missing Kp.")
    return "\n".join(lines)
