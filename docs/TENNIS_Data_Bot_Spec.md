# Tennis Data Bot Specification

## Objective

Extend this repository with a tennis-first data pipeline that follows the existing repo pattern:

- small Python CLI entrypoint
- flat `scraper/` modules that each return pandas DataFrames
- timestamped CSV/JSON outputs in `./output/`
- one consolidated markdown artifact in `data/tennis_data.md`
- simple shell automation for scheduled refreshes

The target outcome is a reliable pre-match tennis slate for ATP and WTA singles that can be consumed by a downstream execution layer, with enough normalized context to support pricing, edge calculation, and operational guardrails around withdrawals and retirements.

## Scope

### In Scope for v1

- ATP Tour singles main draw
- WTA singles main draw
- Grand Slam singles main draw
- official rankings, schedule, order of play, results, and match stats
- pre-match withdrawal and in-match retirement tracking
- normalized market line ingestion through a provider adapter
- markdown export plus machine-readable outputs

### Explicit Non-Goals for v1

- live point-by-point trading
- doubles modeling
- junior events
- full Challenger and ITF coverage on day one
- replacing the existing NBA workflow

## Repository Style Alignment

To stay aligned with the current codebase, tennis should be added in parallel rather than by rewriting the NBA path.

Preferred file layout:

```text
nba_data_bot/
├── tennis_main.py
├── scraper/
│   ├── tennis_calendar.py
│   ├── tennis_rankings.py
│   ├── tennis_results.py
│   ├── tennis_match_stats.py
│   ├── tennis_withdrawals.py
│   ├── tennis_odds.py
│   └── tennis_features.py
├── data/
│   └── tennis_data.md
├── output/
│   └── tennis_*.csv|json
└── scripts/
    └── update_tennis_and_publish.sh
```

Implementation rules:

- Keep DataFrame columns in `UPPER_SNAKE_CASE`, matching the NBA code.
- Keep timestamps in UTC and write them as ISO-8601 or `YYYY-MM-DD HH:MM UTC`.
- Keep each scraper module source-specific and side-effect light.
- Keep markdown generation in the CLI layer, same as `main.py`.
- Do not couple tennis refresh logic to the NBA command list in phase 1.

## Data Sources

Use official sources first. Secondary or paid market feeds should only fill gaps that official sources do not expose.

| Source Group | Primary Source | Coverage | Notes |
|---|---|---|---|
| ATP calendar and results | `https://www.atptour.com/en/scores/current` | tournament discovery, draws, results, schedules | scrape current-event pages and per-event draw/results pages |
| ATP rankings | `https://www.atptour.com/rankings/singles` | official ATP singles ranking and points | refresh daily, with Monday ranking change awareness |
| ATP match stats | `https://www.atptour.com/en/stats/individual-game-stats` plus match result pages | serve and return leaderboard metrics, match-level context | leaderboard data is useful for backfill and sanity checks; match pages remain source of record for match results |
| WTA tournament calendar | `https://www.wtatennis.com/tournaments` | upcoming and active event discovery | use tournament overview pages to discover level, surface, draw size, and dates |
| WTA rankings | `https://www.wtatennis.com/rankings/singles` | official WTA singles ranking and points | refresh daily, with Monday ranking change awareness |
| WTA scores and match stats | tournament score pages under `https://www.wtatennis.com/tournaments/.../scores/...` | match result, scoreline, duration, detailed stats, `RET` markers | WTA match pages expose rich service and return stats and should drive match-stat ingestion |
| ITF tournament pages | `https://www.itftennis.com/en/tournament/.../draws-and-results` | lower-tier backfill, qualifiers, replacement tracking | phase 2+ source for Challenger/ITF expansion and replacement validation |
| Official press/news pages | ATP/WTA/tournament official news pages | withdrawals, injury notes, protected ranking entries, lucky loser changes | only used when the draw or score page is ambiguous |
| Market odds provider | provider-specific adapter, not hardcoded in v1 spec | moneyline, spreads, totals, player props | normalize into canonical market keys before feature joins |

### Source Priority

