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


class VenueTests(unittest.TestCase):
    TODAY = __import__("datetime").date(2026, 10, 25)

    def load(self, name, fn):
        return fn((FX / f"{name}.html").read_text(), today=self.TODAY)

    def test_keller(self):
        ev = self.load("keller", scrape.parse_keller)
        by = {e["title"]: e for e in ev}
        self.assertEqual(len(ev), 6)                       # "milonga" has no date -> skipped
        self.assertNotIn("milonga im kellertheater", by)
        e = by["lass mir dein lachen"]
        self.assertEqual((e["start"], e["time"], e["type"], e["venue"]), ("2026-10-25", "17:30", "event", "kellertheater"))
        self.assertEqual(by["lüdi singt zur maschine"]["category"], "comedy")
        self.assertEqual(by["alles ist gross"]["category"], "theater")
        self.assertEqual(by["heitere lieder zur einordnung der gegenwart"]["start"], "2027-01-03")  # year rolls over
        self.assertEqual(by["peter fratton – der mensch hinter den ideen"]["status"], "Ausverkauft")

    def test_gleis(self):
        ev = self.load("gleis", scrape.parse_gleis)
        by = {e["title"]: e for e in ev}
        self.assertEqual(len(ev), 6)
        e = by["Die kleinste Gabel der Welt"]
        self.assertEqual((e["start"], e["time"], e["category"], e["subtitle"]), ("2026-10-28", "15:00", "kids", "Das Büro mit dem lustigen Namen"))
        self.assertEqual(by["Theatersport"]["category"], "theater")
        self.assertEqual(by["Beratung rund um Produktionsfragen"]["type"], "event")   # no performance category
        self.assertEqual(by["34. Tanzfestival Winterthur"]["category"], "dance")
        self.assertEqual(by["Geisterbahn!"]["status"], "Ausverkauft")
        self.assertEqual(by["Geisterbahn!"]["start"], "2027-01-27")
        self.assertEqual(by["FRI3SER – Album-Release-Show"]["start"], "2027-01-08")
        self.assertTrue(by["Theatersport"]["url"].endswith("/theatersport-40"))

    def test_casino(self):
        ev = self.load("casino", scrape.parse_casino)
        titles = [(e["title"], e["start"]) for e in ev]
        self.assertEqual(len(ev), 12)
        self.assertNotIn("Nikita Miller", [t for t, _ in titles])               # cancelled
        self.assertNotIn("Bundesordner - On Tour", [t for t, _ in titles])      # "ausser Haus"
        self.assertEqual([e["start"] for e in ev if e["title"] == "Chaostheater Oropax"], ["2026-10-27", "2026-10-28"])
        self.assertEqual([e["start"] for e in ev if e["title"] == "Bundesordner"], ["2027-01-09", "2027-01-10"])
        self.assertEqual([e["start"] for e in ev if e["title"] == "Theatersport"], ["2027-03-02"])  # "März" parsed
        by = {(e["title"], e["start"]): e for e in ev}
        self.assertEqual(by[("Häsch nid gseit", "2026-10-26")]["status"], "Ausverkauft")
        self.assertEqual(by[("Häsch nid gseit", "2026-10-26")]["category"], "comedy")
        self.assertEqual(by[("Marc Sway", "2026-10-31")]["category"], "music")
        self.assertEqual(by[("Schneewittli", "2026-11-04")]["category"], "kids")
        self.assertEqual(by[("Forever Young", "2026-12-26")]["category"], "theater")
        self.assertEqual(by[("Forever Young", "2026-12-28")]["status"], "Clubangebot")
        e = by[("Escape Dinner", "2026-11-26")]
        self.assertEqual(e["type"], "event")                                    # dinner, not a show
        self.assertEqual(e["url"], "https://www.casinotheater.ch/spielplan/produktion/escape-dinner/")  # ?backID dropped
        self.assertTrue(by[("Häsch nid gseit", "2026-10-26")]["description"].startswith("Nach zahlreichen"))

    def test_tkz_only_public_winterthur(self):
        ev = self.load("tkz", scrape.parse_tkz)
        self.assertEqual([(e["title"], e["start"], e["venue"]) for e in ev], [
            ("Das Versprechen", "2026-10-25", "theater-winterthur"),
            ("Grrrls", "2026-11-17", "tkz-winterthur"),
            ("Sherlock Holmes: Der Fall Moriarty", "2026-11-20", "tkz-winterthur"),
            ("Die Katze im Sack", "2027-01-14", "tkz-winterthur")])             # not Freiburg/Zürich, no school shows
        self.assertEqual(ev[1]["status"], "Premiere")
        self.assertEqual(ev[1]["category"], "kids")
        self.assertEqual(ev[0]["url"], "https://theaterkantonzuerich.ch/spielplan/das-versprechen/")

    def test_figurentheater(self):
        ev = self.load("figurentheater", scrape.parse_figurentheater)
        by = {e["start"]: e for e in ev}
        self.assertEqual(len(ev), 4)                                            # "past performances" have no date
        e = by["2026-10-28"]
        self.assertEqual((e["title"], e["time"], e["category"], e["subtitle"]), ("Als die Steine noch Vögel Waren", "14:30", "kids", "ab 6 Jahren"))
        self.assertEqual(by["2026-10-29"]["type"], "event")                     # workshop
        self.assertEqual(by["2027-01-28"]["category"], "theater")               # evening performance
        self.assertEqual(by["2027-01-28"]["title"], "Sein oder Schein")
        self.assertEqual(by["2027-03-10"]["title"], "Des Kaisers Neue Kleider")

    def test_discount_marking(self):
        own = [
            {"type": "show", "title": "Lass mir dein Lachen", "start": "2026-10-25", "time": "17:30", "venue": "kellertheater"},
            {"type": "show", "title": "Other", "start": "2026-10-25", "time": "20:00", "venue": "kellertheater"},
            {"type": "exhibition", "title": "Expo", "start": "2026-10-25", "end": "2026-11-01", "time": None, "venue": "kellertheater"}]
        ap = [
            {"type": "show", "title": "x", "start": "2026-10-25", "time": "17:30", "venue": "kellertheater"},
            {"type": "show", "title": "Ariane show", "start": "2026-10-25", "time": "17:00", "venue": "zimmer-theater-ariane"}]
        extra = scrape.mark_discounts(own, ap)
        self.assertTrue(own[0]["applaus"])                                      # same venue/date/time
        self.assertNotIn("applaus", own[1])                                     # different time
        self.assertNotIn("applaus", own[2])                                     # exhibitions never match
        self.assertEqual([e["title"] for e in extra], ["Ariane show"])          # no own source -> kept from the list
        self.assertTrue(extra[0]["applaus"])


