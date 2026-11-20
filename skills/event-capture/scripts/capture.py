#!/usr/bin/env python3
"""Record which tracking requests a page really sends, step by step.

Opens the page in headless Chromium, runs your steps (goto, click, fill, wait,
reload), and writes every analytics or ad request plus navigations and cookie
names to a JSON lines file that the other tracking-doctor scripts read.

By default the event beacons are answered locally with an empty 204, so the test
does not add fake visits or purchases to your real analytics. Tag libraries
(gtm.js, gtag/js, fbevents.js) still load so the tags run as they do for users.
Pass --live to let beacons reach the vendors.

  python capture.py https://shop.example/ --out capture.jsonl
  python capture.py --steps steps.json --out capture.jsonl
  python capture.py --from-har devtools-export.har --out capture.jsonl   (no browser needed)

Steps file: a JSON list, run in order. Each item has "step" (a name) and one action:
  {"step": "landing", "goto": "https://shop.example/?utm_source=test"}
  {"step": "consent-accept", "click": "#accept-all"}
  {"step": "name", "fill": ["#name", "Test Buyer"]}
  {"step": "pause", "wait": 2}
  {"step": "thanks-reload", "reload": true}
A relative "goto" is resolved against --serve (a local folder served on 127.0.0.1,
for testing a build before deploy) or, without it, against the steps file folder.

Needs: pip install playwright && python -m playwright install chromium
(--from-har needs nothing beyond Python.)
Exit: 0 written, 2 setup or input problem.
"""
import argparse
import base64
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trackhits  # noqa: E402


def body_fields(buf):
    if not buf:
        return None, "utf8"
    try:
        return buf.decode("utf-8"), "utf8"
    except UnicodeDecodeError:
        return base64.b64encode(buf).decode("ascii"), "base64"


def from_har(har_path, out):
    try:
        har = json.loads(Path(har_path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        print(f"{har_path}: cannot read HAR ({e})", file=sys.stderr)
        sys.exit(2)
    entries = har.get("log", {}).get("entries", [])
    t0 = None
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for e in entries:
            req = e.get("request", {})
            url = req.get("url", "")
            started = e.get("startedDateTime", "")
            t0 = t0 or started
            mime = e.get("response", {}).get("content", {}).get("mimeType", "")
            if e.get("_resourceType") == "document" or (req.get("method") == "GET" and mime.startswith("text/html")):
                f.write(json.dumps({"kind": "nav", "step": e.get("pageref") or "har", "t": n, "url": url, "from": None}) + "\n")
            vendor, _ = trackhits.classify(url)
            if not vendor:
                continue
            post = req.get("postData", {}) or {}
            f.write(json.dumps({"kind": "request", "step": e.get("pageref") or "har", "t": n, "page": None,
                                "method": req.get("method"), "url": url, "body": post.get("text"),
                                "body_encoding": "utf8"}) + "\n")
            n += 1
    print(f"wrote {n} tracking requests from {len(entries)} HAR entries to {out}")


def run_browser(a, steps):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright is not installed. Run: pip install playwright && python -m playwright install chromium\n"
                 "Or export a HAR from browser DevTools and use --from-har.")
    out = open(a.out, "w", encoding="utf-8")
    t0 = time.time()
    state = {"step": steps[0]["step"] if steps else "start", "n": 0, "last_nav": None}

    def write(rec):
        rec["t"] = round(time.time() - t0, 3)
        rec.setdefault("step", state["step"])
        out.write(json.dumps(rec) + "\n")

    def on_request(req):
        vendor, kind = trackhits.classify(req.url)
        if req.is_navigation_request() and req.frame == page.main_frame:
            prev = req.redirected_from.url if req.redirected_from else None
            write({"kind": "nav", "url": req.url, "from": prev})
            state["last_nav"] = req.url
        if not vendor:
            return
        body, enc = body_fields(req.post_data_buffer)
        write({"kind": "request", "page": page.url, "method": req.method, "url": req.url,
               "body": body, "body_encoding": enc})
        state["n"] += 1

    def on_frame(frame):
        if frame == page.main_frame and frame.url != state["last_nav"]:
            state["last_nav"] = frame.url
            write({"kind": "nav", "url": frame.url, "from": "client-side"})

    def beacon_route(route):
        vendor, kind = trackhits.classify(route.request.url)
        if vendor and kind == "hit" and not a.live:
            return route.fulfill(status=204, body="")
        return route.continue_()

    def snapshot_cookies():
        cookies = [{"name": c["name"], "domain": c["domain"]} for c in ctx.cookies()]
        write({"kind": "cookies", "cookies": cookies})

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not a.headed)
        ctx = browser.new_context(user_agent=a.user_agent) if a.user_agent else browser.new_context()
        page = ctx.new_page()
        page.route("**/*", beacon_route)
        page.on("request", on_request)
        page.on("framenavigated", on_frame)
        for st in steps:
            state["step"] = st["step"]
            try:
                if "goto" in st:
                    page.goto(st["goto"], wait_until="load", timeout=a.timeout * 1000)
                elif "click" in st:
                    page.click(st["click"], timeout=a.timeout * 1000)
                elif "fill" in st:
                    page.fill(st["fill"][0], st["fill"][1], timeout=a.timeout * 1000)
                elif "reload" in st:
                    page.reload(wait_until="load", timeout=a.timeout * 1000)
                elif "wait" in st:
                    pass
                else:
                    print(f"step {st['step']}: no action, skipped", file=sys.stderr)
                page.wait_for_timeout(int(float(st.get("wait", a.wait)) * 1000))
            except Exception as e:  # keep going: a broken step is itself a finding
                write({"kind": "error", "error": f"{type(e).__name__}: {str(e).splitlines()[0]}"})
                print(f"step {st['step']}: {type(e).__name__}", file=sys.stderr)
            snapshot_cookies()
        browser.close()
    out.close()
    print(f"wrote {state['n']} tracking requests over {len(steps)} steps to {a.out}"
          f" ({'live' if a.live else 'beacons answered locally, nothing sent to vendors'})")


