"""Tests for the fetch planning and parsing. Run with: python -m unittest"""

import unittest
from datetime import date

from fetch_weather import chunks, parse_daily, plan_ranges

BACKFILL = date(1991, 1, 1)
YESTERDAY = date(2026, 10, 18)


class PlanRangesTests(unittest.TestCase):
    def test_empty_database_backfills_everything(self):
        self.assertEqual(plan_ranges(None, None, BACKFILL, YESTERDAY), [(BACKFILL, YESTERDAY)])

    def test_daily_run_refreshes_last_week(self):
        ranges = plan_ranges(BACKFILL, date(2026, 10, 17), BACKFILL, YESTERDAY)
        self.assertEqual(ranges, [(date(2026, 10, 10), YESTERDAY)])

    def test_fills_early_years_for_an_existing_2023_database(self):
        ranges = plan_ranges(date(2023, 1, 1), date(2026, 10, 17), BACKFILL, YESTERDAY)
        self.assertEqual(ranges[0], (BACKFILL, date(2022, 12, 31)))
        self.assertEqual(ranges[1], (date(2026, 10, 10), YESTERDAY))

    def test_refresh_never_starts_before_first_day(self):
        ranges = plan_ranges(date(2026, 10, 15), date(2026, 10, 16), date(2026, 10, 15), YESTERDAY)
        self.assertEqual(ranges, [(date(2026, 10, 15), YESTERDAY)])


class ChunkTests(unittest.TestCase):
    def test_chunks_cover_range_without_gaps(self):
        parts = list(chunks(date(1991, 1, 1), date(2026, 10, 18), size=365 * 5))
        self.assertEqual(parts[0][0], date(1991, 1, 1))
        self.assertEqual(parts[-1][1], date(2026, 10, 18))
        for (_, end), (start, _) in zip(parts, parts[1:]):
            self.assertEqual((start - end).days, 1)


class ParseTests(unittest.TestCase):
    def test_skips_missing_values(self):
        payload = {"daily": {"time": ["2026-01-01", "2026-01-02"],
                             "temperature_2m_max": [14.2, None],
                             "temperature_2m_min": [7.1, 6.0]}}
        self.assertEqual(parse_daily(payload), [("2026-01-01", 14.2, 7.1)])


if __name__ == "__main__":
    unittest.main()
