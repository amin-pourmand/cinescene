"""Stage attributed film plots from yearly box-office lists and explicit seeds.

No credentials, videos, invented scenes, or subtitle claims. Active data is not
modified; activate_movie_expansion.py installs a validated index generation.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_environment import configure_runtime
configure_runtime()
import requests
from scripts.import_tvmaze_series import load_list, save_list

WIKIPEDIA = "https://en.wikipedia.org/w/api.php"
WIKIDATA = "https://www.wikidata.org/w/api.php"
LICENSE = "CC-BY-SA-4.0"


class RankedFilmTables(HTMLParser):
    """Read cells/links structurally; only rank/title/gross tables are selected."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.rows, self.row, self.cell = [], [], [], None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.rows = []
        if self.depth != 1:
            return
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"}:
            self.cell = {"text": [], "links": []}
        elif tag == "a" and self.cell is not None:
            href = attrs.get("href", "")
            if href.startswith("/wiki/") and ":" not in unquote(href[6:]).split("#")[0].split("(")[0]:
                title = attrs.get("title") or unquote(href[6:]).replace("_", " ")
                self.cell["links"].append(title)
            elif href.startswith("/wiki/") and attrs.get("title") and not href.startswith(("/wiki/File:", "/wiki/Help:", "/wiki/Category:")):
                self.cell["links"].append(attrs["title"])

    def handle_data(self, data):
        if self.depth == 1 and self.cell is not None:
            self.cell["text"].append(data)

    def handle_endtag(self, tag):
        if self.depth == 1:
            if tag in {"td", "th"} and self.cell is not None:
                self.row.append(self.cell)
                self.cell = None
            elif tag == "tr" and self.row:
                self.rows.append(self.row)
            elif tag == "table":
                self.tables.append(self.rows)
        if tag == "table":
            self.depth -= 1

    def titles(self, limit=10):
        found = []
        for rows in self.tables:
            column = None
            for row in rows:
                texts = [" ".join("".join(cell["text"]).split()).casefold() for cell in row]
                if "rank" in texts and any(value in {"title", "film"} for value in texts) and any("gross" in value for value in texts):
                    column = next(i for i, value in enumerate(texts) if value in {"title", "film"})
                    continue
                if column is not None and len(row) > column and row[column]["links"]:
                    title = row[column]["links"][0]
                    if title not in found:
                        found.append(title)
                if len(found) >= limit:
                    return found
        return found


