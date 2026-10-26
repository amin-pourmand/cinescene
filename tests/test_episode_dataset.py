import unittest
from scripts.expand_episode_dataset import episode_document, normalized_title, refresh_show


class EpisodeDatasetTests(unittest.TestCase):
    def test_refresh_preserves_identity_and_updates_sourced_genres(self):
        row = {"id": "provider:abc", "genres": ["British TV Shows"], "overview": "Old summary"}
        refresh_show(row, {"id": 12, "name": "A Show", "genres": ["Science-Fiction"],
                           "summary": "<p>A complete official summary.</p>", "premiered": "2011-01-01",
                           "url": "https://www.tvmaze.com/shows/12"})
        self.assertEqual(row["id"], "provider:abc")
        self.assertEqual(row["genres"], ["Science Fiction"])
        self.assertEqual(row["provider_genres"], ["British TV Shows"])
        self.assertEqual(row["overview"], "A complete official summary.")
        self.assertEqual(row["license"], "CC-BY-SA-4.0")

    def test_official_premiere_year_overrides_platform_catalog_year(self):
        from scripts.build_pwa_catalog import year_for
        self.assertEqual(year_for({"release_year": "2013", "premiered": "2008-01-20"}), "2008")
        self.assertEqual(year_for({"release_year": "2013"}), "2013")

    def test_episode_has_provenance_and_no_fake_scene_timing(self):
        row = episode_document({"id": "tvmaze:1", "title": "Example"}, {"id": 9, "season": 2, "number": 3, "name": "An event", "summary": "<p>A detective returns to a city and finds an unexpected clue.</p>", "url": "https://www.tvmaze.com/episodes/9"})
        self.assertEqual(row["parent_id"], "tvmaze:1")
        self.assertEqual(row["record_type"], "episode")
        self.assertEqual(row["scene_timeline"], [])
        self.assertEqual(row["matched_episode"]["license"], "CC-BY-SA-4.0")
        self.assertNotIn("<p>", row["overview"])

    def test_empty_episodes_are_not_indexed(self):
        self.assertIsNone(episode_document({"id": 1, "title": "Example"}, {"summary": "", "id": 9}))

    def test_title_matching_handles_diacritics_without_fuzzy_identity(self):
        self.assertEqual(normalized_title("Shōgun"), normalized_title("Shogun"))
        self.assertNotEqual(normalized_title("Dark"), normalized_title("Dark Matter"))
