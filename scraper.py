from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sqlite3
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "which.csv"
DEFAULT_OUT = ROOT / "scraped"
AUTH_STATE_NAME = "auth-state.json"
WHICH_HOST = "www.which.co.uk"
WHICH_ROOT_DOMAIN = "which.co.uk"
AUTH_HOST = "auth.which.co.uk"
SCHEMA_VERSION = 1
DEFAULT_TARGET_SECONDS_PER_PAGE = 5.0

COOKIE_HINTS = (
    "auth",
    "identity",
    "jwt",
    "login",
    "member",
    "session",
    "token",
    "user",
)
LOGIN_MARKERS = (
    "sign in to unlock",
    "log in to unlock",
    "already a member? log in",
    "subscribe to unlock",
    "verify you are human",
    "access denied",
)


class AuthRequired(RuntimeError):
    pass


class SessionRepairRequired(AuthRequired):
    pass


class SitePressure(RuntimeError):
    def __init__(self, message: str, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class UrlFailure(RuntimeError):
    pass


class RedirectLoopFailure(UrlFailure):
    pass


@dataclass(frozen=True)
class Paths:
    out: Path
    db: Path
    profile: Path
    raw_html: Path
    mhtml: Path
    meta: Path


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def paths(out_dir: Path) -> Paths:
    out = out_dir.resolve()
    return Paths(
        out=out,
        db=out / "manifest.sqlite",
        profile=out / "browser-profile",
        raw_html=out / "raw-html",
        mhtml=out / "mhtml",
        meta=out / "meta",
    )


def ensure_dirs(p: Paths) -> None:
    for path in (p.out, p.profile, p.raw_html, p.mhtml, p.meta):
        path.mkdir(parents=True, exist_ok=True)


def normalise_url(url: str, *, base: str | None = None, keep_fragment: bool = False) -> str:
    value = url.strip()
    if not value:
        return ""
    if base:
        value = urljoin(base, value)
    parsed = urlsplit(value)
    if not parsed.scheme and parsed.netloc:
        parsed = urlsplit(f"https:{value}")
    scheme = (parsed.scheme or "https").lower()
    host = parsed.netloc.lower()
    if not host:
        return value
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = urlencode(query_pairs, doseq=True)
    fragment = parsed.fragment if keep_fragment else ""
    return urlunsplit((scheme, host, path, query, fragment))


def is_which_host(host: str) -> bool:
    value = host.lower().strip(".")
    return value == WHICH_ROOT_DOMAIN or value.endswith(f".{WHICH_ROOT_DOMAIN}")


def is_which_content_host(host: str) -> bool:
    value = host.lower().strip(".")
    return bool(value) and is_which_host(value) and value != AUTH_HOST


def canonical_key(url: str, *, base: str | None = None) -> str:
    return normalise_url(url, base=base, keep_fragment=False)


def detect_url_column(fieldnames: list[str]) -> str:
    for candidate in ("URL", "url", "loc", "canonical_url"):
        if candidate in fieldnames:
            return candidate
    if len(fieldnames) == 1:
        return fieldnames[0]
    raise ValueError(f"Could not find a URL column. Columns: {', '.join(fieldnames)}")


def read_urls(csv_path: Path) -> list[str]:
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")
        column = detect_url_column(reader.fieldnames)
        seen: set[str] = set()
        urls: list[str] = []
        for row in reader:
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            url = canonical_key(raw)
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
    return urls


def slug_for_url(url: str) -> str:
    parsed = urlsplit(url)
    bits = [part for part in parsed.path.split("/") if part]
    hint = "-".join(bits[-3:]) if bits else "index"
    hint = re.sub(r"[^a-zA-Z0-9._-]+", "-", hint).strip("-._").lower()[:96] or "page"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return f"{digest[:16]}_{hint}"


def relpath(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def init_db(p: Paths) -> sqlite3.Connection:
    ensure_dirs(p)
    conn = sqlite3.connect(p.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pages(
            id INTEGER PRIMARY KEY,
            input_order INTEGER NOT NULL,
            url TEXT NOT NULL UNIQUE,
            canonical_url TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            http_status INTEGER,
            final_url TEXT,
            title TEXT,
            raw_html_path TEXT,
            mhtml_path TEXT,
            mirror_path TEXT,
            fetched_at TEXT,
            updated_at TEXT NOT NULL,
            error TEXT,
            retry_after_until TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status)")
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
    conn.commit()
    return conn


def import_manifest(conn: sqlite3.Connection, csv_path: Path) -> int:
    urls = read_urls(csv_path)
    now = utc_now()
    with conn:
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS current_manifest(url TEXT PRIMARY KEY)")
        conn.execute("DELETE FROM current_manifest")
        conn.executemany("INSERT INTO current_manifest(url) VALUES(?)", [(url,) for url in urls])
        for index, url in enumerate(urls, start=1):
            conn.execute(
                """
                INSERT INTO pages(input_order, url, canonical_url, slug, status, updated_at)
                VALUES(?, ?, ?, ?, 'pending', ?)
                ON CONFLICT(canonical_url) DO UPDATE SET
                    input_order=excluded.input_order,
                    url=excluded.url,
                    slug=excluded.slug,
                    updated_at=excluded.updated_at
                """,
                (index, url, url, slug_for_url(url), now),
            )
        conn.execute(
            """
            DELETE FROM pages
            WHERE NOT EXISTS(
                SELECT 1 FROM current_manifest WHERE current_manifest.url=pages.canonical_url
            )
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('csv_sha256', ?)",
            (hashlib.sha256(csv_path.read_bytes()).hexdigest(),),
        )
        conn.execute(
            "UPDATE pages SET status='pending', error='Recovered from interrupted run' WHERE status='in_progress'"
        )
    return len(urls)


def page_output_paths(p: Paths, row: sqlite3.Row) -> tuple[Path, Path, Path]:
    slug = row["slug"]
    prefix = slug[:2]
    raw = p.raw_html / prefix / f"{slug}.raw.html"
    mhtml = p.mhtml / prefix / f"{slug}.mhtml"
    meta = p.meta / prefix / f"{slug}.json"
    return raw, mhtml, meta


def auth_state_path(profile_dir: Path) -> Path:
    return profile_dir / AUTH_STATE_NAME


def site_cookies(context: Any, url: str) -> list[dict[str, Any]]:
    host = (urlsplit(url).hostname or "").lower()
    cookies = list(context.cookies([url]))
    result = []
    for cookie in cookies:
        domain = str(cookie.get("domain", "")).lstrip(".").lower()
        if host == domain or host.endswith(f".{domain}"):
            result.append(cookie)
    return result


def record_auth_state(context: Any, profile_dir: Path, verification_url: str) -> Path:
    cookies = site_cookies(context, verification_url)
    hinted = {
        str(cookie["name"])
        for cookie in cookies
        if cookie.get("value")
        and any(hint in str(cookie["name"]).lower() for hint in COOKIE_HINTS)
    }
    secure_http_only = {
        str(cookie["name"])
        for cookie in cookies
        if cookie.get("value") and cookie.get("secure") and cookie.get("httpOnly")
    }
    required_names = sorted(hinted or secure_http_only)
    if not required_names:
        raise AuthRequired(
            "Could not identify a session cookie. Make sure the verification page is a logged-in subscriber page."
        )
    payload = {
        "version": 1,
        "domain": WHICH_HOST,
        "verification_url": verification_url,
        "verified_at": utc_now(),
        "required_cookie_names": required_names,
    }
    profile_dir.mkdir(parents=True, exist_ok=True)
    target = auth_state_path(profile_dir)
    partial = target.with_suffix(".partial")
    partial.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    partial.replace(target)
    return target


def check_auth_state(context: Any, profile_dir: Path) -> None:
    state_file = auth_state_path(profile_dir)
    if not state_file.is_file():
        raise AuthRequired("No verified login state. Run the login command first.")
    state = json.loads(state_file.read_text(encoding="utf-8"))
    if state.get("domain") != WHICH_HOST:
        raise AuthRequired("Stored login state is for a different domain.")
    required = {str(name) for name in state.get("required_cookie_names", [])}
    if not required:
        raise AuthRequired("Stored login state has no required cookie names.")
    now = time.time()
    active = {
        str(cookie["name"])
        for cookie in site_cookies(context, f"https://{WHICH_HOST}/")
        if cookie.get("value")
        and (float(cookie.get("expires", -1)) <= 0 or float(cookie["expires"]) > now)
    }
    missing = sorted(required - active)
    if missing:
        raise AuthRequired(f"Login session cookie is missing or expired: {', '.join(missing)}")


def parse_retry_after(value: str | None) -> int | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return max(0, int(value))
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0, int((when - datetime.now(UTC)).total_seconds()))


def detect_login_or_block(page: Any) -> str | None:
    current = str(page.url)
    host = (urlsplit(current).hostname or "").lower()
    if host == AUTH_HOST:
        return "auth host"
    path = (urlsplit(current).path or "/").lower()
    if any(part in path for part in ("/login", "/sign-in", "/signin")):
        return "login page"
    with suppress(Exception):
        title = str(page.title()).strip().lower()
        if title.startswith(("sign in", "log in", "login")):
            return "login title"
        if any(marker in title for marker in ("captcha", "access denied", "verify you are human")):
            return "block title"
    selector = (
        "iframe[src*='captcha'], .g-recaptcha, .h-captcha, [data-sitekey], "
        "form[action*='login'], form[action*='signin'], input[type='password']"
    )
    with suppress(Exception):
        visible_match = page.evaluate(
            """
            (selector) => {
              const isVisible = (el) => {
                const style = window.getComputedStyle(el);
                if (!style || style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) {
                  return false;
                }
                const rect = el.getBoundingClientRect();
                if (rect.width < 2 || rect.height < 2) {
                  return false;
                }
                return rect.bottom >= 0 && rect.right >= 0 && rect.top <= window.innerHeight && rect.left <= window.innerWidth;
              };
              for (const el of document.querySelectorAll(selector)) {
                if (isVisible(el)) {
                  return el.tagName.toLowerCase() + (el.getAttribute('type') ? `[type="${el.getAttribute('type')}"]` : '');
                }
              }
              return "";
            }
            """,
            selector,
        )
        if visible_match:
            return f"visible login or CAPTCHA form: {visible_match}"
    with suppress(Exception):
        visible_marker = page.evaluate(
            """
            (markers) => {
              const isVisibleInViewport = (el) => {
                const style = window.getComputedStyle(el);
                if (!style || style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) {
                  return false;
                }
                const rect = el.getBoundingClientRect();
                if (rect.width < 2 || rect.height < 2) {
                  return false;
                }
                return rect.bottom >= 0 && rect.right >= 0 && rect.top <= window.innerHeight && rect.left <= window.innerWidth;
              };
              const candidates = document.querySelectorAll(
                'dialog, form, [role="dialog"], [role="alert"], h1, h2, h3, p, a, button, label, span, li'
              );
              for (const el of candidates) {
                if (!isVisibleInViewport(el)) {
                  continue;
                }
                const text = (el.innerText || '').toLowerCase();
                if (!text) {
                  continue;
                }
                for (const marker of markers) {
                  if (text.includes(marker)) {
                    return marker;
                  }
                }
              }
              return "";
            }
            """,
            list(LOGIN_MARKERS),
        )
        if visible_marker:
            return f"visible login or access marker: {visible_marker}"
    return None


def launch_context(profile_dir: Path, channel: str, block_media: bool) -> tuple[Any, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Install dependencies first: uv pip install -r requirements.txt") from exc

    profile_dir.mkdir(parents=True, exist_ok=True)
    playwright = sync_playwright().start()
    kwargs: dict[str, Any] = {
        "user_data_dir": str(profile_dir),
        "headless": False,
        "viewport": {"width": 1440, "height": 1000},
        "accept_downloads": False,
    }
    if channel not in {"", "bundled", "chromium"}:
        kwargs["channel"] = channel
    try:
        context = playwright.chromium.launch_persistent_context(**kwargs)
        if block_media:
            context.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"media"}
                else route.continue_(),
            )
    except Exception:
        playwright.stop()
        raise
    return playwright, context


def first_page(context: Any) -> Any:
    pages = list(context.pages)
    return pages[0] if pages else context.new_page()


def page_host(page: Any) -> str:
    return (urlsplit(str(page.url)).hostname or "").lower()


def settle_page(page: Any) -> None:
    with suppress(Exception):
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
    with suppress(Exception):
        page.wait_for_load_state("load", timeout=10_000)


def navigation_was_interrupted(exc: Exception) -> bool:
    return "interrupted by another navigation" in str(exc).lower()


def navigation_was_redirect_loop(exc: Exception) -> bool:
    message = str(exc).lower()
    return "err_too_many_redirects" in message or "too many redirects" in message


def remove_auth_marker(p: Paths) -> None:
    with suppress(FileNotFoundError):
        auth_state_path(p.profile).unlink()


def clear_session_in_context(context: Any, p: Paths) -> None:
    with suppress(Exception):
        context.clear_cookies()
    with suppress(Exception):
        page = first_page(context)
        session = context.new_cdp_session(page)
        try:
            for origin in ("https://www.which.co.uk", "https://auth.which.co.uk"):
                session.send(
                    "Storage.clearDataForOrigin",
                    {"origin": origin, "storageTypes": "all"},
                )
        finally:
            session.detach()
    remove_auth_marker(p)


def stored_verification_url(p: Paths) -> str | None:
    state_file = auth_state_path(p.profile)
    if not state_file.is_file():
        return None
    with suppress(Exception):
        state = json.loads(state_file.read_text(encoding="utf-8"))
        url = str(state.get("verification_url") or "").strip()
        if (urlsplit(url).hostname or "").lower() == WHICH_HOST:
            return url
    return None


def redirect_probe_candidates(p: Paths, current_url: str) -> list[str]:
    candidates: list[str] = []
    verification_url = stored_verification_url(p)
    if verification_url and canonical_key(verification_url) != canonical_key(current_url):
        candidates.append(verification_url)
    candidates.append(f"https://{WHICH_HOST}/")

    seen: set[str] = set()
    unique: list[str] = []
    for url in candidates:
        key = canonical_key(url)
        if key not in seen:
            seen.add(key)
            unique.append(url)
    return unique


def session_still_looks_usable_after_redirect_loop(context: Any, p: Paths, current_url: str, timeout: int) -> bool:
    for probe_url in redirect_probe_candidates(p, current_url):
        probe = context.new_page()
        try:
            response = probe.goto(probe_url, wait_until="domcontentloaded", timeout=timeout * 1000)
            settle_page(probe)
            host = page_host(probe)
            if host == AUTH_HOST:
                continue
            if not is_which_content_host(host):
                continue
            if response is not None and int(response.status) in {401, 403}:
                continue
            if detect_login_or_block(probe):
                continue
            return True
        except Exception as exc:
            if navigation_was_redirect_loop(exc):
                continue
            continue
        finally:
            with suppress(Exception):
                probe.close()
    return False


def open_which_home_for_login(page: Any) -> None:
    with suppress(Exception):
        page.goto(f"https://{WHICH_HOST}/", wait_until="domcontentloaded", timeout=60_000)
    settle_page(page)


def goto_for_verification(page: Any, url: str) -> bool:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    except Exception as exc:
        if navigation_was_redirect_loop(exc):
            raise SessionRepairRequired(
                "Which redirected too many times. The dedicated browser session needs to be cleared and verified again."
            ) from exc
        if navigation_was_interrupted(exc):
            settle_page(page)
            return False
        raise
    settle_page(page)
    return True


def verify_current_login_page(
    context: Any,
    p: Paths,
    page: Any,
    *,
    verification_url: str | None,
) -> tuple[Path | None, str | None]:
    settle_page(page)
    host = page_host(page)
    current_url = str(page.url)

    if host == AUTH_HOST:
        return None, "Which is still showing the auth flow. Finish that page in the browser first."
    if host and host != WHICH_HOST:
        return None, f"The browser is on {host}, not {WHICH_HOST}."

    if host == WHICH_HOST:
        reason = detect_login_or_block(page)
        if reason:
            return None, f"Which still looks blocked: {reason}."
        path = urlsplit(current_url).path or "/"
        if path != "/" or verification_url is None:
            return record_auth_state(context, p.profile, current_url), None

    if verification_url:
        navigated = goto_for_verification(page, verification_url)
        if not navigated:
            return None, "Which started another navigation while verification was loading."
        host = page_host(page)
        if host == AUTH_HOST:
            return None, "Which redirected to auth during verification. Finish that in the browser."
        if host != WHICH_HOST:
            return None, f"Verification page is on {host or 'an unknown host'}, not {WHICH_HOST}."
        reason = detect_login_or_block(page)
        if reason:
            return None, f"Login verification still looks blocked: {reason}."
        return record_auth_state(context, p.profile, str(page.url)), None

    return None, "Open a logged-in Which page in the browser before pressing Enter."


def interactive_login(p: Paths, channel: str, verification_url: str | None, block_media: bool) -> Path:
    playwright, context = launch_context(p.profile, channel, block_media)
    try:
        page = first_page(context)
        try:
            goto_for_verification(page, "https://www.which.co.uk/")
        except SessionRepairRequired as exc:
            clear_session_in_context(context, p)
            open_which_home_for_login(page)
            print(f"{exc} Cleared the dedicated session; sign in again.")
        print()
        print("A dedicated browser profile is open.")
        print("Sign in to Which? there, then open a subscriber page that shows the full article.")
        while True:
            input("Press Enter here once you are signed in and the page is visible...")
            try:
                state_path, problem = verify_current_login_page(
                    context,
                    p,
                    page,
                    verification_url=verification_url,
                )
            except SessionRepairRequired as exc:
                clear_session_in_context(context, p)
                open_which_home_for_login(page)
                print(f"{exc} Cleared the dedicated session; sign in again.")
                continue
            if state_path is not None:
                return state_path
            print(problem or "Login was not verified yet.")
    finally:
        context.close()
        playwright.stop()


def prompt_relogin(context: Any, p: Paths, verification_url: str) -> None:
    print()
    print("Login validation failed. The current URL has been left pending.")
    answer = input("Open the dedicated browser in this same session so you can sign in again? [Y/n] ")
    if answer.strip().lower() in {"n", "no"}:
        raise AuthRequired("Login required before scraping can continue.")
    page = first_page(context)
    try:
        goto_for_verification(page, "https://www.which.co.uk/")
    except SessionRepairRequired as exc:
        clear_session_in_context(context, p)
        open_which_home_for_login(page)
        print(f"{exc} Cleared the dedicated session; sign in again.")
    while True:
        input("Sign in in the browser, then press Enter here to verify and resume...")
        try:
            state_path, problem = verify_current_login_page(
                context,
                p,
                page,
                verification_url=verification_url,
            )
        except SessionRepairRequired as exc:
            clear_session_in_context(context, p)
            open_which_home_for_login(page)
            print(f"{exc} Cleared the dedicated session; sign in again.")
            continue
        if state_path is not None:
            return
        print(problem or "Login was not verified yet.")


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def wait_politely(seconds: float, jitter: float) -> None:
    total = max(0.0, seconds)
    if total > 0 and jitter > 0:
        total += random.uniform(0, jitter)
    if total > 0:
        print(f"Waiting {total:.1f}s before the next page...")
        time.sleep(total)


def wait_for_pace(args: argparse.Namespace) -> None:
    if args.delay is not None:
        wait_politely(args.delay, args.jitter)
        return
    target = getattr(args, "_target_seconds_per_page", None)
    previous = getattr(args, "_last_page_seconds", None)
    if target is None or previous is None:
        return
    wait_politely(max(0.0, target - previous), args.jitter)


def alert_pause(
    p: Paths,
    *,
    heading: str,
    message: str,
    next_step: str,
    alert_filename: str,
    window_title: str,
    gui_alert: bool,
) -> None:
    banner = "!" * 78
    print("\a\a\a", end="", flush=True)
    print()
    print(banner)
    print(heading)
    print(message)
    print(next_step)
    print(banner)
    alert_file = p.out / alert_filename
    alert_file.write_text(
        f"{heading}\n\n{message}\n\n{next_step}\n\nCreated: {utc_now()}\n",
        encoding="utf-8",
    )
    if gui_alert and os.name == "nt":
        with suppress(Exception):
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                f"{message}\n\n{next_step}",
                window_title,
                0x00001000 | 0x00000030,
            )


def alert_login_required(p: Paths, message: str, *, gui_alert: bool) -> None:
    alert_pause(
        p,
        heading="LOGIN REQUIRED - SCRAPER PAUSED",
        message=message,
        next_step="The current URL is still pending. Sign in again to continue.",
        alert_filename="LOGIN_REQUIRED.txt",
        window_title="Which scraper paused: login required",
        gui_alert=gui_alert,
    )


def alert_scraper_stopped(p: Paths, message: str, *, gui_alert: bool) -> None:
    alert_pause(
        p,
        heading="SCRAPER STOPPED - ATTENTION REQUIRED",
        message=message,
        next_step="The current URL is still pending. Resume with: uv run python scraper.py scrape",
        alert_filename="SCRAPER_STOPPED.txt",
        window_title="Which scraper stopped",
        gui_alert=gui_alert,
    )


def compact_error(exc: BaseException) -> str:
    detail = str(exc).splitlines()[0].strip()
    return detail or type(exc).__name__


def capture_mhtml(page: Any, max_mhtml_mb: int) -> tuple[str | None, str | None]:
    session = None
    try:
        session = page.context.new_cdp_session(page)
        snapshot = session.send("Page.captureSnapshot", {"format": "mhtml"})["data"]
    except Exception as exc:
        return None, compact_error(exc)
    finally:
        if session is not None:
            with suppress(Exception):
                session.detach()

    if len(snapshot.encode("utf-8")) > max_mhtml_mb * 1024 * 1024:
        return None, f"MHTML snapshot is larger than {max_mhtml_mb} MB"
    return snapshot, None


def update_page(
    conn: sqlite3.Connection,
    row_id: int,
    status: str,
    *,
    error: str | None = None,
    http_status: int | None = None,
    retry_after_seconds: int | None = None,
    paths_update: dict[str, str] | None = None,
    final_url: str | None = None,
    title: str | None = None,
) -> None:
    retry_until = None
    if retry_after_seconds is not None:
        retry_until = (datetime.now(UTC) + timedelta(seconds=retry_after_seconds)).isoformat(timespec="seconds")
    updates = {
        "status": status,
        "updated_at": utc_now(),
        "error": error,
        "http_status": http_status,
        "retry_after_until": retry_until,
        "final_url": final_url,
        "title": title,
    }
    if paths_update:
        updates.update(paths_update)
    assignments = ", ".join(f"{key}=?" for key in updates)
    values = list(updates.values()) + [row_id]
    with conn:
        conn.execute(f"UPDATE pages SET {assignments} WHERE id=?", values)


def mark_in_progress(conn: sqlite3.Connection, row_id: int) -> None:
    with conn:
        conn.execute(
            """
            UPDATE pages
            SET status='in_progress', attempts=attempts+1, updated_at=?, error=NULL
            WHERE id=?
            """,
            (utc_now(), row_id),
        )


def scrape_one(conn: sqlite3.Connection, p: Paths, row: sqlite3.Row, page: Any, args: argparse.Namespace) -> None:
    url = str(row["canonical_url"])
    raw_path, mhtml_path, meta_path = page_output_paths(p, row)
    for path in (raw_path.parent, mhtml_path.parent, meta_path.parent):
        path.mkdir(parents=True, exist_ok=True)

    check_auth_state(page.context, p.profile)
    wait_for_pace(args)
    mark_in_progress(conn, int(row["id"]))

    response = None
    for attempt in range(args.retries + 1):
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
        except Exception as exc:
            if navigation_was_redirect_loop(exc):
                if session_still_looks_usable_after_redirect_loop(page.context, p, url, args.timeout):
                    raise RedirectLoopFailure(
                        "Redirect loop (ERR_TOO_MANY_REDIRECTS) on this URL; session probe still looked usable."
                    ) from exc
                raise SessionRepairRequired(
                    "Which redirected too many times and the session probe could not verify a usable Which session."
                ) from exc
            if attempt >= args.retries:
                detail = str(exc).splitlines()[0].strip() or type(exc).__name__
                raise SitePressure(f"Navigation failed after {attempt + 1} attempt(s): {detail}") from exc
            backoff = args.backoff * (2**attempt)
            print(f"Navigation error; retrying in {backoff:.1f}s...")
            time.sleep(backoff)
            continue

        if response is None:
            raise SitePressure("Browser navigation returned no HTTP response.")
        status = int(response.status)
        if status == 429:
            retry_after = parse_retry_after(response.headers.get("retry-after"))
            raise SitePressure("HTTP 429 from Which; stopping the run.", retry_after)
        if status in {401, 403}:
            raise AuthRequired(f"HTTP {status}; login or subscription access must be checked.")
        if status >= 500:
            if attempt >= args.retries:
                raise SitePressure(f"HTTP {status} after bounded retries; stopping the run.")
            backoff = args.backoff * (2**attempt)
            print(f"HTTP {status}; retrying in {backoff:.1f}s...")
            time.sleep(backoff)
            continue
        if 300 <= status < 400:
            print(f"HTTP {status} redirect response; capturing the loaded final page if it stayed on Which.")
            break
        if status != 200:
            raise UrlFailure(f"HTTP {status}")
        break

    assert response is not None
    with suppress(Exception):
        page.wait_for_load_state("load", timeout=30_000)
    page.wait_for_timeout(int(args.settle * 1000))

    reason = detect_login_or_block(page)
    if reason:
        raise AuthRequired(f"Page appears logged out or blocked: {reason}")

    final_url = str(page.url)
    final_host = (urlsplit(final_url).hostname or "").lower()
    if final_host == AUTH_HOST:
        raise AuthRequired("Which redirected to the auth host before capture.")
    if not is_which_content_host(final_host):
        raise SitePressure(f"Browser ended on unexpected host {final_host or 'unknown'}; stopping before capture.")
    if final_host != WHICH_HOST:
        print(f"Capturing Which content after redirect to {final_host}.")

    try:
        raw_html = page.content()
    except Exception as exc:
        raise UrlFailure(f"Could not read rendered HTML: {compact_error(exc)}") from exc
    raw_path.write_text(raw_html, encoding="utf-8")

    snapshot, mhtml_error = capture_mhtml(page, args.max_mhtml_mb)
    mhtml_rel: str | None = None
    if snapshot is not None:
        mhtml_path.write_text(snapshot, encoding="utf-8")
        mhtml_rel = relpath(mhtml_path, p.out)
    else:
        with suppress(FileNotFoundError):
            mhtml_path.unlink()
        print(f"MHTML capture failed for this page; saved raw HTML and continuing: {mhtml_error}")

    title = ""
    with suppress(Exception):
        title = str(page.title())
    fetched_at = utc_now()
    metadata = {
        "url": url,
        "final_url": final_url,
        "title": title,
        "http_status": int(response.status),
        "fetched_at": fetched_at,
        "raw_html_path": relpath(raw_path, p.out),
        "mhtml_path": mhtml_rel,
    }
    if mhtml_error:
        metadata["mhtml_error"] = mhtml_error
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    update_page(
        conn,
        int(row["id"]),
        "downloaded",
        error=f"MHTML capture failed: {mhtml_error}" if mhtml_error else None,
        http_status=int(response.status),
        final_url=final_url,
        title=title,
        paths_update={
            "raw_html_path": relpath(raw_path, p.out),
            "mhtml_path": mhtml_rel,
            "fetched_at": fetched_at,
        },
    )


def selectable_rows(conn: sqlite3.Connection, limit: int | None, retry_failed: bool) -> list[sqlite3.Row]:
    statuses = ["pending"]
    if retry_failed:
        statuses.append("failed")
    placeholders = ", ".join("?" for _ in statuses)
    sql = f"SELECT * FROM pages WHERE status IN ({placeholders}) ORDER BY input_order"
    if limit is not None:
        sql += " LIMIT ?"
        return list(conn.execute(sql, (*statuses, limit)))
    return list(conn.execute(sql, statuses))


def selectable_count(conn: sqlite3.Connection, retry_failed: bool) -> int:
    statuses = ["pending"]
    if retry_failed:
        statuses.append("failed")
    placeholders = ", ".join("?" for _ in statuses)
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM pages WHERE status IN ({placeholders})",
        statuses,
    ).fetchone()
    return int(row["n"])


def configure_pacing(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    pending = selectable_count(conn, args.retry_failed)
    args._pending_at_start = pending
    args._last_page_seconds = None
    args._target_seconds_per_page = None

    if args.delay is not None:
        average_delay = args.delay + (args.jitter / 2 if args.jitter > 0 else 0)
        print(f"Fixed wait: about {average_delay:.2f}s/page before load/capture.")
        return

    if args.target_hours is not None:
        if args.target_hours <= 0 or pending <= 0:
            print("No fixed wait or target pacing is enabled.")
            return
        args._target_seconds_per_page = (args.target_hours * 3600) / pending
        print(
            f"Target pace: {args._target_seconds_per_page:.2f}s/page "
            f"to finish {pending:,} pending URL(s) in about {args.target_hours:.1f}h."
        )
        print("If page load and MHTML capture take longer than that, the run will take longer.")
        return

    if args.target_seconds is None or args.target_seconds <= 0:
        print("No fixed wait or target pacing is enabled.")
        return
    args._target_seconds_per_page = args.target_seconds
    estimated_seconds = pending * args.target_seconds
    print(
        f"Target pace: {args._target_seconds_per_page:.2f}s/page "
        f"for {pending:,} pending URL(s), about {format_duration(estimated_seconds)}."
    )
    print("Page load and capture time count toward this pace; slower pages will not get extra waiting.")


def print_progress(
    conn: sqlite3.Connection,
    *,
    run_started: float,
    processed_this_run: int,
    page_seconds: float,
    args: argparse.Namespace,
) -> None:
    remaining = selectable_count(conn, args.retry_failed)
    elapsed = time.monotonic() - run_started
    average = elapsed / processed_this_run if processed_this_run else 0
    eta = average * remaining if average else 0
    target = getattr(args, "_target_seconds_per_page", None)
    target_text = f"; target {target:.2f}s/page" if target else ""
    print(
        f"Saved raw HTML and MHTML. Last page {page_seconds:.1f}s; "
        f"run average {average:.1f}s/page{target_text}; remaining {remaining:,}; "
        f"ETA {format_duration(eta)}."
    )


def scrape(args: argparse.Namespace) -> int:
    p = paths(args.out)
    conn = init_db(p)
    total = import_manifest(conn, args.csv)
    print(f"Manifest loaded: {total:,} URL(s)")
    configure_pacing(conn, args)

    playwright, context = launch_context(p.profile, args.channel, args.block_media)
    processed = 0
    run_started = time.monotonic()
    try:
        page = first_page(context)
        while True:
            rows = selectable_rows(conn, 1, args.retry_failed)
            if not rows:
                print("No pending URLs remain.")
                break
            if args.limit is not None and processed >= args.limit:
                print(f"Invocation limit reached: {processed}")
                break

            row = rows[0]
            url = str(row["canonical_url"])
            print(f"\n[{row['input_order']}/{total}] {url}")
            page_started = time.monotonic()
            try:
                scrape_one(conn, p, row, page, args)
            except AuthRequired as exc:
                if isinstance(exc, SessionRepairRequired):
                    clear_session_in_context(context, p)
                    print("Cleared the dedicated Which session cookies, storage, and auth marker.")
                update_page(conn, int(row["id"]), "pending", error=str(exc))
                alert_login_required(p, str(exc), gui_alert=not args.no_gui_alert)
                if args.no_prompt_login:
                    print(f"Stopped: {exc}")
                    return 2
                prompt_relogin(context, p, url)
                continue
            except SitePressure as exc:
                update_page(
                    conn,
                    int(row["id"]),
                    "pending",
                    error=str(exc),
                    retry_after_seconds=exc.retry_after_seconds,
                )
                alert_message = str(exc)
                if exc.retry_after_seconds is not None:
                    alert_message = f"{alert_message}\nRetry-After: {exc.retry_after_seconds}s"
                alert_scraper_stopped(p, alert_message, gui_alert=not args.no_gui_alert)
                print(f"Stopped safely: {exc}")
                if exc.retry_after_seconds is not None:
                    print(f"Retry-After: {exc.retry_after_seconds}s")
                return 3
            except UrlFailure as exc:
                update_page(conn, int(row["id"]), "failed", error=str(exc))
                print(f"Marked failed and continued: {exc}")
                processed += 1
                continue
            except KeyboardInterrupt:
                update_page(conn, int(row["id"]), "pending", error="Interrupted by user")
                print("\nInterrupted. Current URL is pending and the run can be resumed.")
                return 130

            processed += 1
            page_seconds = time.monotonic() - page_started
            args._last_page_seconds = page_seconds
            print_progress(
                conn,
                run_started=run_started,
                processed_this_run=processed,
                page_seconds=page_seconds,
                args=args,
            )
    finally:
        context.close()
        playwright.stop()
        conn.close()

    print("Scrape run finished. Raw captures are saved.")
    return 0


def status(args: argparse.Namespace) -> int:
    p = paths(args.out)
    conn = init_db(p)
    total = import_manifest(conn, args.csv)
    print(f"Manifest: {total:,} URL(s)")
    for row in conn.execute("SELECT status, COUNT(*) AS n FROM pages GROUP BY status ORDER BY status"):
        print(f"{row['status']}: {row['n']:,}")
    next_row = conn.execute(
        "SELECT input_order, canonical_url, error FROM pages WHERE status IN ('pending', 'in_progress') ORDER BY input_order LIMIT 1"
    ).fetchone()
    if next_row:
        print(f"Next: #{next_row['input_order']} {next_row['canonical_url']}")
        if next_row["error"]:
            print(f"Last note: {next_row['error']}")
    print(f"DB: {p.db}")
    print(f"Raw HTML: {p.raw_html}")
    print(f"MHTML: {p.mhtml}")
    conn.close()
    return 0


def reset(args: argparse.Namespace) -> int:
    p = paths(args.out)
    conn = init_db(p)
    import_manifest(conn, args.csv)
    if args.failed:
        with conn:
            changed = conn.execute(
                "UPDATE pages SET status='pending', error=NULL, updated_at=? WHERE status='failed'",
                (utc_now(),),
            ).rowcount
        print(f"Requeued {changed:,} failed page(s).")
    elif args.url:
        key = canonical_key(args.url)
        with conn:
            changed = conn.execute(
                "UPDATE pages SET status='pending', error=NULL, updated_at=? WHERE canonical_url=?",
                (utc_now(), key),
            ).rowcount
        print(f"Requeued {changed:,} page(s).")
    else:
        raise SystemExit("Choose --failed or --url.")
    conn.close()
    return 0


def login(args: argparse.Namespace) -> int:
    p = paths(args.out)
    conn = init_db(p)
    import_manifest(conn, args.csv)
    verification_url = args.verify_url
    if verification_url is None:
        row = conn.execute("SELECT canonical_url FROM pages ORDER BY input_order LIMIT 1").fetchone()
        verification_url = str(row["canonical_url"]) if row else f"https://{WHICH_HOST}/"
    conn.close()
    state = interactive_login(p, args.channel, verification_url, args.block_media)
    print(f"Verified login state: {state}")
    return 0


def clear_session(args: argparse.Namespace) -> int:
    p = paths(args.out)
    playwright, context = launch_context(p.profile, args.channel, args.block_media)
    try:
        clear_session_in_context(context, p)
    finally:
        context.close()
        playwright.stop()
    print("Cleared the dedicated Which browser session.")
    print("Raw scraped pages, MHTML files, metadata, and resume state were not changed.")
    print("Next: uv run python scraper.py login")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Raw, resumable Which scraper for the local which.csv.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    sub = parser.add_subparsers(dest="command", required=True)

    common_browser = argparse.ArgumentParser(add_help=False)
    common_browser.add_argument("--channel", default="chrome", help="chrome, msedge, or chromium/bundled")
    common_browser.add_argument("--block-media", action="store_true", help="Abort video/audio resource loads.")

    sub.add_parser("status").set_defaults(func=status)

    login_parser = sub.add_parser("login", parents=[common_browser])
    login_parser.add_argument("--verify-url", default=None)
    login_parser.set_defaults(func=login)

    clear_parser = sub.add_parser("clear-session", parents=[common_browser])
    clear_parser.set_defaults(func=clear_session)

    scrape_parser = sub.add_parser("scrape", parents=[common_browser])
    scrape_parser.add_argument("--limit", type=int, default=None)
    scrape_parser.add_argument(
        "--target-hours",
        type=float,
        default=None,
        help="Adaptive pacing target for the current pending set. Overrides --target-seconds unless --delay is set.",
    )
    scrape_parser.add_argument(
        "--target-seconds",
        type=float,
        default=DEFAULT_TARGET_SECONDS_PER_PAGE,
        help="Total target seconds per page including load/capture time. Set 0 to disable pacing.",
    )
    scrape_parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Fixed wait before each page. Overrides --target-seconds and --target-hours when set.",
    )
    scrape_parser.add_argument("--jitter", type=float, default=0.0)
    scrape_parser.add_argument("--settle", type=float, default=0.5)
    scrape_parser.add_argument("--timeout", type=int, default=60, help="Navigation timeout in seconds.")
    scrape_parser.add_argument("--retries", type=int, default=2)
    scrape_parser.add_argument("--backoff", type=float, default=30.0)
    scrape_parser.add_argument("--max-mhtml-mb", type=int, default=200)
    scrape_parser.add_argument("--retry-failed", action="store_true")
    scrape_parser.add_argument("--no-prompt-login", action="store_true")
    scrape_parser.add_argument("--no-gui-alert", action="store_true")
    scrape_parser.set_defaults(func=scrape)

    reset_parser = sub.add_parser("reset")
    reset_parser.add_argument("--failed", action="store_true")
    reset_parser.add_argument("--url", default=None)
    reset_parser.set_defaults(func=reset)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