class AggregatorTests(unittest.TestCase):
    TODAY = __import__("datetime").date(2026, 10, 25)

    def test_venue_for(self):
        self.assertEqual(scrape.venue_for("Casinotheater Winterthur")[0], "casinotheater")       # not "theater winterthur"
        self.assertEqual(scrape.venue_for("Theater Winterthur Winterthur")[0], "theater-winterthur")
        self.assertEqual(scrape.venue_for("Kunst Museum | Beim Stadthaus Winterthur")[0], "kmw-stadthaus")
        self.assertEqual(scrape.venue_for("Villa Flora Winterthur | Sammlung Hahnloser Winterthur")[0], "kmw-flora")
        self.assertEqual(scrape.venue_for("Schloss Kyburg Kyburg")[0], "kyburg")
        self.assertEqual(scrape.venue_for("Salzhaus Winterthur"), ("other", "Salzhaus"))          # city suffix dropped
        self.assertEqual(scrape.venue_for("Sportanlage Oberseen, Gotzenwilerstrasse 12, 8405 Winterthur")[1],
                         "Sportanlage Oberseen, Gotzenwilerstrasse 12")

    def test_coucou(self):
        ev = scrape.parse_coucou((FX / "coucou.html").read_text(), today=self.TODAY)
        by = {(e["title"], e["start"]): e for e in ev}
        self.assertEqual(len([e for e in ev if e["type"] != "exhibition"]), 9)
        e = by[("Marc Sway", "2026-10-31")]
        self.assertEqual((e["time"], e["venue"], e["category"], e["type"]), ("20:00", "casinotheater", "music", "show"))
        self.assertEqual(by[("Circus Monti", "2026-10-31")]["category"], "kids")                  # Theater + Kinder -> kids
        self.assertEqual(by[("Die rote Zora", "2026-10-31")]["category"], "film")
        self.assertEqual(by[("Die rote Zora", "2026-10-31")]["place"], "Kino Cameo")
        self.assertEqual(by[("90s are now", "2026-10-31")]["category"], "party")
        self.assertEqual(by[("Jäger*innen und Sammler*innen", "2026-10-31")]["category"], "talk")
        self.assertEqual(by[("Wer hat Angst vor Leo Trotzki?", "2026-10-31")]["venue"], "zimmer-theater-ariane")
        self.assertEqual(by[("Sofalesung mit Janica Irina Madjar", "2026-11-01")]["start"], "2026-11-01")
        # exhibitions: one entry per exhibition, spanning the days it was seen; KMW and generic museum entries dropped
        ex = {e["title"]: e for e in ev if e["type"] == "exhibition"}
        self.assertEqual(sorted(ex), ["Andri Pol – Poliversum", "Rebecca Solari"])
        self.assertEqual((ex["Andri Pol – Poliversum"]["start"], ex["Andri Pol – Poliversum"]["end"]), ("2026-10-31", "2026-11-01"))
        self.assertEqual(ex["Andri Pol – Poliversum"]["venue"], "fotomuseum")
        self.assertTrue(ex["Andri Pol – Poliversum"]["ongoing"])
        self.assertEqual([e["type"] for e in ev if e["title"] == "Rebecca Solari"], ["exhibition"])   # listed once, as an exhibition
        self.assertIsNone(ex["Rebecca Solari"]["time"])                                            # 00:00-23:59 = all day

    def test_nuxt_events(self):
        ev = scrape.parse_nuxt_events((FX / "nuxt_events.html").read_text(), "https://stadt.winterthur.ch/")
        by = {e["title"]: e for e in ev}
        self.assertEqual(len(ev), 5)
        self.assertEqual((by["Boutique Nepomuk - Lagerverkauf"]["venue"], by["Boutique Nepomuk - Lagerverkauf"]["time"]), ("alte-kaserne", "10:00"))
        self.assertEqual(by["Bistro Taktvoll"]["venue"], "alte-kaserne")
        self.assertEqual(by["VOM ZUFALLSFUND ZUM KULTURGUT"]["venue"], "muenzkabinett")
        self.assertEqual(by["Girls' Day"]["venue"], "other")
        self.assertEqual(by["Girls' Day"]["place"], "Sportanlage Oberseen, Gotzenwilerstrasse 12")
        self.assertEqual(by["Girls' Day"]["start"], "2026-11-07")

    def test_lokal_skips_private_hire_and_past(self):
        ev = scrape.parse_lokal((FX / "lokal.html").read_text(), today=self.TODAY)
        self.assertEqual([e["title"] for e in ev], ["The Crocks Albumtaufe im Lok.al!", "GlobalDance mit Toxidi im Lok.al!", "Flower Power im Lok.al!"])
        g = ev[1]
        self.assertEqual((g["start"], g["end"], g["time"]), ("2026-11-14", "2026-11-14", "19:30"))   # "14.–15. Nov, until 1:00" = one evening
        self.assertEqual(ev[0]["category"], "music")
        self.assertEqual(ev[0]["venue"], "lokal")

    def test_dampfzentrum_rule(self):
        ev = scrape.scrape_dampfzentrum(today=self.TODAY)
        days = [e["start"] for e in ev][:4]
        self.assertEqual(days, ["2026-10-24" if False else "2026-11-14", "2026-11-28", "2026-12-12", "2026-12-26"])  # 2nd & 4th Saturdays
        self.assertTrue(all(e["time"] == "13:00" for e in ev))

    def test_jsonld_best_effort(self):
        html = (FX / "jsonld_museum.html").read_text()
        ev = scrape.jsonld_events(html, "https://www.fotomuseum.ch/de/", "fotomuseum", today=self.TODAY)
        self.assertEqual([e["title"] for e in ev], ["Familienführung", "Bad link"])                  # past event dropped
        self.assertEqual((ev[0]["start"], ev[0]["time"], ev[0]["venue"]), ("2026-11-15", "14:00", "fotomuseum"))
        self.assertEqual(ev[1]["url"], "https://www.fotomuseum.ch/de/")                              # javascript: URL rejected
        only_w = scrape.jsonld_events(html, "https://x.ch/", "other", True, today=self.TODAY)
        self.assertEqual([e["title"] for e in only_w], ["Familienführung"])                          # location must say Winterthur

    def test_dedupe_aggregators(self):
        own = {"type": "show", "title": "Marc Sway", "start": "2026-10-31", "time": "20:00", "venue": "casinotheater"}
        agg = dict(own, title="Marc Sway – Roots Unplugged")
        same_title_other_time = {"type": "event", "title": "Wissenschaft um 11", "start": "2026-11-01", "time": "11:00", "venue": "alte-kaserne"}
        agg2 = dict(same_title_other_time, time="10:45")
        a = {"type": "event", "title": "Foo", "start": "2026-11-01", "time": "18:00", "venue": "other", "place": "Salzhaus"}
        b = {"type": "event", "title": "Bar", "start": "2026-11-01", "time": "18:00", "venue": "other", "place": "Gaswerk"}   # different place, same time
        out = scrape.dedupe([("own", [own, same_title_other_time]), ("coucou", [agg, agg2, a, b])])
        self.assertEqual([e["title"] for e in out], ["Marc Sway", "Wissenschaft um 11", "Foo", "Bar"])
        ex1 = {"type": "exhibition", "title": "Show", "start": "2026-10-31", "end": "2026-11-01", "venue": "fotomuseum"}
        self.assertEqual(len(scrape.dedupe([("a", [ex1]), ("b", [dict(ex1)])])), 2)                  # exhibitions are never merged


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


