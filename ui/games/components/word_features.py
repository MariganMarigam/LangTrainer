"""Pure word-analysis helpers shared across games (no Qt imports)."""

VOWELS_RU = set("аеёиоуыэюяАЕЁИОУЫЭЮЯ")
VOWELS_EN = set("aeiouAEIOU")


def is_cyrillic(word: str) -> bool:
    """Return True if the word contains any Cyrillic letter."""
    return any("\u0400" <= ch <= "\u04FF" for ch in word)


def letters_of(word: str) -> list[str]:
    """Return the word's letters uppercased, e.g. "sky" -> ["S", "K", "Y"]."""
    return [ch.upper() for ch in word if ch.isalpha()]


def word_length(word: str) -> int:
    """Return the number of letters in the word."""
    return len(letters_of(word))


def vowel_count(word: str) -> int:
    """Count vowels using both the Russian and English vowel sets."""
    return sum(1 for ch in letters_of(word) if ch in VOWELS_RU or ch in VOWELS_EN)


def consonant_count(word: str) -> int:
    """Count consonants (letters that are in neither vowel set)."""
    return sum(1 for ch in letters_of(word) if ch not in VOWELS_RU and ch not in VOWELS_EN)


def unique_letters(word: str) -> set[str]:
    """Return the set of unique uppercase letters in the word."""
    return set(letters_of(word))


def letter_positions(word: str) -> dict[str, list[int]]:
    """Map each uppercase letter to its 0-based positions, e.g. "sky" -> {"S": [0], "K": [1], "Y": [2]}."""
    positions: dict[str, list[int]] = {}
    for index, ch in enumerate(letters_of(word)):
        positions.setdefault(ch, []).append(index)
    return positions