"""
NBA Injury Report scraper.

Fetches the latest injury report PDF from the official NBA injury report hub
and parses player injury status by team.
"""

import re
import requests
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd
from io import BytesIO
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

HUB_URL = "https://official.nba.com/nba-injury-report-2025-26-season/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# Valid injury statuses
STATUSES = {"OUT", "DOUBTFUL", "QUESTIONABLE", "PROBABLE", "AVAILABLE", "NOT YET SUBMITTED"}


@dataclass
class InjuryEntry:
    game_date: str
    game_time: str
    matchup: str
    team: str
    player_name: str
    current_status: str
    reason: str


def get_latest_pdf_url() -> Optional[str]:
    """
    Scrape the injury report hub page to find the latest PDF link.

    Returns:
        URL to the most recent injury report PDF, or None if not found.
    """
    response = requests.get(HUB_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # Find all PDF links - they follow pattern like:
    # https://ak-static.cms.nba.com/referee/injury/Injury-Report_YYYY-MM-DD_HH_MMAM.pdf
    pdf_links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "Injury-Report" in href and href.endswith(".pdf"):
            pdf_links.append(href)

    if not pdf_links:
        # Try finding links in the page content another way
        # Sometimes they're in paragraph text
        text = soup.get_text()
        pattern = r'https://ak-static\.cms\.nba\.com/referee/injury/Injury-Report[^\s"\'<>]+'
        matches = re.findall(pattern, str(soup))
        pdf_links.extend(matches)

    if not pdf_links:
        return None

    # Sort by timestamp in filename to get latest
    # Filename format: Injury-Report_2026-01-16_09_00AM.pdf
    def extract_timestamp(url: str) -> datetime:
        try:
            match = re.search(r"Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)", url)
            if match:
                date_str = match.group(1)
                hour = int(match.group(2))
                minute = int(match.group(3))
                ampm = match.group(4)

                if ampm == "PM" and hour != 12:
                    hour += 12
                elif ampm == "AM" and hour == 12:
                    hour = 0

                return datetime.strptime(f"{date_str} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")
        except Exception:
            pass
        return datetime.min

    pdf_links.sort(key=extract_timestamp, reverse=True)
    return pdf_links[0]


def parse_injury_pdf(pdf_url: str) -> list[InjuryEntry]:
    """
    Download and parse an injury report PDF.

    Args:
        pdf_url: URL to the injury report PDF

    Returns:
        List of InjuryEntry objects
    """
    response = requests.get(pdf_url, headers=HEADERS, timeout=60)
    response.raise_for_status()

    entries = []

    with pdfplumber.open(BytesIO(response.content)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()

            for table in tables:
                if not table:
                    continue

                for row in table:
                    if not row or len(row) < 5:
                        continue

                    # Skip header rows
                    if row[0] and "Game Date" in str(row[0]):
                        continue

                    # Typical columns: Game Date, Game Time, Matchup, Team, Player Name,
                    #                  Current Status, Reason
                    try:
                        # Clean up cell values
                        cells = [str(c).strip() if c else "" for c in row]

                        # Skip empty rows
                        if not any(cells):
                            continue

                        # Handle different column arrangements
                        if len(cells) >= 7:
                            game_date = cells[0]
                            game_time = cells[1]
                            matchup = cells[2]
                            team = cells[3]
                            player_name = cells[4]
                            current_status = cells[5].upper()
                            reason = cells[6]
                        elif len(cells) >= 5:
                            # Condensed format
                            game_date = cells[0]
                            matchup = cells[1]
                            team = cells[2]
                            player_name = cells[3]
                            current_status = cells[4].upper() if len(cells) > 4 else ""
                            game_time = ""
                            reason = cells[5] if len(cells) > 5 else ""
                        else:
                            continue

                        # Validate this looks like real data
                        if not player_name or player_name.lower() in ["player name", "none", ""]:
                            continue

                        entries.append(InjuryEntry(
                            game_date=game_date,
                            game_time=game_time,
                            matchup=matchup,
                            team=team,
                            player_name=player_name,
                            current_status=current_status,
                            reason=reason,
                        ))

                    except Exception:
                        continue

    return entries


def get_injury_report() -> pd.DataFrame:
    """
    Get the latest injury report as a DataFrame.

    Returns:
        DataFrame with columns:
            - GAME_DATE, GAME_TIME, MATCHUP, TEAM
            - PLAYER_NAME, CURRENT_STATUS, REASON
    """
    pdf_url = get_latest_pdf_url()

    if not pdf_url:
        raise ValueError("Could not find injury report PDF on hub page")

    entries = parse_injury_pdf(pdf_url)

    if not entries:
        return pd.DataFrame(columns=[
            "GAME_DATE", "GAME_TIME", "MATCHUP", "TEAM",
            "PLAYER_NAME", "CURRENT_STATUS", "REASON"
        ])

    df = pd.DataFrame([
        {
            "GAME_DATE": e.game_date,
            "GAME_TIME": e.game_time,
            "MATCHUP": e.matchup,
            "TEAM": e.team,
            "PLAYER_NAME": e.player_name,
            "CURRENT_STATUS": e.current_status,
            "REASON": e.reason,
        }
        for e in entries
    ])

    return df


def summarize_by_team(df: pd.DataFrame) -> dict:
    """
    Summarize injury report by team with player counts per status.

    Args:
        df: Injury report DataFrame

    Returns:
        Dict mapping team -> {status -> [player_names]}
    """
    summary = {}

    for team in df["TEAM"].unique():
        team_df = df[df["TEAM"] == team]
        team_summary = {}

        for status in ["OUT", "DOUBTFUL", "QUESTIONABLE", "PROBABLE"]:
            players = team_df[team_df["CURRENT_STATUS"] == status]["PLAYER_NAME"].tolist()
            if players:
                team_summary[status] = players

        if team_summary:
            summary[team] = team_summary

    return summary


if __name__ == "__main__":
    print("Fetching latest injury report...")
    pdf_url = get_latest_pdf_url()
    print(f"Found PDF: {pdf_url}")

    if pdf_url:
        df = get_injury_report()
        print(f"\nFound {len(df)} injury entries")
        print(df.head(20).to_string())

        print("\n=== Summary by Team ===")
        summary = summarize_by_team(df)
        for team, statuses in summary.items():
            print(f"\n{team}:")
            for status, players in statuses.items():
                print(f"  {status}: {', '.join(players)}")
