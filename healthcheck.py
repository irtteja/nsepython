#!/usr/bin/env python3
"""Health check for nsepython: calls the key functions once against live NSE
data and reports which work, which are broken, and why.

    python healthcheck.py            # human-readable report
    python healthcheck.py --json     # machine-readable report
    NSE_DOMAIN=nseindia.in python healthcheck.py

Exit code is 0 if every check passed, 1 otherwise.

Each check has a `validate` function that looks at the *shape* of the result
(expected keys present, price is a sane number, table not empty), because the
common failure mode when NSE changes something is not an exception but a
silent 0 / empty result.

To cover a new function, add one line to CHECKS.
"""
import json
import sys
import time
import traceback

import nsepython as n


def _is_df(min_rows=1, cols=()):
    def v(r):
        if not hasattr(r, "shape") or len(r) < min_rows:
            return f"expected DataFrame with >= {min_rows} rows, got {type(r).__name__} len={getattr(r, '__len__', lambda: '?')()}"
        missing = [c for c in cols if c not in r.columns]
        return f"missing columns {missing}; have {list(r.columns)[:15]}" if missing else None
    return v


def _is_dict_with(*keys):
    def v(r):
        if not isinstance(r, dict) or not r:
            return f"expected non-empty dict, got {type(r).__name__}"
        missing = [k for k in keys if k not in r]
        return f"missing keys {missing}; have {list(r)[:15]}" if missing else None
    return v


def _is_price(r):
    try:
        ok = float(r) > 0
    except (TypeError, ValueError):
        ok = False
    return None if ok else f"expected a positive price, got {r!r}"


def _non_empty(r):
    return None if r else f"empty result: {r!r}"


# (label, callable, validator)
CHECKS = [
    ("nse_marketStatus",     lambda: n.nse_marketStatus(),                    _is_dict_with("marketState")),
    ("nse_holidays",         lambda: n.nse_holidays(),                        _is_dict_with()),
    ("indiavix",             lambda: n.indiavix(),                            _is_price),
    ("nse_quote RELIANCE",   lambda: n.nse_quote("RELIANCE"),                 _is_dict_with()),
    ("nse_quote_ltp RELIANCE", lambda: n.nse_quote_ltp("RELIANCE"),           _is_price),
    ("nse_quote_ltp NIFTY",  lambda: n.nse_quote_ltp("NIFTY"),                _is_price),
    ("nse_optionchain NIFTY", lambda: n.nse_optionchain_scrapper("NIFTY"),    _is_dict_with("data")),
    ("expiry_list NIFTY",    lambda: n.expiry_list("NIFTY", "list"),          _non_empty),
    ("pcr NIFTY",            lambda: n.pcr(n.nse_optionchain_scrapper("NIFTY")), _is_price),
    ("fnolist",              lambda: n.fnolist(),                             _non_empty),
    ("nse_index",            lambda: n.nse_index(),                           _is_df()),
    ("nse_get_index_list",   lambda: n.nse_get_index_list(),                  _non_empty),
    ("nse_fiidii",           lambda: n.nse_fiidii(),                          _is_df()),
    ("nse_most_active",      lambda: n.nse_most_active(),                     _is_df()),
    ("nse_preopen NIFTY",    lambda: n.nse_preopen("NIFTY"),                  _is_df()),
    ("nse_events",           lambda: n.nse_events(),                          _is_df()),
    ("nse_eq_symbols",       lambda: n.nse_eq_symbols(),                      _non_empty),
    ("nse_mcp_list_tools",   lambda: n.nse_mcp_list_tools(),                  _non_empty),
]


def run(checks=CHECKS):
    results = []
    for label, fn, validate in checks:
        t0 = time.time()
        entry = {"check": label, "status": "ok", "detail": "", "seconds": 0.0}
        try:
            problem = validate(fn())
            if problem:
                entry.update(status="BAD_DATA", detail=problem)
        except Exception as e:  # noqa: BLE001 - we want every failure reported
            entry.update(status="ERROR", detail=f"{type(e).__name__}: {e}")
            entry["trace"] = traceback.format_exc(limit=3)
        entry["seconds"] = round(time.time() - t0, 2)
        results.append(entry)
    return results


def main(argv):
    results = run()
    failed = [r for r in results if r["status"] != "ok"]
    if "--json" in argv:
        print(json.dumps({"domain": n.nse_get_domain(), "results": results}, indent=2, default=str))
    else:
        print(f"NSE domain in use: {n.nse_get_domain()}\n")
        for r in results:
            mark = "PASS" if r["status"] == "ok" else "FAIL"
            line = f"[{mark}] {r['check']:<28} {r['seconds']:>5}s"
            if r["detail"]:
                line += f"  {r['status']}: {r['detail'][:200]}"
            print(line)
        print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
