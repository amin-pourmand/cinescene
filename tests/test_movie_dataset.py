from datetime import date
import unittest
from unittest.mock import Mock

from scripts.expand_movie_dataset import RankedFilmTables, complete_article, match_existing, merge_document, movie_document, text_sections


def claim(value):
    return {"mainsnak": {"snaktype": "value", "datavalue": {"value": value}}}


def source():
    page = {"pageid": 123, "title": "Example (2024 film)", "revisions": [{"revid": 456}],
            "extract": "Example is a 2024 mystery film.\n\n== Plot ==\nA detective finds a key.\n\nShe opens a hidden room.\n\n== Production ==\nShot in a studio."}
    entity = {"id": "Q123", "labels": {"en": {"value": "Example"}},
              "claims": {"P577": [claim({"time": "+2024-03-01T00:00:00Z"})], "P4947": [claim("999")]}}
    return page, entity


class MovieDatasetTests(unittest.TestCase):
    def test_each_full_article_is_requested_individually_not_silently_truncated(self):
        client = Mock()
        client.get.return_value = {"query": {"pages": [{"pageid": 123, "extract": "Complete text"}]}}
        page = {"pageid": 123, "pageprops": {"wikibase_item": "Q123"}}
        self.assertEqual(complete_article(client, page)["extract"], "Complete text")
        self.assertEqual(client.get.call_args.kwargs["exlimit"], 1)
        self.assertEqual(client.get.call_args.kwargs["pageids"], 123)
        self.assertNotIn("extract", page)

    def test_only_rank_title_gross_tables_supply_seeds(self):
        parser = RankedFilmTables()
        parser.feed('<table><tr><th>Rank</th><th>Title</th><th>Worldwide gross</th></tr>'
                    '<tr><th>1</th><td><i><a href="/wiki/Example:_Part_Two" title="Example: Part Two">Example</a></i></td><td>10</td></tr></table>'
                    '<table><tr><td><a href="/wiki/Actor">An actor</a></td></tr></table>')
        self.assertEqual(parser.titles(), ["Example: Part Two"])

    def test_plot_excludes_production_and_keeps_late_story_details(self):
        overview, plot = text_sections(source()[0]["extract"])
        self.assertIn("mystery film", overview)
        self.assertIn("hidden room", plot)
        self.assertNotIn("studio", plot)

    def test_source_revision_and_license_are_retained_without_fake_scenes(self):
        doc = movie_document(*source(), {}, date(2026, 10, 28))
        self.assertEqual(doc["id"], 999)
        self.assertEqual(doc["evidence_sources"][0]["revision_id"], 456)
        self.assertEqual(doc["evidence_sources"][0]["license"], "CC-BY-SA-4.0")
        self.assertEqual(doc["scene_timeline"], [])
        self.assertEqual(doc["scene_descriptions"], [])
        self.assertEqual(len(doc["story_passages"]), 2)

    def test_unreleased_or_unverified_movies_are_not_imported(self):
        page, entity = source()
        with self.assertRaisesRegex(ValueError, "unreleased"):
            movie_document(page, entity, {}, date(2023, 1, 1))
        entity["claims"]["P577"] = []
        page["extract"] = "Example is a mystery film."
        with self.assertRaisesRegex(ValueError, "unverified"):
            movie_document(page, entity, {}, date(2026, 1, 1))

    def test_historical_lead_year_can_fill_missing_structured_release_with_explicit_provenance(self):
        page, entity = source()
        entity["claims"]["P577"] = []
        document = movie_document(page, entity, {}, date(2026, 10, 28))
        self.assertEqual(document["release_date"], "2024")
        self.assertEqual(document["release_date_source"], "wikipedia:lead-year")

    def test_historical_year_precision_is_preserved_without_inventing_a_date(self):
        page, entity = source()
        entity["claims"]["P577"] = [claim({"time": "+1997-00-00T00:00:00Z"})]
        self.assertEqual(movie_document(page, entity, {}, date(2026, 1, 1))["release_date"], "1997")
        entity["claims"]["P577"] = [claim({"time": "+2026-00-00T00:00:00Z"})]
        page["extract"] = "Example is a 2026 mystery film."
        with self.assertRaisesRegex(ValueError, "unreleased"):
            movie_document(page, entity, {}, date(2026, 10, 28))

    def test_disambiguation_is_not_a_film(self):
        page, entity = source()
        page["pageprops"] = {"disambiguation": ""}
        with self.assertRaisesRegex(ValueError, "disambiguation"):
            movie_document(page, entity, {}, date(2026, 1, 1))
        page.pop("pageprops")
        page["extract"] = "Example may refer to a 1997 film or a 2026 film."
        with self.assertRaisesRegex(ValueError, "disambiguation"):
            movie_document(page, entity, {}, date(2026, 1, 1))

    def test_remakes_require_same_year_and_ambiguous_identity_is_rejected(self):
        doc = movie_document(*source(), {}, date(2026, 10, 28))
        older = {"id": 1, "title": "Example", "release_year": "1980"}
        self.assertIsNone(match_existing([older], doc))
        newer = {"id": 2, "title": "Example", "release_year": "2024"}
        self.assertIs(match_existing([older, newer], doc), newer)
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            match_existing([newer, dict(newer, id=3)], doc)

    def test_merge_is_repeatable_and_preserves_real_scene_evidence(self):
        incoming = movie_document(*source(), {}, date(2026, 10, 28))
        old = dict(incoming, id="original:1", overview="Existing summary", wiki_plot="", plot="",
                   scene_timeline=[{"start": 10}], source="legacy", rich_text="Title: Original | Mood: tense")
        merged = merge_document(old, incoming)
        self.assertEqual(merged["id"], "original:1")
        self.assertEqual(merged["overview"], "Existing summary")
        self.assertEqual(merged["scene_timeline"], [{"start": 10}])
        self.assertEqual(merged["rich_text"], old["rich_text"])
        self.assertEqual(merge_document(merged, incoming), merged)

    def test_revision_attribution_matches_the_imported_plot_even_when_older_text_is_longer(self):
        incoming = movie_document(*source(), {}, date(2026, 10, 28))
        old = dict(incoming, wiki_plot="Unattributed old text. " * 100)
        merged = merge_document(old, incoming)
        self.assertEqual(merged["wiki_plot"], incoming["wiki_plot"])
        self.assertEqual(merged["legacy_plot"], old["wiki_plot"])


if __name__ == "__main__":
    unittest.main()
