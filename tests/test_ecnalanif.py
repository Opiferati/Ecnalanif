"""Ecnalanif tests. Synthetic prices only — no real SPY is examined before the Charter is signed.
Reference sky values were generated with PyEphem 4.2.1 (2026-11-03)."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import charter  # noqa: E402
import fleet  # noqa: E402
import sky  # noqa: E402
import sources  # noqa: E402
import stats  # noqa: E402


def fake_prices(n=320, start=date(2026, 1, 2), seed=7):
    import random
    rnd, out, d, px = random.Random(seed), [], start, 500.0
    while len(out) < n:
        if d.weekday() < 5:
            px *= 1 + rnd.gauss(0.0004, 0.01)
            out.append((d.isoformat(), round(px, 4)))
        d += timedelta(days=1)
    return out


class TestSky(unittest.TestCase):
    def test_new_moons_match_ephem(self):
        nms = set(sky.new_moons_ny())
        for d in ("1995-03-01", "2008-03-07", "2020-03-24", "2026-03-18"):
            self.assertIn(date.fromisoformat(d), nms, d)

    def test_lunar_window_is_15_days(self):
        nm = date(2026, 3, 18)
        held = [sky.lunar_hold(nm + timedelta(days=k)) for k in range(-10, 11)]
        self.assertEqual(sum(held), 15)
        self.assertTrue(sky.lunar_hold(nm + timedelta(days=7)))
        self.assertFalse(sky.lunar_hold(nm + timedelta(days=8)))
        self.assertFalse(sky.lunar_hold(nm + timedelta(days=15)))   # around full moon

    def test_mercury_retrograde_periods_match_ephem(self):
        periods = [("2025-03-15", "2025-04-06"), ("2025-07-18", "2025-08-10"), ("2025-11-09", "2025-11-28"),
                   ("2026-02-26", "2026-03-19"), ("2026-06-29", "2026-07-23"), ("2026-10-24", "2026-11-12")]
        for a, b in periods:
            a, b = date.fromisoformat(a), date.fromisoformat(b)
            self.assertTrue(sky.mercury_retrograde(a + timedelta(days=1)), a)
            self.assertTrue(sky.mercury_retrograde(b - timedelta(days=1)), b)
            self.assertFalse(sky.mercury_retrograde(a - timedelta(days=3)), a)
            self.assertFalse(sky.mercury_retrograde(b + timedelta(days=3)), b)


class TestFleet(unittest.TestCase):
    def setUp(self):
        self.p = fake_prices()

    def test_earth_fees_once(self):
        sim = fleet.simulate(self.p, [1] * len(self.p), 0)
        self.assertEqual(len(sim["trades"]), 1)
        self.assertAlmostEqual(sim["equity"][0], fleet.START_CASH / (1 + fleet.FEE + fleet.SLIP), places=6)
        self.assertAlmostEqual(sim["equity"][-1] / sim["equity"][0], self.p[-1][1] / self.p[0][1], places=9)

    def test_round_trip_cost(self):
        pos = [1, 0] + [0] * (len(self.p) - 2)
        flat = [(d, 100.0) for d, _ in self.p]
        sim = fleet.simulate(flat, pos, 0)
        self.assertAlmostEqual(sim["equity"][-1], fleet.START_CASH * (1 - 0.001) / (1 + 0.001), places=6)

    def test_sky_ships_use_next_days_sky(self):
        pos = fleet.positions(self.p, {})
        for i in range(len(self.p) - 1):
            nxt = date.fromisoformat(self.p[i + 1][0])
            self.assertEqual(pos["lunar"][i], int(sky.lunar_hold(nxt)))
            self.assertEqual(pos["mercury"][i], int(sky.mercury_hold(nxt)))

    def test_echo_is_lagged_one_day(self):
        pos = fleet.positions(self.p, None)
        closes = [c for _, c in self.p]
        for i in range(fleet.SMA_N, len(self.p)):
            t = i - 1
            sma = sum(closes[t - fleet.SMA_N + 1:t + 1]) / fleet.SMA_N
            self.assertEqual(pos["echo"][i], int(closes[t] > sma))

    def test_solar_storm_window(self):
        kp = {}
        d = date.fromisoformat(self.p[0][0]) - timedelta(days=20)
        while d <= date.fromisoformat(self.p[-1][0]):
            kp[d.isoformat()] = 2.0; d += timedelta(days=1)
        storm_i = 100
        storm = self.p[storm_i][0]
        kp[storm] = 7.0
        pos = fleet.positions(self.p, kp)
        # decided at closes of the 6 trading days after the storm day -> positions shifted one bar later
        for k in range(1, 7):
            self.assertEqual(pos["solar"][storm_i + k + 1], 0, k)
        self.assertEqual(pos["solar"][storm_i + 1], 1)      # storm day itself isn't complete at its own close
        self.assertEqual(pos["solar"][storm_i + 8], 1)

    def test_solar_grounded_without_kp(self):
        pos = fleet.positions(self.p, {})
        self.assertTrue(all(x is None for x in pos["solar"]))
        sim = fleet.simulate(self.p, pos["solar"], 0)
        self.assertEqual(sim["trades"], [])                  # grounded ship never trades, never invents data

    def test_hold_cash_split(self):
        pos = [1, 0] * (len(self.p) // 2)
        h, c = fleet.hold_cash_returns(self.p, pos, 0)
        self.assertEqual(len(h) + len(c), len(self.p) - 1)


class TestStats(unittest.TestCase):
    def test_t_sf(self):
        self.assertAlmostEqual(stats.t_sf(0.0, 10), 0.5, places=9)
        self.assertAlmostEqual(stats.t_sf(2.228, 10), 0.025, places=3)
        self.assertAlmostEqual(stats.t_sf(1.645, 1e6), 0.05, places=3)

    def test_welch_direction(self):
        w = stats.welch_one_sided([0.01, 0.02, 0.015, 0.012], [-0.01, -0.02, -0.015, -0.011])
        self.assertLess(w["p"], 0.01)


class TestCharterAndData(unittest.TestCase):
    def test_unsigned_detection(self):
        self.assertFalse(charter.signed("**Date signed:** ______________ &nbsp;")[0])
        self.assertTrue(charter.signed("**Date signed:** 11/3/2026 &nbsp;")[0])

    def test_hash_ignores_signature_and_amendments(self):
        a = "x\n**Date signed:** ____\nbody"
        b = "x\n**Date signed:** 11/3/2026\nbody\n## AMENDMENT 1 — later"
        self.assertEqual(charter.body_hash(a), charter.body_hash(b))
        self.assertNotEqual(charter.body_hash(a), charter.body_hash(a + "!"))

    def test_kp_parse_only_complete_days(self):
        rows = ["#h"] + [f"2026 11 01 {h:.1f} 0 0 0 {k:.3f} 0 0" for h, k in zip(range(0, 24, 3), [1, 2, 6.333, 1, 1, 1, 1, 1])]
        rows += [f"2026 11 02 {h:.1f} 0 0 0 1.000 0 0" for h in range(0, 21, 3)]          # only 7 values
        rows += ["2026 11 02 21.0 0 0 0 -1.000 -1 0"]
        kp = sources.parse_kp("\n".join(rows))
        self.assertEqual(kp, {"2026-11-01": 6.333})

    def test_integrity_stops_on_gap(self):
        with self.assertRaises(sources.SourceError):
            sources.check_integrity([("2026-01-02", 1.0), ("2026-01-20", 1.0)])

    def test_never_touches_finalance_writes_or_brokers(self):
        for f in os.listdir(HERE):
            if f.endswith(".py"):
                src = open(os.path.join(HERE, f)).read().lower()
                for bad in ("alpaca", "schwab", "place_order", "submit_order"):
                    self.assertNotIn(bad, src, f)


class TestScanEndToEnd(unittest.TestCase):
    """A full scan against a fake Finalance folder and fake Kp, in a temp copy of the app."""

    def test_docked_then_launch(self):
        tmp = tempfile.mkdtemp()
        try:
            app = os.path.join(tmp, "app")
            shutil.copytree(HERE, app, ignore=shutil.ignore_patterns("state", "data", "Bridge.html", "__pycache__", ".git"))
            fin = os.path.join(tmp, "fin", "data", "v2_prices"); os.makedirs(fin)
            p = fake_prices(400, date(2025, 6, 2))
            with open(os.path.join(fin, "SPY.csv"), "w") as f:
                f.write("date,close\n" + "".join(f"{d},{c}\n" for d, c in p))
            kp_lines = []
            d = date(2025, 5, 1)
            while d <= date.fromisoformat(p[-1][0]):
                kp_lines += [f"{d.year} {d.month:02d} {d.day:02d} {h:.1f} 0 0 0 2.000 0 0" for h in range(0, 24, 3)]
                d += timedelta(days=1)
            env = dict(os.environ, FINALANCE_DIR=os.path.join(tmp, "fin"), IMPERIUM_DIR=os.path.join(tmp, "imp"))
            code = ("import sys,json; sys.path.insert(0,'.'); import sources; "
                    f"sources._get=lambda url,tries=3: open({json.dumps(os.path.join(tmp, 'kp.txt'))},'rb').read(); "
                    "import scan; st=scan.run(); print(json.dumps({'status':st['status'],'ships':len(st.get('ships',[]))}))")
            with open(os.path.join(tmp, "kp.txt"), "w") as f:
                f.write("\n".join(kp_lines))
            import subprocess
            out = subprocess.run([sys.executable, "-c", code], cwd=app, env=env, capture_output=True, text=True)
            self.assertEqual(json.loads(out.stdout.strip().splitlines()[-1])["status"], "docked", out.stderr)
            ch = os.path.join(app, "THESIS_D.md")
            txt = open(ch).read().replace("**Date signed:** ______________", "**Date signed:** 2026-11-03", 1)
            open(ch, "w").write(txt)
            out = subprocess.run([sys.executable, "-c", code], cwd=app, env=env, capture_output=True, text=True)
            res = json.loads(out.stdout.strip().splitlines()[-1])
            self.assertEqual(res, {"status": "flying", "ships": 5}, out.stderr)
            self.assertTrue(os.path.exists(os.path.join(app, "Bridge.html")))
            launch = json.load(open(os.path.join(app, "state", "launch.json")))
            self.assertEqual(launch["launch_date"], p[-1][0])
            st = json.load(open(os.path.join(app, "state", "state.json")))
            self.assertTrue(all(abs(s["equity"] - 50000) < 60 for s in st["ships"]))   # day 0: only the entry fee
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
