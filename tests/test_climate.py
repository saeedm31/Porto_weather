"""Tests for the climate analysis. Run with: python -m unittest"""

import math
import random
import unittest
from datetime import date, timedelta

import climate


def synthetic_rows(start, end, warming_per_year=0.0, noise=0.0, seed=0):
    """Seasonal temperatures (warm in July, cool in January), with optional trend and noise."""
    rng = random.Random(seed)
    rows, d = [], start
    while d <= end:
        season = -math.cos(2 * math.pi * (d.timetuple().tm_yday - 15) / 365.25)
        shift = warming_per_year * (d.year - start.year) + rng.gauss(0, noise)
        rows.append((d, 19 + 6 * season + shift, 11 + 5 * season + shift))
        d += timedelta(days=1)
    return rows


class BaselineTests(unittest.TestCase):
    def test_uses_1991_2020_when_covered(self):
        rows = synthetic_rows(date(1990, 1, 1), date(2024, 6, 30))
        self.assertEqual(climate.choose_baseline(rows, date(2024, 7, 1)), (1991, 2020))

    def test_falls_back_to_complete_years(self):
        rows = synthetic_rows(date(2023, 1, 1), date(2026, 3, 20))
        self.assertEqual(climate.choose_baseline(rows, date(2026, 3, 21)), (2023, 2025))

    def test_no_baseline_with_too_little_data(self):
        rows = synthetic_rows(date(2025, 1, 1), date(2026, 3, 20))
        self.assertIsNone(climate.choose_baseline(rows, date(2026, 3, 21)))

    def test_current_year_never_counts_as_complete(self):
        rows = synthetic_rows(date(2023, 1, 1), date(2025, 12, 31))
        self.assertEqual(climate.complete_years(rows, date(2025, 12, 31)), [2023, 2024])


class NormalsTests(unittest.TestCase):
    def test_normals_cover_every_day_including_feb_29(self):
        rows = synthetic_rows(date(2001, 1, 1), date(2003, 12, 31))  # no leap day in the baseline
        normals = climate.daily_normals(rows, (2001, 2003))
        self.assertEqual(len(normals), 366)
        self.assertIn("02-29", normals)

    def test_normals_follow_the_seasons(self):
        rows = synthetic_rows(date(1991, 1, 1), date(2020, 12, 31), noise=2.0)
        normals = climate.daily_normals(rows, (1991, 2020))
        self.assertGreater(normals["07-15"][0], normals["01-15"][0] + 8)
        self.assertGreater(normals["07-15"][0], normals["07-15"][1])  # highs above lows

    def test_anomaly_is_zero_for_a_normal_day(self):
        rows = synthetic_rows(date(1991, 1, 1), date(2020, 12, 31))
        normals = climate.daily_normals(rows, (1991, 2020))
        d = date(2021, 4, 10)
        nmax, nmin = normals["04-10"]
        self.assertAlmostEqual(climate.anomaly(d, nmax, nmin, normals), 0.0)
        self.assertAlmostEqual(climate.anomaly(d, nmax + 2, nmin + 2, normals), 2.0)


class AnalysisTests(unittest.TestCase):
    def test_detects_the_warming_trend(self):
        # 0.03 °C per year = 0.3 °C per decade
        rows = synthetic_rows(date(1991, 1, 1), date(2025, 10, 18), warming_per_year=0.03, noise=1.5)
        result = climate.analyse(rows, today=date(2025, 10, 19))
        self.assertAlmostEqual(result["summary"]["trend_per_decade"], 0.3, delta=0.05)
        self.assertEqual(result["summary"]["baseline"], "1991–2020")
        self.assertEqual(result["summary"]["warmest_year"]["year"] >= 2015, True)

    def test_partial_year_compared_with_same_days(self):
        # A normal climate with no trend: a half year must not look warm or cold just
        # because it is missing the winter months.
        rows = synthetic_rows(date(1991, 1, 1), date(2025, 7, 31))
        years = climate.analyse(rows, today=date(2025, 8, 1))["years"]
        current = years[-1]
        self.assertFalse(current["complete"])
        self.assertAlmostEqual(current["anomaly"], 0.0, delta=0.15)

    def test_records_and_hot_days(self):
        rows = synthetic_rows(date(2023, 1, 1), date(2025, 12, 31))
        rows.append((date(2026, 1, 1), 35.5, -2.0))
        result = climate.analyse(rows, today=date(2026, 1, 2))
        s = result["summary"]
        self.assertEqual(s["record_high"], {"date": "2026-01-01", "value": 35.5})
        self.assertEqual(s["record_low"], {"date": "2026-01-01", "value": -2.0})
        self.assertEqual(result["years"][-1]["hot_days"], 1)
        self.assertIsNone(s["trend_per_decade"])  # only 3 full years: too few for a trend

    def test_works_without_normals(self):
        rows = synthetic_rows(date(2025, 6, 1), date(2025, 9, 1))
        result = climate.analyse(rows, today=date(2025, 9, 2))
        self.assertIsNone(result["summary"]["baseline"])
        self.assertNotIn("anomaly", result["summary"]["latest"])
        self.assertIsNone(result["years"][0]["anomaly"])

    def test_empty(self):
        self.assertIsNone(climate.analyse([]))


if __name__ == "__main__":
    unittest.main()