When two sources disagree, resolve in this order:

1. official draw or score page for the specific match
2. official tournament overview or order of play
3. official ATP/WTA ranking or player page
4. official press release or tournament announcement
5. odds-provider metadata

## Canonical Data Model

All tables should be representable as pandas DataFrames and serializable to both CSV and JSON without custom post-processing.

### Global Conventions

- `PLAYER_A` and `PLAYER_B` are draw-order based, not "home" and "away".
- `MATCH_ID` must be stable across schedule refreshes and odds refreshes.
- `TOURNAMENT_ID` must be stable across ATP/WTA source variants.
- Numeric percentages should be stored as decimal fractions, not strings.
- Nulls are allowed when a source does not expose a field, but not when the field is mandatory for a completed match.

### `PLAYERS`

Canonical player registry for joins across ATP, WTA, ITF, and odds feeds.

| Column | Type | Required | Description |
|---|---|---|---|
| `PLAYER_ID` | string | yes | internal stable key, for example `ATP_104745` |
| `SOURCE_PLAYER_ID` | string | yes | source-native player id |
| `TOUR` | string | yes | `ATP`, `WTA`, `ITF` |
| `PLAYER_NAME` | string | yes | display name |
| `COUNTRY_CODE` | string | no | ISO-3 if available |
| `HAND` | string | no | `R`, `L`, `U` |
| `BACKHAND` | string | no | `1H`, `2H`, `U` |
| `DOB` | date | no | birth date |
| `HEIGHT_CM` | float | no | height when available |
| `IS_ACTIVE` | bool | yes | active registry flag |
| `LAST_SEEN_UTC` | datetime | yes | last source confirmation timestamp |

### `TOURNAMENTS`

| Column | Type | Required | Description |
|---|---|---|---|
| `TOURNAMENT_ID` | string | yes | stable internal key |
| `SOURCE_TOURNAMENT_ID` | string | yes | source-native tournament id |
| `TOUR` | string | yes | `ATP`, `WTA`, `ITF`, `GS` |
| `SEASON` | int | yes | season year |
| `EVENT_NAME` | string | yes | official event label |
| `LEVEL` | string | yes | `ATP250`, `ATP500`, `ATP1000`, `GS`, `WTA250`, `WTA500`, `WTA1000`, `WTA125`, `CH`, `ITF` |
| `SURFACE` | string | yes | `HARD`, `CLAY`, `GRASS` |
| `COURT_ENV` | string | no | `INDOOR`, `OUTDOOR`, `U` |
| `CITY` | string | no | city |
| `COUNTRY_CODE` | string | no | ISO-3 code |
| `START_DATE` | date | yes | event start |
| `END_DATE` | date | yes | event end |
| `DRAW_SIZE_SINGLES` | int | no | main draw size |
| `BEST_OF` | int | yes | `3` or `5` |
| `LAST_UPDATED_UTC` | datetime | yes | ingestion timestamp |

### `MATCHES`

`MATCH_ID` format:

```text
{TOUR}_{SOURCE_TOURNAMENT_ID}_{ROUND}_{PLAYER_A_ID}_{PLAYER_B_ID}
```

If a player is not known at draw-publish time, use placeholder tokens such as `TBD_TOP` and regenerate only until both players are confirmed. Once both players are known, freeze the final `MATCH_ID`.

