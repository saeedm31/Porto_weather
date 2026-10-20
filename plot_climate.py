"""Draw the climate chart used in the README (docs/climate.svg).

Usage:
    python plot_climate.py        # reads the database configured in .env

Top: the last 12 months of daily highs and lows against the 1991-2020 normal range.
Bottom: every year's average difference from normal, with the least-squares
warming trend. Uses the same analysis as the dashboard (climate.py).
Plain SVG, no plotting library needed.
"""

import os
from datetime import date

import climate

W = 900
STYLE = """
  .bg { fill: #fcfcfb; } .grid { stroke: #e4e3df; stroke-width: 1; } .zero { stroke: #8a8984; stroke-width: 1; }
  .axis { fill: #52514e; font: 12px system-ui, -apple-system, sans-serif; }
  .title { fill: #0b0b0b; font: 600 15px system-ui, -apple-system, sans-serif; }
  .sub { fill: #0b0b0b; font: 600 13px system-ui, -apple-system, sans-serif; }
  .normal { fill: #8a8984; opacity: .22; }
  .high { fill: none; stroke: #eb6834; stroke-width: 1.5; } .low { fill: none; stroke: #2a78d6; stroke-width: 1.5; }
  .warm { fill: #eb6834; } .cold { fill: #2a78d6; } .partial { opacity: .45; }
  .trend { stroke: #0b0b0b; stroke-width: 2; stroke-dasharray: 6 4; }
  .key-high { stroke: #eb6834; stroke-width: 2.5; } .key-low { stroke: #2a78d6; stroke-width: 2.5; }
  @media (prefers-color-scheme: dark) {
    .bg { fill: #1a1a19; } .grid { stroke: #34332f; } .zero { stroke: #7a7973; } .axis { fill: #c3c2b7; }
    .title, .sub { fill: #f0efec; } .normal { fill: #c3c2b7; opacity: .2; }
    .high, .key-high { stroke: #d95926; } .low, .key-low { stroke: #3987e5; }
    .warm { fill: #d95926; } .cold { fill: #3987e5; } .trend { stroke: #f0efec; }
  }
"""


