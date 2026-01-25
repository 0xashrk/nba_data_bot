#!/bin/bash
# NBA Data Bot - Local update script
# Runs the scraper and pushes to GitHub

set -e

cd /path/to/nba_data_bot

# Activate venv
source .venv/bin/activate

# Run the markdown export
python main.py markdown --output ./data

# Commit and push if changed
git add data/nba_data.md
if ! git diff --staged --quiet; then
    GIT_COMMITTER_NAME="NBA Bot" GIT_COMMITTER_EMAIL="nba-bot@automated.local" \
    git commit --author="NBA Bot <nba-bot@automated.local>" -m "Update NBA data [$(date -u '+%Y-%m-%d %H:%M') UTC]"
    git push
fi
