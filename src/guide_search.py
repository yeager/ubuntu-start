"""Search normalized guide entries without GTK dependencies."""
from __future__ import annotations

from collections.abc import Iterable
import unicodedata

GuideSearchEntry = tuple[str, int, str, str, str]


def _normalize_token(token: str) -> str:
    decomposed = unicodedata.normalize("NFKD", token.casefold())
    return "".join(character for character in decomposed if character.isalnum())


def _normalized_words(value: str) -> set[str]:
    return {
        normalized
        for word in value.casefold().split()
        if (normalized := _normalize_token(word))
    }


def _contains_term(term: str, words: set[str]) -> bool:
    """Match whole words and prefixes, never arbitrary interior substrings."""
    return any(word.startswith(term) for word in words)


def find_guide_matches(
    query: str,
    entries: Iterable[GuideSearchEntry],
) -> list[GuideSearchEntry]:
    """Return relevant steps when every query term matches within a guide.

    Entries contain a guide kind, its index, the guide title, a step title,
    and the step description. Matching is case-insensitive, ignores accents
    and punctuation, accepts terms in any order, and supports word prefixes.
    Punctuation within a whitespace-delimited term is ignored, so shortcuts
    such as ``Ctrl+Shift+C`` remain searchable. If query terms span multiple
    steps in one guide, return the steps matching at least one term.
    """
    terms = [_normalize_token(term) for term in query.split()]
    terms = [term for term in terms if term]
    if not terms:
        return []

    grouped: dict[tuple[str, int, str], list[tuple[GuideSearchEntry, set[str]]]] = {}
    seen_entries: set[GuideSearchEntry] = set()
    for entry in entries:
        if entry in seen_entries:
            continue
        seen_entries.add(entry)
        key = entry[:3]
        step_words = _normalized_words(" ".join(entry[3:]))
        grouped.setdefault(key, []).append((entry, step_words))

    matches = []
    for (_kind, _index, guide_title), steps in grouped.items():
        all_words = _normalized_words(guide_title)
        for _entry, step_words in steps:
            all_words.update(step_words)
        if not all(_contains_term(term, all_words) for term in terms):
            continue

        exact_matches = [
            entry for entry, words in steps
            if all(_contains_term(term, words) for term in terms)
        ]
        if exact_matches:
            matches.extend(exact_matches)
            continue

        partial_matches = [
            entry for entry, words in steps
            if any(_contains_term(term, words) for term in terms)
        ]
        matches.extend(partial_matches or [entry for entry, _words in steps])
    return matches
