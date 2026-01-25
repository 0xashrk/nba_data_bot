# NBA Data Bot

CLI tool for extracting NBA stats and injury data from multiple sources.

## Data Sources

| Source | Command | Data Extracted |
|--------|---------|----------------|
| TeamRankings.com | `last5` | L5_WINS, L5_LOSSES, L5_RATING |
| NBA.com Advanced | `advanced` | W, L, NET_RATING, OFF_RATING, DEF_RATING, PACE |
| NBA.com Four Factors | `fourfactors` | EFG_PCT, TOV_PCT, OREB_PCT, FT_RATE |
| NBA.com Defense | `defense` | OPP_FG_PCT, OPP_FG3_PCT, OPP_PTS, etc. |
| NBA Injury Report | `injuries` | Player status (OUT/DOUBTFUL/QUESTIONABLE/PROBABLE) by team |

## Installation

```bash
cd nba_data_bot
conda create -n nba_bot python=3.11 -y
conda activate nba_bot
pip install -r requirements.txt
```

## Usage

```bash
# Fetch all data sources
python main.py all

# Fetch individual sources
python main.py last5
python main.py advanced
python main.py fourfactors
python main.py defense
python main.py injuries

# Options
python main.py all --format json    # Output as JSON instead of CSV
python main.py all --output ./data  # Custom output directory
```

Output files are saved to `./output/` by default with timestamps (e.g., `advanced_stats_20260116_143022.csv`).

## Live Data URL

A consolidated markdown file is available at:

```
https://raw.githubusercontent.com/0xashrk/nba_data_bot/main/data/nba_data.md
```

Use this URL with tools like Jina AI to fetch the latest NBA stats programmatically.

## Update & Push to GitHub

Run the update script to fetch fresh data and push to GitHub:

```bash
cd /path/to/nba_data_bot
./scripts/update_and_push.sh
```

This will:
1. Fetch all NBA data (stats + injuries)
2. Generate `data/nba_data.md`
3. Commit and push to GitHub (only if data changed)
4. Commits are authored as "NBA Bot" (won't count to your GitHub profile)

## Project Structure

```
nba_data_bot/
├── main.py                    # CLI entry point
├── scraper/
│   ├── teamrankings.py        # Last-5 form scraper
│   ├── nba_stats.py           # NBA.com stats API client
│   └── injury_report.py       # Injury report PDF parser
├── scripts/
│   └── update_and_push.sh     # Update and push script
├── data/
│   └── nba_data.md            # Consolidated markdown
├── output/                    # Generated CSV/JSON files
└── requirements.txt
```
