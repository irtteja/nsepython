#!/usr/bin/env python3
"""Live smoke test of EVERY public nsepython function, against real NSE data.

Each function is called once with realistic arguments and its result is
checked for shape (non-empty, sane price, etc.).  Functions are grouped by
the network route they use, so you can run the groups that work where you are:

    offline       pure computation, no network
    mcp           NSE's official MCP servers (mcp.nseindia.in), plain HTTPS
    niftyindices  niftyindices.com historical index data
    nse           nseindia.com website APIs (the scraping transport)

    python smoketest.py                    # all groups
    python smoketest.py --groups mcp,offline
    python smoketest.py --json             # machine-readable
    python smoketest.py --only pcr,indiavix

Exit code 0 if nothing FAILED (skips don't count), 1 otherwise.
healthcheck.py is the quick 18-check version; this is the exhaustive one.
"""
import datetime as dt
import json
import sys
import time
import traceback

import nsepython as n

TODAY = dt.date.today()


def _last_weekday(before=TODAY, back=1):
    d = before
    while back:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            back -= 1
    return d


D1 = _last_weekday()                    # last weekday (may be a holiday)
D_FROM = TODAY - dt.timedelta(days=30)
DMY = lambda d: d.strftime("%d-%m-%Y")  # noqa: E731  21-10-2026
DBY = lambda d: d.strftime("%d-%b-%Y")  # noqa: E731  21-Oct-2026


# ---- validators: return None if OK, else a short reason -------------------
def nonempty(r):
    if r is None:
        return "returned None"
    try:
        return None if len(r) > 0 else f"empty {type(r).__name__}"
    except TypeError:
        return None  # scalars / bools are fine


def price(r):
    try:
        return None if float(r) > 0 else f"non-positive price {r!r}"
    except (TypeError, ValueError):
        return f"not a number: {r!r}"


def boolean(r):
    return None if isinstance(r, bool) else f"expected bool, got {type(r).__name__}"


def anything(r):
    return None


# ---- shared fetches reused by dependent checks ----------------------------
_cache = {}


def chain():
    if "chain" not in _cache:
        _cache["chain"] = n.nse_optionchain_scrapper("NIFTY")
    return _cache["chain"]


def nifty_expiry():
    if "exp" not in _cache:
        _cache["exp"] = n.expiry_list("NIFTY", "list")[0]
    return _cache["exp"]


