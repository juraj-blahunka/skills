---
name: search-console
description: Query Google Search Console for a site - search traffic (clicks, impressions, CTR, position by query, page, country, device, date), URL Inspection (is a page indexed, Google's chosen canonical, last crawl, robots and fetch state, mobile and rich results), and sitemaps (status, errors, submit). Use when debugging SEO, indexing, "why is this page not on Google", traffic drops, sitemap problems, or when asked how a site or post performs in search.
---

# Search Console

Run `uv run <this skill's dir>/scripts/gsc.py`; `--help` on it and on each subcommand lists every flag.
Output is JSON on stdout, so pipe it through `jq`.
The default property comes from `GSC_SITE`, else `~/.config/search-console/site`; override with `--site` before the subcommand.
Properties are `sc-domain:example.com` (domain property, covers all subdomains and protocols) or `https://www.example.com/` (URL-prefix).

```bash
S=<this skill's dir>/scripts/gsc.py
uv run "$S" sites                                              # properties the account can see, with permission level
uv run "$S" query --dim page --days 28 --limit 50              # top pages
uv run "$S" query --dim query --filter 'page~/posts/foo/'      # queries that land on one page
uv run "$S" query --dim date --days 90                         # daily trend, for spotting drops
uv run "$S" query --dim query --dim page --filter 'country=svk' --filter 'device=MOBILE'
uv run "$S" inspect https://example.com/posts/foo/ https://example.com/
uv run "$S" sitemaps
uv run "$S" sitemap submit https://example.com/sitemap.xml   # write: confirm with the user first
```

Filter operators: `=` equals, `!=`, `~` contains, `!~` not contains, `=~` regex, `!=~` not regex.
Countries are ISO 3166-1 alpha-3, lowercase (`svk`, `usa`); devices are `DESKTOP`, `MOBILE`, `TABLET`.

## How to debug with it

- **Page not on Google**: `inspect` the URL.
  Read `inspectionResult.indexStatusResult`: `verdict`, `coverageState` (for example "Crawled - currently not indexed", "Discovered - currently not indexed", "Duplicate, Google chose different canonical"), `robotsTxtState`, `indexingState`, `pageFetchState`, `lastCrawlTime`, `googleCanonical` against `userCanonical`, `sitemap`, `referringUrls`.
  Then check the live page yourself (`curl -sI`, the HTML `<link rel=canonical>`, `<meta name=robots>`, robots.txt, sitemap) to find the cause in the site's code.
- **Traffic drop**: `query --dim date` over 90+ days to date it, then compare two windows with `--start/--end` by `page` and by `query` to find what fell.
- **Sitemap problems**: `sitemaps` shows `errors`, `warnings`, `lastDownloaded`, `isPending` and submitted URL counts per content type.
  Google deprecated `contents[].indexed` and it usually reads 0; never treat it as the indexed count, `inspect` sample URLs instead.

## Limits worth knowing

- Search Analytics data lags 2-3 days; `query` ends 3 days ago by default and uses final data unless `--fresh`.
  `--dim hour` switches to Google's hourly data, which covers only the last few days, so pair it with `--days 3 --end <today>`.
  Sums by `query` undercount totals because Google hides rare queries for privacy; use no `--dim` or `--dim date` for true totals.
- URL Inspection is capped at 2000 calls a day and 600 a minute per property; inspect the URLs that matter, never a whole sitemap.
- It reports Google's indexed view; a page fixed since `lastCrawlTime` still shows the old state.
  The API cannot request indexing (the "Request indexing" button is UI only), and it has no Page indexing report, Core Web Vitals, manual actions or links reports; send the user to the Search Console UI for those.
- Sitemap `submit`/`delete` and anything else that writes needs Full or Owner permission for the service account; ask before writing.

## Setup

Auth is a Google Cloud service account added as a user on the Search Console property.
The key is `~/.config/search-console/service-account.json` (override with `GSC_CREDENTIALS`); `uv run "$S" whoami` shows which account is in use.
If the key is missing, stop and tell the user setup is needed; do not create credentials unasked.

- `403 PERMISSION_DENIED` saying the user lacks permission: the service account is not a user on that property, or `--site` differs from what `sites` lists.
- `403` saying the API has not been used in the project: the Search Console API is not enabled in the key's Cloud project.
- `Invalid JWT Signature` right after a key was made: it activates within about a minute; retry.
