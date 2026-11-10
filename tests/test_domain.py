"""Offline tests for the nseindia.com <-> nseindia.in handling. No network."""
import unittest
from unittest import mock

import nsepython.rahu as r


class FakeResp:
    def __init__(self, status=200, body=None, text="x"):
        self.status_code, self._body, self.text = status, body, text

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeSession:
    """Answers 200 only for URLs containing `ok_domain`; records every URL."""
    def __init__(self, ok_domain):
        self.ok_domain, self.urls = ok_domain, []

    def get(self, url, **kw):
        self.urls.append(url)
        if self.ok_domain in url:
            return FakeResp(200, {"hit": url}, text="a,b\n1,2")
        return FakeResp(503)


class DomainTests(unittest.TestCase):
    def setUp(self):
        r._nse_domain, r._nse_warmed = "nseindia.com", True

    def test_rewrite_all_nse_hosts(self):
        r._nse_domain = "nseindia.in"
        self.assertEqual(r._nse_url("https://www.nseindia.com/api/x?a=1"), "https://www.nseindia.in/api/x?a=1")
        self.assertEqual(r._nse_url("https://nsearchives.nseindia.com/c/a.csv"), "https://nsearchives.nseindia.in/c/a.csv")
        self.assertEqual(r._nse_url("https://archives.nseindia.com/c/a.csv"), "https://archives.nseindia.in/c/a.csv")

    def test_other_sites_untouched(self):
        self.assertEqual(r._nse_url("https://www.niftyindices.com/x", "nseindia.in"), "https://www.niftyindices.com/x")
        self.assertFalse(r._is_nse_url("https://www.niftyindices.com/x"))
        self.assertFalse(r._is_nse_url("https://evil.com/?u=https://www.nseindia.com"))

    def test_set_domain_validates(self):
        with self.assertRaises(ValueError):
            r.nse_set_domain("example.org")
        r.nse_set_domain("nseindia.in")
        self.assertEqual(r.nse_get_domain(), "nseindia.in")

    def test_nsefetch_uses_active_domain(self):
        r.nse_set_domain("nseindia.in")
        s = FakeSession("nseindia.in")
        with mock.patch.object(r, "_get_nse_session", return_value=s):
            out = r.nsefetch("https://www.nseindia.com/api/marketStatus")
        self.assertEqual(out["hit"], "https://www.nseindia.in/api/marketStatus")

    def test_nsefetch_falls_back_and_switches(self):
        s = FakeSession("nseindia.in")  # .com always 503
        with mock.patch.object(r, "_get_nse_session", return_value=s):
            out = r.nsefetch("https://www.nseindia.com/api/marketStatus")
        self.assertIn("nseindia.in", out["hit"])
        self.assertEqual(r.nse_get_domain(), "nseindia.in")

    def test_nsefetch_both_fail_raises(self):
        s = FakeSession("nowhere")
        with mock.patch.object(r, "_get_nse_session", return_value=s):
            with self.assertRaises(r.NSEEndpointError) as cm:
                r.nsefetch("https://www.nseindia.com/api/marketStatus")
        self.assertIn("fallback on nseindia.in also failed", str(cm.exception))
        self.assertEqual(r.nse_get_domain(), "nseindia.com")  # unchanged

    def test_csv_fallback(self):
        s = FakeSession("nseindia.in")
        with mock.patch.object(r, "_get_nse_session", return_value=s):
            txt = r._nse_fetch_csv_text("https://nsearchives.nseindia.com/content/a.csv")
        self.assertEqual(txt, "a,b\n1,2")
        self.assertEqual(r.nse_get_domain(), "nseindia.in")

    def test_non_nse_url_passthrough(self):
        s = FakeSession("example.org")
        with mock.patch.object(r, "_get_nse_session", return_value=s):
            out = r.nsefetch("https://example.org/data")
        self.assertEqual(out["hit"], "https://example.org/data")


if __name__ == "__main__":
    unittest.main()