| Column | Type | Required | Description |
|---|---|---|---|
| `MATCH_ID` | string | yes | stable match key |
| `TOURNAMENT_ID` | string | yes | foreign key |
| `TOUR` | string | yes | source tour |
| `EVENT_TYPE` | string | yes | `SINGLES` in v1 |
| `ROUND` | string | yes | `R128`, `R64`, `R32`, `R16`, `QF`, `SF`, `F`, `RR`, `Q1`, `Q2`, `Q3` |
| `MATCH_DATE_UTC` | datetime | no | scheduled first-serve time if known |
| `ORDER_OF_PLAY_SEQ` | int | no | court order |
| `COURT_NAME` | string | no | official court label |
| `PLAYER_A_ID` | string | yes | top/draw-order side |
| `PLAYER_B_ID` | string | yes | bottom/draw-order side |
| `PLAYER_A_NAME` | string | yes | snapshot name |
| `PLAYER_B_NAME` | string | yes | snapshot name |
| `PLAYER_A_SEED` | string | no | tournament seed or entry tag |
| `PLAYER_B_SEED` | string | no | tournament seed or entry tag |
| `PLAYER_A_ENTRY` | string | no | `Q`, `WC`, `LL`, `PR`, `SE`, `ALT` |
| `PLAYER_B_ENTRY` | string | no | same as above |
| `MATCH_STATUS` | string | yes | `SCHEDULED`, `IN_PROGRESS`, `FINAL`, `RET`, `W_O`, `SUSPENDED`, `POSTPONED`, `CANCELLED` |
| `WINNER_PLAYER_ID` | string | no | winner when official |
| `SCORELINE` | string | no | canonical score text |
| `SETS_PLAYED` | int | no | completed sets |
| `DURATION_MIN` | int | no | official duration |
| `SOURCE_URL` | string | yes | match page or draw page |
| `SCRAPED_AT_UTC` | datetime | yes | ingestion time |

### `MATCH_STATS`

One row per player per match.

| Column | Type | Required | Description |
|---|---|---|---|
| `MATCH_ID` | string | yes | foreign key |
| `PLAYER_ID` | string | yes | foreign key |
| `ACES` | int | no | official aces |
| `DOUBLE_FAULTS` | int | no | official double faults |
| `FIRST_SERVE_IN_PCT` | float | no | decimal fraction |
| `FIRST_SERVE_PTS_WON_PCT` | float | no | decimal fraction |
| `SECOND_SERVE_PTS_WON_PCT` | float | no | decimal fraction |
| `BREAK_POINTS_FACED` | int | no | official count |
| `BREAK_POINTS_SAVED_PCT` | float | no | decimal fraction |
| `SERVICE_GAMES_PLAYED` | int | no | official count |
| `FIRST_RETURN_PTS_WON_PCT` | float | no | decimal fraction |
| `SECOND_RETURN_PTS_WON_PCT` | float | no | decimal fraction |
| `BREAK_POINTS_CONVERTED_PCT` | float | no | decimal fraction |
| `RETURN_GAMES_PLAYED` | int | no | official count |
| `TOTAL_SERVICE_PTS_WON_PCT` | float | no | decimal fraction |
| `TOTAL_RETURN_PTS_WON_PCT` | float | no | decimal fraction |
| `TOTAL_POINTS_WON_PCT` | float | no | decimal fraction |
| `STATS_SOURCE_URL` | string | yes | match stats page |
| `SCRAPED_AT_UTC` | datetime | yes | ingestion time |

### `PLAYER_FORM`

Derived feature table recalculated on every batch refresh.

| Column | Type | Required | Description |
|---|---|---|---|
| `PLAYER_ID` | string | yes | player key |
| `AS_OF_DATE` | date | yes | feature cutoff date |
| `OVERALL_ELO` | float | yes | all-surface Elo |
| `SURFACE_ELO` | float | yes | current surface Elo |
| `FORM_LAST_5_WINS` | int | yes | wins in last 5 completed matches |
| `FORM_LAST_10_WINS` | int | yes | wins in last 10 completed matches |
| `SURFACE_WIN_PCT_52W` | float | yes | 52-week same-surface win rate |
| `HOLD_PCT_52W` | float | no | 52-week service hold rate |
| `BREAK_PCT_52W` | float | no | 52-week return break rate |
| `TB_WIN_PCT_52W` | float | no | tiebreak win rate |
| `AVG_MATCH_DURATION_30D` | float | no | minutes |
| `MATCHES_7D` | int | yes | recent workload |
| `MATCHES_14D` | int | yes | recent workload |
| `MINUTES_7D` | float | no | total minutes played |
| `DAYS_SINCE_LAST_MATCH` | float | no | rest proxy |
| `RETIREMENTS_180D` | int | yes | recent in-match retirements |
| `WITHDRAWALS_180D` | int | yes | pre-match withdrawals |
| `TRAVEL_DISTANCE_KM_7D` | float | no | approximate travel load |
| `FEATURES_UPDATED_UTC` | datetime | yes | feature build time |

