"""
NBA.com Stats API client for team statistics.

Uses the stats.nba.com API endpoints directly (they return JSON).
"""

import requests
import pandas as pd
from typing import Optional

# NBA.com stats API requires specific headers
HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
}

BASE_URL = "https://stats.nba.com/stats/leaguedashteamstats"

# Current season (update as needed)
CURRENT_SEASON = "2025-26"


def _fetch_team_stats(measure_type: str, per_mode: str = "PerGame") -> pd.DataFrame:
    """
    Fetch team stats from NBA.com stats API.

    Args:
        measure_type: One of "Base", "Advanced", "Four Factors", "Defense"
        per_mode: "PerGame", "Totals", "Per48", etc.

    Returns:
        DataFrame with team stats
    """
    params = {
        "Conference": "",
        "DateFrom": "",
        "DateTo": "",
        "Division": "",
        "GameScope": "",
        "GameSegment": "",
        "Height": "",
        "ISTRound": "",
        "LastNGames": 0,
        "LeagueID": "00",
        "Location": "",
        "MeasureType": measure_type,
        "Month": 0,
        "OpponentTeamID": 0,
        "Outcome": "",
        "PORound": 0,
        "PaceAdjust": "N",
        "PerMode": per_mode,
        "Period": 0,
        "PlayerExperience": "",
        "PlayerPosition": "",
        "PlusMinus": "N",
        "Rank": "N",
        "Season": CURRENT_SEASON,
        "SeasonSegment": "",
        "SeasonType": "Regular Season",
        "ShotClockRange": "",
        "StarterBench": "",
        "TeamID": 0,
        "TwoWay": 0,
        "VsConference": "",
        "VsDivision": "",
    }

    response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()

    # NBA API returns data in resultSets[0] with headers and rowSet
    result_set = data["resultSets"][0]
    headers = result_set["headers"]
    rows = result_set["rowSet"]

    return pd.DataFrame(rows, columns=headers)


def get_advanced_stats() -> pd.DataFrame:
    """
    Fetch team advanced stats.

    Returns DataFrame with columns including:
        - TEAM_NAME, W, L, NET_RATING, OFF_RATING, DEF_RATING, PACE
    """
    df = _fetch_team_stats("Advanced")

    # Select relevant columns
    columns = [
        "TEAM_ID", "TEAM_NAME",
        "W", "L", "W_PCT",
        "NET_RATING", "OFF_RATING", "DEF_RATING",
        "PACE", "AST_PCT", "AST_TO", "AST_RATIO",
        "TS_PCT", "EFG_PCT",
    ]

    available = [c for c in columns if c in df.columns]
    return df[available]


def get_four_factors() -> pd.DataFrame:
    """
    Fetch team four factors stats.

    Returns DataFrame with columns including:
        - TEAM_NAME, EFG_PCT, FTA_RATE, TM_TOV_PCT, OREB_PCT
    """
    df = _fetch_team_stats("Four Factors")

    # Select relevant columns
    columns = [
        "TEAM_ID", "TEAM_NAME",
        "W", "L",
        "EFG_PCT", "FTA_RATE", "TM_TOV_PCT", "OREB_PCT",
        "OPP_EFG_PCT", "OPP_FTA_RATE", "OPP_TOV_PCT", "OPP_OREB_PCT",
    ]

    available = [c for c in columns if c in df.columns]
    return df[available]


def get_defense_stats() -> pd.DataFrame:
    """
    Fetch team defensive stats.

    Returns DataFrame with various defensive metrics.
    """
    # Defense stats come from the "Defense" measure type
    # but that endpoint structure differs - we'll use opponent stats
    df = _fetch_team_stats("Opponent")

    columns = [
        "TEAM_ID", "TEAM_NAME",
        "W", "L",
        "OPP_FGM", "OPP_FGA", "OPP_FG_PCT",
        "OPP_FG3M", "OPP_FG3A", "OPP_FG3_PCT",
        "OPP_FTM", "OPP_FTA", "OPP_FT_PCT",
        "OPP_PTS",
    ]

    available = [c for c in columns if c in df.columns]
    return df[available]


if __name__ == "__main__":
    print("=== Advanced Stats ===")
    print(get_advanced_stats().head())

    print("\n=== Four Factors ===")
    print(get_four_factors().head())

    print("\n=== Defense Stats ===")
    print(get_defense_stats().head())
