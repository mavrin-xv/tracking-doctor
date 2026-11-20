#!/usr/bin/env python3
"""Compare what really fired (a capture) with what should fire (a tracking plan).

  python audit.py capture.jsonl --plan plan.csv
  python audit.py capture.jsonl                  (automatic checks only, no plan)

Plan CSV columns: step, vendor, event, required, count
  required  params that must be present, separated by ";" (value, currency,
            transaction_id, eid, oid, order_id, or any event param name)
  count     how many times it must fire in that step: 1 (default), 0 (must not
            fire, for reload tests), or 1+ (at least once)

Checks:
  A01 MISSING          planned event did not fire (NAME if a near name fired)
  A02 DUPLICATE        fired more often than planned, or fired where count is 0
  A03 PARAM            a required param is missing or empty
  A04 ORDER_TWICE      the same order id sent twice to one vendor
  A05 NO_ORDER_ID      a purchase-type hit with no order id or event id (cannot dedupe)
  A06 VALUE            value without currency, currency without value, or value <= 0
  A07 DOUBLE_TAG       more than one tag id for one vendor (often a forgotten old tag)
  A08 PII              an email or phone number in a URL or param sent to a vendor
  A09 STEP_ERROR       a capture step failed (selector not found, timeout)
  A10 UNPLANNED        fired but not in the plan (info only)
Exit: 0 no FAIL, 1 at least one FAIL, 2 bad input.
"""
import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trackhits  # noqa: E402

PURCHASE = {"purchase", "order_completed", "completepayment", "conversion", "checkout_completed"}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?:phone|tel|mobile)[^&=]*=\+?\d[\d\s().-]{7,}", re.I)
SPECIAL = {"value": "value", "currency": "currency", "eid": "event_id", "event_id": "event_id",
           "oid": "order_id", "transaction_id": "order_id", "order_id": "order_id", "currency_code": "currency"}


def norm(name):
    return re.sub(r"[\s\-]+", "_", str(name or "").strip()).lower()


def has_param(hit, key):
    if key in SPECIAL and hit.get(SPECIAL[key]) not in (None, ""):
        return True
    for src in (hit.get("params") or {}, hit.get("raw") or {}):
        if src.get(key) not in (None, ""):
            return True
    return False


