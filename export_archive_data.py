from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from html import escape as html_escape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "which.csv"
DEFAULT_OUT = ROOT / "scraped"
DEFAULT_TARGET = ROOT / "archive-web" / "static" / "data" / "archive.json"
DEFAULT_STATIC_ROOT = ROOT / "archive-web" / "static"
WHICH_HOST = "www.which.co.uk"

# Hrefs that are not navigable page links and must be left untouched.
SKIP_HREF_PREFIXES = ("#", "javascript:", "mailto:", "tel:", "sms:", "data:", "blob:", "about:")


def is_which_host(host: str) -> bool:
    """True for which.co.uk and any of its content subdomains."""
    host = host.lower()
    return host == "which.co.uk" or host.endswith(".which.co.uk")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


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


def import_bs4() -> Any:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("Install dependencies first: uv pip install -r requirements.txt") from exc
    return BeautifulSoup


def path_from_rel(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    return root / Path(value)


def humanize_slug(value: str) -> str:
    text = re.sub(r"[-_]+", " ", value).strip()
    special = {
        "ai": "AI",
        "bbqs": "BBQs",
        "diy": "DIY",
        "gps": "GPS",
        "hd": "HD",
        "oled": "OLED",
        "pc": "PC",
        "pcs": "PCs",
        "sim": "SIM",
        "tvs": "TVs",
        "uk": "UK",
        "usb": "USB",
        "wifi": "Wi-Fi",
    }
    words = []
    for word in text.split():
        lowered = word.lower()
        words.append(special.get(lowered, word.capitalize()))
    return " ".join(words) or "Index"


def strip_which_id(slug: str) -> str:
    parts = slug.split("-")
    if len(parts) < 2:
        return slug
    tail = parts[-1]
    if re.fullmatch(r"[a-zA-Z0-9]{8,}", tail) and any(char.isdigit() for char in tail):
        return "-".join(parts[:-1])
    return slug


def clean_title(value: str) -> str:
    title = re.sub(r"\s+", " ", value).strip()
    title = re.sub(r"\s*\|\s*Which\??\s*$", "", title, flags=re.IGNORECASE)
    return title


def page_label_from_url(url: str) -> str:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    if not parts:
        return "Home"
    slug = strip_which_id(parts[-1])
    if len(parts) >= 4 and parts[0] == "reviews" and parts[2] == "article":
        return humanize_slug(slug)
    if len(parts) >= 2 and parts[0] == "reviews":
        return humanize_slug(slug) if len(parts) > 2 else f"{humanize_slug(parts[1])} Reviews"
    return humanize_slug(slug)


def category_path_for_url(url: str) -> list[str]:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    if not parts:
        return ["Other"]

    first = parts[0]
    if first == "reviews":
        path = ["Reviews"]
        if len(parts) >= 2:
            path.append(humanize_slug(parts[1]))
        return path

    if first == "l":
        path = ["Product Hubs"]
        if len(parts) >= 2:
            path.append(humanize_slug(parts[1]))
        if len(parts) >= 3:
            path.extend(humanize_slug(part) for part in parts[2:-1])
        return path

    if first == "policy-and-insight":
        return ["Policy And Insight"]

    return [humanize_slug(first)]


def page_type_for_url(url: str) -> str:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    slug = parts[-1].lower() if parts else ""
    if len(parts) >= 3 and parts[0] == "reviews" and parts[2] == "article":
        if is_best_or_top_url(url):
            return "Best guide"
        if slug.startswith("how-to-buy"):
            return "Buying guide"
        if slug.startswith("how-we-test"):
            return "How we test"
        if slug == "guides":
            return "Guide hub"
        return "Guide"
    if parts and parts[0] == "reviews":
        return "Review hub"
    if parts and parts[0] == "l":
        return "Product hub"
    if parts and parts[0] == "policy-and-insight":
        return "Policy"
    return "Page"


def is_best_or_top_url(url: str) -> bool:
    slug = urlsplit(url).path.rstrip("/").split("/")[-1].lower()
    return bool(
        slug.startswith(("best-", "top-", "top-five-", "which-"))
        or "-best-" in slug
        or "-top-" in slug
        or "best-buy" in slug
    )


def is_featured(title: str, url: str) -> bool:
    lowered = title.lower()
    return is_best_or_top_url(url) or lowered.startswith(("best ", "top ", "which "))


def stable_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


# Card metadata (title/description/image) is expensive to parse for every
# capture, so it is cached by relative path + file signature. Repeat exports
# only re-parse captures whose source file actually changed.
_META_CACHE: dict[str, dict[str, str]] = {}
_META_FIELDS = ("title", "description", "image")


def load_meta_cache(out_dir: Path) -> None:
    global _META_CACHE
    path = out_dir / ".meta-cache.json"
    if path.exists():
        with suppress(Exception):
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                _META_CACHE = loaded


def save_meta_cache(out_dir: Path) -> None:
    with suppress(Exception):
        (out_dir / ".meta-cache.json").write_text(
            json.dumps(_META_CACHE), encoding="utf-8"
        )


def extract_raw_metadata(root: Path, row: sqlite3.Row | None) -> dict[str, str]:
    if row is None:
        return {}
    rel = str(row["raw_html_path"] or "")
    raw_path = path_from_rel(root, rel)
    if raw_path is None or not raw_path.exists():
        return {}
    try:
        stat = raw_path.stat()
        signature = f"{int(stat.st_mtime)}:{stat.st_size}"
    except OSError:
        signature = ""
    cached = _META_CACHE.get(rel)
    if signature and cached and cached.get("sig") == signature:
        return {field: cached[field] for field in _META_FIELDS if cached.get(field)}
    data: dict[str, str] = {}
    with suppress(Exception):
        BeautifulSoup = import_bs4()
        soup = BeautifulSoup(raw_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
        for key, selectors in {
            "title": [
                ('meta[property="og:title"]', "content"),
                ("title", None),
                ("h1", None),
            ],
            "description": [
                ('meta[name="description"]', "content"),
                ('meta[property="og:description"]', "content"),
            ],
            "image": [
                ('meta[property="og:image"]', "content"),
                ('meta[name="twitter:image"]', "content"),
                ('link[rel="image_src"]', "href"),
                ("img[src]", "src"),
            ],
        }.items():
            for selector, attr in selectors:
                tag = soup.select_one(selector)
                if not tag:
                    continue
                value = str(tag.get(attr, "") if attr else tag.get_text(" ", strip=True)).strip()
                if not value or value.startswith("data:"):
                    continue
                data[key] = value
                break
    if signature:
        _META_CACHE[rel] = {"sig": signature, **data}
    return data


def load_db_rows(db_path: Path) -> dict[str, sqlite3.Row]:
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return {
            str(row["canonical_url"]): row
            for row in conn.execute("SELECT * FROM pages ORDER BY input_order")
        }
    finally:
        conn.close()


def capture_url(rel_value: str) -> str:
    if not rel_value:
        return ""
    return "/" + (Path("captures") / Path(rel_value)).as_posix()


# --- Link-rewrite pipeline -------------------------------------------------
#
# Inside every captured page we want:
#   * links to pages that were ALSO scraped  -> the local captured copy
#   * links to Which pages that were NOT scraped -> the real, absolute live URL
#   * links to anything else (external hosts) -> left exactly as they are
#
# This lets a human browse the archive as a self-contained mirror: following a
# link stays local when we have the target, and falls back to live Which only
# when we do not. Root-relative ("/foo") and protocol-relative ("//host/foo")
# Which links are resolved to absolute live URLs so they never resolve against
# the local dev server.


def build_capture_map(records: list[dict[str, Any]]) -> dict[str, str]:
    """Map canonical URL -> local capture URL for every downloaded page."""
    mapping: dict[str, str] = {}
    for record in records:
        if record.get("status") != "downloaded":
            continue
        local = str(record.get("localHtmlUrl") or "")
        if not local:
            continue
        for candidate in (record.get("url"), record.get("finalUrl")):
            if candidate:
                mapping.setdefault(canonical_key(str(candidate)), local)
    return mapping


def archive_banner_html(record: dict[str, Any]) -> str:
    """A slim, self-contained bar prepended to each captured page."""
    original = html_escape(str(record.get("url") or ""), quote=True)
    title = html_escape(str(record.get("title") or "Archived page"))
    fetched = str(record.get("fetchedAt") or "")
    fetched_txt = f" &middot; captured {html_escape(fetched[:10])}" if fetched else ""
    outer = (
        "all:initial;display:block;box-sizing:border-box;width:100%;"
        "background:#0b706f;color:#fff;font-family:Inter,system-ui,-apple-system,"
        "'Segoe UI',sans-serif;font-size:14px;line-height:1.4;padding:8px 14px;"
        "border-bottom:2px solid #075e5d;position:relative;z-index:2147483647;"
    )
    inner = (
        "display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;"
        "max-width:1200px;margin:0 auto;"
    )
    return (
        f'<div id="which-archive-bar" style="{outer}">'
        f'<div style="{inner}">'
        f'<a href="/" target="_top" style="color:#fff;font-weight:800;'
        f'text-decoration:none;">&#8962; Which Archive</a>'
        f'<span style="opacity:.75;overflow:hidden;text-overflow:ellipsis;'
        f'white-space:nowrap;max-width:60%;">{title}{fetched_txt}</span>'
        f'<a href="{original}" target="_blank" rel="noreferrer noopener" '
        f'style="margin-left:auto;color:#fff;font-weight:700;'
        f'text-decoration:underline;">View live original &#8599;</a>'
        f"</div></div>"
    )


def rewrite_capture(
    html: str,
    record: dict[str, Any],
    capture_map: dict[str, str],
    *,
    inject_banner: bool,
) -> str:
    BeautifulSoup = import_bs4()
    soup = BeautifulSoup(html, "html.parser")
    base_url = str(record.get("finalUrl") or record.get("url") or "")
    for anchor in soup.find_all("a", href=True):
        raw_href = (anchor.get("href") or "").strip()
        if not raw_href or raw_href.lower().startswith(SKIP_HREF_PREFIXES):
            continue
        try:
            absolute = urljoin(base_url, raw_href)
        except ValueError:
            continue
        parts = urlsplit(absolute)
        if parts.scheme not in ("http", "https"):
            continue
        local = capture_map.get(canonical_key(absolute))
        if local:
            anchor["href"] = f"{local}#{parts.fragment}" if parts.fragment else local
            anchor["data-archive"] = "local"
        elif is_which_host(parts.netloc):
            anchor["href"] = absolute
            anchor["data-archive"] = "live"
        # external anchors are intentionally left untouched
    if inject_banner and soup.body is not None and not soup.find(id="which-archive-bar"):
        soup.body.insert(0, BeautifulSoup(archive_banner_html(record), "html.parser"))
    return str(soup)


def _read_rewrite_signature(state_path: Path) -> str:
    if not state_path.exists():
        return ""
    with suppress(Exception):
        return str(json.loads(state_path.read_text(encoding="utf-8")).get("signature", ""))
    return ""


def page_record(index: int, url: str, row: sqlite3.Row | None, out_dir: Path) -> dict[str, Any]:
    raw_meta = extract_raw_metadata(out_dir, row)
    final_url = str(row["final_url"] or url) if row is not None else url
    title = clean_title(str(row["title"] or "")) if row is not None else ""
    title = clean_title(raw_meta.get("title", "")) or title or page_label_from_url(url)
    description = clean_title(raw_meta.get("description", ""))
    image = raw_meta.get("image", "")
    if image:
        image = normalise_url(image, base=final_url)
    status = str(row["status"]) if row is not None else "pending"
    raw_html_path = str(row["raw_html_path"] or "") if row is not None else ""
    mhtml_path = str(row["mhtml_path"] or "") if row is not None else ""
    page_type = page_type_for_url(url)
    category_path = category_path_for_url(url)
    has_raw_capture = bool(raw_html_path and (out_dir / Path(raw_html_path)).exists())
    has_mhtml_capture = bool(mhtml_path and (out_dir / Path(mhtml_path)).exists())
    return {
        "id": stable_id(url),
        "order": int(row["input_order"]) if row is not None else index,
        "url": url,
        "finalUrl": final_url,
        "status": status,
        "httpStatus": int(row["http_status"]) if row is not None and row["http_status"] is not None else None,
        "title": title,
        "description": description,
        "image": image,
        "type": page_type,
        "categoryPath": category_path,
        "featured": is_featured(title, url),
        "downloaded": status == "downloaded",
        "error": str(row["error"] or "") if row is not None else "",
        "fetchedAt": str(row["fetched_at"] or "") if row is not None else "",
        "rawHtmlPath": raw_html_path,
        "mhtmlPath": mhtml_path,
        "localHtmlUrl": capture_url(raw_html_path) if has_raw_capture else "",
        "localMhtmlUrl": capture_url(mhtml_path) if has_mhtml_capture else "",
    }


def summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    types: dict[str, int] = {}
    for record in records:
        counts[record["status"]] = counts.get(record["status"], 0) + 1
        types[record["type"]] = types.get(record["type"], 0) + 1
    return {
        "total": len(records),
        "counts": counts,
        "types": types,
        "featured": sum(1 for record in records if record["featured"]),
        "withImages": sum(1 for record in records if record["image"]),
        "withLocalCaptures": sum(1 for record in records if record["localHtmlUrl"]),
    }


def publish_file(src: Path, dest: Path) -> bool:
    if not src.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        try:
            src_stat = src.stat()
            dest_stat = dest.stat()
            if dest_stat.st_size == src_stat.st_size and dest_stat.st_mtime >= src_stat.st_mtime:
                return False
        except OSError:
            pass
        dest.unlink()
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)
    return True


def _write_text_atomic(dest: Path, text: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".partial")
    partial.write_text(text, encoding="utf-8")
    partial.replace(dest)


def publish_captures(
    records: list[dict[str, Any]],
    out_dir: Path,
    static_root: Path,
    *,
    rewrite: bool = True,
    banner: bool = True,
    force: bool = False,
) -> dict[str, int]:
    """Publish captures into the web app's static tree.

    Raw HTML is link-rewritten (see rewrite_capture); MHTML is copied verbatim
    for fidelity. Because a rewrite depends on the whole set of scraped URLs, a
    full re-pass runs whenever that set changes; otherwise only new/changed
    source files are re-published.
    """
    captures_root = static_root / "captures"
    capture_map = build_capture_map(records) if rewrite else {}
    signature = (
        hashlib.sha256("\n".join(sorted(capture_map)).encode("utf-8")).hexdigest()
        if rewrite
        else ""
    )
    state_path = captures_root / ".rewrite-state.json"
    full_pass = force or (rewrite and signature != _read_rewrite_signature(state_path))
    stats = {"rewritten": 0, "copied": 0, "skipped": 0}
    total_raw = sum(1 for r in records if r.get("rawHtmlPath"))
    done = 0

    for record in records:
        raw_rel = str(record.get("rawHtmlPath") or "")
        if raw_rel:
            src = out_dir / Path(raw_rel)
            dest = captures_root / Path(raw_rel)
            if src.exists():
                if not rewrite:
                    stats["copied" if publish_file(src, dest) else "skipped"] += 1
                elif (
                    full_pass
                    or not dest.exists()
                    or src.stat().st_mtime > dest.stat().st_mtime
                ):
                    content = src.read_text(encoding="utf-8", errors="replace")
                    _write_text_atomic(
                        dest, rewrite_capture(content, record, capture_map, inject_banner=banner)
                    )
                    stats["rewritten"] += 1
                else:
                    stats["skipped"] += 1
            done += 1
            if total_raw and done % 500 == 0:
                print(f"  ...processed {done:,}/{total_raw:,} captures", flush=True)

        mhtml_rel = str(record.get("mhtmlPath") or "")
        if mhtml_rel:
            src = out_dir / Path(mhtml_rel)
            dest = captures_root / Path(mhtml_rel)
            if src.exists() and publish_file(src, dest):
                stats["copied"] += 1

    if rewrite:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"signature": signature, "generatedAt": utc_now()}),
            encoding="utf-8",
        )
    return stats


