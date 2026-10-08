"""
article_fetcher.py

Retrieves a recent article from the GNews API and stores it as a local
text file for use by later stages of the AI Content Pipeline.

Responsibilities:
    - Search for recent articles using configurable keywords.
    - Ignore articles that have already been processed.
    - Save the selected article to the pipeline workspace.
    - Return the saved file path to the next pipeline stage.

This module can be run independently or called by the pipeline orchestrator.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import requests


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GNEWS_ENDPOINT = "https://gnews.io/api/v4/search"

# Keep credentials outside the source code.
# Example:
#   GNEWS_API_KEY=your_api_key_here
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

# Default locations used by the pipeline.
WORKSPACE_DIR = Path("workspace")
ARTICLE_DIR = WORKSPACE_DIR / "source_articles"
LOG_PATH = WORKSPACE_DIR / "state" / "article_history.json"

# Neutral default topics for the public/demo version of the pipeline.
# These can be overridden when calling fetch_next_article().
DEFAULT_KEYWORDS = [
    "technology",
    "artificial intelligence",
    "science",
    "business",
    "innovation",
]


# ---------------------------------------------------------------------------
# Article history
# ---------------------------------------------------------------------------

def create_article_hash(title: str) -> str:
    """
    Create a stable identifier for an article title.

    The identifier is stored in the article history so the same story
    is not processed repeatedly.
    """

    normalized_title = title.lower().strip()

    return hashlib.sha256(
        normalized_title.encode("utf-8")
    ).hexdigest()


def load_article_history() -> List[str]:
    """
    Load hashes of previously processed articles.
    
    Returns an empty list when no history file exists yet.
    """

    if not LOG_PATH.exists():
        return []

    try:
        with LOG_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError) as error:
        print(f"[FETCH] Could not read article history: {error}")
        return []


def save_article_history(history: List[str]) -> None:
    """
    Save the updated article history to disk.
    """

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with LOG_PATH.open("w", encoding="utf-8") as file:
        json.dump(history, file, indent=2)


# ---------------------------------------------------------------------------
# GNews retrieval
# ---------------------------------------------------------------------------

def fetch_next_article(
    keywords: Optional[List[str]] = None,
    max_results: int = 10,
) -> Optional[str]:
    """
    Fetch the first valid article that has not already been processed.

    Args:
        keywords:
            Search terms used to query GNews.
            If omitted, DEFAULT_KEYWORDS are used.

        max_results:
            Maximum number of articles requested from the API.

    Returns:
        The path to the saved article text file if an article is found.
        Returns None when no valid new article is available.
    """

    if not GNEWS_API_KEY:
        raise RuntimeError(
            "GNEWS_API_KEY is not configured. "
            "Add it to your environment before running the fetcher."
        )

    search_terms = keywords or DEFAULT_KEYWORDS
    query = " OR ".join(search_terms)

    params = {
        "q": query,
        "lang": "en",
        "country": "us",
        "max": max_results,
        "token": GNEWS_API_KEY,
    }

    print(f"[FETCH] Searching for: {query}")

    try:
        response = requests.get(
            GNEWS_ENDPOINT,
            params=params,
            timeout=10,
        )

        response.raise_for_status()
        data: Dict = response.json()

    except requests.RequestException as error:
        print(f"[FETCH] API request failed: {error}")
        return None

    except ValueError as error:
        print(f"[FETCH] Invalid JSON response: {error}")
        return None

    articles = data.get("articles", [])

    print(f"[FETCH] Received {len(articles)} candidate articles")

    article_history = load_article_history()

    # -----------------------------------------------------------------------
    # Select the first usable article that has not already been processed.
    # -----------------------------------------------------------------------

    for article in articles:

        title = article.get("title")
        description = article.get("description")

        source_data = article.get("source") or {}
        source_name = source_data.get("name", "Unknown")

        article_url = article.get("url", "")
        published_at = article.get("publishedAt", "")

        # Skip incomplete records.
        if not title or not description:
            continue

        article_hash = create_article_hash(title)

        # Skip stories already used in previous pipeline runs.
        if article_hash in article_history:
            print(f"[FETCH] Duplicate skipped: {title}")
            continue

        print(f"[FETCH] Selected article: {title}")

        # Store the article in a predictable, structured format.
        article_text = (
            f"Headline: {title}\n"
            f"Description: {description}\n"
            f"Source: {source_name}\n"
            f"URL: {article_url}\n"
            f"Published: {published_at}\n"
        )

        # Create the output directory if this is the first pipeline run.
        ARTICLE_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        article_path = ARTICLE_DIR / f"article_{timestamp}.txt"

        with article_path.open("w", encoding="utf-8") as file:
            file.write(article_text)

        # Record the article so future runs will not reuse it.
        article_history.append(article_hash)
        save_article_history(article_history)

        print(f"[FETCH] Article saved: {article_path}")

        return str(article_path)

    print("[FETCH] No new valid articles were found.")

    return None


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    saved_path = fetch_next_article()

    if saved_path:
        print(f"[FETCH] Complete: {saved_path}")
    else:
        print("[FETCH] No article returned.")