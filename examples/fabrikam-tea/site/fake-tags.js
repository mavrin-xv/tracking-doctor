// Stand-in tags for the invented Fabrikam Tea shop. They send requests shaped like
// GA4, Meta Pixel, Google Ads and PostHog beacons, with planted mistakes, so the
// capture and audit scripts have something real to catch. capture.py answers these
// requests locally, nothing reaches a vendor. Not a copy of any vendor library.
(function () {
  var GA4 = "G-FABRIKAM1", OLD_GA4 = "G-OLDTAG001", PIXEL = "PIXEL-FABRIKAM", AW = "AW-FABRIKAM";
  var cid = "555.111";
  function consent() { return localStorage.getItem("consent"); }
  function gcs() { return consent() === "granted" ? "G111" : "G100"; }
  function q(o) {
    return Object.keys(o).map(function (k) { return encodeURIComponent(k) + "=" + encodeURIComponent(o[k]); }).join("&");
  }
  function ga4(tid, en, ep, epn, extra) {
    var p = { v: "2", tid: tid, cid: cid, en: en, dl: location.href, gcs: gcs() };
    Object.keys(extra || {}).forEach(function (k) { p[k] = extra[k]; });
    Object.keys(ep || {}).forEach(function (k) { p["ep." + k] = ep[k]; });
    Object.keys(epn || {}).forEach(function (k) { p["epn." + k] = epn[k]; });
    navigator.sendBeacon("https://region1.google-analytics.com/g/collect?" + q(p));
  }
  function meta(ev, cd, eid) {
    var p = { id: PIXEL, ev: ev, dl: location.href };
    Object.keys(cd || {}).forEach(function (k) { p["cd[" + k + "]"] = cd[k]; });
    if (eid) p.eid = eid;
    new Image().src = "https://www.facebook.com/tr/?" + q(p);
  }
  function posthog(events) {
    var batch = events.map(function (e) {
      return { event: e[0], distinct_id: "anon-555", uuid: e[2] || null,
               properties: Object.assign({ $current_url: location.href }, e[1] || {}) };
    });
    fetch("https://eu.i.posthog.com/batch/", { method: "POST", mode: "no-cors",
      body: JSON.stringify({ api_key: "phc_example_public_key", batch: batch }) });
  }
  function gads(value, currency, oid) {
    var p = { label: "purchase_label", value: value, currency_code: currency, oid: oid, gcs: gcs() };
    new Image().src = "https://www.googleadservices.com/pagead/conversion/" + AW + "/?" + q(p);
  }
  function setCookie(name, val) { document.cookie = name + "=" + val + "; path=/"; }

  window.tags = {
    pageView: function () {
      ga4(GA4, "page_view");
      ga4(OLD_GA4, "page_view");               // planted: a second, forgotten GA4 tag
      meta("PageView");                         // planted: ignores consent
      setCookie("_fbp", "fb.1.0.example");      // planted: ad cookie before consent
      if (consent() === "granted") { setCookie("_ga", "GA1.1." + cid); posthog([["$pageview"]]); }
    },
    grant: function () {
      localStorage.setItem("consent", "granted");
      setCookie("_ga", "GA1.1." + cid);
      ga4(GA4, "user_engagement");
      posthog([["$pageview"]]);
    },
    deny: function () { localStorage.setItem("consent", "denied"); },
    addToCart: function () {
      ga4(GA4, "add_to_cart", { currency: "EUR" }, { value: 12.5 });
      meta("AddToCart", { value: "12.5", currency: "EUR" });
      if (consent() === "granted") posthog([["Add To Cart", { value: 12.5 }]]);   // planted: name differs from the plan
    },
    purchase: function () {
      var order = new URLSearchParams(location.search).get("order");
      ga4(GA4, "purchase", { transaction_id: order }, { value: 38.5 });           // planted: no currency
      meta("Purchase", { value: "38.50", currency: "EUR" });                      // planted: no eid, cannot dedupe
      gads("38.50", "EUR", order);
      if (consent() === "granted") posthog([["order_completed", { order_id: order, value: 38.5, currency: "EUR" }, "evt-" + order]]);
    }
  };
})();