### `PLAYER_STATUS`

This replaces the NBA-style centralized injury sheet with a tennis availability ledger.

| Column | Type | Required | Description |
|---|---|---|---|
| `STATUS_ID` | string | yes | unique event key |
| `PLAYER_ID` | string | yes | player key |
| `TOURNAMENT_ID` | string | no | event context |
| `MATCH_ID` | string | no | match context |
| `STATUS` | string | yes | `ACTIVE`, `QUESTIONABLE`, `WITHDRAWN_PRE_EVENT`, `WITHDRAWN_PRE_MATCH`, `RETIRED_IN_MATCH`, `WALKOVER_RECEIVED`, `LUCKY_LOSER_REPLACEMENT`, `REST_UNCONFIRMED` |
| `STATUS_REASON` | string | no | free text reason |
| `SOURCE_TYPE` | string | yes | `DRAW`, `SCORE_PAGE`, `ORDER_OF_PLAY`, `PRESS`, `ODDS_FEED` |
| `SOURCE_URL` | string | yes | evidence link |
| `SOURCE_PRIORITY` | int | yes | lower number wins conflicts |
| `ANNOUNCED_AT_UTC` | datetime | no | when status was seen |
| `EFFECTIVE_AT_UTC` | datetime | no | when it impacts lineup availability |
| `CONFIDENCE_SCORE` | float | yes | `0.0` to `1.0` |
| `IS_BLOCKING` | bool | yes | whether execution should stop |

### `MARKET_LINES`

| Column | Type | Required | Description |
|---|---|---|---|
| `LINE_ID` | string | yes | provider line id or generated id |
| `MATCH_ID` | string | yes | foreign key |
| `BOOK` | string | yes | normalized provider label |
| `MARKET_KEY` | string | yes | canonical market identifier |
| `SELECTION_KEY` | string | yes | canonical side identifier |
| `PLAYER_ID` | string | no | required for player props |
| `LINE` | float | no | handicap or total number |
| `PRICE_DECIMAL` | float | yes | decimal odds |
| `PRICE_AMERICAN` | int | no | american odds |
| `IMPLIED_PROB` | float | yes | raw implied probability |
| `NO_VIG_PROB` | float | no | devigged implied probability |
| `ODDS_TIMESTAMP_UTC` | datetime | yes | line snapshot time |
| `IS_LIVE` | bool | yes | live or pre-match |
| `SOURCE_EVENT_ID` | string | no | provider event id |

### `EDGE_REPORT`

One row per actionable or inspected market selection.

| Column | Type | Required | Description |
|---|---|---|---|
| `MATCH_ID` | string | yes | foreign key |
| `MARKET_KEY` | string | yes | canonical market key |
| `SELECTION_KEY` | string | yes | canonical side |
| `MODEL_PROB` | float | yes | model probability |
| `MARKET_PROB` | float | yes | devigged market probability |
| `EDGE_PCT` | float | yes | `MODEL_PROB - MARKET_PROB` |
| `EDGE_BPS` | int | yes | basis points form of edge |
| `FAIR_DECIMAL` | float | yes | `1 / MODEL_PROB` |
| `BEST_BOOK` | string | no | best available source |
| `BEST_PRICE_DECIMAL` | float | no | best price seen |
| `CONFIDENCE_TIER` | string | yes | `LOW`, `MEDIUM`, `HIGH` |
| `BLOCKED_REASON` | string | no | empty when actionable |
| `EXECUTION_STATUS` | string | yes | `SKIP`, `WATCH`, `READY`, `BLOCKED` |
| `GENERATED_AT_UTC` | datetime | yes | report timestamp |

## Update Cadence

All scheduled times below are UTC.

