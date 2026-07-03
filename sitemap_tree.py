from __future__ import annotations

import argparse
import csv
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parent
DEFAULT_TREE_OUT = ROOT / "scraped" / "sitemap_tree.json"
DEFAULT_CSV_OUT = ROOT / "which_active_urls_only.csv"
WHICH_HOST_SUFFIX = "which.co.uk"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

ORDERED_SITEMAPS = [
    (
        "Product Hubs",
        "https://www.which.co.uk/product-hubs/sitemap/product-hub-pages-sitemap.xml",
    ),
    ("Glide Reviews", "https://www.which.co.uk/dispatch/glide-reviews-sitemap.xml"),
    ("Reviews", "https://www.which.co.uk/reviews/sitemaps/product-sitemap-index.xml"),
    ("Money", "https://www.which.co.uk/money/sitemap/money-sitemap.xml"),
    ("News", "https://www.which.co.uk/news/sitemaps/news.xml"),
    ("News Archive", "https://www.which.co.uk/news/sitemaps/news-archive.xml"),
    ("Videos", "https://www.which.co.uk/feeds/sitemaps/video-sitemap.xml"),
    (
        "Policy And Insight",
        "https://www.which.co.uk/dispatch/policy-and-insight-sitemap.xml",
    ),
]


def clean_tag(tag: str) -> str:
    return tag.split("}")[-1].lower()


def humanize_slug(value: str) -> str:
    value = re.sub(r"\.xml(?:\.gz)?$", "", value, flags=re.I)
    value = re.sub(r"(^|[-_])(sitemap|index|pages?|product|products|which)([-_]|$)", " ", value, flags=re.I)
    value = re.sub(r"[-_]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        value = "Pages"
    special = {"ai": "AI", "bbqs": "BBQs", "diy": "DIY", "sim": "SIM", "tvs": "TVs", "uk": "UK"}
    words = [special.get(word.lower(), word.capitalize()) for word in value.split()]
    return " ".join(words)


def label_from_sitemap_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if not name:
        parts = [part for part in parsed.path.split("/") if part]
        name = parts[-1] if parts else parsed.netloc
    return humanize_slug(name)


def is_which_page_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not (host == WHICH_HOST_SUFFIX or host.endswith(f".{WHICH_HOST_SUFFIX}")):
        return False
    return not parsed.path.lower().endswith((".xml", ".xml.gz"))


def node_template(label: str, url: str, node_type: str) -> dict[str, object]:
    return {
        "label": label,
        "url": url,
        "type": node_type,
        "children": [],
        "pages": [],
        "page_count": 0,
    }


def fetch_xml(url: str, timeout: int) -> ET.Element:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return ET.fromstring(response.content)


def loc_texts(node: ET.Element) -> list[str]:
    values: list[str] = []
    for child in node.iter():
        if clean_tag(child.tag) == "loc" and child.text:
            values.append(child.text.strip())
    return values


def parse_page(node: ET.Element) -> dict[str, str] | None:
    page: dict[str, str] = {}
    for child in node:
        tag = clean_tag(child.tag)
        if tag in {"loc", "lastmod", "changefreq", "priority"} and child.text:
            page[tag] = child.text.strip()
    url = page.get("loc")
    if not url or not is_which_page_url(url):
        return None
    return {"url": url, **{key: value for key, value in page.items() if key != "loc"}}


def fetch_sitemap_tree(
    url: str,
    *,
    label: str | None,
    delay: float,
    timeout: int,
    seen_sitemaps: set[str],
    seen_pages: set[str],
) -> dict[str, object]:
    if url in seen_sitemaps:
        return node_template(label or label_from_sitemap_url(url), url, "duplicate-sitemap")
    seen_sitemaps.add(url)

    print(f"Fetching sitemap: {url}")
    root = fetch_xml(url, timeout)
    root_tag = clean_tag(root.tag)
    node = node_template(label or label_from_sitemap_url(url), url, root_tag)

    if root_tag == "sitemapindex":
        for sitemap_node in root:
            if clean_tag(sitemap_node.tag) != "sitemap":
                continue
            locs = loc_texts(sitemap_node)
            if not locs:
                continue
            child_url = locs[0]
            time.sleep(delay)
            child = fetch_sitemap_tree(
                child_url,
                label=label_from_sitemap_url(child_url),
                delay=delay,
                timeout=timeout,
                seen_sitemaps=seen_sitemaps,
                seen_pages=seen_pages,
            )
            node["children"].append(child)
    elif root_tag == "urlset":
        for url_node in root:
            if clean_tag(url_node.tag) != "url":
                continue
            page = parse_page(url_node)
            if not page:
                continue
            page_url = str(page["url"])
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            node["pages"].append(page)
    else:
        for loc in loc_texts(root):
            if loc.endswith(".xml"):
                time.sleep(delay)
                child = fetch_sitemap_tree(
                    loc,
                    label=label_from_sitemap_url(loc),
                    delay=delay,
                    timeout=timeout,
                    seen_sitemaps=seen_sitemaps,
                    seen_pages=seen_pages,
                )
                node["children"].append(child)
            elif is_which_page_url(loc) and loc not in seen_pages:
                seen_pages.add(loc)
                node["pages"].append({"url": loc})

    node["page_count"] = len(node["pages"]) + sum(
        int(child.get("page_count", 0)) for child in node["children"]  # type: ignore[union-attr]
    )
    return node


def flatten_pages(node: dict[str, object]) -> list[str]:
    urls = [str(page["url"]) for page in node.get("pages", [])]  # type: ignore[index]
    for child in node.get("children", []):
        urls.extend(flatten_pages(child))  # type: ignore[arg-type]
    return urls


def write_csv(path: Path, urls: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["URL"])
        for url in urls:
            writer.writerow([url])


def build_tree(args: argparse.Namespace) -> int:
    seen_sitemaps: set[str] = set()
    seen_pages: set[str] = set()
    root = node_template("Which Sitemap", "ordered-sitemaps", "root")

    for label, url in ORDERED_SITEMAPS:
        time.sleep(args.delay)
        child = fetch_sitemap_tree(
            url,
            label=label,
            delay=args.delay,
            timeout=args.timeout,
            seen_sitemaps=seen_sitemaps,
            seen_pages=seen_pages,
        )
        root["children"].append(child)

    root["page_count"] = sum(int(child.get("page_count", 0)) for child in root["children"])  # type: ignore[union-attr]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(root, indent=2) + "\n", encoding="utf-8")

    urls = flatten_pages(root)
    write_csv(args.csv_out, urls)
    print(f"Wrote sitemap tree: {args.out}")
    print(f"Wrote flat URL CSV: {args.csv_out}")
    print(f"Unique pages: {len(urls):,}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Which sitemap indexes as a nested tree.")
    parser.add_argument("--out", type=Path, default=DEFAULT_TREE_OUT)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV_OUT)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    return build_tree(args)


if __name__ == "__main__":
    raise SystemExit(main())