def daily_panel(days, top, height, left=48, right=16):
    """Daily highs/lows for the last 365 days over the normal range."""
    days = days[-365:]
    lo = min(min(d["temp_min"], d["normal_min"]) for d in days)
    hi = max(max(d["temp_max"], d["normal_max"]) for d in days)
    lo, hi = 5 * (int(lo) // 5) - (5 if lo < 0 else 0), 5 * (int(hi) // 5 + 1)
    n, y0, y1 = len(days), top + height, top

    def x(i):
        return left + i * (W - left - right) / (n - 1)

    def y(v):
        return y0 - (v - lo) * (y0 - y1) / (hi - lo)

    out = [f'<text class="sub" x="{left}" y="{top - 30}">Last 12 months: daily highs and lows vs the normal range</text>',
           f'<line class="key-high" x1="{left}" x2="{left + 22}" y1="{top - 14}" y2="{top - 14}"/>'
           f'<text class="axis" x="{left + 28}" y="{top - 10}">Daily high</text>'
           f'<line class="key-low" x1="{left + 110}" x2="{left + 132}" y1="{top - 14}" y2="{top - 14}"/>'
           f'<text class="axis" x="{left + 138}" y="{top - 10}">Daily low</text>'
           f'<rect class="normal" x="{left + 216}" y="{top - 20}" width="22" height="12" rx="2"/>'
           f'<text class="axis" x="{left + 244}" y="{top - 10}">Normal range (1991–2020 average low to high)</text>']
    for v in range(lo, hi + 1, 5):
        out.append(f'<line class="grid" x1="{left}" x2="{W - right}" y1="{y(v):.0f}" y2="{y(v):.0f}"/>'
                   f'<text class="axis" x="{left - 8}" y="{y(v) + 4:.0f}" text-anchor="end">{v}°</text>')
    band = (" ".join(f"{x(i):.0f},{y(d['normal_max']):.0f}" for i, d in enumerate(days)) + " " +
            " ".join(f"{x(i):.0f},{y(d['normal_min']):.0f}" for i, d in reversed(list(enumerate(days)))))
    out.append(f'<polygon class="normal" points="{band}"/>')
    for key, cls in (("temp_max", "high"), ("temp_min", "low")):
        pts = " ".join(f"{x(i):.0f},{y(d[key]):.0f}" for i, d in enumerate(days))
        out.append(f'<polyline class="{cls}" points="{pts}"/>')
    for i, d in enumerate(days):
        if d["date"].endswith("-01"):
            label = date.fromisoformat(d["date"]).strftime("%b")
            out.append(f'<text class="axis" x="{x(i):.0f}" y="{y0 + 18}" text-anchor="middle">{label}</text>')
    return out


def yearly_panel(years, trend, top, height, left=48, right=16):
    """Each year's anomaly as a bar, plus the least-squares trend over complete years."""
    years = [y for y in years if y["anomaly"] is not None]
    lim = max(1.0, max(abs(y["anomaly"]) for y in years))
    lim = (int(lim * 2) + 1) / 2
    y0, y1 = top + height, top
    step = (W - left - right) / len(years)

    def y(v):
        return y1 + (lim - v) * (y0 - y1) / (2 * lim)

    def xc(i):
        return left + (i + 0.5) * step

    title = "Every year vs normal (average daily difference)"
    if trend is not None:
        title += f": warming {trend:+.2f} °C per decade"
    out = [f'<text class="sub" x="{left}" y="{top - 14}">{title}</text>']
    v = -lim
    while v <= lim + 1e-9:
        out.append(f'<line class="{"zero" if abs(v) < 1e-9 else "grid"}" x1="{left}" x2="{W - right}" '
                   f'y1="{y(v):.0f}" y2="{y(v):.0f}"/>'
                   f'<text class="axis" x="{left - 8}" y="{y(v) + 4:.0f}" text-anchor="end">{v:+.1f}°</text>')
        v += 0.5
    for i, yr in enumerate(years):
        a = yr["anomaly"]
        cls = ("warm" if a >= 0 else "cold") + ("" if yr["complete"] else " partial")
        top_y, h = (y(a), y(0) - y(a)) if a >= 0 else (y(0), y(a) - y(0))
        out.append(f'<rect class="{cls}" x="{xc(i) - step / 2 + 1.5:.1f}" y="{top_y:.1f}" '
                   f'width="{step - 3:.1f}" height="{max(h, 1):.1f}" rx="2"/>')
        if yr["year"] % 5 == 0 and yr["complete"]:
            out.append(f'<text class="axis" x="{xc(i):.0f}" y="{y0 + 18}" text-anchor="middle">{yr["year"]}</text>')
        elif not yr["complete"]:
            out.append(f'<text class="axis" x="{xc(i) + step / 2:.0f}" y="{min(y(a), y(0)) - 6:.0f}" '
                       f'text-anchor="end">{yr["year"]} so far</text>')
    full = [(i, yr["year"], yr["anomaly"]) for i, yr in enumerate(years) if yr["complete"]]
    if len(full) >= climate.MIN_TREND_YEARS:
        mx = sum(t for _, t, _ in full) / len(full)
        my = sum(a for _, _, a in full) / len(full)
        slope = sum((t - mx) * (a - my) for _, t, a in full) / sum((t - mx) ** 2 for _, t, _ in full)
        (i0, t0, _), (i1, t1, _) = full[0], full[-1]
        out.append(f'<line class="trend" x1="{xc(i0):.0f}" y1="{y(my + slope * (t0 - mx)):.0f}" '
                   f'x2="{xc(i1):.0f}" y2="{y(my + slope * (t1 - mx)):.0f}"/>')
    return out


def draw(result, out="docs/climate.svg", city="Porto"):
    """result: the dict returned by climate.analyse()."""
    s = result["summary"]
    H = 640
    parts = daily_panel(result["daily"], top=96, height=230) + \
        yearly_panel(result["years"], s["trend_per_decade"], top=410, height=180)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"
  aria-label="{city}: last 12 months of temperatures against the normal range, and every year since {result['years'][0]['year']} against normal with the warming trend">
<style>{STYLE}</style>
<rect class="bg" width="{W}" height="{H}" rx="8"/>
<text class="title" x="48" y="28">{city}: how today compares with the 30-year normal (data to {s['last_date']})</text>
{"".join(parts)}
</svg>
"""
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(svg)
    return out


def main():
    from db import CITY_NAME, TABLE, query
    rows = query(f"SELECT date, temp_max, temp_min FROM {TABLE} WHERE temp_max IS NOT NULL "
                 f"AND temp_min IS NOT NULL ORDER BY date")
    print("Wrote", draw(climate.analyse(rows), city=CITY_NAME))


if __name__ == "__main__":
    main()