| Dataset | Cadence | Reason |
|---|---|---|
| tournament calendar | every 6 hours | low churn outside draw release windows |
| rankings | daily at `03:00` UTC | rankings usually update weekly, but daily refresh keeps cache simple |
| order of play and schedules | every 15 minutes during active event windows | match times and court assignments move often |
| results and match status | every 10 minutes during active events | fast enough for pre-match and settlement workflows |
| match stats | every 15 minutes for active events, daily backfill at `02:00` UTC | official stat pages can lag final score publication |
| player status / withdrawals | every 10 minutes during event week, every 5 minutes in the two hours before first scheduled serve | tennis availability changes close to match time |
| odds | every 5 minutes pre-match | enough for edge monitoring without live-trading scope |
| markdown export | after every successful full merge | keeps `data/tennis_data.md` current |
| feature rebuild | after results, status, and odds merges | avoids stale edge calculations |

## Ingestion Flow

The ingestion flow should remain linear and debuggable, similar to the current NBA flow.

### Step 1: Discover Active Tournaments

- scrape ATP current scores page
- scrape WTA tournaments calendar page
- optionally scrape ITF draws-and-results pages for phase 2 events
- normalize event metadata into `TOURNAMENTS`

### Step 2: Build or Refresh Player Registry

- extract player identifiers from tournament draws and rankings pages
- map source-native IDs into a stable `PLAYER_ID`
- reject fuzzy joins unless country and full normalized name both match

### Step 3: Ingest Rankings

- fetch ATP and WTA singles rankings
- store latest rank, rank points, and ranking date in a lightweight side table or merge into `PLAYER_FORM` inputs
- rankings are an input feature, not the primary join key

### Step 4: Ingest Match Schedule and Results

- walk tournament pages to collect draw positions, rounds, order of play, and result states
- create or update `MATCHES`
- keep `PLAYER_A` and `PLAYER_B` consistent with draw order, not winner order

### Step 5: Ingest Match Stats

- for matches with `FINAL` or `RET` status, scrape the official stat page
- create two `MATCH_STATS` rows per singles match
- if stats are missing at first pass, retry in the next batch rather than backfilling fake zeros

### Step 6: Ingest Withdrawals and Availability

- inspect draw changes, walkovers, score-page tags, and official announcements
- upsert into `PLAYER_STATUS`
- mark blocking statuses before odds and edge evaluation

### Step 7: Ingest Market Data

- call the provider adapter
- map provider event ids to `MATCH_ID`
- normalize prices, sides, and market names into `MARKET_LINES`

### Step 8: Build Tennis Features

- aggregate rolling form, surface splits, fatigue, serve/return strength, and retirement risk
- persist into `PLAYER_FORM`
- generate `EDGE_REPORT`

### Step 9: Write Outputs

- timestamped raw outputs to `./output/`
- consolidated markdown to `data/tennis_data.md`
- optional `data/tennis_execution_candidates.json` sidecar for machine-first consumption

## Tennis Feature Engineering

Tennis is materially different from team sports. The feature layer should emphasize surface fit, serve/return profile, fatigue, and retirement risk.

### Core Form Features

- rolling win/loss record over last 5 and last 10 completed matches
- 52-week overall Elo
- 52-week surface Elo
- opponent-adjusted win rate by surface
- round-adjusted performance in current tournament level

### Serve and Return Strength

- first-serve points won percentage
- second-serve points won percentage
- first-return points won percentage
- second-return points won percentage
- service games won percentage
- return games won percentage
- break points saved percentage
- break points converted percentage
- aces per service game
- double faults per service game
- tiebreak frequency and tiebreak win percentage

### Surface and Environment

- hard, clay, and grass splits over 52 weeks
- indoor versus outdoor split when available
- tournament altitude bucket if location metadata is later enriched
- Grand Slam best-of-5 adjustment for ATP men when applicable

### Fatigue and Travel

- days since last completed match
- matches played in last 7 days
- matches played in last 14 days
- total minutes played in last 7 days
- number of deciding-set matches in last 14 days
- previous match finish lag in hours
- rough travel distance from previous tournament city to current tournament city

### Draw and Matchup Context

