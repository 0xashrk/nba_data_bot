import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import main


class MainDispatchTests(unittest.TestCase):
    def test_main_dispatches_supported_commands_with_default_args(self):
        command_map = {
            "all": "cmd_all",
            "last5": "cmd_last5",
            "advanced": "cmd_advanced",
            "fourfactors": "cmd_fourfactors",
            "defense": "cmd_defense",
            "injuries": "cmd_injuries",
            "markdown": "cmd_markdown",
        }

        for command_name, function_name in command_map.items():
            with self.subTest(command=command_name):
                with patch.object(main, function_name) as command_mock:
                    with patch.object(sys, "argv", ["main.py", command_name]):
                        main.main()

                command_mock.assert_called_once()
                parsed_args = command_mock.call_args.args[0]
                self.assertEqual(parsed_args.command, command_name)
                self.assertEqual(parsed_args.format, "csv")
                self.assertEqual(parsed_args.output, "./output")

    def test_main_exits_with_status_one_when_command_raises(self):
        with patch.object(main, "cmd_last5", side_effect=RuntimeError("boom")):
            with patch.object(sys, "argv", ["main.py", "last5"]):
                with redirect_stdout(io.StringIO()) as stdout:
                    with self.assertRaises(SystemExit) as exit_context:
                        main.main()

        self.assertEqual(exit_context.exception.code, 1)
        self.assertIn("Error: boom", stdout.getvalue())


class MainSmokeTests(unittest.TestCase):
    def test_cmd_all_continues_after_individual_command_failure(self):
        args = SimpleNamespace(format="csv", output="./output")
        last5_df = pd.DataFrame([{"TEAM": "Boston Celtics", "L5_WINS": 4, "L5_LOSSES": 1, "L5_RATING": 12.5}])
        injury_df = pd.DataFrame(
            [{"TEAM": "Boston Celtics", "PLAYER_NAME": "Player One", "CURRENT_STATUS": "OUT", "REASON": "Knee"}]
        )

        with patch.object(main, "cmd_last5", return_value=last5_df):
            with patch.object(main, "cmd_advanced", side_effect=RuntimeError("nba api down")):
                with patch.object(main, "cmd_fourfactors", return_value=pd.DataFrame([{"TEAM_NAME": "Boston Celtics"}])):
                    with patch.object(main, "cmd_defense", return_value=pd.DataFrame([{"TEAM_NAME": "Boston Celtics"}])):
                        with patch.object(main, "cmd_injuries", return_value=injury_df):
                            results = main.cmd_all(args)

        self.assertEqual(list(results), ["last5", "advanced", "fourfactors", "defense", "injuries"])
        self.assertEqual(len(results["last5"]), 1)
        self.assertIsNone(results["advanced"])
        self.assertEqual(len(results["injuries"]), 1)

    def test_cmd_markdown_writes_expected_nba_sections(self):
        advanced_df = pd.DataFrame(
            [
                {
                    "TEAM_NAME": "Boston Celtics",
                    "W": 50,
                    "L": 20,
                    "NET_RATING": 8.5,
                    "OFF_RATING": 120.1,
                    "DEF_RATING": 111.6,
                    "PACE": 99.2,
                }
            ]
        )
        last5_df = pd.DataFrame([{"TEAM": "Boston Celtics", "L5_WINS": 4, "L5_LOSSES": 1, "L5_RATING": 12.5}])
        four_factors_df = pd.DataFrame([{"TEAM_NAME": "Boston Celtics", "EFG_PCT": 0.58}])
        defense_df = pd.DataFrame([{"TEAM_NAME": "Boston Celtics", "OPP_PTS": 104.2}])
        injuries_df = pd.DataFrame(
            [
                {
                    "TEAM": "Boston Celtics",
                    "PLAYER_NAME": "Player One",
                    "CURRENT_STATUS": "QUESTIONABLE",
                    "REASON": "Ankle soreness",
                }
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            args = SimpleNamespace(output=tmpdir)
            with patch.object(main, "get_last5_form", return_value=last5_df):
                with patch.object(main, "get_advanced_stats", return_value=advanced_df):
                    with patch.object(main, "get_four_factors", return_value=four_factors_df):
                        with patch.object(main, "get_defense_stats", return_value=defense_df):
                            with patch.object(main, "get_injury_report", return_value=injuries_df):
                                results = main.cmd_markdown(args)

            output_path = Path(tmpdir) / "nba_data.md"
            self.assertTrue(output_path.exists())
            self.assertEqual(len(results["advanced"]), 1)

            content = output_path.read_text()
            self.assertIn("# NBA Stats & Injury Report", content)
            self.assertIn("## Data Sources", content)
            self.assertIn("## Team Standings & Ratings", content)
            self.assertIn("## Last 5 Games Form", content)
            self.assertIn("## Four Factors", content)
            self.assertIn("## Defense Stats", content)
            self.assertIn("## Injury Report", content)
            self.assertIn("### Boston Celtics", content)
            self.assertIn("| Advanced Stats | stats.nba.com | OK | 1 |", content)


if __name__ == "__main__":
    unittest.main()