def serve(folder):
    import functools
    import http.server
    import threading
    handler = functools.partial(QuietHandler, directory=str(Path(folder).resolve()))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_address[1]}/"


try:
    import http.server as _hs

    class QuietHandler(_hs.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
except ImportError:  # pragma: no cover
    QuietHandler = None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="pages to open, one step each (or use --steps)")
    ap.add_argument("--steps", help="JSON steps file")
    ap.add_argument("--out", default="capture.jsonl")
    ap.add_argument("--wait", type=float, default=3, help="seconds to wait after each step (default 3)")
    ap.add_argument("--timeout", type=float, default=30)
    ap.add_argument("--live", action="store_true", help="let beacons reach the vendors")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--user-agent")
    ap.add_argument("--posthog-host", action="append", default=[],
                    help="your PostHog reverse proxy host, read as PostHog (repeatable)")
    ap.add_argument("--serve", help="serve this folder on 127.0.0.1 and resolve relative gotos against it")
    ap.add_argument("--from-har", help="convert a DevTools HAR export instead of opening a browser")
    a = ap.parse_args()
    trackhits.EXTRA_POSTHOG_HOSTS.update(h.lower() for h in a.posthog_host)

    if a.from_har:
        return from_har(a.from_har, a.out)
    base = serve(a.serve) if a.serve else None
    if a.steps:
        sp = Path(a.steps)
        steps = json.loads(sp.read_text(encoding="utf-8"))
        for st in steps:
            g = st.get("goto")
            if g and "://" not in g:
                if base:
                    st["goto"] = base + g.lstrip("/")
                else:
                    path, _, query = g.partition("?")
                    st["goto"] = (sp.parent / path).resolve().as_uri() + ("?" + query if query else "")
    elif a.urls:
        steps = [{"step": f"page{i + 1}", "goto": u} for i, u in enumerate(a.urls)]
    else:
        ap.print_usage()
        sys.exit(2)
    run_browser(a, steps)


if __name__ == "__main__":
    main()