- seed differential
- ranking differential
- Elo differential
- surface Elo differential
- handedness matchup
- direct head-to-head overall
- direct head-to-head on same surface
- qualifier, lucky loser, wildcard, or protected ranking entry flags

### Availability and Fragility

- retirements in last 30, 90, and 180 days
- pre-match withdrawals in last 180 days
- current tournament medical or withdrawal flag
- ambiguous status confidence penalty

### Feature Exclusions

Do not include the current match's closing market price in the predictive feature set. Market data is for edge comparison and execution, not label leakage.

## Quality Checks

Quality checks should fail loudly at batch time and appear in the markdown source-status table.

### Structural Checks

- `PLAYER_ID`, `TOURNAMENT_ID`, and `MATCH_ID` uniqueness
- no null `PLAYER_A_ID` or `PLAYER_B_ID` once a match is officially scheduled
- `MATCHES` must not contain duplicate `MATCH_ID` rows
- `MATCH_STATS` must contain either zero rows for an incomplete match or exactly two rows for a singles match

### Domain Checks

- `SURFACE` must be one of `HARD`, `CLAY`, `GRASS`
- `BEST_OF` must be `3` or `5`
- `MATCH_STATUS` must be in the approved enum list
- `PLAYER_STATUS.STATUS` must be in the approved enum list

### Result Consistency

- completed matches must have `WINNER_PLAYER_ID`
- `RET` matches may have partial stats, but must still have a winner and scoreline
- `W_O` matches must not have match stats or duration
- scoreline parsing must agree with `SETS_PLAYED` and winner side

### Freshness Checks

- active tournament schedule data older than 30 minutes is stale
- odds data older than 10 minutes for `READY` recommendations is stale
- ranking data older than 8 days is stale
- withdrawal data older than 15 minutes on active match day is stale

### Join Checks

- every `MARKET_LINES.MATCH_ID` must resolve to one `MATCHES.MATCH_ID`
- every `PLAYER_STATUS.PLAYER_ID` must resolve to `PLAYERS`
- every `MATCHES.TOURNAMENT_ID` must resolve to `TOURNAMENTS`

### Statistical Sanity Checks

- percentages must be in `[0, 1]`
- `ACES`, `DOUBLE_FAULTS`, `DURATION_MIN` must be non-negative
- hold and break rates must not exceed logical bounds
- extreme feature jumps should trigger warnings rather than silent overwrite

## Injury and Withdrawal Handling

There is no NBA-style centralized official injury report for tennis. Availability must therefore be modeled as an event ledger built from official evidence.

### Status Definitions

| Status | Meaning | Execution Impact |
|---|---|---|
| `ACTIVE` | no blocking issue seen | allowed |
| `QUESTIONABLE` | official ambiguity or recent concerning signal without formal withdrawal | blocked by default in v1 |
| `WITHDRAWN_PRE_EVENT` | player removed before tournament start | blocked |
| `WITHDRAWN_PRE_MATCH` | player removed after draw creation but before first ball | blocked |
| `RETIRED_IN_MATCH` | match started and player stopped mid-match | settlement only, no future same-match execution |
| `WALKOVER_RECEIVED` | opponent advanced without play | opponent match should settle as void for pre-match markets that require play |
| `LUCKY_LOSER_REPLACEMENT` | draw slot changed to a replacement player | rebuild `MATCH_ID` only if opponent changes before line mapping is finalized |
| `REST_UNCONFIRMED` | concern inferred from compressed schedule, not from official source | watch-only, not a hard status unless configured |

### Detection Rules

- `RET` on official score pages becomes `RETIRED_IN_MATCH`
- `W/O`, walkover, or opponent advance without ball-in-play becomes `WITHDRAWN_PRE_MATCH` for the withdrawing player and `WALKOVER_RECEIVED` for the opponent
- draw replacement by `LL`, `ALT`, or qualifier after original publication creates a new status row and a refreshed match mapping record
- official press note outranks odds-provider flags when both exist

### Conflict Resolution

If two sources disagree:

