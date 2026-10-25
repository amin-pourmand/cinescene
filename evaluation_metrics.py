"""Deterministic relevance judgments for movie and scene regression reports."""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def matches(title: str, expected: List[str]) -> bool:
    normalized = normalize_title(title)
    return bool(normalized) and normalized in {normalize_title(item) for item in expected}


def expected_rank(results: List[Dict], case: Dict):
    for rank, result in enumerate(results, 1):
        if case.get("expected_ids"):
            relevant = str(result.get("id")) in {str(value) for value in case["expected_ids"]}
        else:
            relevant = matches(str(result.get("title", "")), case["expected"])
        if relevant and case.get("episode") is not None:
            relevant = result.get("episode") == case["episode"] and result.get("season") == case.get("season")
        if relevant:
            return rank
    return None


def summarize(rows: List[Dict]) -> Dict:
    count = len(rows)
    ranks = [row.get("rank") for row in rows]
    return {
        "cases": count,
        "hit_at_1": round(sum(rank == 1 for rank in ranks) / count, 4) if count else 0,
        "hit_at_5": round(sum(rank is not None and rank <= 5 for rank in ranks) / count, 4) if count else 0,
        "mrr_at_10": round(sum(1 / rank for rank in ranks if rank is not None and rank <= 10) / count, 4) if count else 0,
    }
