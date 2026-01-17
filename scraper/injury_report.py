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


NBA_TEAMS = {
    "AtlantaHawks", "BostonCeltics", "BrooklynNets", "CharlotteHornets",
    "ChicagoBulls", "ClevelandCavaliers", "DallasMavericks", "DenverNuggets",
    "DetroitPistons", "GoldenStateWarriors", "HoustonRockets", "IndianaPacers",
    "LAClippers", "LosAngelesLakers", "MemphisGrizzlies", "MiamiHeat",
    "MilwaukeeBucks", "MinnesotaTimberwolves", "NewOrleansPelicans",
    "NewYorkKnicks", "OklahomaCityThunder", "OrlandoMagic", "Philadelphia76ers",
    "PhoenixSuns", "PortlandTrailBlazers", "SacramentoKings", "SanAntonioSpurs",
    "TorontoRaptors", "UtahJazz", "WashingtonWizards",
}

TEAM_NAME_MAP = {
    "AtlantaHawks": "Atlanta Hawks",
    "BostonCeltics": "Boston Celtics",
    "BrooklynNets": "Brooklyn Nets",
    "CharlotteHornets": "Charlotte Hornets",
    "ChicagoBulls": "Chicago Bulls",
    "ClevelandCavaliers": "Cleveland Cavaliers",
    "DallasMavericks": "Dallas Mavericks",
    "DenverNuggets": "Denver Nuggets",
    "DetroitPistons": "Detroit Pistons",
    "GoldenStateWarriors": "Golden State Warriors",
    "HoustonRockets": "Houston Rockets",
    "IndianaPacers": "Indiana Pacers",
    "LAClippers": "LA Clippers",
    "LosAngelesLakers": "Los Angeles Lakers",
    "MemphisGrizzlies": "Memphis Grizzlies",
    "MiamiHeat": "Miami Heat",
    "MilwaukeeBucks": "Milwaukee Bucks",
    "MinnesotaTimberwolves": "Minnesota Timberwolves",
    "NewOrleansPelicans": "New Orleans Pelicans",
    "NewYorkKnicks": "New York Knicks",
    "OklahomaCityThunder": "Oklahoma City Thunder",
    "OrlandoMagic": "Orlando Magic",
    "Philadelphia76ers": "Philadelphia 76ers",
    "PhoenixSuns": "Phoenix Suns",
    "PortlandTrailBlazers": "Portland Trail Blazers",
    "SacramentoKings": "Sacramento Kings",
    "SanAntonioSpurs": "San Antonio Spurs",
    "TorontoRaptors": "Toronto Raptors",
    "UtahJazz": "Utah Jazz",
    "WashingtonWizards": "Washington Wizards",
}


def parse_injury_pdf(pdf_url: str) -> list[InjuryEntry]:
    """
    Download and parse an injury report PDF using text extraction.

    Args:
        pdf_url: URL to the injury report PDF

    Returns:
        List of InjuryEntry objects
    """
    response = requests.get(pdf_url, headers=HEADERS, timeout=60)
    response.raise_for_status()

    entries = []

    with pdfplumber.open(BytesIO(response.content)) as pdf:
        # Extract all text from all pages
        all_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text += text + "\n"

        # Clean up the text - remove page headers/footers
        lines = all_text.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            # Skip headers, footers, empty lines
            if not line:
                continue
            if "Injury Report:" in line:
                continue
            if line.startswith("GameDate"):
                continue
            if re.match(r"^Page\d+of\d+$", line):
                continue
            cleaned_lines.append(line)

        # Join lines back - we'll parse the full text
        full_text = " ".join(cleaned_lines)

        # Pattern for game: date time matchup
        # e.g., "01/17/2026 05:00(ET) UTA@DAL" or just "07:30(ET) BOS@ATL"
        game_pattern = r"(?:(\d{2}/\d{2}/\d{4})\s+)?(\d{2}:\d{2}\(ET\))\s+([A-Z]{3}@[A-Z]{3})"

        # Split by game pattern to process each game separately
        game_splits = re.split(game_pattern, full_text)

        # game_splits will be: [before_first_game, date1, time1, matchup1, content1, date2, time2, matchup2, content2, ...]
        # Process in groups of 4 (date, time, matchup, content)
        current_date = ""
        i = 1  # Skip content before first game
        while i + 3 <= len(game_splits):
            date_part = game_splits[i]
            time_part = game_splits[i + 1]
            matchup = game_splits[i + 2]
            content = game_splits[i + 3] if i + 3 < len(game_splits) else ""

            if date_part:
                current_date = date_part

            # Now parse content for this game
            # Content has format: TeamName Player,First Status Reason TeamName Player,First Status Reason ...

            # Find all team sections in this content
            team_positions = []
            for team_key in NBA_TEAMS:
                pos = 0
                while True:
                    idx = content.find(team_key, pos)
                    if idx == -1:
                        break
                    team_positions.append((idx, team_key))
                    pos = idx + 1

            # Sort by position
            team_positions.sort(key=lambda x: x[0])

            # Extract team sections
            for j, (pos, team_key) in enumerate(team_positions):
                team_name = TEAM_NAME_MAP.get(team_key, team_key)

                # Get content for this team (until next team or end)
                start = pos + len(team_key)
                if j + 1 < len(team_positions):
                    end = team_positions[j + 1][0]
                else:
                    end = len(content)

                team_content = content[start:end].strip()

                # Parse players from team content
                # Pattern: LastName,FirstName Status Reason
                # Reason can contain spaces and continues until next player pattern or end
                player_pattern = r"([A-Za-z\'\-]+(?:Jr\.|Sr\.|II|III|IV)?),([A-Za-z\'\-\.]+)\s+(Out|Questionable|Doubtful|Probable|Available)\s*"

                matches = list(re.finditer(player_pattern, team_content, re.IGNORECASE))

                for k, match in enumerate(matches):
                    last_name = match.group(1)
                    first_name = match.group(2)
                    status = match.group(3).upper()

                    # Reason is from end of this match to start of next match (or end of team content)
                    reason_start = match.end()
                    if k + 1 < len(matches):
                        reason_end = matches[k + 1].start()
                    else:
                        reason_end = len(team_content)

                    reason = team_content[reason_start:reason_end].strip()

                    entries.append(InjuryEntry(
                        game_date=current_date,
                        game_time=time_part,
                        matchup=matchup,
                        team=team_name,
                        player_name=f"{first_name} {last_name}",
                        current_status=status,
                        reason=reason,
                    ))

            i += 4

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
