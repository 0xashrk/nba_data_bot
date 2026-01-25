#!/usr/bin/env python3
"""
NBA Data Bot - CLI tool for extracting NBA stats and injury data.

Usage:
    python main.py all                    # Fetch all data sources
    python main.py last5                  # TeamRankings Last-5 form
    python main.py advanced               # NBA.com advanced stats
    python main.py fourfactors            # NBA.com four factors
    python main.py defense                # NBA.com defense stats
    python main.py injuries               # Latest injury report

Options:
    --format csv|json     Output format (default: csv)
    --output DIR          Output directory (default: ./output)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from scraper import (
    get_last5_form,
    get_advanced_stats,
    get_four_factors,
    get_defense_stats,
    get_injury_report,
)
from scraper.injury_report import summarize_by_team


def save_dataframe(df: pd.DataFrame, name: str, output_dir: str, fmt: str, timestamp: str = None) -> str:
    """Save DataFrame to file and return the path."""
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    if fmt == "csv":
        filepath = os.path.join(output_dir, f"{name}_{timestamp}.csv")
        df.to_csv(filepath, index=False)
    else:  # json
        filepath = os.path.join(output_dir, f"{name}_{timestamp}.json")
        df.to_json(filepath, orient="records", indent=2)

    return filepath


def df_to_markdown(df: pd.DataFrame, max_cols: list = None) -> str:
    """Convert DataFrame to markdown table."""
    if max_cols:
        df = df[max_cols]
    return df.to_markdown(index=False)


def cmd_last5(args):
    """Fetch Last-5 games form data from TeamRankings."""
    print("Fetching Last-5 form data from TeamRankings...")
    df = get_last5_form()
    filepath = save_dataframe(df, "last5_form", args.output, args.format)
    print(f"Saved {len(df)} teams to {filepath}")
    return df


def cmd_advanced(args):
    """Fetch advanced stats from NBA.com."""
    print("Fetching advanced stats from NBA.com...")
    df = get_advanced_stats()
    filepath = save_dataframe(df, "advanced_stats", args.output, args.format)
    print(f"Saved {len(df)} teams to {filepath}")
    return df


def cmd_fourfactors(args):
    """Fetch four factors stats from NBA.com."""
    print("Fetching four factors stats from NBA.com...")
    df = get_four_factors()
    filepath = save_dataframe(df, "four_factors", args.output, args.format)
    print(f"Saved {len(df)} teams to {filepath}")
    return df


def cmd_defense(args):
    """Fetch defense stats from NBA.com."""
    print("Fetching defense stats from NBA.com...")
    df = get_defense_stats()
    filepath = save_dataframe(df, "defense_stats", args.output, args.format)
    print(f"Saved {len(df)} teams to {filepath}")
    return df


def cmd_injuries(args):
    """Fetch latest injury report."""
    print("Fetching latest injury report...")
    try:
        df = get_injury_report()
        filepath = save_dataframe(df, "injury_report", args.output, args.format)
        print(f"Saved {len(df)} injury entries to {filepath}")

        # Also save summary
        if len(df) > 0:
            summary = summarize_by_team(df)
            summary_path = os.path.join(args.output, f"injury_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(summary_path, "w") as f:
                json.dump(summary, f, indent=2)
            print(f"Saved team summary to {summary_path}")

        return df
    except Exception as e:
        print(f"Error fetching injury report: {e}")
        return pd.DataFrame()


def cmd_all(args):
    """Fetch all data sources."""
    results = {}

    print("=" * 50)
    print("NBA DATA BOT - Fetching All Sources")
    print("=" * 50)

    # Last-5 form
    print("\n[1/5] Last-5 Form (TeamRankings)")
    try:
        results["last5"] = cmd_last5(args)
    except Exception as e:
        print(f"  Error: {e}")
        results["last5"] = None

    # Advanced stats
    print("\n[2/5] Advanced Stats (NBA.com)")
    try:
        results["advanced"] = cmd_advanced(args)
    except Exception as e:
        print(f"  Error: {e}")
        results["advanced"] = None

    # Four factors
    print("\n[3/5] Four Factors (NBA.com)")
    try:
        results["fourfactors"] = cmd_fourfactors(args)
    except Exception as e:
        print(f"  Error: {e}")
        results["fourfactors"] = None

    # Defense
    print("\n[4/5] Defense Stats (NBA.com)")
    try:
        results["defense"] = cmd_defense(args)
    except Exception as e:
        print(f"  Error: {e}")
        results["defense"] = None

    # Injuries
    print("\n[5/5] Injury Report (NBA Official)")
    try:
        results["injuries"] = cmd_injuries(args)
    except Exception as e:
        print(f"  Error: {e}")
        results["injuries"] = None

    print("\n" + "=" * 50)
    print("COMPLETE")
    print("=" * 50)

    # Summary
    for name, df in results.items():
        if df is not None and len(df) > 0:
            print(f"  {name}: {len(df)} rows")
        else:
            print(f"  {name}: FAILED or empty")

    return results


def cmd_markdown(args):
    """Fetch all data and output as a single consolidated markdown file."""
    from datetime import timezone

    print("Fetching all data for markdown export...")

    results = {}

    # Fetch all data
    print("  [1/5] Last-5 Form...")
    try:
        results["last5"] = get_last5_form()
    except Exception as e:
        print(f"    Error: {e}")
        results["last5"] = None

    print("  [2/5] Advanced Stats...")
    try:
        results["advanced"] = get_advanced_stats()
    except Exception as e:
        print(f"    Error: {e}")
        results["advanced"] = None

    print("  [3/5] Four Factors...")
    try:
        results["fourfactors"] = get_four_factors()
    except Exception as e:
        print(f"    Error: {e}")
        results["fourfactors"] = None

    print("  [4/5] Defense Stats...")
    try:
        results["defense"] = get_defense_stats()
    except Exception as e:
        print(f"    Error: {e}")
        results["defense"] = None

    print("  [5/5] Injury Report...")
    try:
        results["injuries"] = get_injury_report()
    except Exception as e:
        print(f"    Error: {e}")
        results["injuries"] = None

    # Build markdown
    now = datetime.now(timezone.utc)
    md_lines = [
        "# NBA Stats & Injury Report",
        "",
        f"**Last Updated:** {now.strftime('%Y-%m-%d %H:%M')} UTC",
        "",
        "## Data Sources",
        "",
        "| Source | Website | Status | Records |",
        "|--------|---------|--------|---------|",
    ]

    # Source status table
    sources = [
        ("Advanced Stats", "stats.nba.com", "advanced"),
        ("Last 5 Games", "teamrankings.com", "last5"),
        ("Four Factors", "stats.nba.com", "fourfactors"),
        ("Defense Stats", "stats.nba.com", "defense"),
        ("Injury Report", "nba.com (PDF)", "injuries"),
    ]

    for name, website, key in sources:
        df = results.get(key)
        if df is not None and len(df) > 0:
            md_lines.append(f"| {name} | {website} | OK | {len(df)} |")
        else:
            md_lines.append(f"| {name} | {website} | FAILED | 0 |")

    md_lines.append("")

    # Advanced Stats
    if results.get("advanced") is not None and len(results["advanced"]) > 0:
        md_lines.extend([
            "## Team Standings & Ratings",
            "",
            df_to_markdown(results["advanced"], ["TEAM_NAME", "W", "L", "NET_RATING", "OFF_RATING", "DEF_RATING", "PACE"]),
            "",
        ])

    # Last-5 Form
    if results.get("last5") is not None and len(results["last5"]) > 0:
        md_lines.extend([
            "## Last 5 Games Form",
            "",
            df_to_markdown(results["last5"]),
            "",
        ])

    # Four Factors
    if results.get("fourfactors") is not None and len(results["fourfactors"]) > 0:
        md_lines.extend([
            "## Four Factors",
            "",
            df_to_markdown(results["fourfactors"]),
            "",
        ])

    # Defense Stats
    if results.get("defense") is not None and len(results["defense"]) > 0:
        md_lines.extend([
            "## Defense Stats",
            "",
            df_to_markdown(results["defense"]),
            "",
        ])

    # Injuries
    if results.get("injuries") is not None and len(results["injuries"]) > 0:
        md_lines.extend([
            "## Injury Report",
            "",
        ])
        # Group by team
        injury_df = results["injuries"]
        for team in sorted(injury_df["TEAM"].unique()):
            team_injuries = injury_df[injury_df["TEAM"] == team]
            md_lines.append(f"### {team}")
            md_lines.append("")
            md_lines.append("| Player | Status | Reason |")
            md_lines.append("|--------|--------|--------|")
            for _, row in team_injuries.iterrows():
                md_lines.append(f"| {row['PLAYER_NAME']} | {row['CURRENT_STATUS']} | {row['REASON']} |")
            md_lines.append("")

    # Write file
    Path(args.output).mkdir(parents=True, exist_ok=True)
    filepath = os.path.join(args.output, "nba_data.md")

    with open(filepath, "w") as f:
        f.write("\n".join(md_lines))

    print(f"\nSaved consolidated markdown to {filepath}")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="NBA Data Bot - Extract stats and injury data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "command",
        choices=["all", "last5", "advanced", "fourfactors", "defense", "injuries", "markdown"],
        help="Data source to fetch (use 'markdown' for single consolidated file)",
    )

    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Output format (default: csv)",
    )

    parser.add_argument(
        "--output",
        default="./output",
        help="Output directory (default: ./output)",
    )

    args = parser.parse_args()

    commands = {
        "all": cmd_all,
        "last5": cmd_last5,
        "advanced": cmd_advanced,
        "fourfactors": cmd_fourfactors,
        "defense": cmd_defense,
        "injuries": cmd_injuries,
        "markdown": cmd_markdown,
    }

    try:
        commands[args.command](args)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
