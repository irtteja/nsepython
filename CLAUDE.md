# nsepython — instructions for Claude

This library scrapes undocumented NSE endpoints, so it breaks whenever NSE
changes something. The owner uses it only through Claude, so Claude is the
maintainer: check before use, fix what is broken, and keep the fix.

## Before answering any data request using this library

1. Run `python healthcheck.py` (add `--json` if you want to parse it).
   Do this once per session, not before every call. For a full sweep of
   every public function use `python smoketest.py` (`--groups mcp,offline`
   runs only the routes that don't touch the nseindia.com website).
2. If everything passes, go ahead and answer.
3. If something fails, find out why before using it:
   - `HTTP 403/503` on everything: bot protection or network block. Try the
     other domain (`NSE_DOMAIN=nseindia.in` / `nseindia.com`). If it is still
     blocked, tell the user; do not escalate evasion (no spoofing beyond what
     `nsefetch()` already does).
   - One function fails, others pass: an endpoint moved or a field was
     renamed. Fix that function in `nsepython/rahu.py`.
   - `BAD_DATA` (e.g. price is 0 or the table is empty): NSE changed the
     response shape. Look at the raw response with `nsefetch(url)` and update
     the code that reads it.
   - A new NSE data set the user wants: use `nsefetch(url)` or
     `nse_mcp_call(server, tool, **args)` directly, and add a proper function
     only if the user asks.
4. After a fix, re-run `python healthcheck.py` and show the result. Never
   report a fix as working without a passing run. If live NSE is unreachable
   from the environment, say the fix is unverified.

## Domain (nseindia.com / nseindia.in)

URLs in the code are written with `nseindia.com`; `_nse_url()` rewrites them to
the active domain. Switch with `NSE_DOMAIN` or `nse_set_domain()`. `nsefetch()`
automatically retries on the other domain and switches if that works. Do not
hardcode a domain in new code; keep writing `https://www.nseindia.com/...`.

## Keeping fixes

- Work on the branch the session names; commit with a clear message
  saying which function and what NSE changed. Do not open a PR or publish to
  PyPI unless asked.
- Run `python -m unittest discover -s tests` before committing (offline).
- When adding a function, add a matching line to `CHECKS` in `healthcheck.py`
  so it is covered next time.
- Prefer a clear `NSEEndpointError` over returning `0`/`{}` when data is
  missing; silent wrong values are worse than errors.
