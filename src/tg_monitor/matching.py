"""Pure topic matching that can be tested without Telegram access."""


def find_matches(text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
    """Return each configured keyword found in text, preserving configuration order."""
    normalized_text = text.casefold()
    matches: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        cleaned = keyword.strip()
        normalized_keyword = cleaned.casefold()
        if normalized_keyword and normalized_keyword not in seen and normalized_keyword in normalized_text:
            matches.append(cleaned)
            seen.add(normalized_keyword)
    return tuple(matches)