1. keep the highest-priority official source
2. preserve the lower-priority record for audit
3. mark the player `QUESTIONABLE` if the conflict remains unresolved
4. block execution until the conflict is cleared

### Training and Backtest Treatment

- `FINAL` matches enter the core training set
- `RET` matches should be stored separately and excluded from naive win-probability training by default
- `W_O` matches should never be treated as completed competitive matches
- retirement frequency remains a feature even when retirement matches are excluded from label generation

## Market Mapping

Tennis has no home/away construct, so selection mapping must be draw-order based.

### Canonical Selection Keys

- `PLAYER_A`
- `PLAYER_B`
- `OVER`
- `UNDER`
- explicit score selections such as `2_0`, `2_1`, `3_0`, `3_1`, `3_2`

### Canonical Market Keys

| `MARKET_KEY` | Scope | Line Field | Notes |
|---|---|---|---|
| `MATCH_ML` | match winner | null | maps to match moneyline |
| `MATCH_SPREAD_GAMES` | game handicap | yes | example `-2.5`, `+2.5` |
| `MATCH_TOTAL_GAMES` | total games | yes | over/under total games |
| `SET1_ML` | first set winner | null | set-level winner market |
| `SET1_TOTAL_GAMES` | first set games | yes | over/under |
| `CORRECT_SCORE` | exact set score | null | outcomes depend on `BEST_OF` |
| `PLAYER_ACES` | player prop | yes | requires `PLAYER_ID` |
| `PLAYER_DOUBLE_FAULTS` | player prop | yes | requires `PLAYER_ID` |
| `PLAYER_TOTAL_GAMES_WON` | player prop | yes | requires `PLAYER_ID` |

### Mapping Rules

- map provider sides to `PLAYER_A` and `PLAYER_B` using normalized player ids, never by raw display order alone
- for props, always attach `PLAYER_ID`
- if a provider flips player order from the official draw, remap into canonical order during ingestion
- for `CORRECT_SCORE`, validate legal outcomes against `BEST_OF`

### No-Vig Calculation

For two-way markets:

```text
market_prob = implied_prob / sum(implied_prob_all_sides)
```

Store both raw implied probability and devigged probability.

## Cron Workflow

The cron layer should match the existing shell-script automation pattern, but tennis should have its own script.

Preferred script:

```bash
#!/bin/bash
set -e

cd /path/to/nba_data_bot
source .venv/bin/activate

python tennis_main.py all --output ./output
python tennis_main.py markdown --output ./data

git add data/tennis_data.md
if ! git diff --staged --quiet; then
  git commit -m "Update tennis data [$(date -u '+%Y-%m-%d %H:%M') UTC]"
  git push
fi
```

Recommended cron schedule:

```cron
# rankings and calendar refresh
0 */6 * * * /path/to/nba_data_bot/scripts/update_tennis_and_publish.sh

# active-event refresh window
*/15 6-23 * * * /path/to/nba_data_bot/scripts/update_tennis_and_publish.sh
```

For lower-noise operation, phase 1 can split publishing from local refresh:

- `update_tennis_data.sh` for frequent local refresh
- `publish_tennis_data.sh` for less frequent commits

## Edge Interpretation

Edge should be computed only after data quality and availability checks pass.

### Core Formula

```text
EDGE_PCT = MODEL_PROB - MARKET_PROB
EDGE_BPS = round(EDGE_PCT * 10000)
FAIR_DECIMAL = 1 / MODEL_PROB
```

### Execution States

| State | Meaning |
|---|---|
| `SKIP` | no material edge or incomplete data |
| `WATCH` | edge exists but confidence or freshness is not good enough |
| `READY` | edge exists and all operational checks passed |
| `BLOCKED` | withdrawal, stale line, unresolved player mapping, or failed quality check |

### Blocking Conditions

Set `EXECUTION_STATUS=BLOCKED` when any of the following is true:

- match has `MATCH_STATUS` in `RET`, `W_O`, `CANCELLED`, `POSTPONED`
- either player has blocking `PLAYER_STATUS`
- odds snapshot is stale
- ranking or feature build is stale
- match identity cannot be mapped confidently between source and market feed

