# Which Archive

A personal, self-hosted archive of Which pages, in three stages:

1. **`scraper.py`** captures raw pages listed in `which.csv` using a logged-in
   browser session, storing everything under `scraped/`.
2. **`export_archive_data.py`** builds the browsable dataset **and runs the
   link-rewrite pipeline**: inside every captured page, links to pages that were
   *also* scraped are pointed at the local copy, while links to pages that were
   *not* scraped stay as their real, live Which URLs.
3. **`archive-web/`** is a SvelteKit app for browsing the result — categories,
   search, page details, and one-click opening of captured pages.

The scraper never rewrites anything. Raw capture stays raw; the rewrite happens
only on the published copies under `archive-web/static/captures/`.

> Captured pages are Which subscriber content. They live under `scraped/` and
> `archive-web/static/captures/`, both of which are git-ignored and never
> committed. Keep the archive private.

---

## Quick start — view the website

**Just double-click `Start Which Archive.bat`.** It installs anything missing,
builds the data on the first run, and opens the site at
<http://localhost:5173>. Keep the window open while you browse; close it (or
press Ctrl+C) to stop.

After a **new scrape**, double-click **`Refresh Data and Start.bat`** instead —
it rebuilds the data and rewrites captures first, then opens the site.

Prefer the terminal? From the project root in PowerShell:

```powershell
./scripts/run-site.ps1            # start (exports data only if missing)
./scripts/run-site.ps1 -Refresh   # rebuild data after a scrape, then start
```