def atm_strike():
    rows = [x for x in chain()["data"] if x.get("CE") and x.get("PE")]
    spot = (rows[0]["CE"] or {}).get("underlyingValue") or rows[len(rows) // 2]["strikePrice"]
    return min(rows, key=lambda x: abs(float(x["strikePrice"]) - float(spot)))["strikePrice"]


# (name, group, call, validator)
CHECKS = [
    # ---- offline
    ("black_scholes_dexter", "offline", lambda: n.black_scholes_dexter(24000, 24100, 7, 15), nonempty),
    ("nsesymbolpurify",      "offline", lambda: n.nsesymbolpurify("M&M") == "M%26M" or "bad encoding", lambda r: None if r is True else r),
    ("running_status",       "offline", lambda: n.running_status(), boolean),
    ("nse_get_domain",       "offline", lambda: n.nse_get_domain(), nonempty),
    ("nse_set_domain",       "offline", lambda: n.nse_set_domain(n.nse_get_domain()), nonempty),

    # ---- NSE official MCP: bhavcopy server
    ("nse_mcp_list_tools",              "mcp", lambda: n.nse_mcp_list_tools("bhavcopy"), nonempty),
    ("nse_mcp_call",                    "mcp", lambda: n.nse_mcp_call("bhavcopy", "search_symbols", query="RELIANCE"), nonempty),
    ("nse_mcp_get_top_by_volume",       "mcp", lambda: n.nse_mcp_get_top_by_volume(), nonempty),
    ("nse_mcp_get_top_movers",          "mcp", lambda: n.nse_mcp_get_top_movers(), nonempty),
    ("nse_mcp_nse_lookup_symbol",       "mcp", lambda: n.nse_mcp_nse_lookup_symbol("Reliance"), nonempty),
    ("nse_mcp_get_market_mood",         "mcp", lambda: n.nse_mcp_get_market_mood(), nonempty),
    ("nse_mcp_get_index_valuation",     "mcp", lambda: n.nse_mcp_get_index_valuation("Nifty 50", 6), nonempty),
    ("nse_mcp_get_market_breadth",      "mcp", lambda: n.nse_mcp_get_market_breadth(), nonempty),
    ("nse_mcp_get_corporate_actions",   "mcp", lambda: n.nse_mcp_get_corporate_actions("RELIANCE"), anything),
    ("nse_mcp_compare_indices",         "mcp", lambda: n.nse_mcp_compare_indices(["Nifty 50", "Nifty Bank"]), nonempty),
    ("nse_mcp_get_index_movers",        "mcp", lambda: n.nse_mcp_get_index_movers(), nonempty),
    ("nse_mcp_get_ltp_by_date",         "mcp", lambda: n.nse_mcp_get_ltp_by_date("RELIANCE"), nonempty),
    ("nse_mcp_get_bulk_quote",          "mcp", lambda: n.nse_mcp_get_bulk_quote(["RELIANCE", "TCS"]), nonempty),
    ("nse_mcp_get_volume_analysis",     "mcp", lambda: n.nse_mcp_get_volume_analysis("RELIANCE"), nonempty),
    ("nse_mcp_get_stock_history",       "mcp", lambda: n.nse_mcp_get_stock_history("RELIANCE", 1), nonempty),
    ("nse_mcp_get_index_snapshot",      "mcp", lambda: n.nse_mcp_get_index_snapshot(), nonempty),
    ("nse_mcp_search_symbols",          "mcp", lambda: n.nse_mcp_search_symbols("TATA"), nonempty),
    ("nse_mcp_get_stock_vs_index",      "mcp", lambda: n.nse_mcp_get_stock_vs_index("RELIANCE", months=3), nonempty),
    ("nse_mcp_compare_stocks",          "mcp", lambda: n.nse_mcp_compare_stocks(["RELIANCE", "TCS"], 3), nonempty),
    ("nse_mcp_get_index_history",       "mcp", lambda: n.nse_mcp_get_index_history("Nifty 50", 1), nonempty),
    ("nse_mcp_moving_average",          "mcp", lambda: n.nse_mcp_moving_average("RELIANCE"), nonempty),
    ("nse_mcp_get_52_week_high_low",    "mcp", lambda: n.nse_mcp_get_52_week_high_low("RELIANCE"), nonempty),
    ("nse_mcp_get_index_performance",   "mcp", lambda: n.nse_mcp_get_index_performance("Nifty 50"), nonempty),
    # ---- NSE official MCP: live cash-market server
    ("nse_mcp_cm_get_live_market_data",      "mcp", lambda: n.nse_mcp_cm_get_live_market_data(), nonempty),
    ("nse_mcp_cm_get_equity_stocks",         "mcp", lambda: n.nse_mcp_cm_get_equity_stocks(5), nonempty),
    ("nse_mcp_nse_get_losers",               "mcp", lambda: n.nse_mcp_nse_get_losers(5), nonempty),
    ("nse_mcp_cm_get_call_auction_stocks",   "mcp", lambda: n.nse_mcp_cm_get_call_auction_stocks(5), anything),
    ("nse_mcp_cm_get_bond_stocks",           "mcp", lambda: n.nse_mcp_cm_get_bond_stocks(5), nonempty),
    ("nse_mcp_cm_get_live_gainers",          "mcp", lambda: n.nse_mcp_cm_get_live_gainers(), nonempty),
    ("nse_mcp_nse_get_gainers",              "mcp", lambda: n.nse_mcp_nse_get_gainers(5), nonempty),
    ("nse_mcp_cm_get_data_status",           "mcp", lambda: n.nse_mcp_cm_get_data_status(), nonempty),
    ("nse_mcp_cm_get_stock_quote",           "mcp", lambda: n.nse_mcp_cm_get_stock_quote("RELIANCE"), nonempty),
    ("nse_mcp_cm_get_index_quote",           "mcp", lambda: n.nse_mcp_cm_get_index_quote("NIFTY 50"), nonempty),
    ("nse_mcp_cm_get_sme_stocks",            "mcp", lambda: n.nse_mcp_cm_get_sme_stocks(5), nonempty),
    ("nse_mcp_cm_get_live_losers",           "mcp", lambda: n.nse_mcp_cm_get_live_losers(), nonempty),
    ("nse_mcp_cm_get_live_indices",          "mcp", lambda: n.nse_mcp_cm_get_live_indices("broad"), nonempty),
    ("nse_mcp_nse_get_market_movers",        "mcp", lambda: n.nse_mcp_nse_get_market_movers(limit=5), nonempty),
    ("nse_mcp_cm_get_allstocks_status",      "mcp", lambda: n.nse_mcp_cm_get_allstocks_status(), nonempty),

    # ---- niftyindices.com
    ("index_history",        "niftyindices", lambda: n.index_history("NIFTY 50", DBY(D_FROM), DBY(TODAY)), nonempty),
    ("index_pe_pb_div",      "niftyindices", lambda: n.index_pe_pb_div("NIFTY 50", DBY(D_FROM), DBY(TODAY)), nonempty),
    ("index_total_returns",  "niftyindices", lambda: n.index_total_returns("NIFTY 50", DBY(D_FROM), DBY(TODAY)), nonempty),

    # ---- nseindia.com website APIs: market status / reference
    ("nsefetch",             "nse", lambda: n.nsefetch("https://www.nseindia.com/api/marketStatus"), nonempty),
    ("nse_marketStatus",     "nse", lambda: n.nse_marketStatus(), nonempty),
    ("is_market_open",       "nse", lambda: n.is_market_open("CM"), boolean),
    ("nse_holidays",         "nse", lambda: n.nse_holidays(), nonempty),
    ("holiday_master",       "nse", lambda: n.holiday_master(), nonempty),
    ("nse_circular",         "nse", lambda: n.nse_circular(), nonempty),
    ("nse_events",           "nse", lambda: n.nse_events(), nonempty),
    ("nse_results",          "nse", lambda: n.nse_results(), nonempty),
    ("nse_past_results",     "nse", lambda: n.nse_past_results("RELIANCE"), nonempty),
    ("nse_eq_symbols",       "nse", lambda: n.nse_eq_symbols(), nonempty),
    ("fnolist",              "nse", lambda: n.fnolist(), nonempty),
    ("nse_get_fno_lot_sizes", "nse", lambda: n.nse_get_fno_lot_sizes(), nonempty),
    ("whoistheboss",         "nse", lambda: n.whoistheboss(), nonempty),
    # quotes
    ("nse_quote",            "nse", lambda: n.nse_quote("RELIANCE"), nonempty),
    ("nse_quote trade_info", "nse", lambda: n.nse_quote("RELIANCE", "trade_info"), nonempty),
    ("nse_quote_ltp eq",     "nse", lambda: n.nse_quote_ltp("RELIANCE"), price),
    ("nse_quote_ltp index",  "nse", lambda: n.nse_quote_ltp("NIFTY"), price),
    ("nse_quote_ltp option", "nse", lambda: n.nse_quote_ltp("NIFTY", "latest", "CE", atm_strike()), price),
    ("nse_quote_ltp future", "nse", lambda: n.nse_quote_ltp("NIFTY", "latest", "Fut"), price),
    ("nse_quote_meta",       "nse", lambda: n.nse_quote_meta("NIFTY", "latest", "Fut"), nonempty),
    ("nse_quote_derivatives", "nse", lambda: n.nse_quote_derivatives("NIFTY"), nonempty),
    ("nse_eq",               "nse", lambda: n.nse_eq("RELIANCE"), nonempty),
    ("quote_equity",         "nse", lambda: n.quote_equity("RELIANCE"), nonempty),
    ("nse_fno",              "nse", lambda: n.nse_fno("RELIANCE"), nonempty),
    ("quote_derivative",     "nse", lambda: n.quote_derivative("RELIANCE"), nonempty),
    ("nsetools_get_quote",   "nse", lambda: n.nsetools_get_quote("RELIANCE"), nonempty),
    ("nse_custom_function_secfno", "nse", lambda: n.nse_custom_function_secfno("RELIANCE"), price),
    # options / futures
    ("nse_optionchain_scrapper", "nse", lambda: chain(), lambda r: None if r.get("data") else "no data"),
    ("option_chain",         "nse", lambda: n.option_chain("NIFTY"), nonempty),
    ("expiry_list",          "nse", lambda: n.expiry_list("NIFTY", "list"), nonempty),
    ("pcr",                  "nse", lambda: n.pcr(chain()), price),
    ("nse_optionchain_ltp",  "nse", lambda: n.nse_optionchain_ltp(chain(), atm_strike(), "CE"), price),
    ("nse_expirydetails",    "nse", lambda: n.nse_expirydetails(chain(), 0, "NIFTY"), nonempty),
    ("nse_expirydetails_by_symbol", "nse", lambda: n.nse_expirydetails_by_symbol("NIFTY"), nonempty),
    ("oi_chain_builder",     "nse", lambda: n.oi_chain_builder("NIFTY"), nonempty),
    # indices
    ("nse_index",            "nse", lambda: n.nse_index(), nonempty),
    ("nse_get_index_list",   "nse", lambda: n.nse_get_index_list(), nonempty),
    ("nse_get_index_quote",  "nse", lambda: n.nse_get_index_quote("NIFTY 50"), nonempty),
    ("index_info",           "nse", lambda: n.index_info("NIFTY 50"), nonempty),
    ("indiavix",             "nse", lambda: n.indiavix(), price),
    # movers / activity
    ("nse_get_top_gainers",  "nse", lambda: n.nse_get_top_gainers(), nonempty),
    ("nse_get_top_losers",   "nse", lambda: n.nse_get_top_losers(), nonempty),
    ("nse_get_advances_declines", "nse", lambda: n.nse_get_advances_declines(), nonempty),
    ("nse_most_active",      "nse", lambda: n.nse_most_active(), nonempty),
    ("nse_price_band_hitters", "nse", lambda: n.nse_price_band_hitters(), nonempty),
    ("nse_preopen",          "nse", lambda: n.nse_preopen("NIFTY"), nonempty),
    ("nse_preopen_movers",   "nse", lambda: n.nse_preopen_movers(), anything),
    # deals / flows
    ("nse_fiidii",           "nse", lambda: n.nse_fiidii(), nonempty),
    ("nse_blockdeal",        "nse", lambda: n.nse_blockdeal(), anything),
    ("get_bulkdeals",        "nse", lambda: n.get_bulkdeals(), anything),
    ("get_blockdeals",       "nse", lambda: n.get_blockdeals(), anything),
    ("nse_largedeals",       "nse", lambda: n.nse_largedeals(), anything),
    ("nse_largedeals_historical", "nse", lambda: n.nse_largedeals_historical(DMY(D_FROM), DMY(TODAY)), anything),
    ("get_fao_participant_oi", "nse", lambda: n.get_fao_participant_oi(DMY(D1)), nonempty),
    # history / archives
    ("equity_history",       "nse", lambda: n.equity_history("RELIANCE", "EQ", DMY(D_FROM), DMY(TODAY)), nonempty),
    ("equity_history_virgin", "nse", lambda: n.equity_history_virgin("RELIANCE", "EQ", DMY(D_FROM), DMY(TODAY)), nonempty),
    ("derivative_history",   "nse", lambda: n.derivative_history("NIFTY", DMY(D_FROM), DMY(TODAY), "futidx", nifty_expiry()), anything),
    ("derivative_history_virgin", "nse", lambda: n.derivative_history_virgin("NIFTY", DMY(D_FROM), DMY(TODAY), "FUTIDX", nifty_expiry()), anything),
    ("expiry_history",       "nse", lambda: n.expiry_history("NIFTY", DMY(D_FROM), DMY(TODAY)), nonempty),
    ("get_bhavcopy",         "nse", lambda: n.get_bhavcopy(DMY(D1)), nonempty),
    ("security_wise_archive", "nse", lambda: n.security_wise_archive(DMY(D_FROM), DMY(TODAY), "RELIANCE"), nonempty),
    # corporate
    ("dividend_timeline",    "nse", lambda: n.dividend_timeline("ITC"), anything),
    ("share_holding",        "nse", lambda: n.share_holding("RELIANCE"), nonempty),
    ("nse_annual_reports",   "nse", lambda: n.nse_annual_reports("RELIANCE"), nonempty),
    # analytics
    ("get_beta_df_maker",    "nse", lambda: n.get_beta_df_maker("RELIANCE", 60), nonempty),
    ("get_beta",             "nse", lambda: n.get_beta("RELIANCE", 60), price),
    ("getbeta",              "nse", lambda: n.getbeta("RELIANCE", 60), price),
]

# Functions deliberately not called, with the reason.
SKIPPED = {
    "nse_harvest_playwright_cookies": "optional; launches a real browser (needs Playwright installed)",
}


def run(groups=None, only=None):
    results = []
    for name, group, call, validate in CHECKS:
        if groups and group not in groups:
            continue
        if only and name.split()[0] not in only and name not in only:
            continue
        t0 = time.time()
        res = {"name": name, "group": group, "status": "PASS", "detail": ""}
        try:
            problem = validate(call())
            if problem:
                res.update(status="BAD_DATA", detail=str(problem))
        except Exception as e:  # noqa: BLE001
            res.update(status="ERROR", detail=f"{type(e).__name__}: {e}")
            res["trace"] = traceback.format_exc(limit=4)
        res["seconds"] = round(time.time() - t0, 2)
        results.append(res)
    return results


def coverage():
    """Public functions in the library that no check calls (should be none)."""
    import inspect
    called = {c[0].split()[0] for c in CHECKS} | set(SKIPPED)
    public = {k for k, v in inspect.getmembers(n.rahu, inspect.isfunction)
              if not k.startswith("_") and v.__module__ == "nsepython.rahu"}
    return sorted(public - called)


def main(argv):
    def arg(flag):
        return next((a.split("=", 1)[1] for a in argv if a.startswith(flag + "=")), None) or \
               (argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else None)

    groups = set(arg("--groups").split(",")) if arg("--groups") else None
    only = set(arg("--only").split(",")) if arg("--only") else None
    results = run(groups, only)
    missing = coverage()
    failed = [r for r in results if r["status"] != "PASS"]

    if "--json" in argv:
        print(json.dumps({"domain": n.nse_get_domain(), "results": results,
                          "skipped": SKIPPED, "uncovered": missing}, indent=2, default=str))
    else:
        print(f"nsepython smoke test  |  NSE domain: {n.nse_get_domain()}  |  {dt.datetime.now():%Y-%m-%d %H:%M}\n")
        for g in ("offline", "mcp", "niftyindices", "nse"):
            rows = [r for r in results if r["group"] == g]
            if not rows:
                continue
            ok = sum(r["status"] == "PASS" for r in rows)
            print(f"== {g}: {ok}/{len(rows)} passed")
            for r in rows:
                if r["status"] != "PASS":
                    print(f"   [FAIL] {r['name']:<34} {r['status']}: {r['detail'][:160]}")
        for k, why in SKIPPED.items():
            print(f"   [SKIP] {k}: {why}")
        if missing:
            print(f"\nNOT COVERED by any check: {', '.join(missing)}")
        print(f"\nTOTAL: {len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
