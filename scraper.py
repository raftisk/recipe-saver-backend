"""
Recipe scraper module.

Usage (CLI):    uv run python scraper.py --url <url>
Usage (module): from scraper import scrape_url
"""

import argparse
import json

import httpx
from fastapi import HTTPException
from recipe_scrapers import scrape_html, scrape_me

from schemas import RecipeData


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _build_result(scraper, url: str, method: str | None) -> RecipeData:
    def safe(fn):
        try:
            result = fn()
            if result in (None, "", [], {}):
                return None
            return result
        except Exception:
            return None

    warnings = []
    fields = {
        "title": safe(scraper.title),
        "ingredients": safe(scraper.ingredients),
        "instructions": safe(scraper.instructions),
        "image": safe(scraper.image),
        "prep_time": safe(scraper.prep_time),
        "cook_time": safe(scraper.cook_time),
        "total_time": safe(scraper.total_time),
        "yields": safe(scraper.yields),
        "host": safe(scraper.host),
        "cuisine": safe(scraper.cuisine),
        "category": safe(scraper.category),
        "language": safe(scraper.language),
    }

    for field in ("title", "ingredients", "instructions"):
        if not fields[field]:
            warnings.append(f"Required field '{field}' is missing.")

    return RecipeData(url=url, method=method, warnings=warnings, **fields)


def scrape_url(url: str) -> RecipeData:
    """
    Scrape structured recipe data from the given URL.

    Retry chain (stops at first success):
      1. scrape_me(url) — standard scrape with built-in HTTP request
      2. scrape_html(html, org_url=url) with wild_mode disabled
      3. scrape_html(html, org_url=url, wild_mode=True) for more aggressive parsing

    Returns:
        RecipeData: Structured recipe information.

    Raises:
        HTTPException(422): If all three attempts fail.
    """
    last_error: Exception | None = None

    # Attempt 1: scrape_me (handles its own HTTP request)
    try:
        scraper = scrape_me(url)
        return _build_result(scraper, url, method="scrape_me")
    except Exception as e:
        last_error = e

    # Fetch HTML once for attempts 2 and 3
    html: str | None = None
    try:
        with httpx.Client(headers=_BROWSER_HEADERS, timeout=15, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.content.decode("utf-8", errors="replace")
    except Exception as e:
        last_error = e

    if html is not None:
        # Attempt 2: scrape_html strict
        try:
            scraper = scrape_html(html, org_url=url, wild_mode=False)
            return _build_result(scraper, url, method="scrape_html_strict")
        except Exception as e:
            last_error = e

        # Attempt 3: scrape_html wild_mode
        try:
            scraper = scrape_html(html, org_url=url, wild_mode=True)
            return _build_result(scraper, url, method="scrape_html_wild")
        except Exception as e:
            last_error = e

    raise HTTPException(
        status_code=422,
        detail=f"Failed to scrape recipe from {url!r}. Last error: {last_error}",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape a recipe from a URL.")
    parser.add_argument("--url", required=True, help="Full URL of the recipe page")
    args = parser.parse_args()

    try:
        result = scrape_url(args.url)
        print(result.model_dump_json(indent=2))
    except Exception as e:
        print(json.dumps({"error": type(e).__name__, "message": str(e)}, indent=2))
        raise SystemExit(1)
