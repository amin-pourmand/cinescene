"""Import attributed TVmaze episode evidence, without inventing scene timestamps."""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.import_tvmaze_series import load_list, save_list, strip_html, to_document

LICENSE = "CC-BY-SA-4.0"
EXPECTED_YEARS = {"Silo": "2023", "Severance": "2022", "Fallout": "2024", "The Bear": "2022", "Shogun": "2024", "Lost": "2004"}
DEFAULT_SHOWS = ["Breaking Bad", "Better Call Saul", "Dark", "Black Mirror", "Stranger Things",
                 "Severance", "Silo", "Andor", "The Last of Us", "The Bear", "Fallout", "Shogun",
                 "The Queen's Gambit", "Chernobyl", "Westworld", "Mr. Robot", "Sherlock", "Lost"]


def normalized_title(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))


def existing_show(shows, official, unambiguous_name, official_cast=None):
    shows = list(shows)
    identity = str(official["id"])
    imdb = (official.get("externals") or {}).get("imdb")
    exact_ids = [row for row in shows if str(row.get("external_tvmaze")) == identity or
                 str(row.get("id")) == f"tvmaze:{identity}" or (imdb and row.get("external_imdb") == imdb)]
    if len(exact_ids) > 1:
        raise ValueError("Multiple existing series claim the same external identity")
    names = [row for row in shows if normalized_title(row["title"]) == normalized_title(official["name"])]
    if official_cast:
        actors = {normalized_title(name) for name in official_cast}
        proven = [row for row in names if not row.get("external_tvmaze") and not row.get("external_imdb") and not row.get("premiere_source")
                  and len(actors & {normalized_title(name) for name in row.get("cast", [])}) >= 2]
        if len(proven) > 1:
            raise ValueError("Multiple provider records match the canonical cast; identity needs review")
        if proven:
            proven[0]["identity_evidence"] = {"method": "exact-title-and-main-cast", "tvmaze": identity,
                                               "cast_overlap": sorted(actors & {normalized_title(name) for name in proven[0].get("cast", [])})}
            return proven[0]
    if exact_ids:
        return exact_ids[0]
    year = str(official.get("premiered") or "")[:4]
    canonical = [row for row in names if row.get("premiere_source") and str(row.get("release_year")) == year]
    if len(canonical) == 1:
        return canonical[0]
    unknown = [row for row in names if not row.get("premiere_source") and row.get("source") != "tvmaze_series"]
    # Platform catalog years often refer to a later season, not the show's premiere.
    # Only reconcile by title when TVmaze has one exact-name identity, not a remake ambiguity.
    return unknown[0] if unambiguous_name and len(unknown) == 1 else None


def merge_show_aliases(shows, episodes, existing, tvmaze_id):
    duplicates = [row for row in shows.values() if str(row["id"]) != str(existing["id"])
                  and str(row.get("external_tvmaze")) == str(tvmaze_id)]
    aliases = set(map(str, existing.get("id_aliases", [])))
    for duplicate in duplicates:
        aliases.update([str(duplicate["id"]), *map(str, duplicate.get("id_aliases", []))])
        del shows[str(duplicate["id"])]
    if aliases:
        existing["id_aliases"] = sorted(aliases)
        for episode in episodes.values():
            if str(episode.get("parent_id")) in aliases:
                episode["parent_id"] = existing["id"]


def refresh_show(existing, official):
    updated = to_document(official)
    # Keep the catalog identity and provider metadata; refresh sourced story/genres.
    existing.setdefault("provider_genres", existing.get("genres", []))
    existing.setdefault("provider_release_year", existing.get("release_year"))
    for key in ("overview", "genres", "rich_text", "keywords", "mood_tags", "poster_url", "external_imdb"):
        if updated.get(key):
            existing[key] = updated[key]
    existing.update({"source_url": str(official.get("url") or existing.get("source_url", "")),
                     "license": LICENSE, "overview_source": "tvmaze"})
    if official.get("premiered"):
        existing["premiered"] = str(official["premiered"])
        existing["release_year"] = str(official["premiered"])[:4]
        existing["premiere_source"] = existing["source_url"]


def episode_document(show, episode):
    summary = strip_html(str(episode.get("summary") or ""))
    # A title-only episode adds noise, not evidence for scene identification.
    if len(summary.split()) < 8 or episode.get("season") is None or episode.get("number") is None:
        return None
    title = str(show["title"])
    season, number = int(episode["season"]), int(episode["number"])
    evidence = {"id": f"tvmaze-episode:{episode['id']}", "name": str(episode.get("name") or ""),
                "season": season, "episode": number, "summary": summary,
                "source_url": str(episode.get("url") or ""), "license": LICENSE,
                "airdate": str(episode.get("airdate") or "")}
    return {"id": evidence["id"], "parent_id": show["id"], "record_type": "episode", "title": title,
            "original_title": title, "media_type": "series", "season": season, "episode": number,
            "release_year": show.get("release_year"), "genres": show.get("genres", []), "director": "Unknown",
            "cast": [], "overview": summary, "scene_descriptions": [], "scene_timeline": [], "scene_count": 0,
            "mood_tags": [], "keywords": [evidence["name"], f"S{season:02}E{number:02}"],
            "source": "tvmaze_episode", "source_url": evidence["source_url"], "license": LICENSE,
            "matched_episode": evidence,
            "rich_text": f"Title: {title} | Episode: S{season:02}E{number:02} {evidence['name']} | Plot: {summary}"}