def write_json_atomic(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".partial")
    partial.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    partial.replace(target)


def export_data(args: argparse.Namespace) -> int:
    urls = read_urls(args.csv)
    db_rows = load_db_rows(args.out / "manifest.sqlite")
    load_meta_cache(args.out)
    records = [
        page_record(index, url, db_rows.get(url), args.out)
        for index, url in enumerate(urls, start=1)
    ]
    save_meta_cache(args.out)
    payload = {
        "generatedAt": utc_now(),
        "sourceCsv": str(args.csv),
        "summary": summarise(records),
        "pages": records,
    }
    write_json_atomic(args.target, payload)
    print(f"Exported {len(records):,} page record(s) to {args.target}")
    stats = publish_captures(
        records,
        args.out,
        args.static_root,
        rewrite=not args.no_rewrite,
        banner=not args.no_banner,
        force=args.force_rewrite,
    )
    mode = "verbatim copy" if args.no_rewrite else "link-rewritten"
    print(
        f"Captures ({mode}): {stats['rewritten']:,} written, "
        f"{stats['copied']:,} copied, {stats['skipped']:,} unchanged "
        f"under {args.static_root / 'captures'}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export scraper state for the archive frontend.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--static-root", type=Path, default=DEFAULT_STATIC_ROOT)
    parser.add_argument(
        "--no-rewrite",
        action="store_true",
        help="Publish raw captures verbatim instead of rewriting their links.",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Do not inject the archive navigation bar into captures.",
    )
    parser.add_argument(
        "--force-rewrite",
        action="store_true",
        help="Re-rewrite every capture even if nothing changed.",
    )
    parser.set_defaults(func=export_data)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
