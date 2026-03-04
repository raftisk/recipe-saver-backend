"""
Recipe scraper module.

Usage (CLI):    uv run python scraper.py --url <url>
Usage (module): from scraper import scrape_recipe
"""

import argparse
import json
from typing import TypedDict

import requests
from recipe_scrapers import scrape_html

class NetworkError(Exception):
    """Raised when the recipe URL cannot be fetched (connection / HTTP error)."""


class ParsingError(Exception):
    """Raised when the page loads but recipe data cannot be extracted."""

class RecipeData(TypedDict):
    title: str | None
    ingredients: list[str] | None
    instructions: str | None
    image: str | None
    prep_time: int | None
    cook_time: int | None
    total_time: int | None
    yields: str | None
    host: str | None
    url: str
    cuisine: str | None
    category: str | None
    language: str | None
    wild_mode_used: bool
    warnings: list[str]

def scrape_recipe(url: str) -> RecipeData:
    """
    Scrape structured recipe data from the given URL.

    Args:
        url: The full URL of the recipe page.

    Returns:
        A RecipeData dict. Optional fields are None when absent.
        ``warnings`` lists any missing required fields (title, ingredients, instructions).

    Raises:
        NetworkError: If the URL cannot be fetched.
        ParsingError: If recipe data cannot be extracted from the page.
    """
    # Step 1: fetch raw HTML (network errors surface here)
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Failed to fetch {url!r}: {e}") from e

    html = response.text

    # Step 2: try strict parsing, fall back to wild mode on failure
    wild_mode_used = False
    try:
        scraper = scrape_html(html, org_url=url, wild_mode=False)
    except Exception:
        try:
            scraper = scrape_html(html, org_url=url, wild_mode=True)
            wild_mode_used = True
        except Exception as e:
            raise ParsingError(f"Failed to parse recipe at {url!r}: {e}") from e

    def safe(fn):
        """Call fn(), returning None on any exception or blank/empty result."""
        try:
            result = fn()
            if result in (None, "", [], {}):
                return None
            return result
        except Exception:
            return None

    data: RecipeData = {
        "title": safe(scraper.title),
        "ingredients": safe(scraper.ingredients),
        "instructions": safe(scraper.instructions),
        "image": safe(scraper.image),
        "prep_time": safe(scraper.prep_time),
        "cook_time": safe(scraper.cook_time),
        "total_time": safe(scraper.total_time),
        "yields": safe(scraper.yields),
        "host": safe(scraper.host),
        "url": url,
        "cuisine": safe(scraper.cuisine),
        "category": safe(scraper.category),
        "language": safe(scraper.language),
        "wild_mode_used": wild_mode_used,
        "warnings": [],
    }

    for field in ("title", "ingredients", "instructions"):
        if not data[field]:  # type: ignore[literal-required]
            data["warnings"].append(f"Required field '{field}' is missing.")

    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape a recipe from a URL.")
    parser.add_argument("--url", required=True, help="Full URL of the recipe page")
    args = parser.parse_args()

    try:
        result = scrape_recipe(args.url)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (NetworkError, ParsingError) as e:
        print(json.dumps({"error": type(e).__name__, "message": str(e)}, indent=2))
        raise SystemExit(1)
