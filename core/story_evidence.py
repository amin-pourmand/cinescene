"""Bounded, query-relevant context from existing full plots, not invented scenes."""
from __future__ import annotations

import math
import re


def story_windows(plot):
    chunks, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", str(plot or "").strip()):
        words = sentence.split()
        for offset in range(0, len(words), 100):
            part = " ".join(words[offset:offset + 100])
            if len(current) + len(part) > 750 and current:
                chunks.append(current)
                current = " ".join(current.split()[-20:])
            current = (current + " " + part).strip()
    if current:
        chunks.append(current)
    return chunks


def select_story_evidence(query, windows, existing, tokenize, idf=None):
    terms = set(tokenize(query))
    idf = idf or {}
    def score(text):
        words = tokenize(text)
        overlap = terms.intersection(words)
        return sum(max(.1, idf.get(word, 1)) for word in overlap) / math.sqrt(max(1, len(words)))
    best, best_score = existing or "", score(existing or "")
    for text in windows:
        value = score(text)
        if value > best_score:
            best, best_score = text, value
    return best


def story_snippet(query, plot, existing, tokenize, max_words=210):
    terms = set(tokenize(query))
    sentences = re.split(r"(?<=[.!?])\s+", str(plot or "").strip())
    scored = [(i, len(terms.intersection(tokenize(sentence)))) for i, sentence in enumerate(sentences)]
    selected, count = [], 0
    for i, overlap in sorted(scored, key=lambda row: (-row[1], row[0])):
        if not overlap or len(selected) >= 8:
            break
        size = len(sentences[i].split())
        if count + size <= max_words:
            selected.append(i)
            count += size
    return " ... ".join(sentences[i] for i in sorted(selected)) if selected else existing
