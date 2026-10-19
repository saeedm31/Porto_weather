"""Climate analysis on daily min/max temperatures.

Pure Python (no database, no web), so it is easy to test. Takes rows of
(date, temp_max, temp_min) and answers: what is normal for each day of the
year, how unusual was a given day or year, and how fast is it warming?
"""

from collections import defaultdict
from datetime import date, timedelta

PREFERRED_BASELINE = (1991, 2020)  # the current WMO standard climate normal
MIN_BASELINE_YEARS = 3              # fewer complete years than this: no normals
MIN_TREND_YEARS = 10                # fewer complete years than this: no trend
SMOOTHING_DAYS = 31                 # window for smoothing the day-of-year normals
HOT_DAY = 30.0                      # °C, a "hot day" for the yearly summary


def complete_years(rows, today):
    """Years before `today`'s year with (almost) every day present."""
    counts = defaultdict(int)
    for d, _, _ in rows:
        counts[d.year] += 1
    return sorted(y for y, n in counts.items() if n >= 360 and y < today.year)


def choose_baseline(rows, today):
    """Pick the reference period: 1991-2020 if fully covered, else all complete years."""
    years = complete_years(rows, today)
    first, last = PREFERRED_BASELINE
    if all(y in years for y in range(first, last + 1)):
        return first, last
    if len(years) >= MIN_BASELINE_YEARS:
        return years[0], years[-1]
    return None


def day_key(d):
    """Day-of-year key that treats Feb 29 as its own day: 'MM-DD'."""
    return d.strftime("%m-%d")


# Every calendar day in order, including Feb 29 (2000 was a leap year).
ALL_KEYS = [day_key(date(2000, 1, 1) + timedelta(days=i)) for i in range(366)]


def daily_normals(rows, baseline):
    """Smoothed normal max/min for each calendar day, from the baseline years.

    Raw averages over ~30 years are noisy from one day to the next, so they are
    smoothed with a centred moving average that wraps around the new year.
    """
    start, end = baseline
    sums = {k: [0.0, 0.0, 0] for k in ALL_KEYS}
    for d, tmax, tmin in rows:
        if start <= d.year <= end:
            s = sums[day_key(d)]
            s[0] += tmax
            s[1] += tmin
            s[2] += 1

    raw = [(s[0] / s[2], s[1] / s[2]) if s[2] else None for s in (sums[k] for k in ALL_KEYS)]
    n, half = len(ALL_KEYS), SMOOTHING_DAYS // 2
    normals = {}
    for i, key in enumerate(ALL_KEYS):
        window = [raw[(i + j) % n] for j in range(-half, half + 1)]
        window = [w for w in window if w is not None]
        normals[key] = (sum(w[0] for w in window) / len(window),
                        sum(w[1] for w in window) / len(window))
    return normals


def mean_temp(tmax, tmin):
    return (tmax + tmin) / 2


def anomaly(d, tmax, tmin, normals):
    """How much warmer (+) or colder (-) than normal a day was, in °C (daily mean)."""
    nmax, nmin = normals[day_key(d)]
    return mean_temp(tmax, tmin) - mean_temp(nmax, nmin)


def yearly_summary(rows, normals, today):
    """One row per year: averages, extremes, hot days and the anomaly vs normal.

    The anomaly is the average daily anomaly, so a year in progress is compared
    with the normal for the same days, not with a full year.
    """
    by_year = defaultdict(list)
    for r in rows:
        by_year[r[0].year].append(r)

    full = set(complete_years(rows, today))
    out = []
    for year in sorted(by_year):
        days = by_year[year]
        item = {
            "year": year,
            "days": len(days),
            "complete": year in full,
            "mean_max": round(sum(r[1] for r in days) / len(days), 2),
            "mean_min": round(sum(r[2] for r in days) / len(days), 2),
            "highest": max(r[1] for r in days),
            "lowest": min(r[2] for r in days),
            "hot_days": sum(1 for r in days if r[1] >= HOT_DAY),
            "anomaly": None,
        }
        if normals:
            item["anomaly"] = round(sum(anomaly(*r, normals) for r in days) / len(days), 2)
        out.append(item)
    return out


def warming_trend(years):
    """Least-squares trend of the yearly anomaly, in °C per decade (complete years only)."""
    pts = [(y["year"], y["anomaly"]) for y in years if y["complete"] and y["anomaly"] is not None]
    if len(pts) < MIN_TREND_YEARS:
        return None
    n = len(pts)
    mx = sum(x for x, _ in pts) / n
    my = sum(v for _, v in pts) / n
    slope = sum((x - mx) * (v - my) for x, v in pts) / sum((x - mx) ** 2 for x, _ in pts)
    return round(slope * 10, 2)


def analyse(rows, today=None):
    """Everything the dashboard shows, computed from the stored rows."""
    today = today or date.today()
    rows = sorted(rows)
    if not rows:
        return None

    baseline = choose_baseline(rows, today)
    normals = daily_normals(rows, baseline) if baseline else None
    years = yearly_summary(rows, normals, today)

    def day_info(r):
        info = {"date": r[0].isoformat(), "temp_max": r[1], "temp_min": r[2]}
        if normals:
            nmax, nmin = normals[day_key(r[0])]
            info.update(normal_max=round(nmax, 2), normal_min=round(nmin, 2),
                        anomaly=round(anomaly(*r, normals), 2))
        return info

    hottest = max(rows, key=lambda r: r[1])
    coldest = min(rows, key=lambda r: r[2])
    this_year = next((y for y in years if y["year"] == rows[-1][0].year), None)

    summary = {
        "first_date": rows[0][0].isoformat(),
        "last_date": rows[-1][0].isoformat(),
        "days": len(rows),
        "baseline": f"{baseline[0]}–{baseline[1]}" if baseline else None,
        "latest": day_info(rows[-1]),
        "record_high": {"date": hottest[0].isoformat(), "value": hottest[1]},
        "record_low": {"date": coldest[0].isoformat(), "value": coldest[2]},
        "this_year": this_year,
        "trend_per_decade": warming_trend(years),
        "warmest_year": max((y for y in years if y["complete"] and y["anomaly"] is not None),
                            key=lambda y: y["anomaly"], default=None),
    }
    return {"summary": summary, "years": years, "daily": [day_info(r) for r in rows]}
