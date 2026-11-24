#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-auth>=2.30", "requests>=2.32"]
# ///
"""Google Search Console API CLI.

Prints JSON to stdout so an agent can pipe it through jq.
Auth: a service account key, added as a user on the Search Console property.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

import requests
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

SCOPES_RO = ["https://www.googleapis.com/auth/webmasters.readonly"]
SCOPES_RW = ["https://www.googleapis.com/auth/webmasters"]
WEBMASTERS = "https://www.googleapis.com/webmasters/v3"
INSPECT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
CONFIG_DIR = Path.home() / ".config" / "search-console"
DEFAULT_KEY = CONFIG_DIR / "service-account.json"
SITE_FILE = CONFIG_DIR / "site"


def default_site() -> str | None:
    if os.environ.get("GSC_SITE"):
        return os.environ["GSC_SITE"]
    if SITE_FILE.is_file():
        return SITE_FILE.read_text().strip() or None
    return None


def key_path() -> Path:
    return Path(os.environ.get("GSC_CREDENTIALS", DEFAULT_KEY)).expanduser()


def session(write: bool = False) -> AuthorizedSession:
    path = key_path()
    if not path.is_file():
        sys.exit(f"No service account key at {path}. See the Setup section of SKILL.md.")
    creds = service_account.Credentials.from_service_account_file(
        str(path), scopes=SCOPES_RW if write else SCOPES_RO
    )
    return AuthorizedSession(creds)


def call(resp: requests.Response) -> dict:
    if resp.status_code >= 400:
        try:
            err = resp.json().get("error", {})
            msg = f"{err.get('status', resp.status_code)}: {err.get('message', resp.text)}"
        except ValueError:
            msg = f"{resp.status_code}: {resp.text}"
        sys.exit(f"API error {msg}")
    return resp.json() if resp.content else {}


def site_url(site: str) -> str:
    return quote(site, safe="")


def out(data: object) -> None:
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def cmd_whoami(_: argparse.Namespace) -> None:
    info = json.loads(key_path().read_text())
    out({"client_email": info.get("client_email"), "project_id": info.get("project_id"), "key": str(key_path())})


def cmd_sites(_: argparse.Namespace) -> None:
    out(call(session().get(f"{WEBMASTERS}/sites")))


def default_dates(args: argparse.Namespace) -> tuple[str, str]:
    # Search Analytics data lags 2-3 days; ending 3 days ago avoids partial days.
    end = dt.date.fromisoformat(args.end) if args.end else dt.date.today() - dt.timedelta(days=3)
    start = dt.date.fromisoformat(args.start) if args.start else end - dt.timedelta(days=args.days - 1)
    return start.isoformat(), end.isoformat()


def parse_filter(raw: str) -> dict:
    # dimension<op>expression, op one of: =  !=  ~ (contains)  !~ (not contains)  =~ (regex)  !=~ (not regex)
    for token, op in (("!=~", "excludingRegex"), ("=~", "includingRegex"), ("!~", "notContains"),
                      ("!=", "notEquals"), ("~", "contains"), ("=", "equals")):
        if token in raw:
            dim, expr = raw.split(token, 1)
            return {"dimension": dim.strip(), "operator": op, "expression": expr.strip()}
    sys.exit(f"Bad filter {raw!r}; use e.g. page~/posts/ or query=foo or country=svk")


def cmd_query(args: argparse.Namespace) -> None:
    start, end = default_dates(args)
    body: dict = {
        "startDate": start,
        "endDate": end,
        "dimensions": args.dim or [],
        "type": args.type,
        "rowLimit": args.limit,
        "startRow": args.offset,
        "dataState": "all" if args.fresh else "final",
    }
    if "hour" in body["dimensions"]:
        # Hourly rows exist only for recent, not-yet-final data and need their own data state.
        body["dataState"] = "hourly_all"
    if args.filter:
        body["dimensionFilterGroups"] = [{"groupType": "and", "filters": [parse_filter(f) for f in args.filter]}]
    if args.aggregation:
        body["aggregationType"] = args.aggregation
    data = call(session().post(f"{WEBMASTERS}/sites/{site_url(args.site)}/searchAnalytics/query", json=body))
    out({"request": body, **data})


def cmd_inspect(args: argparse.Namespace) -> None:
    s = session()
    results = []
    for url in args.urls:
        body = {"inspectionUrl": url, "siteUrl": args.site, "languageCode": "en-US"}
        results.append({"url": url, **call(s.post(INSPECT, json=body))})
    out(results if len(results) > 1 else results[0])


def cmd_sitemaps(args: argparse.Namespace) -> None:
    out(call(session().get(f"{WEBMASTERS}/sites/{site_url(args.site)}/sitemaps")))


def cmd_sitemap(args: argparse.Namespace) -> None:
    base = f"{WEBMASTERS}/sites/{site_url(args.site)}/sitemaps/{site_url(args.feedpath)}"
    if args.action == "get":
        out(call(session().get(base)))
    elif args.action == "submit":
        call(session(write=True).put(base))
        out({"submitted": args.feedpath})
    elif args.action == "delete":
        call(session(write=True).delete(base))
        out({"deleted": args.feedpath})


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--site", default=default_site(),
                   help=f"property, sc-domain:example.com or https://example.com/ (default: env GSC_SITE, else {SITE_FILE})")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami", help="show which service account is in use").set_defaults(fn=cmd_whoami)
    sub.add_parser("sites", help="list properties the service account can see").set_defaults(fn=cmd_sites)

    q = sub.add_parser("query", help="Search Analytics: clicks, impressions, CTR, position")
    q.add_argument("--dim", action="append", choices=["query", "page", "country", "device", "date", "searchAppearance", "hour"],
                   help="group by dimension, repeatable")
    q.add_argument("--filter", action="append",
                   help="dimension filter, repeatable (ANDed): page~/posts/  query=foo  country=svk  device=MOBILE  page=~regex  page!~x")
    q.add_argument("--days", type=int, default=28, help="window length when --start is not given (default 28)")
    q.add_argument("--start", help="YYYY-MM-DD")
    q.add_argument("--end", help="YYYY-MM-DD (default 3 days ago)")
    q.add_argument("--type", default="web", choices=["web", "image", "video", "news", "discover", "googleNews"])
    q.add_argument("--limit", type=int, default=100, help="rows, max 25000")
    q.add_argument("--offset", type=int, default=0)
    q.add_argument("--aggregation", choices=["auto", "byPage", "byProperty", "byNewsShowcasePanel"])
    q.add_argument("--fresh", action="store_true", help="include not-yet-final recent data (implied by --dim hour)")
    q.set_defaults(fn=cmd_query)

    i = sub.add_parser("inspect", help="URL Inspection: index status, canonical, crawl, mobile, rich results")
    i.add_argument("urls", nargs="+")
    i.set_defaults(fn=cmd_inspect)

    sub.add_parser("sitemaps", help="list submitted sitemaps with errors and warnings").set_defaults(fn=cmd_sitemaps)

    sm = sub.add_parser("sitemap", help="get, submit or delete one sitemap")
    sm.add_argument("action", choices=["get", "submit", "delete"])
    sm.add_argument("feedpath", help="full sitemap URL, e.g. https://example.com/sitemap.xml")
    sm.set_defaults(fn=cmd_sitemap)

    args = p.parse_args()
    if args.cmd in {"query", "inspect", "sitemaps", "sitemap"} and not args.site:
        sys.exit(f"No property given; pass --site, set GSC_SITE, or write it to {SITE_FILE}. `sites` lists them.")
    try:
        args.fn(args)
    except RefreshError as e:
        sys.exit(f"Auth failed for {key_path()}: {e.args[0]}. "
                 "A key created in the last few minutes may not be active yet; a revoked or deleted key needs a new one.")


if __name__ == "__main__":
    main()
