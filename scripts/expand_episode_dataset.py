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
    parser.add_argument("--shows", nargs="+", default=DEFAULT_SHOWS)
    parser.add_argument("--max-episodes-per-show", type=int, default=100)
    args = parser.parse_args()
    folder = ROOT / "data/processed"
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
        for selection in args.shows:
            name, separator, year = selection.rpartition("@")
            if not separator:
                name, year = selection, ""
            if year and not (len(year) == 4 and year.isdigit()):
                raise ValueError("Use Title@YYYY to disambiguate a show")
            expected_year = year or EXPECTED_YEARS.get(name)
            existing = next((row for row in shows.values() if normalized_title(row["title"]) == normalized_title(name)
                             and (not expected_year or str(row.get("release_year", "")) == expected_year)), None)
            tvmaze_id = str(existing["id"]).split(":")[-1] if existing and str(existing["id"]).startswith("tvmaze:") else None
            if tvmaze_id is None:
                results = fetch("/search/shows", {"q": name})
                exact = [row["show"] for row in results if normalized_title(row["show"]["name"]) == normalized_title(name)
                         and (not expected_year or str(row["show"].get("premiered", "")).startswith(expected_year))]
                if len(exact) != 1:
                    raise ValueError(f"Ambiguous show name {name!r}; use Title@YYYY to select the intended series.")
                tvmaze_id = str(exact[0]["id"])
                if existing is None:
                    existing = to_document(exact[0])
                    shows[str(existing["id"])] = existing
                    added_shows += 1
            existing.update({"source_url": f"https://www.tvmaze.com/shows/{tvmaze_id}", "license": LICENSE, "external_tvmaze": tvmaze_id})
            official = fetch(f"/shows/{tvmaze_id}")
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
        save_list(folder / "tv_series_enriched.json", series)
        save_list(folder / "tv_episodes_enriched.json", evidence)
        save_list(folder / "episode_expansion_documents.json", series + evidence)
        save_list(folder / "cinescene_catalog.json", combined)
        report = {"generated_at": datetime.now(timezone.utc).isoformat(), "new_shows": added_shows,
                  "episode_documents": len(evidence), "show_coverage": counts,
                  "source": "https://www.tvmaze.com/api", "license": LICENSE,
                  "limitations": "Episode summaries are not exhaustive scene annotations or recovered dialogue."}
        (folder / "episode_expansion_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