def main():
    import requests
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shows", nargs="+")
    parser.add_argument("--shows-file", help="JSON file with an explicit, reproducible list of show selections.")
    parser.add_argument("--max-episodes-per-show", type=int, default=100)
    parser.add_argument("--staging-dir", help="Write a candidate dataset separately; do not replace the active catalogs.")
    args = parser.parse_args()
    if args.shows and args.shows_file:
        raise ValueError("Choose either --shows or --shows-file")
    selections = json.loads(Path(args.shows_file).read_text(encoding="utf-8")) if args.shows_file else args.shows or DEFAULT_SHOWS
    if not isinstance(selections, list) or not selections or any(not isinstance(value, str) or not value.strip() for value in selections):
        raise ValueError("Show selections must be a nonempty JSON list of names")
    folder = ROOT / "data/processed"
    output = Path(args.staging_dir) if args.staging_dir else folder
    if not output.is_absolute():
        output = ROOT / output
    output.mkdir(parents=True, exist_ok=True)
    cache = ROOT / "data/raw/tvmaze"
    cache.mkdir(parents=True, exist_ok=True)
    shows = {str(row["id"]): row for row in load_list(folder / "tv_series_enriched.json")}
    episodes = {str(row["id"]): row for row in load_list(folder / "tv_episodes_enriched.json")}
    session = requests.Session()
    session.headers["User-Agent"] = "CineScene-Academic-Project/4.0 (attributed metadata research)"
    def fetch(route, params=None):
        key = route.strip("/").replace("/", "-") + ("-" + str(params.get("q")) if params else "")
        path = cache / ("".join(c if c.isalnum() or c in "-_ " else "_" for c in key) + ".json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        for attempt in range(5):
            response = session.get("https://api.tvmaze.com" + route, params=params, timeout=45)
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(min(30, 2 ** (attempt + 1)))
                continue
            response.raise_for_status()
            data = response.json()
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            time.sleep(.6)
            return data
        raise RuntimeError(f"TVmaze did not recover after retries: {route}")
    counts, added_shows = {}, 0
    try:
        for selection in selections:
            name, separator, year = selection.rpartition("@")
            if not separator:
                name, year = selection, ""
            if year and not (len(year) == 4 and year.isdigit()):
                raise ValueError("Use Title@YYYY to disambiguate a show")
            expected_year = year or EXPECTED_YEARS.get(name)
            results = fetch("/search/shows", {"q": name})
            exact_name = [row["show"] for row in results if normalized_title(row["show"]["name"]) == normalized_title(name)]
            exact = [row for row in exact_name if not expected_year or str(row.get("premiered", "")).startswith(expected_year)]
            if len(exact) != 1:
                raise ValueError(f"Ambiguous show name {name!r}; use Title@YYYY to select the intended series.")
            tvmaze_id = str(exact[0]["id"])
            official = fetch(f"/shows/{tvmaze_id}")
            cast = [row["person"]["name"] for row in fetch(f"/shows/{tvmaze_id}/cast")] if len(exact_name) > 1 else None
            existing = existing_show(shows.values(), official, len(exact_name) == 1, cast)
            if existing is None:
                existing = to_document(official)
                shows[str(existing["id"])] = existing
                added_shows += 1
            merge_show_aliases(shows, episodes, existing, tvmaze_id)
            existing.update({"source_url": f"https://www.tvmaze.com/shows/{tvmaze_id}", "license": LICENSE, "external_tvmaze": tvmaze_id})
            refresh_show(existing, official)
            payload = fetch(f"/shows/{tvmaze_id}/episodes")
            valid = [doc for row in payload if (doc := episode_document(existing, row))]
            valid = valid[:max(1, args.max_episodes_per_show)]
            for doc in valid:
                episodes[str(doc["id"])] = doc
            counts[name] = len(valid)
            print(f"{name}: {len(valid)} attributed episode summaries", flush=True)
        series = list(shows.values())
        evidence = list(episodes.values())
        combined = load_list(folder / "movies_enriched.json") + series + load_list(folder / "offline_media_enriched.json") + evidence
        save_list(output / "tv_series_enriched.json", series)
        save_list(output / "tv_episodes_enriched.json", evidence)
        save_list(output / "episode_expansion_documents.json", series + evidence)
        save_list(output / "cinescene_catalog.json", combined)
        report = {"generated_at": datetime.now(timezone.utc).isoformat(), "new_shows": added_shows,
                  "series_documents": len(series),
                  "episode_documents": len(evidence), "show_coverage": counts,
                  "identity_aliases": {str(row["id"]): row["id_aliases"] for row in series if row.get("id_aliases")},
                  "source": "https://www.tvmaze.com/api", "license": LICENSE,
                  "staged": bool(args.staging_dir),
                  "limitations": "Episode summaries are not exhaustive scene annotations or recovered dialogue."}
        (output / "episode_expansion_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