def read_plan(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            if not r.get("event"):
                continue
            cnt = r.get("count") or "1"
            if cnt not in ("0", "1", "1+") and not cnt.isdigit():
                sys.exit(f"{path}: count must be 0, 1, 1+ or a number, got {cnt!r}")
            rows.append({"step": r.get("step", ""), "vendor": r.get("vendor", "").lower(), "event": r["event"],
                         "required": [x.strip() for x in r.get("required", "").split(";") if x.strip()],
                         "count": cnt})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture")
    ap.add_argument("--plan")
    ap.add_argument("--posthog-host", action="append", default=[])
    a = ap.parse_args()
    trackhits.EXTRA_POSTHOG_HOSTS.update(h.lower() for h in a.posthog_host)

    records = trackhits.load_records(a.capture)
    hits = [h for r in records for h in trackhits.parse_request(r) if not h.get("loader")]
    rows = []

    def add(state, check, where, detail):
        rows.append((state, check, where, detail))

    for r in records:
        if r.get("kind") == "error":
            add("FAIL", "A09 STEP_ERROR", r.get("step"), r.get("error"))

    planned = set()
    if a.plan:
        for p in read_plan(a.plan):
            where = f"{p['step']} / {p['vendor']} {p['event']}"
            in_step = [h for h in hits if h["step"] == p["step"] and h["vendor"] == p["vendor"]]
            exact = [h for h in in_step if h["event"] == p["event"]]
            planned.add((p["vendor"], p["event"]))
            n, want = len(exact), p["count"]
            if want == "0":
                if n:
                    add("FAIL", "A02 DUPLICATE", where, f"fired {n}x where the plan says it must not fire")
                continue
            if not n:
                near = [h["event"] for h in in_step if norm(h["event"]) == norm(p["event"])]
                if near:
                    add("FAIL", "A01 MISSING", where, f"fired as {near[0]!r}; names are case and space sensitive")
                    planned.add((p["vendor"], near[0]))
                else:
                    add("FAIL", "A01 MISSING", where, "did not fire in this step")
                continue
            if want != "1+" and n > int(want):
                ids = sorted({str(h.get("tag_id")) for h in exact})
                why = f" (from {len(ids)} tag ids: {', '.join(ids)})" if len(ids) > 1 else ""
                add("FAIL", "A02 DUPLICATE", where, f"fired {n}x, plan says {want}{why}")
            for key in p["required"]:
                miss = sum(1 for h in exact if not has_param(h, key))
                if miss:
                    add("FAIL", "A03 PARAM", where, f"missing {key!r} in {miss} of {n} hits")
            if not any(r[1].startswith(("A01", "A02", "A03")) and r[2] == where for r in rows):
                add("PASS", "plan", where, f"fired {n}x with required params")

    seen = defaultdict(list)
    no_id = set()
    for h in hits:
        if norm(h["event"]) in PURCHASE or h["vendor"] == "gads":
            where = f"{h['step']} / {h['vendor']} {h['event']}"
            if h.get("order_id"):
                seen[(h["vendor"], h["order_id"])].append(h["step"])
            key = (h["vendor"], h["event"])
            if key in no_id:
                continue
            if h["vendor"] == "meta" and not h.get("event_id"):
                no_id.add(key)
                add("FAIL", "A05 NO_ORDER_ID", where, "no eid; Meta needs eid equal to the server event_id to dedupe with CAPI")
            elif not h.get("order_id") and not h.get("event_id"):
                no_id.add(key)
                add("FAIL", "A05 NO_ORDER_ID", where, "no order id or event id, so repeats cannot be dropped")
    for (vendor, oid), steps in seen.items():
        if len(steps) > 1:
            add("FAIL", "A04 ORDER_TWICE", f"{vendor} order {oid}", f"sent {len(steps)}x, in steps {', '.join(steps)}")

    flagged = set()
    for h in hits:
        where = f"{h['step']} / {h['vendor']} {h['event']}"
        v, c = h.get("value"), h.get("currency")
        key = (h["vendor"], h["event"], "value")
        if key not in flagged and ((v is not None and not c) or (c and v is None) or (v is not None and v <= 0)):
            flagged.add(key)
            add("FAIL", "A06 VALUE", where, f"value={v} currency={c or 'missing'}")
        text = " ".join([h.get("url") or ""] + [str(x) for x in (h.get("params") or {}).values()])
        for _ in range(3):
            text = unquote(text)
        if (EMAIL.search(text) or PHONE.search(text)) and (h["vendor"], "pii") not in flagged:
            flagged.add((h["vendor"], "pii"))
            add("FAIL", "A08 PII", where, "email or phone in what is sent; strip it from URLs and params")

    tags = defaultdict(set)
    for h in hits:
        if h.get("tag_id"):
            tags[h["vendor"]].add(h["tag_id"])
    for vendor, ids in sorted(tags.items()):
        if len(ids) > 1:
            add("WARN", "A07 DOUBLE_TAG", vendor, f"{len(ids)} tag ids: {', '.join(sorted(ids))}")

    if a.plan:
        extra = Counter((h["vendor"], h["event"]) for h in hits if (h["vendor"], h["event"]) not in planned)
        for (vendor, ev), n in sorted(extra.items(), key=lambda x: (x[0][0], str(x[0][1]))):
            add("INFO", "A10 UNPLANNED", f"{vendor} {ev}", f"{n}x")

    vendors = Counter(h["vendor"] for h in hits)
    print(f"capture: {len(hits)} hits ({', '.join(f'{v} {n}' for v, n in sorted(vendors.items()))}), "
          f"steps: {', '.join(str(s) for s in trackhits.step_order(records))}")
    if not a.plan:
        print("no --plan given: automatic checks only (A04-A09)")
    order = {"FAIL": 0, "WARN": 1, "PASS": 2, "INFO": 3}
    rows.sort(key=lambda r: order[r[0]])
    w = max([len(r[2] or "") for r in rows] + [10])
    for state, check, where, detail in rows:
        print(f"{state:<5} {check:<16} {where or '-':<{w}}  {detail}")
    fails = sum(1 for r in rows if r[0] == "FAIL")
    print(f"\n{fails} FAIL, {sum(1 for r in rows if r[0] == 'WARN')} WARN, {sum(1 for r in rows if r[0] == 'PASS')} PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
