"""Run with: python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import scrape

FX = Path(__file__).parent / "fixtures"


class ParseTests(unittest.TestCase):
    def test_exhibitions(self):
        ex = scrape.parse_kmw_exhibitions((FX / "exhibitions.html").read_text())
        by = {e["url"].rstrip("/").split("/")[-1]: e for e in ex}
        self.assertEqual(len(ex), 4)  # duplicate Hatoum link is dropped
        self.assertEqual(by["3-x-2-fokus-winterthur-3"]["start"], "2026-10-09")  # year inferred
        self.assertEqual(by["3-x-2-fokus-winterthur-3"]["end"], "2026-11-01")
        self.assertEqual(by["mona-hatoum"]["end"], "2027-01-31")  # crosses new year
        self.assertEqual(by["mona-hatoum"]["title"], "Mona Hatoum – Routes of Dissonance")
        self.assertEqual(by["zur-sonne-zur-freiheit"]["start"], "2026-07-04")
        self.assertEqual(by["jutta-koether"]["venue"], "kmw-flora")

    def test_events(self):
        ev = scrape.parse_kmw_events((FX / "agenda.html").read_text())
        self.assertEqual(len(ev), 2)
        self.assertEqual(ev[1]["start"], "2026-11-08")
        self.assertEqual(ev[1]["time"], "15:00–17:00")
        self.assertEqual(ev[1]["venue"], "kmw-stadthaus")
        self.assertIn("Second Skin", ev[1]["title"])


if __name__ == "__main__":
    unittest.main()
