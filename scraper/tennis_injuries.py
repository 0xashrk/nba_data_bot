"""
Keyword-based tennis injury signal scraper.
"""

from datetime import datetime, timedelta, timezone
import re

import pandas as pd

from .tennis_common import DEFAULT_TOURS, SITE_API_BASE, TOUR_LABELS, fetch_json, normalize_tours, tour_slug


DEFAULT_INJURY_KEYWORDS = (
    "injury",
    "injured",
    "withdraw",
    "withdraws",
    "withdrawn",
    "withdrew",
    "withdrawal",
    "retire due to",
    "retired due to",
    "retired with",
    "illness",
    "ankle injury",
    "ankle pain",
    "arm injury",
    "back pain",
    "back spasms",
    "elbow injury",
    "hamstring injury",
    "hip injury",
    "knee injury",
    "knee issue",
    "knee pain",
    "shoulder injury",
    "wrist injury",
)

EXCLUSION_PATTERNS = (
    r"\bback-to-back\b",
    r"\bforearm\b",
)

INJURY_COLUMNS = [
    "TOUR",
    "ARTICLE_ID",
    "PLAYER_ID",
    "PLAYER",
    "HEADLINE",
    "DESCRIPTION",
    "PUBLISHED_UTC",
    "URL",
    "SIGNAL_KEYWORDS",
]


def _match_injury_keywords(haystack: str, keywords: tuple[str, ...]) -> list[str]:
    """Match injury keywords after removing common false-positive phrases."""
    if not haystack:
        return []

    filtered_text = haystack
    for pattern in EXCLUSION_PATTERNS:
        filtered_text = re.sub(pattern, " ", filtered_text, flags=re.IGNORECASE)

    matches = set()
    for keyword in keywords:
        pattern = rf"\b{re.escape(keyword)}\b"
        matches.update(match.group(0).lower() for match in re.finditer(pattern, filtered_text, re.IGNORECASE))

    return sorted(matches)


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO timestamp into a timezone-aware datetime."""
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_tennis_injuries(
    tours: tuple[str, ...] = DEFAULT_TOURS,
    keywords: tuple[str, ...] = DEFAULT_INJURY_KEYWORDS,
    lookback_days: int | None = 14,
) -> pd.DataFrame:
    """
    Fetch tennis injury signals from ESPN news headlines and blurbs.

    TODO: Replace this heuristic with a structured injury/withdrawal feed if one
    becomes reliably available without authentication.
    """
    rows = []
    seen_rows = set()
    cutoff = None
    if lookback_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    for tour in normalize_tours(tours):
        news_url = f"{SITE_API_BASE}/{tour_slug(tour)}/news"
        payload = fetch_json(news_url)

        for article in payload.get("articles", []):
            published = article.get("published") or article.get("lastModified")
            published_dt = _parse_timestamp(published)
            if cutoff is not None and published_dt is not None and published_dt < cutoff:
                continue

            headline = article.get("headline", "")
            description = article.get("description", "")
            haystack = " ".join(part for part in [headline, description] if part)
            matches = _match_injury_keywords(haystack, keywords)
            if not matches:
                continue

            athletes = [item for item in article.get("categories", []) if item.get("type") == "athlete"]
            if not athletes:
                athletes = [{"athleteId": None, "description": None}]

            for athlete in athletes:
                row_key = (article.get("id"), athlete.get("athleteId"))
                if row_key in seen_rows:
                    continue

                seen_rows.add(row_key)
                rows.append(
                    {
                        "TOUR": TOUR_LABELS.get(tour, tour),
                        "ARTICLE_ID": article.get("id"),
                        "PLAYER_ID": str(athlete.get("athleteId")) if athlete.get("athleteId") is not None else None,
                        "PLAYER": athlete.get("description"),
                        "HEADLINE": headline,
                        "DESCRIPTION": description,
                        "PUBLISHED_UTC": published_dt.isoformat() if published_dt else published,
                        "URL": article.get("links", {}).get("web", {}).get("href"),
                        "SIGNAL_KEYWORDS": ",".join(matches),
                    }
                )

    if not rows:
        return pd.DataFrame(columns=INJURY_COLUMNS)

    df = pd.DataFrame(rows)
    return df.sort_values(["PUBLISHED_UTC", "TOUR", "PLAYER"], ascending=[False, True, True]).reset_index(drop=True)


def get_tennis_injury_report(
    tours: tuple[str, ...] = DEFAULT_TOURS,
    keywords: tuple[str, ...] = DEFAULT_INJURY_KEYWORDS,
    lookback_days: int | None = 14,
) -> pd.DataFrame:
    """Backward-compatible alias for news-based injury signals."""
    return get_tennis_injuries(tours=tours, keywords=keywords, lookback_days=lookback_days)
