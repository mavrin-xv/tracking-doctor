#!/usr/bin/env python3
"""Find where visits lose their source: stripped click ids, payment gateway and
self referrals, UTM values that split or fall into Unassigned.

  python leaks.py --capture capture.jsonl
  python leaks.py --sources ga4-sources.csv --domain fabrikam-tea.example
  python leaks.py --capture capture.jsonl --sources ga4-sources.csv --domain shop.example

--capture   a capture from event-capture whose first page URL carries a click id or
            utm_* (use a test URL like ?gclid=TEST&utm_source=test)
--sources   a GA4 export with "Session source / medium" (or Source and Medium
            columns) and Sessions; extra columns are ignored

Checks:
  L01 CLICK_ID_LOST    the landing URL had gclid/gbraid/wbraid/fbclid/msclkid/ttclid/li_fat_id,
                       but no tracking hit carried it (a redirect or router dropped it)
  L02 UTM_LOST         same for utm_* parameters
  L03 PAYMENT_REFERRAL a payment gateway shows up as a referral source
  L04 SELF_REFERRAL    your own domain shows up as a referral source
  L05 CASE_SPLIT       one source / medium split into rows that differ by case or spaces
  L06 UNKNOWN_MEDIUM   a medium no default channel rule matches (lands in Unassigned)
  L07 NOT_SET          share of (not set) and Unassigned sessions (WARN above --not-set-max)
Exit: 0 no FAIL, 1 at least one FAIL, 2 bad input.
"""
import argparse
import csv
import io
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trackhits  # noqa: E402

CLICK_IDS = ["gclid", "gbraid", "wbraid", "dclid", "fbclid", "msclkid", "ttclid", "li_fat_id", "twclid"]
PAYMENT = ["paypal.com", "stripe.com", "klarna.com", "adyen.com", "mollie.com", "checkout.com",
           "pay.google.com", "shop.app", "braintreegateway.com", "worldpay.com", "sagepay.com",
           "squareup.com", "afterpay.com", "clearpay.co.uk", "affirm.com", "razorpay.com", "paddle.com"]
# Simplified from GA4's default channel group rules. Check the current list in GA4 help.
MEDIUM_RULES = [
    ("Direct / none", r"^\(?(none|not set)\)?$"),
    ("Organic", r"^organic$"),
    ("Referral", r"^(referral|app|link)$"),
    ("Paid", r"^(.*cp.*|ppc|retargeting|paid.*)$"),
    ("Email", r"^(email|e-mail|e_mail|e mail)$"),
    ("Affiliates", r"^affiliate$"),
    ("Display", r"^(display|banner|expandable|interstitial|cpm)$"),
    ("Social", r"^(social|social-network|social-media|sm|social network|social media)$"),
    ("Video", r"^(.*video.*)$"),
    ("Audio", r"^audio$"),
    ("SMS", r"^sms$"),
    ("Push", r"^(.*push$|.*mobile.*|.*notification.*)$"),
    ("Cross-network", r"^cross-network$"),
]


def channel_for(medium):
    m = medium.strip().lower()
    for name, rx in MEDIUM_RULES:
        if re.match(rx, m):
            return name
    return None


def num(x):
    x = (x or "").replace(",", "").replace(" ", "").strip()
    try:
        return float(x)
    except ValueError:
        return 0.0


def read_sources(path):
    raw = Path(path).read_bytes()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    delim = "\t" if lines and lines[0].count("\t") > lines[0].count(",") else ","
    rows = list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delim))
    out = []
    for r in rows:
        k = {(a or "").strip().lower(): (b or "").strip() for a, b in r.items()}
        sm = next((v for kk, v in k.items() if "source / medium" in kk or "source/medium" in kk), None)
        if sm is not None:
            src, _, med = sm.partition("/")
        else:
            src = next((v for kk, v in k.items() if kk.endswith("source")), "")
            med = next((v for kk, v in k.items() if kk.endswith("medium")), "")
        sess = next((v for kk, v in k.items() if "sessions" in kk), "0")
        if src.strip().lower() in ("total", "grand total"):
            continue
        out.append({"source": src.strip(), "medium": med.strip(), "sessions": num(sess)})
    if not out:
        sys.exit(f"{path}: no rows with a source / medium column")
    return out


