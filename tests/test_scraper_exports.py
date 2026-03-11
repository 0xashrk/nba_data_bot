import unittest

import scraper
from scraper.injury_report import get_injury_report
from scraper.nba_stats import get_advanced_stats, get_defense_stats, get_four_factors
from scraper.teamrankings import get_last5_form


class ScraperExportTests(unittest.TestCase):
    def test_nba_exports_remain_available_from_top_level_package(self):
        expected_exports = {
            "get_last5_form": get_last5_form,
            "get_advanced_stats": get_advanced_stats,
            "get_four_factors": get_four_factors,
            "get_defense_stats": get_defense_stats,
            "get_injury_report": get_injury_report,
        }

        for export_name, function in expected_exports.items():
            with self.subTest(export=export_name):
                self.assertIn(export_name, scraper.__all__)
                self.assertTrue(hasattr(scraper, export_name))
                self.assertIs(getattr(scraper, export_name), function)


if __name__ == "__main__":
    unittest.main()