See [Manual setup](#manual-setup) for the step-by-step.

---

## What the website gives you

- **Home** — headline stats, top-level categories, best/buying guides, and the
  most recently captured pages.
- **Browse** (`/browse/...`) — a collapsible category tree plus deep-linkable
  category pages with breadcrumbs, sub-sections, filters and search.
- **Page detail** (`/page/<id>`) — metadata, capture status, previous/next
  within the category, related pages, and buttons to open the archived copy,
  the MHTML snapshot, or the live original.
- **Search** (`/search?q=...`) — filter across every page by title, URL,
  category, type or status.

Every archived page also carries a slim bar at the top linking back to the
archive home and out to the live original.

---

## Manual setup

```powershell
cd C:\Users\Chris\Desktop\which
uv venv
uv pip install -r requirements.txt
uv run playwright install chromium
cd archive-web
npm install
cd ..
```

If Chrome or Edge is already installed, the bundled Chromium install is
optional. The default scraper channel is Chrome; use `--channel msedge` for Edge
or `--channel chromium` for Playwright's bundled browser.

---

## 1. Scrape raw pages

Log in first:

```powershell
uv run python scraper.py login
```

This opens a dedicated browser profile under `scraped/browser-profile`. Sign in
yourself, open a subscriber page that shows the full content, then press Enter in
the terminal. The scraper stores only the *names* of the session cookies it
expects to remain present, never cookie values or passwords.

Resume scraping:

```powershell
uv run python scraper.py scrape
```

The scraper:

- imports all URLs from `which.csv`
- stores resume state in `scraped/manifest.sqlite`
- resets interrupted `in_progress` rows back to `pending`
- checks login cookies before every page
- checks the loaded page for login, CAPTCHA, and access-block markers
- stops on 401, 403, 429, external hosts, and repeated navigation/server failures
- respects `Retry-After` when present
- targets about 5 seconds per page by default, and only waits when running ahead
- saves raw rendered HTML for each page and attempts an MHTML snapshot for fidelity
- **discovers pagination**: when a listing links to `?page=2`, `?page=3`, … those
  pages are queued and captured too (chained until the whole series is covered),
  tagged `source=pagination` so they survive `which.csv` changes

### Paginated listings

Which paginates listings with a `?page=N` query parameter. New scrapes pick these
up automatically. To backfill pagination for pages captured **before** this
support existed, run the one-time discovery pass (offline, no re-fetch), then scrape:

```powershell
uv run python scraper.py discover   # queues ?page=N versions from existing captures
uv run python scraper.py scrape     # fetches them; deeper pages are found as it goes
```

Use `scrape --no-pagination` to disable discovery for a run.

If the login expires mid-run, the current URL stays pending and the scraper
alerts loudly (terminal bell, banner, `scraped/LOGIN_REQUIRED.txt`, and a
Windows message box), then prompts you to sign in again. Other safe stops (rate
limits, repeated navigation failures, genuinely external hosts) use the same
alert path and write `scraped/SCRAPER_STOPPED.txt`. Use `--no-gui-alert` for a
terminal-only alert.

Some Which URLs redirect to Which-owned content subdomains (e.g.
`broadband.which.co.uk`); those are captured as raw pages. The scraper still
stops before auth pages or non-Which hosts.

If Chrome shows `ERR_TOO_MANY_REDIRECTS`, clear only the dedicated scraper
session and sign in again — this does **not** delete captured pages or state:

```powershell
uv run python scraper.py clear-session
uv run python scraper.py login
uv run python scraper.py scrape
```

## 2. Build data + rewrite links

```powershell
uv run python export_archive_data.py
```

This reads `which.csv` and `scraped/manifest.sqlite`, writes
`archive-web/static/data/archive.json`, and publishes each capture into
`archive-web/static/captures/` with its links rewritten:

- **Scraped → local.** A link whose target was also scraped is repointed at that
  target's local capture, so browsing stays inside the archive.
- **Unscraped Which → live.** A link to a Which page that was *not* scraped is
  resolved to its absolute, live `https://www.which.co.uk/...` URL (root-relative
  `/foo` and protocol-relative `//host/foo` links are made absolute so they never
  resolve against the local server).
- **External → untouched.** Non-Which links are left exactly as they are.

Captures are fully-rendered React pages, so their `<script>` tags are dropped
during publishing. Otherwise the page's own JavaScript re-runs against
`localhost`, fails to route, and replaces the captured content with a 404
(also wiping the rewritten links). Removing scripts freezes each capture as a
static snapshot that displays its content and keeps the rewritten links working.

A rewrite depends on the whole set of scraped URLs, so a full re-pass runs
automatically whenever that set changes; otherwise only new/changed captures are
re-published. Useful flags:

| Flag | Effect |
| --- | --- |
| `--force-rewrite` | Rewrite every capture even if nothing changed. |
| `--no-rewrite` | Publish captures verbatim (no link changes, no banner). |
| `--no-banner` | Rewrite links but skip the top archive bar. |
| `--keep-scripts` | Keep `<script>` tags (captures will re-run and usually 404). |

## 3. Browse the archive

```powershell
cd archive-web
npm run dev      # exports data first, then starts the dev server
```

Production build (also refreshes data first):

```powershell
cd archive-web
npm run build
npm run preview
```

The app is a static, client-rendered SvelteKit SPA (`adapter-static`) that reads
`static/data/archive.json` at runtime, so the same build works whether it is
served locally or from a private server later.

---

## Status and recovery

```powershell
uv run python scraper.py status
uv run python scraper.py reset --failed
uv run python scraper.py reset --url https://www.which.co.uk/example
```

## On-disk layout

```text
which/
  scraper.py                 raw page capture (stage 1)
  export_archive_data.py     dataset + link-rewrite pipeline (stage 2)
  sitemap.py / sitemap_tree.py   build the URL lists from Which sitemaps
  which.csv                  the list of URLs to scrape
  which_active_urls_only.csv full flat list of active Which URLs
  scripts/run-site.ps1       one command to bring the website up
  archive-web/               SvelteKit browser (stage 3)
  scraped/                   (git-ignored) raw captures, DB, browser profile
    browser-profile/         dedicated logged-in browser profile
    manifest.sqlite          resume/status database
    raw-html/                rendered DOM snapshots (the archive source)
    mhtml/                   browser MHTML snapshots for fidelity
    meta/                    per-page metadata sidecars
```