def check_capture(path, add):
    recs = trackhits.load_records(path)
    navs = [r for r in recs if r.get("kind") == "nav"]
    if not navs:
        add("WARN", "L01 CLICK_ID_LOST", path, "no navigations in the capture, nothing to check")
        return
    landing = dict(parse_qsl(urlsplit(navs[0]["url"]).query))
    want = {k: v for k, v in landing.items() if k in CLICK_IDS or k.startswith("utm_")}
    if not want:
        add("WARN", "L01 CLICK_ID_LOST", "landing", "the first URL has no click id or utm_*; start the capture with a test URL that has them")
        return
    hits = [h for r in recs for h in trackhits.parse_request(r) if not h.get("loader")]
    carried = " ".join(unquote(unquote(h.get("url") or "")) for h in hits)
    hops = [urlsplit(n["url"]).path or "/" for n in navs]
    path_txt = " > ".join(dict.fromkeys(hops))
    for k, v in want.items():
        if f"{k}={v}" in carried:
            add("PASS", "carried", k, "reaches the tracking hits")
        else:
            check = "L01 CLICK_ID_LOST" if k in CLICK_IDS else "L02 UTM_LOST"
            add("FAIL", check, k, f"in the landing URL, in no tracking hit; page path: {path_txt}")
    for h in hits:
        dr = (h.get("raw") or {}).get("dr") or ""
        host = (urlsplit(dr).hostname or "").lower()
        if any(host == p or host.endswith("." + p) for p in PAYMENT):
            add("WARN", "L03 PAYMENT_REFERRAL", f"{h['step']} / {h['vendor']} {h['event']}",
                f"referrer is {host}; add it to unwanted referrals")
            break


def check_sources(path, domain, not_set_max, add):
    rows = read_sources(path)
    total = sum(r["sessions"] for r in rows) or 1
    for r in rows:
        src, med = r["source"].lower(), r["medium"].lower()
        label = f"{r['source']} / {r['medium']}"
        share = f"{r['sessions']:.0f} sessions ({100 * r['sessions'] / total:.1f}%)"
        if med == "referral" and any(src == p or src.endswith("." + p) for p in PAYMENT):
            add("FAIL", "L03 PAYMENT_REFERRAL", label, f"{share}; buyers returning from payment lose their real source")
        if domain and med == "referral" and (src == domain or src.endswith("." + domain)):
            add("FAIL", "L04 SELF_REFERRAL", label, f"{share}; a page without the tag, a cross-domain hop or a subdomain")
        if channel_for(r["medium"]) is None:
            add("FAIL", "L06 UNKNOWN_MEDIUM", label, f"{share}; no default channel rule matches, it lands in Unassigned")
    groups = defaultdict(list)
    for r in rows:
        groups[(re.sub(r"\s+", "", r["source"].lower()), re.sub(r"\s+", "", r["medium"].lower()))].append(r)
    for (s, m), g in groups.items():
        if len(g) > 1:
            names = ", ".join(f"{x['source']} / {x['medium']}" for x in g)
            add("FAIL", "L05 CASE_SPLIT", f"{s} / {m}", f"{len(g)} rows: {names}; lowercase UTM values at the source")
    ns = sum(r["sessions"] for r in rows if "(not set)" in (r["source"] + r["medium"]).lower()
             or "unassigned" in (r["source"] + r["medium"]).lower())
    pct = 100 * ns / total
    add("WARN" if pct > not_set_max else "PASS", "L07 NOT_SET", "(not set) and Unassigned",
        f"{pct:.1f}% of {total:.0f} sessions (limit {not_set_max:g}%)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture")
    ap.add_argument("--sources")
    ap.add_argument("--domain", help="your site domain, for the self-referral check")
    ap.add_argument("--not-set-max", type=float, default=5.0, help="WARN above this %% (working rule, default 5)")
    a = ap.parse_args()
    if not (a.capture or a.sources):
        ap.print_usage()
        sys.exit(2)
    rows = []

    def add(state, check, where, detail):
        rows.append((state, check, where, detail))

    if a.capture:
        check_capture(a.capture, add)
    if a.sources:
        check_sources(a.sources, re.sub(r"^www\.", "", (a.domain or "").lower()), a.not_set_max, add)
    order = {"FAIL": 0, "WARN": 1, "PASS": 2}
    rows.sort(key=lambda r: order[r[0]])
    w = max(len(r[2]) for r in rows)
    for state, check, where, detail in rows:
        print(f"{state:<5} {check:<20} {where:<{w}}  {detail}")
    fails = sum(1 for r in rows if r[0] == "FAIL")
    print(f"\n{fails} FAIL, {sum(1 for r in rows if r[0] == 'WARN')} WARN")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
