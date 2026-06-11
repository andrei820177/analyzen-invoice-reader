_LANGUAGES = [
    ("ro", "Română"),
    ("en", "English"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("it", "Italiano"),
    ("es", "Español"),
    ("pt", "Português"),
    ("pl", "Polski"),
    ("ru", "Русский"),
    ("nl", "Nederlands"),
    ("da", "Dansk"),
]


def get_languages() -> list[tuple[str, str]]:
    return _LANGUAGES