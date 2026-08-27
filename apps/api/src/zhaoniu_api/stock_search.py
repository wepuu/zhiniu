import re
import unicodedata

from pypinyin import Style, lazy_pinyin

_SEPARATOR_PATTERN = re.compile(r"[^0-9a-z\u3400-\u9fff]+")


def normalize_stock_search_text(value: str) -> str:
    """Return the stable, punctuation-insensitive stock-search representation."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return _SEPARATOR_PATTERN.sub("", normalized)


def stock_name_search_terms(name: str) -> tuple[str, str, str]:
    normalized_name = normalize_stock_search_text(name)
    full = normalize_stock_search_text(
        "".join(lazy_pinyin(name, style=Style.NORMAL, errors=lambda value: value))
    )
    initials = normalize_stock_search_text(
        "".join(lazy_pinyin(name, style=Style.FIRST_LETTER, errors=lambda value: value))
    )
    return normalized_name, full, initials
