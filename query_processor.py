"""Query normalization, Persian expansion, and lightweight search filters."""

from __future__ import annotations

import re
from typing import Dict


class QueryProcessor:
    def __init__(self, enable_spellcheck: bool = False):
        self.spell = None
        if enable_spellcheck:
            try:
                from spellchecker import SpellChecker

                self.spell = SpellChecker()
            except Exception:
                self.spell = None

        self.genre_aliases = {
            "action": "Action",
            "comedy": "Comedy",
            "funny": "Comedy",
            "drama": "Drama",
            "horror": "Horror",
            "scary": "Horror",
            "thriller": "Thriller",
            "romance": "Romance",
            "romantic": "Romance",
            "sci-fi": "Science Fiction",
            "scifi": "Science Fiction",
            "science fiction": "Science Fiction",
            "fantasy": "Fantasy",
            "animation": "Animation",
            "documentary": "Documentary",
            "اکشن": "Action",
            "کمدی": "Comedy",
            "درام": "Drama",
            "وحشت": "Horror",
            "ترسناک": "Horror",
            "هیجانی": "Thriller",
            "عاشقانه": "Romance",
            "علمی تخیلی": "Science Fiction",
            "فانتزی": "Fantasy",
            "انیمیشن": "Animation",
            "مستند": "Documentary",
        }

        self.expansions = {
            "dark": ["noir", "gritty", "mysterious", "bleak", "suspenseful"],
            "lonely": ["isolation", "solitude", "melancholic", "quiet"],
            "funny": ["comedy", "humorous", "witty"],
            "sad": ["tragic", "emotional", "melancholic"],
            "romantic": ["love", "relationship", "heartwarming"],
            "mind bending": ["surreal", "twist", "dreamlike", "psychological"],
            "chase": ["car chase", "pursuit", "running"],
            "fight": ["battle", "combat", "brawl"],
            "explosion": ["blast", "bomb", "destruction"],
            "detective": ["investigation", "mystery", "crime"],
            "space": ["spaceship", "alien", "future"],
            "dream": ["surreal", "subconscious", "mind bending"],
            "toy": ["toys", "plaything", "animated objects"],
            "hacker": ["computer hacker", "cyberpunk", "virtual reality"],
            "simulation": ["virtual reality", "artificial world", "digital reality"],
            "تنها": ["lonely", "isolation", "solitude"],
            "تاریک": ["dark", "noir", "bleak"],
            "عاشقانه": ["romantic", "love", "relationship"],
            "ترسناک": ["horror", "scary", "haunted"],
            "علمی تخیلی": ["science fiction", "future", "space"],
            "غمگین": ["sad", "tragic", "emotional"],
            "مرموز": ["mysterious", "suspenseful", "secret"],
            "هیجان انگیز": ["thrilling", "tense", "suspenseful"],
            "آرام": ["quiet", "slow", "calm"],
            "رویا": ["dreamlike", "surreal", "subconscious"],
            "تعقیب": ["chase", "pursuit", "running"],
            "فضا": ["space", "spaceship", "science fiction"],
            "کارآگاه": ["detective", "investigation", "crime"],
            "دعوا": ["fight", "combat", "battle"],
            "انفجار": ["explosion", "blast", "destruction"],
            "باران": ["rain", "rainy", "wet city"],
            "جنگل": ["forest", "woods", "wilderness"],
            "ماشین": ["car", "vehicle", "driving"],
            "قطار": ["train", "railway", "station"],
            "بیمارستان": ["hospital", "doctor", "medical"],
            "زندان": ["prison", "jail", "cell"],
            "قتل": ["murder", "crime", "death"],
            "فرار": ["escape", "running away", "fugitive"],
            "بوسه": ["kiss", "romance", "couple"],
            "مهمانی": ["party", "crowd", "celebration"],
            "خواب": ["dream", "subconscious"],
            "هکر": ["hacker", "computer"],
            "شبیه سازی": ["simulation", "virtual reality"],
            "حافظه": ["memory", "amnesia"],
            "خالکوبی": ["tattoo"],
            "معلم": ["teacher"],
            "شیمی": ["chemistry"],
            "جنگ": ["war", "battle"],
            "سرباز": ["soldier", "military"],
            "افسر": ["officer"],
            "موجودات فضایی": ["alien creatures"],
            "دوباره": ["again", "repeat"],
            "همون روز": ["same day"],
            "زنده": ["alive"],
            "میمیره": ["dies"],
            "قرص": ["pill"],
            "قرمز": ["red"],
            "اتاق": ["room"],
            "سرنخ": ["clue"],
            "دزد": ["thief", "steal"],
            "ایده": ["idea"],
            "ذهن": ["mind"],
            "کامپیوتر": ["computer"],
            "قاتل": ["killer"],
            "همسر": ["wife", "husband"],
            "یادداشت": ["notes"],
            "کوتاه مدت": ["short term"],
            "خاطرات": ["memories"],
            "شرکت": ["company"],
            "کارمند": ["employee", "office"],
            "شخصی": ["personal"],
            "جدا": ["separate"],
        }

    @staticmethod
    def normalize_unicode(query: str) -> str:
        return query.replace("ي", "ی").replace("ك", "ک").replace("‌", " ").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

    def correct_spelling(self, query: str) -> str:
        if not self.spell:
            return query
        corrected = []
        for word in query.split():
            if len(word) <= 3 or not word.isascii() or word[0].isupper():
                corrected.append(word)
            else:
                correction = self.spell.correction(word.lower())
                corrected.append(correction if correction else word)
        return " ".join(corrected)

    def extract_filters(self, query: str) -> Dict:
        filters = {"genres": [], "excluded_genres": [], "year_range": None, "director": None}
        query_lower = query.lower()
        # Dates inside a remembered plot or a title are not release-year filters.
        years = [int(year) for year in re.findall(r"(?:\b(?:from|released(?:\s+in)?|release\s+year|year)\s+|(?:محصول|ساخته شده در)\s+)(19\d{2}|20\d{2})\b", query_lower)]
        year_range = re.search(r"\b(?:between\s+)?(19\d{2}|20\d{2})\s*(?:-|to|and)\s*(19\d{2}|20\d{2})\b", query_lower)
        if year_range:
            years = [int(value) for value in year_range.groups()]
        if len(years) == 1:
            filters["year_range"] = (years[0], years[0])
        elif len(years) >= 2:
            filters["year_range"] = (min(years), max(years))

        for alias, genre in self.genre_aliases.items():
            for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", query_lower):
                prefix = query_lower[max(0, match.start() - 35):match.start()]
                negated = re.search(r"(?:\b(?:no|not|without|exclude|excluding|except)\s+(?:any\s+|a\s+)?|(?:بدون|غیر|نه)\s*)$", prefix)
                suffix = query_lower[match.end():match.end() + 18]
                explicit = (query_lower.strip() == alias or
                            re.search(r"(?:\bgenre\s*:\s*|(?:ژانر)\s*)$", prefix) or
                            re.match(r"\s+(?:movies?|films?|series|shows?)\b", suffix) or
                            re.search(r"(?:فیلم|سریال)\s*$", prefix) or
                            alias in {"sci-fi", "scifi", "science fiction", "علمی تخیلی"})
                if not negated and not explicit:
                    continue
                field = "excluded_genres" if negated else "genres"
                if genre not in filters[field]:
                    filters[field].append(genre)
        filters["genres"] = [genre for genre in filters["genres"] if genre not in filters["excluded_genres"]]

        director_match = re.search(r"\bdirected by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", query)
        if director_match:
            filters["director"] = director_match.group(1)
        return filters

    def clean_query(self, query: str) -> str:
        query = re.sub(r"\b(?:from|released(?:\s+in)?|release\s+year|year)\s+(?:19\d{2}|20\d{2})\b", " ", query, flags=re.I)
        query = re.sub(r"\bdirected by\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", " ", query)
        return re.sub(r"\s+", " ", query).strip()

    def expand_query(self, query: str) -> str:
        expanded_terms = [query]
        query_lower = query.lower()
        for phrase, synonyms in self.expansions.items():
            suffix = r"(?:هایی|های|ها|شان|شون|ی|یه)?" if re.search(r"[\u0600-\u06ff]", phrase) else ""
            if re.search(r"(?<!\w)" + re.escape(phrase) + suffix + r"(?!\w)", query_lower):
                expanded_terms.extend(synonyms[:4])
        return " ".join(dict.fromkeys(term for term in expanded_terms if term))

    def process(self, query: str) -> Dict:
        normalized = self.normalize_unicode(query)
        corrected = self.correct_spelling(normalized)
        filters = self.extract_filters(corrected)
        cleaned = self.clean_query(corrected)
        expanded = self.expand_query(cleaned)
        return {
            "original": query,
            "corrected": corrected,
            "cleaned": cleaned,
            "expanded": expanded,
            "filters": filters,
        }


if __name__ == "__main__":
    processor = QueryProcessor()
    for query in [
        "dark lonely sci-fi movie",
        "romantic comedy from 2010",
        "فیلم علمی تخیلی تاریک و تنها",
    ]:
        print(processor.process(query))