class VenueTests(unittest.TestCase):
    TODAY = __import__("datetime").date(2026, 10, 25)

    def load(self, name, fn):
        return fn((FX / f"{name}.html").read_text(), today=self.TODAY)

    def test_keller(self):
        ev = self.load("keller", scrape.parse_keller)
        by = {e["title"]: e for e in ev}
        self.assertEqual(len(ev), 6)                       # "milonga" has no date -> skipped
        self.assertNotIn("milonga im kellertheater", by)
        e = by["lass mir dein lachen"]
        self.assertEqual((e["start"], e["time"], e["type"], e["venue"]), ("2026-10-25", "17:30", "event", "kellertheater"))
        self.assertEqual(by["lüdi singt zur maschine"]["category"], "comedy")
        self.assertEqual(by["alles ist gross"]["category"], "theater")
        self.assertEqual(by["heitere lieder zur einordnung der gegenwart"]["start"], "2027-01-03")  # year rolls over
        self.assertEqual(by["peter fratton – der mensch hinter den ideen"]["status"], "Ausverkauft")

    def test_gleis(self):
        ev = self.load("gleis", scrape.parse_gleis)
        by = {e["title"]: e for e in ev}
        self.assertEqual(len(ev), 6)
        e = by["Die kleinste Gabel der Welt"]
        self.assertEqual((e["start"], e["time"], e["category"], e["subtitle"]), ("2026-10-28", "15:00", "kids", "Das Büro mit dem lustigen Namen"))
        self.assertEqual(by["Theatersport"]["category"], "theater")
        self.assertEqual(by["Beratung rund um Produktionsfragen"]["type"], "event")   # no performance category
        self.assertEqual(by["34. Tanzfestival Winterthur"]["category"], "dance")
        self.assertEqual(by["Geisterbahn!"]["status"], "Ausverkauft")
        self.assertEqual(by["Geisterbahn!"]["start"], "2027-01-27")
        self.assertEqual(by["FRI3SER – Album-Release-Show"]["start"], "2027-01-08")
        self.assertTrue(by["Theatersport"]["url"].endswith("/theatersport-40"))

    def test_casino(self):
        ev = self.load("casino", scrape.parse_casino)
        titles = [(e["title"], e["start"]) for e in ev]
        self.assertEqual(len(ev), 12)
        self.assertNotIn("Nikita Miller", [t for t, _ in titles])               # cancelled
        self.assertNotIn("Bundesordner - On Tour", [t for t, _ in titles])      # "ausser Haus"
        self.assertEqual([e["start"] for e in ev if e["title"] == "Chaostheater Oropax"], ["2026-10-27", "2026-10-28"])
        self.assertEqual([e["start"] for e in ev if e["title"] == "Bundesordner"], ["2027-01-09", "2027-01-10"])
        self.assertEqual([e["start"] for e in ev if e["title"] == "Theatersport"], ["2027-03-02"])  # "März" parsed
        by = {(e["title"], e["start"]): e for e in ev}
        self.assertEqual(by[("Häsch nid gseit", "2026-10-26")]["status"], "Ausverkauft")
        self.assertEqual(by[("Häsch nid gseit", "2026-10-26")]["category"], "comedy")
        self.assertEqual(by[("Marc Sway", "2026-10-31")]["category"], "music")
        self.assertEqual(by[("Schneewittli", "2026-11-04")]["category"], "kids")
        self.assertEqual(by[("Forever Young", "2026-12-26")]["category"], "theater")
        self.assertEqual(by[("Forever Young", "2026-12-28")]["status"], "Clubangebot")
        e = by[("Escape Dinner", "2026-11-26")]
        self.assertEqual(e["type"], "event")                                    # dinner, not a show
        self.assertEqual(e["url"], "https://www.casinotheater.ch/spielplan/produktion/escape-dinner/")  # ?backID dropped
        self.assertTrue(by[("Häsch nid gseit", "2026-10-26")]["description"].startswith("Nach zahlreichen"))

    def test_tkz_only_public_winterthur(self):
        ev = self.load("tkz", scrape.parse_tkz)
        self.assertEqual([(e["title"], e["start"], e["venue"]) for e in ev], [
            ("Das Versprechen", "2026-10-25", "theater-winterthur"),
            ("Grrrls", "2026-11-17", "tkz-winterthur"),
            ("Sherlock Holmes: Der Fall Moriarty", "2026-11-20", "tkz-winterthur"),
            ("Die Katze im Sack", "2027-01-14", "tkz-winterthur")])             # not Freiburg/Zürich, no school shows
        self.assertEqual(ev[1]["status"], "Premiere")
        self.assertEqual(ev[1]["category"], "kids")
        self.assertEqual(ev[0]["url"], "https://theaterkantonzuerich.ch/spielplan/das-versprechen/")

    def test_figurentheater(self):
        ev = self.load("figurentheater", scrape.parse_figurentheater)
        by = {e["start"]: e for e in ev}
        self.assertEqual(len(ev), 4)                                            # "past performances" have no date
        e = by["2026-10-28"]
        self.assertEqual((e["title"], e["time"], e["category"], e["subtitle"]), ("Als die Steine noch Vögel Waren", "14:30", "kids", "ab 6 Jahren"))
        self.assertEqual(by["2026-10-29"]["type"], "event")                     # workshop
        self.assertEqual(by["2027-01-28"]["category"], "theater")               # evening performance
        self.assertEqual(by["2027-01-28"]["title"], "Sein oder Schein")
        self.assertEqual(by["2027-03-10"]["title"], "Des Kaisers Neue Kleider")

    def test_discount_marking(self):
        own = [
            {"type": "show", "title": "Lass mir dein Lachen", "start": "2026-10-25", "time": "17:30", "venue": "kellertheater"},
            {"type": "show", "title": "Other", "start": "2026-10-25", "time": "20:00", "venue": "kellertheater"},
            {"type": "exhibition", "title": "Expo", "start": "2026-10-25", "end": "2026-11-01", "time": None, "venue": "kellertheater"}]
        ap = [
            {"type": "show", "title": "x", "start": "2026-10-25", "time": "17:30", "venue": "kellertheater"},
            {"type": "show", "title": "Ariane show", "start": "2026-10-25", "time": "17:00", "venue": "zimmer-theater-ariane"}]
        extra = scrape.mark_discounts(own, ap)
        self.assertTrue(own[0]["applaus"])                                      # same venue/date/time
        self.assertNotIn("applaus", own[1])                                     # different time
        self.assertNotIn("applaus", own[2])                                     # exhibitions never match
        self.assertEqual([e["title"] for e in extra], ["Ariane show"])          # no own source -> kept from the list
        self.assertTrue(extra[0]["applaus"])


