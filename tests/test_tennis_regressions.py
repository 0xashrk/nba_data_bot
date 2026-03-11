import unittest
from unittest.mock import patch

import scraper.tennis_injuries as tennis_injuries
import scraper.tennis_rankings as tennis_rankings
import scraper.tennis_schedule as tennis_schedule


class TennisScheduleRegressionTests(unittest.TestCase):
    def test_score_line_preserves_literal_non_numeric_scores(self):
        competitor = {"linescores": [{"value": "W/O"}, {"value": 6}, {"value": "RET"}]}

        self.assertEqual(tennis_schedule._score_line(competitor), "W/O-6-RET")

    def test_get_tennis_schedule_continues_when_one_tour_fetch_fails(self):
        def fake_fetch_json(url):
            if url.endswith("/atp/scoreboard"):
                raise RuntimeError("boom")
            if url.endswith("/wta/scoreboard"):
                return {"events": []}
            raise AssertionError(f"Unexpected url: {url}")

        with patch.object(tennis_schedule, "normalize_tours", return_value=("atp", "wta")):
            with patch.object(tennis_schedule, "tour_slug", side_effect=lambda tour: tour):
                with patch.object(tennis_schedule, "fetch_json", side_effect=fake_fetch_json):
                    df = tennis_schedule.get_tennis_schedule()

        self.assertTrue(df.empty)
        self.assertEqual(df.columns.tolist(), tennis_schedule.SCHEDULE_COLUMNS)


class TennisRankingsRegressionTests(unittest.TestCase):
    def test_get_tennis_rankings_returns_empty_frame_when_index_has_no_items(self):
        with patch.object(tennis_rankings, "normalize_tours", return_value=("atp",)):
            with patch.object(tennis_rankings, "tour_slug", side_effect=lambda tour: tour):
                with patch.object(tennis_rankings, "fetch_json", return_value={"items": []}):
                    df = tennis_rankings.get_tennis_rankings(top_n=5)

        self.assertTrue(df.empty)
        self.assertEqual(df.columns.tolist(), tennis_rankings.RANKING_COLUMNS)

    def test_get_tennis_rankings_skips_rank_rows_without_athlete_ref(self):
        def fake_fetch_json(url):
            if url.endswith("/leagues/atp/rankings"):
                return {"items": [{"$ref": "https://example.test/rankings"}]}
            if url == "https://example.test/rankings":
                return {
                    "lastUpdated": "2026-03-11T00:00:00Z",
                    "ranks": [
                        {"current": 1, "athlete": {}},
                        {"current": 2, "athlete": {"$ref": "https://example.test/player/2"}},
                    ],
                }
            if url == "https://example.test/player/2":
                return {
                    "id": "2",
                    "displayName": "Player Two",
                    "shortName": "P. Two",
                    "citizenshipCountry": {"abbreviation": "USA"},
                    "age": 25,
                    "hand": {"displayValue": "Right"},
                    "status": {"type": "active"},
                    "links": [{"href": "https://example.test/playercard/2", "rel": ["playercard"]}],
                }
            raise AssertionError(f"Unexpected url: {url}")

        with patch.object(tennis_rankings, "normalize_tours", return_value=("atp",)):
            with patch.object(tennis_rankings, "tour_slug", side_effect=lambda tour: tour):
                with patch.object(tennis_rankings, "normalize_ref", side_effect=lambda ref: ref):
                    with patch.object(tennis_rankings, "fetch_json", side_effect=fake_fetch_json):
                        df = tennis_rankings.get_tennis_rankings(top_n=5)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, "PLAYER"], "Player Two")
        self.assertEqual(df.loc[0, "RANK"], 2)


class TennisInjuryRegressionTests(unittest.TestCase):
    def test_get_tennis_injuries_excludes_back_to_back_and_forearm_false_positives(self):
        payload = {
            "articles": [
                {
                    "id": "123",
                    "headline": "Player wins back-to-back titles",
                    "description": "A forearm winner sealed the championship.",
                    "published": "2026-03-10T12:00:00Z",
                    "categories": [{"type": "athlete", "athleteId": 99, "description": "Player Name"}],
                    "links": {"web": {"href": "https://example.test/article/123"}},
                }
            ]
        }

        with patch.object(tennis_injuries, "normalize_tours", return_value=("atp",)):
            with patch.object(tennis_injuries, "tour_slug", side_effect=lambda tour: tour):
                with patch.object(tennis_injuries, "fetch_json", return_value=payload):
                    df = tennis_injuries.get_tennis_injuries()

        self.assertTrue(df.empty)
        self.assertEqual(df.columns.tolist(), tennis_injuries.INJURY_COLUMNS)

    def test_get_tennis_injuries_still_matches_specific_injury_language(self):
        payload = {
            "articles": [
                {
                    "id": "456",
                    "headline": "Player withdraws with back pain",
                    "description": "The top seed cited a lingering knee issue.",
                    "published": "2026-03-10T12:00:00Z",
                    "categories": [{"type": "athlete", "athleteId": 42, "description": "Player Two"}],
                    "links": {"web": {"href": "https://example.test/article/456"}},
                }
            ]
        }

        with patch.object(tennis_injuries, "normalize_tours", return_value=("wta",)):
            with patch.object(tennis_injuries, "tour_slug", side_effect=lambda tour: tour):
                with patch.object(tennis_injuries, "fetch_json", return_value=payload):
                    df = tennis_injuries.get_tennis_injuries()

        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, "PLAYER"], "Player Two")
        self.assertIn("withdraw", df.loc[0, "SIGNAL_KEYWORDS"])


if __name__ == "__main__":
    unittest.main()
