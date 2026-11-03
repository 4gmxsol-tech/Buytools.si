#!/usr/bin/env python3
"""Smoke-test every public sitemap URL after GitHub Pages deployment."""
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import sys
import time
import xml.etree.ElementTree as ET


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = []
        self.in_title = False
        self.canonical = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical.append(attrs.get("href", "").strip())

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)


def get(url, attempts=4):
    last_error = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": "BuyTools-Site-Smoke-Test/1.0"})
            with urlopen(request, timeout=25) as response:
                return response.status, response.read().decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Could not fetch {url}: {last_error}")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: smoke_live.py <deployed-site-url>")
    base = sys.argv[1].rstrip("/") + "/"
    sitemap_url = urljoin(base, "sitemap.xml")
    status, sitemap_text = get(sitemap_url)
    if status != 200:
        raise RuntimeError(f"Sitemap returned HTTP {status}: {sitemap_url}")
    root = ET.fromstring(sitemap_text)
    urls = [node.text.strip() for node in root.findall(".//{*}loc") if node.text]
    if not urls:
        raise RuntimeError("Deployed sitemap contains no URLs.")

    failures = []
    for canonical_url in urls:
        path = urlparse(canonical_url).path.lstrip("/")
        live_url = urljoin(base, path)
        try:
            code, body = get(live_url)
            if code != 200:
                raise RuntimeError(f"HTTP {code}")
            parser = Metadata()
            parser.feed(body)
            title = "".join(parser.title).strip()
            if not title:
                raise RuntimeError("missing page title")
            if parser.canonical != [canonical_url]:
                raise RuntimeError(f"canonical mismatch: {parser.canonical}")
            print(f"OK {canonical_url}")
        except Exception as exc:
            failures.append(f"{canonical_url}: {exc}")
            print(f"FAIL {canonical_url}: {exc}")

    if failures:
        raise SystemExit(f"{len(failures)} of {len(urls)} sitemap URLs failed live smoke tests.")
    print(f"Live smoke tests passed: {len(urls)} sitemap URLs, HTTP 200 and matching canonical tags.")


if __name__ == "__main__":
    main()
