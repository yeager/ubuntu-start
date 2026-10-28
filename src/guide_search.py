"""Search normalized guide entries without GTK dependencies."""
from __future__ import annotations

from collections.abc import Iterable
import unicodedata

GuideSearchEntry = tuple[str, int, str, str, str]


def _normalize_token(token: str) -> str:
    decomposed = unicodedata.normalize("NFKD", token.casefold())
    return "".join(character for character in decomposed if character.isalnum())


def find_guide_matches(
    query: str,
    entries: Iterable[GuideSearchEntry],
) -> list[GuideSearchEntry]:
    """Return entries containing every query term in their visible text.

    Entries contain a guide kind, its index, the guide title, a step title,
    and the step description. Matching is case-insensitive, ignores accents
    and punctuation, and accepts terms in any order.
    """
    terms = [_normalize_token(term) for term in query.split()]
    terms = [term for term in terms if term]
    if not terms:
        return []

    matches = []
    for entry in entries:
        searchable = " ".join(
            _normalize_token(word)
            for value in entry[2:]
            for word in value.casefold().split()
        )
        if all(term in searchable for term in terms):
            matches.append(entry)
    return matches
