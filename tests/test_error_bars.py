"""Law 8 — error bars, Ecnalanif side. Display-only, like Amendment 2's
honesty column: THESIS_D is signed and stays as signed."""
from __future__ import annotations

import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import stats  # noqa: E402

def _find_cavalier_stats():
    """The suite runs under WSL and under Windows, so try both spellings. A
    hardcoded path here would skip silently, which defeats the point of the
    check it guards."""
    for p in (r"C:\Cavalier\stats.py", "/mnt/c/Cavalier/stats.py"):
        if os.path.exists(p):
            return p
    return None


CAVALIER_STATS = _find_cavalier_stats()


def equity_from(returns: list[float], start: float = 1.0) -> list[float]:
    eq = [start]
    for r in returns:
        eq.append(eq[-1] * (1 + r))
    return eq


class ErrorBars(unittest.TestCase):
    def test_the_anchor_every_argument_rests_on(self):
        # 504 days, mean zero: SE(Sharpe) = 0.71. This is why a 0.1 Sharpe gap
        # is not a finding. If this breaks, the reasoning breaks with it.
        eq = equity_from([0.01, -0.01] * 252)
        self.assertAlmostEqual(stats.sharpe_se(eq), math.sqrt(0.5), places=3)

    def test_a_LARGER_but_NOISY_edge_is_NOT_decisive(self):
        # The whole purpose of law 8: wins on average, cannot be told from luck.
        bench = [0.01, -0.005, 0.002] * 100
        rider = [bench[i] + (0.05 if i % 2 else -0.045) for i in range(len(bench))]
        d = stats.paired_diff(rider, bench)
        self.assertGreater(d["mean_daily"], 0.0, "it does win on average")
        self.assertFalse(d["decisive"], "but the win is inside its own error bar")

    def test_a_small_steady_edge_is_decisive(self):
        bench = [0.01, -0.005, 0.002] * 100
        d = stats.paired_diff([x + 0.0002 for x in bench], bench)
        self.assertTrue(d["decisive"], d)

    def test_losing_is_never_a_finding(self):
        bench = [0.01, -0.005, 0.002] * 100
        self.assertFalse(stats.paired_diff([x - 0.0002 for x in bench], bench)["decisive"])

    def test_too_short_abstains_instead_of_crashing(self):
        self.assertIsNone(stats.paired_diff([0.01], [0.02])["decisive"])
        self.assertIsNone(stats.sharpe_se([1.0, 1.01]))


class SignedCharterStaysSigned(unittest.TestCase):
    @staticmethod
    def _law8_code() -> str:
        """Executable lines of the law 8 block only, to the end of judge().
        Comments are stripped: prose explaining the rule must not be mistaken
        for code breaking it."""
        with open(os.path.join(HERE, "blackbox.py"), encoding="utf-8") as f:
            src = f.read()
        marker = src.index("Law 8: error bars")
        end = src.index("return out", marker)
        return "\n".join(line for line in src[marker:end].splitlines()
                         if not line.strip().startswith("#"))

    def test_the_law8_block_never_assigns_a_verdict(self):
        code = self._law8_code()
        self.assertIn('out["error_bars"]', code, "the block under test is actually there")
        self.assertNotIn('out["verdicts"]', code,
                         "display-only on a signed charter: it must never assign a verdict")

    def test_the_payload_declares_itself_non_binding(self):
        self.assertIn('"binding": False', self._law8_code())


class NoDriftBetweenStations(unittest.TestCase):
    """The Cavalier's stats.py is a copy of this one and says so in its header.
    A silent divergence would mean the twins score by different rules, which is
    the one thing a side-by-side comparison cannot survive."""

    @unittest.skipUnless(CAVALIER_STATS, "the Cavalier is not on this machine")
    def test_the_two_stations_score_by_the_same_math(self):
        def defs(path):
            with open(path, encoding="utf-8") as f:
                return {ln.strip() for ln in f if ln.startswith("def ")}
        here, there = defs(os.path.join(HERE, "stats.py")), defs(CAVALIER_STATS)
        self.assertEqual(here, there, "stats.py has drifted between the twins")


if __name__ == "__main__":
    unittest.main()
