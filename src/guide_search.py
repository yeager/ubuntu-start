"""Search normalized guide entries without GTK dependencies."""
from __future__ import annotations

from collections.abc import Iterable

GuideSearchEntry = tuple[str, int, str, str, str]


def find_guide_matches(
    query: str,
    entries: Iterable[GuideSearchEntry],
) -> list[GuideSearchEntry]:
    """Return entries containing every query term in their visible text.

    Entries contain a guide kind, its index, the guide title, a step title,
    and the step description. Matching is case-insensitive and accepts terms
    in any order.
    """
    terms = query.casefold().split()
    terms = ["".join(character for character in term if character.isalnum()) for term in terms]
    terms = [term for term in terms if term]
    if not terms:
        return []

    matches = []
    for entry in entries:
        searchable = " ".join(
            "".join(character for character in word if character.isalnum())
            for value in entry[2:]
            for word in value.casefold().split()
        )
        if all(term in searchable for term in terms):
            matches.append(entry)
    return matches
