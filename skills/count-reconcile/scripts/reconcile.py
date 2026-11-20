#!/usr/bin/env python3
"""Line up the same event across tools against the backend, by day and by order id.

  python reconcile.py counts counts.csv --truth backend
  python reconcile.py ids orders.csv ga4-transactions.csv

counts: a CSV with date, source, event, count (one row per day, tool and event).
  The --truth source (default "backend": your database or shop orders) is 100%.
  Every other source gets a ratio per day and a verdict:
    OVER      ratio above --over (default 1.05): something counts twice
    UNDER     ratio below --under (default 0.70): blocked, consent-denied or broken tag
    ZERO      the tool shows 0 on a day the backend has events: the tag is down
    JUMP      ratio moved more than --drift points (default 15) from the day
              before: look for a release or tag change on that day
  Ratios are working rules. Ad platforms count by click or view date and their own
  windows, so compare received events (Events Manager, PostHog, GA4 event count),
  not attributed conversions.

ids: two files with an order id column (order_id, transaction_id, id or oid).
  Lists ids in the backend but missing in the tool, ids in the tool but not in the
  backend (test orders, a staging site sending to live), and ids the tool has twice.
Exit: 0 no FAIL, 1 at least one FAIL, 2 bad input.
"""
import argparse
import csv
import statistics
import sys
from collections import Counter, defaultdict

ID_COLS = ("order_id", "transaction_id", "transaction id", "order id", "oid", "id")


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        lines = [ln for ln in f if ln.strip() and not ln.startswith("#")]
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(lines)]


def counts(a):
    rows = read_csv(a.file)
    need = {"date", "source", "event", "count"}
    if not rows or not need <= set(rows[0]):
        sys.exit(f"{a.file}: needs columns date, source, event, count")
    data = defaultdict(dict)
    for r in rows:
        try:
            data[(r["event"], r["date"])][r["source"].lower()] = float(r["count"].replace(",", "") or 0)
        except ValueError:
            sys.exit(f"{a.file}: count {r['count']!r} is not a number")
    truth = a.truth.lower()
    ratios = defaultdict(list)
    for (ev, day), src in sorted(data.items()):
        t = src.get(truth)
        if not t:
            continue
        for s, n in src.items():
            if s != truth:
                ratios[(ev, s)].append((day, n / t, n, t))
    fails = 0
    print(f"truth: {truth}; OVER > {a.over:g}, UNDER < {a.under:g}, JUMP > {a.drift:g} points day to day")
    for (ev, s), series in sorted(ratios.items()):
        med = statistics.median(r for _, r, _, _ in series)
        flags = []
        prev = None
        for day, r, n, t in series:
            if prev is not None and n and abs(r - prev) * 100 > a.drift:
                flags.append(("WARN", "JUMP", day, f"{100 * prev:.0f}% the day before, {100 * r:.0f}% now"))
            prev = r if n else prev
            if n == 0:
                flags.append(("FAIL", "ZERO", day, f"0 vs {t:.0f}"))
            elif r > a.over:
                flags.append(("FAIL", "OVER", day, f"{n:.0f} vs {t:.0f} ({100 * r:.0f}%)"))
            elif r < a.under:
                flags.append(("WARN", "UNDER", day, f"{n:.0f} vs {t:.0f} ({100 * r:.0f}%)"))
        tot = sum(n for _, _, n, _ in series) / max(sum(t for *_, t in series), 1)
        state = "FAIL" if any(f[0] == "FAIL" for f in flags) else "WARN" if flags else "PASS"
        print(f"\n{state:<5} {ev} in {s}: {100 * tot:.0f}% of {truth} over {len(series)} days, median day {100 * med:.0f}%")
        for st, kind, day, detail in flags:
            print(f"      {st:<5} {kind:<6} {day}  {detail}")
        fails += state == "FAIL"
    return fails


def ids(a):
    def load(path):
        rows = read_csv(path)
        if not rows:
            sys.exit(f"{path}: empty")
        col = next((c for c in ID_COLS if c in rows[0]), None)
        if not col:
            sys.exit(f"{path}: no id column (one of {', '.join(ID_COLS)})")
        return [r[col] for r in rows if r[col] and r[col].lower() not in ("total", "(not set)")], \
            sum(1 for r in rows if r[col].lower() == "(not set)")
    truth, _ = load(a.truth_file)
    tool, not_set = load(a.tool_file)
    ts, cs = set(truth), Counter(tool)
    missing = sorted(ts - set(cs))
    extra = sorted(set(cs) - ts)
    twice = sorted(k for k, v in cs.items() if v > 1)
    print(f"{a.truth_file}: {len(ts)} orders; {a.tool_file}: {len(tool)} rows, {len(cs)} distinct ids")
    out = [("FAIL" if missing else "PASS", "MISSING_IN_TOOL", missing,
            f"{len(missing)} of {len(ts)} orders ({100 * len(missing) / max(len(ts), 1):.0f}%) never reached the tool"),
           ("FAIL" if extra else "PASS", "NOT_IN_BACKEND", extra, f"{len(extra)} id(s) the backend does not know (test orders, staging, made-up ids)"),
           ("FAIL" if twice else "PASS", "COUNTED_TWICE", twice, f"{len(twice)} id(s) recorded more than once"),
           ("FAIL" if not_set else "PASS", "NOT_SET_ID", [], f"{not_set} rows with (not set) transaction id")]
    for st, kind, items, detail in out:
        shown = ", ".join(items[:10]) + (" ..." if len(items) > 10 else "")
        print(f"{st:<5} {kind:<16} {detail}{': ' + shown if items else ''}")
    return sum(1 for o in out if o[0] == "FAIL")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("counts")
    c.add_argument("file")
    c.add_argument("--truth", default="backend")
    c.add_argument("--over", type=float, default=1.05)
    c.add_argument("--under", type=float, default=0.70)
    c.add_argument("--drift", type=float, default=15)
    i = sub.add_parser("ids")
    i.add_argument("truth_file", help="backend orders")
    i.add_argument("tool_file", help="the tool's export (GA4 transactions, PostHog, Ads conversions)")
    a = ap.parse_args()
    fails = counts(a) if a.cmd == "counts" else ids(a)
    print(f"\n{fails} FAIL")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