### Interpretation Notes

- A large positive edge on a newly replaced lucky-loser matchup is untrusted until the market remap is confirmed.
- A `RET` history increases fragility features for future matches, but the retirement match itself should not be interpreted as a clean competitive result.
- When market and model disagree sharply but availability data is noisy, prefer `WATCH` over forced execution.

## Integration Path for a Gina-MCP-Like Execution Layer

The execution layer should consume normalized outputs from this repository, not scrape tennis sources directly.

### Phase 1 Contract

Produce:

- `data/tennis_data.md` for human-readable review
- `output/tennis_edge_report_latest.json` for machine consumption
- `output/tennis_player_status_latest.json` for risk controls

### Machine-Facing Payload

Each candidate row supplied to the execution layer should include:

| Field | Purpose |
|---|---|
| `MATCH_ID` | immutable join key |
| `TOURNAMENT_ID` | context |
| `MARKET_KEY` | canonical market |
| `SELECTION_KEY` | canonical side |
| `BOOK` | source book |
| `LINE` | spread or total |
| `BEST_PRICE_DECIMAL` | execution price |
| `MODEL_PROB` | model probability |
| `MARKET_PROB` | devigged market probability |
| `EDGE_BPS` | edge strength |
| `EXECUTION_STATUS` | gate outcome |
| `BLOCKED_REASON` | explicit rejection reason |
| `ODDS_TIMESTAMP_UTC` | freshness check |
| `STATUS_SUMMARY` | availability snapshot |
| `GENERATED_AT_UTC` | audit trail |

### Execution Guardrails

A Gina-MCP-like layer should:

- reject any row that is not `READY`
- re-check freshness before placement
- re-check `PLAYER_STATUS` immediately before placement
- avoid execution when player mapping changed inside the last refresh window
- log order intent, placement response, and settlement back against `MATCH_ID`

### Suggested Adapter Boundary

The repository should own:

- scraping
- normalization
- feature generation
- edge generation
- markdown and JSON artifacts

The Gina-MCP-like layer should own:

- order routing
- book-specific auth
- stake sizing
- retry logic
- settlement reconciliation

## Consolidated Markdown Output

`data/tennis_data.md` should mirror the existing NBA markdown pattern:

1. title and last-updated timestamp
2. data source status table
3. active tournaments
4. upcoming matches with start times and court
5. player form snapshot
6. withdrawal and availability section
7. market and edge summary

Suggested headings:

```text
# Tennis Schedule, Form & Market Report
## Data Sources
## Active Tournaments
## Upcoming Matches
## Player Form
## Withdrawal Report
## Market Snapshot
## Edge Report
```

## Phased Roadmap

### Phase 1: Core Official Feed Ingestion

- add `tennis_main.py`
- implement ATP/WTA tournament discovery
- implement rankings, schedule, results, and markdown export
- support singles main draw only

### Phase 2: Match Stats and Derived Features

- ingest official match stats
- build `PLAYER_FORM`
- add fatigue, surface, and serve/return features
- add `PLAYER_STATUS` ledger

### Phase 3: Market Integration and Edge Report

- build odds provider adapter
- normalize market keys
- compute no-vig market probabilities
- generate `EDGE_REPORT`

### Phase 4: Execution Readiness

- add machine-first JSON artifacts
- finalize Gina-MCP-like contract
- add stricter freshness and blocking controls
- add auditable decision logs

### Phase 5: Coverage Expansion

- Challenger and ITF support
- qualifying rounds beyond final round
- doubles support
- optional live/in-play extension

## Implementation Notes

The lowest-risk way to add tennis in this repository is:

1. build a parallel tennis CLI and keep the NBA entrypoint untouched
2. reuse the current save-to-CSV/JSON and markdown-export patterns
3. standardize on stable ids before adding odds
4. treat withdrawal handling as a first-class data product, not an afterthought

If those rules are followed, the tennis bot will fit the current repo style while still being usable by an execution layer without major redesign.
