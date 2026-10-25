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


class TheaterTests(unittest.TestCase):
    TODAY = __import__("datetime").date(2026, 10, 25)

    def test_theater_winterthur_home(self):
        ev = scrape.parse_tw_home((FX / "tw_home.html").read_text(), today=self.TODAY)
        self.assertEqual(len(ev), 3)
        self.assertEqual((ev[0]["start"], ev[0]["time"], ev[0]["type"], ev[0]["category"]), ("2026-10-25", "14:30", "show", "theater"))
        self.assertEqual(ev[0]["url"], "https://www.theaterwinterthur.ch/das-versprechen")
        self.assertEqual(ev[1]["type"], "event")          # category "Extra"
        self.assertEqual(ev[2]["start"], "2027-01-14")    # year rolls over

    def test_applaus(self):
        ev = scrape.parse_applaus((FX / "applaus.html").read_text())
        self.assertEqual(len(ev), 12)  # the plain "Zimmer-Theater Ariane" link is ignored
        by = {e["url"].rstrip("/").split("/")[-1]: e for e in ev}

        e = by["wer-hat-angst-vor-leo-trotzki"]
        self.assertEqual((e["start"], e["time"], e["venue"]), ("2026-10-25", "17:00", "zimmer-theater-ariane"))
        self.assertEqual(e["title"], "Wer hat Angst vor Leo Trotzki?")
        self.assertEqual(e["subtitle"], "Jubiläumsproduktion 15 Jahre Theater Ariane")

        self.assertEqual(by["lass-mir-dein-lachen"]["title"], "lass mir dein lachen")
        self.assertEqual(by["lass-mir-dein-lachen"]["venue"], "kellertheater")
        self.assertEqual(by["theatersport-21"]["title"], "Theatersport")            # slug suffix -21 ignored
        self.assertEqual(by["theatersport-21"]["subtitle"], "Badumts vs. Drei-Vierteltakt")
        self.assertEqual(by["der-kirschgarten-2"]["title"], "Der Kirschgarten")
        self.assertEqual(by["familie-floez-dr-nest"]["title"], "Familie Flöz «Dr. Nest»")
        self.assertEqual(by["falsch-verbunden-mit-dem-chaellerfon-auf-die-buehne"]["title"], "«falsch verbunden» – mit dem Chällerfon auf die Bühne")
        self.assertEqual(by["rythmosphere"]["title"], "Rythmosphère")                # accents match the plain slug
        self.assertEqual(by["plattentaufe-stereogefuehle"]["title"], "Plattentaufe «Stereogefühle»")
        self.assertEqual(by["sherlock-holmes-der-fall-moriarty"]["venue"], "tkz-winterthur")
        self.assertEqual(by["die-kleinste-gabel-der-welt"]["title"], "Die kleinste Gabel der Welt")

    def test_applaus_categories(self):
        by = {e["url"].rstrip("/").split("/")[-1]: e["category"] for e in scrape.parse_applaus((FX / "applaus.html").read_text())}
        self.assertEqual(by["die-kleinste-gabel-der-welt"], "kids")
        self.assertEqual(by["rythmosphere"], "dance")
        self.assertEqual(by["junior-ballett-zuerich-art-matters"], "dance")
        self.assertEqual(by["falsch-verbunden-mit-dem-chaellerfon-auf-die-buehne"], "comedy")
        self.assertEqual(by["theatersport-21"], "comedy")
        self.assertEqual(by["der-vogelhaendler"], "music")
        self.assertEqual(by["plattentaufe-stereogefuehle"], "music")
        self.assertEqual(by["der-kirschgarten-2"], "theater")

    def test_applaus_slug_fallback(self):
        kicker, title, desc = scrape.split_by_slug("Etwas ganz anderes im Text", "nicht-vorhanden")
        self.assertIsNone(title)

    def test_dedupe_across_sources(self):
        tw = {"type": "show", "title": "Das Versprechen", "start": "2026-10-25", "end": "2026-10-25", "time": "14:30", "venue": "theater-winterthur"}
        ap = {"type": "show", "title": "Das Versprechen (applaus)", "start": "2026-10-25", "end": "2026-10-25", "time": "14:30", "venue": "theater-winterthur"}
        other = dict(ap, start="2026-10-26")
        out = scrape.dedupe([("tw", [tw]), ("ap", [ap, other])])
        self.assertEqual([e["title"] for e in out], ["Das Versprechen", "Das Versprechen (applaus)"])
        self.assertEqual(out[1]["start"], "2026-10-26")


if __name__ == "__main__":
    unittest.main()
