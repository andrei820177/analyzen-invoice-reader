import json
import os
from typing import Dict


class _LangManager:
    def __init__(self) -> None:
        self._data: Dict[str, str] = {}
        self._code = "ro"

    def load(self, code: str) -> None:
        path = os.path.join(
            os.path.dirname(__file__), "..", "config", "lang", f"{code}.json"
        )
        try:
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)
            self._code = code
        except Exception:
            pass

    def t(self, key: str, *args) -> str:
        val = self._data.get(key, key)
        if args:
            try:
                return val.format(*args)
            except Exception:
                pass
        return val

    @property
    def code(self) -> str:
        return self._code


_instance = _LangManager()


def L() -> _LangManager:
    return _instance


def init_lang() -> None:
    """Load language from settings.json at startup."""
    settings_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "settings.json"
    )
    try:
        with open(settings_path, encoding="utf-8") as f:
            code = json.load(f).get("language", "ro")
    except Exception:
        code = "ro"
    _instance.load(code)