class AggregatorTests(unittest.TestCase):
    TODAY = __import__("datetime").date(2026, 10, 25)

    def test_venue_for(self):
        self.assertEqual(scrape.venue_for("Casinotheater Winterthur")[0], "casinotheater")       # not "theater winterthur"
        self.assertEqual(scrape.venue_for("Theater Winterthur Winterthur")[0], "theater-winterthur")
        self.assertEqual(scrape.venue_for("Kunst Museum | Beim Stadthaus Winterthur")[0], "kmw-stadthaus")
        self.assertEqual(scrape.venue_for("Villa Flora Winterthur | Sammlung Hahnloser Winterthur")[0], "kmw-flora")
        self.assertEqual(scrape.venue_for("Schloss Kyburg Kyburg")[0], "kyburg")
        self.assertEqual(scrape.venue_for("Salzhaus Winterthur"), ("other", "Salzhaus"))          # city suffix dropped
        self.assertEqual(scrape.venue_for("Sportanlage Oberseen, Gotzenwilerstrasse 12, 8405 Winterthur")[1],
                         "Sportanlage Oberseen, Gotzenwilerstrasse 12")

    def test_coucou(self):
        ev = scrape.parse_coucou((FX / "coucou.html").read_text(), today=self.TODAY)
        by = {(e["title"], e["start"]): e for e in ev}
        self.assertEqual(len([e for e in ev if e["type"] != "exhibition"]), 9)
        e = by[("Marc Sway", "2026-10-31")]
        self.assertEqual((e["time"], e["venue"], e["category"], e["type"]), ("20:00", "casinotheater", "music", "show"))
        self.assertEqual(by[("Circus Monti", "2026-10-31")]["category"], "kids")                  # Theater + Kinder -> kids
        self.assertEqual(by[("Die rote Zora", "2026-10-31")]["category"], "film")
        self.assertEqual(by[("Die rote Zora", "2026-10-31")]["place"], "Kino Cameo")
        self.assertEqual(by[("90s are now", "2026-10-31")]["category"], "party")
        self.assertEqual(by[("Jäger*innen und Sammler*innen", "2026-10-31")]["category"], "talk")
        self.assertEqual(by[("Wer hat Angst vor Leo Trotzki?", "2026-10-31")]["venue"], "zimmer-theater-ariane")
        self.assertEqual(by[("Sofalesung mit Janica Irina Madjar", "2026-11-01")]["start"], "2026-11-01")
        # exhibitions: one entry per exhibition, spanning the days it was seen; KMW and generic museum entries dropped
        ex = {e["title"]: e for e in ev if e["type"] == "exhibition"}
        self.assertEqual(sorted(ex), ["Andri Pol – Poliversum", "Rebecca Solari"])
        self.assertEqual((ex["Andri Pol – Poliversum"]["start"], ex["Andri Pol – Poliversum"]["end"]), ("2026-10-31", "2026-11-01"))
        self.assertEqual(ex["Andri Pol – Poliversum"]["venue"], "fotomuseum")
        self.assertTrue(ex["Andri Pol – Poliversum"]["ongoing"])
        self.assertEqual([e["type"] for e in ev if e["title"] == "Rebecca Solari"], ["exhibition"])   # listed once, as an exhibition
        self.assertIsNone(ex["Rebecca Solari"]["time"])                                            # 00:00-23:59 = all day

    def test_nuxt_events(self):
        ev = scrape.parse_nuxt_events((FX / "nuxt_events.html").read_text(), "https://stadt.winterthur.ch/")
        by = {e["title"]: e for e in ev}
        self.assertEqual(len(ev), 5)
        self.assertEqual((by["Boutique Nepomuk - Lagerverkauf"]["venue"], by["Boutique Nepomuk - Lagerverkauf"]["time"]), ("alte-kaserne", "10:00"))
        self.assertEqual(by["Bistro Taktvoll"]["venue"], "alte-kaserne")
        self.assertEqual(by["VOM ZUFALLSFUND ZUM KULTURGUT"]["venue"], "muenzkabinett")
        self.assertEqual(by["Girls' Day"]["venue"], "other")
        self.assertEqual(by["Girls' Day"]["place"], "Sportanlage Oberseen, Gotzenwilerstrasse 12")
        self.assertEqual(by["Girls' Day"]["start"], "2026-11-07")

    def test_lokal_skips_private_hire_and_past(self):
        ev = scrape.parse_lokal((FX / "lokal.html").read_text(), today=self.TODAY)
        self.assertEqual([e["title"] for e in ev], ["The Crocks Albumtaufe im Lok.al!", "GlobalDance mit Toxidi im Lok.al!", "Flower Power im Lok.al!"])
        g = ev[1]
        self.assertEqual((g["start"], g["end"], g["time"]), ("2026-11-14", "2026-11-14", "19:30"))   # "14.–15. Nov, until 1:00" = one evening
        self.assertEqual(ev[0]["category"], "music")
        self.assertEqual(ev[0]["venue"], "lokal")

    def test_dampfzentrum_rule(self):
        ev = scrape.scrape_dampfzentrum(today=self.TODAY)
        days = [e["start"] for e in ev][:4]
        self.assertEqual(days, ["2026-10-24" if False else "2026-11-14", "2026-11-28", "2026-12-12", "2026-12-26"])  # 2nd & 4th Saturdays
        self.assertTrue(all(e["time"] == "13:00" for e in ev))

    def test_jsonld_best_effort(self):
        html = (FX / "jsonld_museum.html").read_text()
        ev = scrape.jsonld_events(html, "https://www.fotomuseum.ch/de/", "fotomuseum", today=self.TODAY)
        self.assertEqual([e["title"] for e in ev], ["Familienführung", "Bad link"])                  # past event dropped
        self.assertEqual((ev[0]["start"], ev[0]["time"], ev[0]["venue"]), ("2026-11-15", "14:00", "fotomuseum"))
        self.assertEqual(ev[1]["url"], "https://www.fotomuseum.ch/de/")                              # javascript: URL rejected
        only_w = scrape.jsonld_events(html, "https://x.ch/", "other", True, today=self.TODAY)
        self.assertEqual([e["title"] for e in only_w], ["Familienführung"])                          # location must say Winterthur

    def test_dedupe_aggregators(self):
        own = {"type": "show", "title": "Marc Sway", "start": "2026-10-31", "time": "20:00", "venue": "casinotheater"}
        agg = dict(own, title="Marc Sway – Roots Unplugged")
        same_title_other_time = {"type": "event", "title": "Wissenschaft um 11", "start": "2026-11-01", "time": "11:00", "venue": "alte-kaserne"}
        agg2 = dict(same_title_other_time, time="10:45")
        a = {"type": "event", "title": "Foo", "start": "2026-11-01", "time": "18:00", "venue": "other", "place": "Salzhaus"}
        b = {"type": "event", "title": "Bar", "start": "2026-11-01", "time": "18:00", "venue": "other", "place": "Gaswerk"}   # different place, same time
        out = scrape.dedupe([("own", [own, same_title_other_time]), ("coucou", [agg, agg2, a, b])])
        self.assertEqual([e["title"] for e in out], ["Marc Sway", "Wissenschaft um 11", "Foo", "Bar"])
        ex1 = {"type": "exhibition", "title": "Show", "start": "2026-10-31", "end": "2026-11-01", "venue": "fotomuseum"}
        self.assertEqual(len(scrape.dedupe([("a", [ex1]), ("b", [dict(ex1)])])), 2)                  # exhibitions are never merged


if __name__ == "__main__":
    unittest.main()