class WikimediaClient:
    def __init__(self, cache, refresh=False, delay=.6):
        self.cache, self.refresh, self.delay = Path(cache), refresh, delay
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "CineScene-Academic-Research/1.0 (https://github.com/amin-pourmand/cinescene)"

    def get(self, endpoint, **params):
        params.update(format="json", formatversion=2, maxlag=5)
        key = hashlib.sha256(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()
        path = self.cache / (key + ".json")
        if path.exists() and not self.refresh:
            return json.loads(path.read_text(encoding="utf-8"))["payload"]
        for attempt in range(4):
            try:
                response = self.session.get(endpoint, params=params, timeout=(15, 60))
                if response.status_code in {429, 502, 503, 504}:
                    time.sleep(min(30, float(response.headers.get("Retry-After", 2 ** (attempt + 1)))))
                    continue
                response.raise_for_status()
                payload = response.json()
                if payload.get("error", {}).get("code") in {"maxlag", "ratelimited"}:
                    time.sleep(2 ** (attempt + 1))
                    continue
                if "error" in payload:
                    raise ValueError(f"Wikimedia API error: {payload['error'].get('code')}")
                temporary = path.with_suffix(".tmp")
                temporary.write_text(json.dumps({"retrieved_at": datetime.now(timezone.utc).isoformat(),
                                                 "payload": payload}, ensure_ascii=False), encoding="utf-8")
                temporary.replace(path)
                time.sleep(self.delay)
                return payload
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(2 ** (attempt + 1))
        raise RuntimeError("Wikimedia did not recover after bounded retries")


def claim_values(entity, key):
    return [row["mainsnak"]["datavalue"]["value"] for row in entity.get("claims", {}).get(key, [])
            if row.get("rank") != "deprecated" and row.get("mainsnak", {}).get("snaktype") == "value"]


def text_sections(extract):
    sections = re.split(r"(?m)^==\s*([^=\n]+?)\s*==\s*$", extract)
    plot = next((sections[i + 1].strip() for i in range(1, len(sections), 2)
                 if sections[i].strip().casefold() in {"plot", "synopsis", "plot summary", "story"}), "")
    plot = re.sub(r"(?m)^={3,}[^\n]+={3,}\s*$", "", plot).strip()
    return sections[0].strip(), plot


def complete_article(client, page):
    result = dict(page)
    if not page.get("missing") and "disambiguation" not in page.get("pageprops", {}):
        # TextExtracts silently restricts whole-article requests to one page.
        full = client.get(WIKIPEDIA, action="query", pageids=page["pageid"],
                          prop="extracts|revisions", explaintext=1, exlimit=1, rvprop="ids")
        result.update(full["query"]["pages"][0])
        if not result.get("extract"):
            raise RuntimeError("Missing whole-article extract; candidate requires source review")
    return result


def normalized_title(value):
    value = unicodedata.normalize("NFKD", str(value).casefold())
    return " ".join("".join(c for c in value if not unicodedata.combining(c)).split())


def match_existing(movies, document):
    tmdb = document.get("external_tmdb")
    exact = [row for row in movies if (tmdb and str(row["id"]) == str(tmdb)) or
             (row.get("external_wikidata") and row["external_wikidata"] == document["external_wikidata"]) or
             (row.get("wikipedia_page_id") and str(row["wikipedia_page_id"]) == str(document["wikipedia_page_id"]))]
    if len(exact) > 1:
        raise ValueError("Multiple movies claim the same external identity")
    if exact:
        year = str(exact[0].get("release_year") or str(exact[0].get("release_date", ""))[:4])
        if year and abs(int(year) - int(document["release_year"])) > 1:
            raise ValueError("Conflicting external identity/release year requires review")
        return exact[0]
    names = {normalized_title(document.get("title")), normalized_title(document.get("original_title"))}
    matches = [row for row in movies if str(row.get("release_year") or str(row.get("release_date", ""))[:4]) == document["release_year"]
               and normalized_title(row.get("title") or row.get("original_title")) in names]
    if len(matches) > 1:
        raise ValueError("Ambiguous title/year identity requires review")
    return matches[0] if matches else None


def verified_release_dates(entity, today):
    dates = []
    for value in claim_values(entity, "P577"):
        raw = str(value.get("time", ""))
        if not re.match(r"^\+\d{4}-\d{2}-\d{2}", raw):
            continue
        year, month, day = map(int, raw[1:11].split("-"))
        if not 1900 <= year <= today.year:
            continue
        if month and day:
            try:
                released = date(year, month, day)
            except ValueError:
                continue
            if released <= today:
                dates.append(released.isoformat())
        elif year < today.year:
            # Retain source precision instead of fabricating a January 1 date.
            dates.append(f"{year:04d}-{month:02d}" if month else str(year))
        elif month and month < today.month:
            dates.append(f"{year:04d}-{month:02d}")
    return sorted(dates)


def movie_document(page, entity, labels, today):
    if page.get("missing") or "disambiguation" in page.get("pageprops", {}):
        raise ValueError("missing-or-disambiguation")
    overview, plot = text_sections(page.get("extract", ""))
    if re.search(r"\bmay (?:also )?refer to\b", overview[:500], re.I):
        raise ValueError("missing-or-disambiguation")
    if not re.search(r"\bfilms?\b", overview[:800], re.I):
        raise ValueError("not-a-film-article")
    dates = verified_release_dates(entity, today)
    release_source = "wikidata:P577"
    if not dates and not claim_values(entity, "P577"):
        historical = re.search(r"\bis (?:an? )?(\d{4})\b[^.\n]{0,150}?\bfilm\b", overview[:500], re.I)
        if historical and 1900 <= int(historical[1]) < today.year:
            dates = [historical[1]]
            release_source = "wikipedia:lead-year"
    if not dates:
        raise ValueError("unreleased-or-unverified-release-date")
    revision = (page.get("revisions") or [{}])[0].get("revid")
    if not revision or not entity.get("id"):
        raise ValueError("missing-revision-or-wikidata-identity")
    title = entity.get("labels", {}).get("en", {}).get("value") or re.sub(r"\s+\((?:\d{4} )?film\)$", "", page["title"])
    label = lambda identity: labels.get(identity, {}).get("labels", {}).get("en", {}).get("value", "")
    directors = [label(value["id"]) for value in claim_values(entity, "P57")]
    cast = [label(value["id"]) for value in claim_values(entity, "P161")][:8]
    genres = [label(value["id"]).removesuffix(" film").title() for value in claim_values(entity, "P136")]
    tmdb = next(iter(claim_values(entity, "P4947")), None)
    url = "https://en.wikipedia.org/wiki/" + quote(page["title"].replace(" ", "_"), safe="():,_")
    provenance = {"provider": "Wikipedia contributors", "url": url,
                  "revision_url": f"https://en.wikipedia.org/w/index.php?oldid={revision}",
                  "revision_id": revision, "license": LICENSE, "transformation": "plain-text plot section extraction"}
    document = {
        "id": int(tmdb) if str(tmdb).isdigit() else f"wikipedia:en:{page['pageid']}",
        "title": title, "original_title": title, "media_type": "movie", "release_year": dates[0][:4],
        "release_date": dates[0], "director": ", ".join(filter(None, directors)) or "Unknown",
        "release_date_source": release_source,
        "cast": list(filter(None, cast)), "genres": list(filter(None, genres)),
        "overview": overview, "wiki_plot": plot, "plot": plot, "plot_source": "wikipedia",
        "story_passages": [text.strip() for text in plot.split("\n\n") if text.strip()],
        "scene_descriptions": [], "scene_timeline": [], "scene_count": 0,
        "mood_tags": [], "keywords": [], "visual_tags": [],
        "source": "wikipedia_film", "source_url": url, "license": LICENSE,
        "evidence_sources": [provenance], "external_wikidata": entity["id"],
        "external_tmdb": str(tmdb) if tmdb else None,
        "external_imdb": next(iter(claim_values(entity, "P345")), None),
        "wikipedia_page_id": page["pageid"], "wikipedia_revision": revision,
        "evidence_coverage": "plot" if plot else "overview-only",
        "vote_average": 0, "popularity": 0,
    }
    document["rich_text"] = rich_text(document)
    return document


def rich_text(document):
    return " | ".join(value for value in [f"Title: {document['title']}", "Type: movie",
        f"Year: {document['release_year']}", f"Genres: {', '.join(document.get('genres', []))}",
        f"Director: {document.get('director', 'Unknown')}", f"Plot: {document.get('overview', '')}"] if value)


def merge_document(existing, incoming):
    if existing is None:
        return incoming
    merged = dict(existing)
    # Keep the original provider identity, overview, rankings and any real video evidence.
    for key in ("external_wikidata", "external_tmdb", "external_imdb", "wikipedia_page_id", "wikipedia_revision", "evidence_sources"):
        if incoming.get(key):
            merged[key] = incoming[key]
    if incoming.get("wiki_plot"):
        old_plot = str(existing.get("wiki_plot") or existing.get("plot") or "")
        if old_plot and old_plot != incoming["wiki_plot"]:
            merged.setdefault("legacy_plot", old_plot)
        for key in ("wiki_plot", "plot", "plot_source", "story_passages", "evidence_coverage"):
            merged[key] = incoming[key]
    else:
        merged["evidence_sources"] = existing.get("evidence_sources", [])
    merged.setdefault("media_type", "movie")
    merged.setdefault("release_year", incoming["release_year"])
    merged["rich_text"] = existing.get("rich_text") or rich_text(merged)
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default="ingestion/movie_sources.json")
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--per-year", type=int, default=10)
    parser.add_argument("--staging-dir", default="data/processed/movie_expansion_candidate")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if not 1900 <= args.start_year <= args.end_year <= date.today().year or not 1 <= args.per_year <= 50:
        parser.error("Use released-year bounds and 1..50 selections per year")
    client = WikimediaClient(ROOT / "data/raw/wikipedia_movies", args.refresh)
    source_spec = json.loads((ROOT / args.sources).read_text(encoding="utf-8"))
    seeds, failures, lists = list(source_spec["pages"]), [], []
    for year in range(args.end_year, args.start_year - 1, -1):
        page_title = f"{year} in film"
        try:
            response = client.get(WIKIPEDIA, action="parse", page=page_title, prop="text|revid")
            parsed = response["parse"]
            table = RankedFilmTables()
            table.feed(parsed["text"])
            titles = table.titles(args.per_year)
            if not titles:
                raise ValueError("no-ranked-films-table")
            seeds.extend(titles)
            lists.append({"page": page_title, "revision": parsed["revid"], "titles": titles})
            print(f"Selected {len(titles)} films from {year}", flush=True)
        except Exception as exc:
            failures.append({"page": page_title, "stage": "discovery", "error": str(exc)[:200]})
    seeds = list(dict.fromkeys(seeds))
    movies = load_list(ROOT / "data/processed/movies_enriched.json")
    by_id = {str(row["id"]): row for row in movies}
    changed, covered, skipped, added = {}, [], [], 0
    for offset in range(0, len(seeds), 20):
        batch = seeds[offset:offset + 20]
        try:
            payload = client.get(WIKIPEDIA, action="query", titles="|".join(batch), redirects=1,
                                 prop="extracts|pageprops|revisions", explaintext=1, exlimit=20, rvprop="ids")
            pages = payload["query"]["pages"]
            ids = sorted({p.get("pageprops", {}).get("wikibase_item") for p in pages} - {None})
            entities = client.get(WIKIDATA, action="wbgetentities", ids="|".join(ids), props="claims|labels", languages="en")["entities"] if ids else {}
            linked = sorted({v["id"] for ent in entities.values() for key in ("P57", "P161", "P136")
                             for v in claim_values(ent, key)[:8] if isinstance(v, dict) and v.get("id")})
            labels = {}
            for start in range(0, len(linked), 50):
                labels.update(client.get(WIKIDATA, action="wbgetentities", ids="|".join(linked[start:start + 50]), props="labels", languages="en")["entities"])
            for page in pages:
                try:
                    page = complete_article(client, page)
                    entity = entities.get(page.get("pageprops", {}).get("wikibase_item"), {})
                    doc = movie_document(page, entity, labels, date.today())
                    previous = match_existing(by_id.values(), doc)
                    merged = merge_document(previous, doc)
                    identity = str(merged["id"])
                    if previous != merged:
                        changed[identity] = merged
                        added += previous is None
                    by_id[identity] = merged
                    covered.append({"id": merged["id"], "title": merged["title"], "year": doc["release_year"],
                                    "plot_words": len(str(merged.get("wiki_plot") or merged.get("plot") or "").split()),
                                    "source_url": doc["source_url"]})
                except ValueError as exc:
                    skipped.append({"page": page.get("title"), "reason": str(exc)})
            print(f"Processed {min(offset + 20, len(seeds))}/{len(seeds)} selections; {added} additions", flush=True)
        except Exception as exc:
            failures.append({"pages": batch, "stage": "fetch", "error": str(exc)[:200]})
    candidate = (ROOT / args.staging_dir).resolve()
    if candidate == (ROOT / "data/processed").resolve() or (ROOT / "data/processed").resolve() not in candidate.parents:
        raise ValueError("Candidate must be a separate processed-data subdirectory")
    covered = list({str(row["id"]): row for row in covered}.values())
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "selection_policy": source_spec["description"],
              "start_year": args.start_year, "end_year": args.end_year, "per_year": args.per_year,
              "selected_pages": len(seeds), "verified_films": len(covered), "new_movies": added,
              "changed_movies": len(changed), "total_movies": len(by_id), "with_plot": sum(r["plot_words"] > 0 for r in covered),
              "coverage": covered, "discovery_lists": lists, "skipped": skipped, "failures": failures,
              "evidence_limit": "Wikipedia plot prose, not decoded scenes or timed subtitles", "active_index_modified": False}
    save_list(candidate / "movies_enriched.json", list(by_id.values()))
    save_list(candidate / "movie_expansion_documents.json", list(changed.values()))
    combined = list(by_id.values())
    for name in ("tv_series_enriched.json", "offline_media_enriched.json", "tv_episodes_enriched.json"):
        combined.extend(load_list(ROOT / "data/processed" / name))
    save_list(candidate / "cinescene_catalog.json", combined)
    (candidate / "movie_expansion_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("selected_pages", "verified_films", "new_movies", "changed_movies", "total_movies", "with_plot")}, indent=2))
    if failures:
        raise SystemExit(f"Candidate retained with {len(failures)} fetch/discovery failures; inspect report before activation")


if __name__ == "__main__":
    main()
