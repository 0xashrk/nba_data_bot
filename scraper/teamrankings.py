"""
TeamRankings.com scraper for Last-5 games form data.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd

URL = "https://www.teamrankings.com/nba/ranking/last-5-games-by-other"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def get_last5_form() -> pd.DataFrame:
    """
    Scrape Last-5 games form data from TeamRankings.

    Returns DataFrame with columns:
        - TEAM: Team name
        - L5_WINS: Wins in last 5 games
        - L5_LOSSES: Losses in last 5 games
        - L5_RATING: TeamRankings rating for last 5 games
    """
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    table = soup.find("table", class_="tr-table")

    if not table:
        raise ValueError("Could not find rankings table on page")

    rows = []
    tbody = table.find("tbody")

    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue

        # Column structure: Rank, Team, Rating, Record, etc.
        rank = cells[0].get_text(strip=True)
        team_cell = cells[1]
        team_name = team_cell.get_text(strip=True)
        rating = cells[2].get_text(strip=True)

        # Record is usually in format "X-Y" (wins-losses)
        record = cells[3].get_text(strip=True)

        # Parse wins/losses from record
        wins, losses = 0, 0
        if "-" in record:
            parts = record.split("-")
            try:
                wins = int(parts[0])
                losses = int(parts[1])
            except ValueError:
                pass

        rows.append({
            "TEAM": team_name,
            "L5_WINS": wins,
            "L5_LOSSES": losses,
            "L5_RATING": float(rating) if rating.replace(".", "").replace("-", "").isdigit() else None,
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = get_last5_form()
    print(df.to_string())
